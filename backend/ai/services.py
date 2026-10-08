"""AI pipelines: rules -> retrieval -> model -> validation -> draft for human review.

Guarantees: original clinical records are only read here; a provider failure or a rejected output
ends in status 'ai_unavailable' with the deterministic findings kept; nothing is ever reported as
a successful AI result unless it passed validation; duplicates are collapsed by idempotency key."""

import hashlib
import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone

from clinical.models import DialysisSession
from core.errors import Conflict
from core.models import Role, User
from core.permissions import assigned_professionals
from core.services import audit
from workflow.models import ReviewTask
from workflow.services import notify

from . import rag
from .context import build_context, fingerprint, record_ids
from .gateway import call_model
from .models import AIReview, AISummary
from .rules import protocol_unavailable_finding, run_checks
from .validation import validate_review, validate_summary

REVIEW_PROMPT, SUMMARY_PROMPT = "review_v1", "summary_v1"


def run_review(session_id, trigger: str, nonce: str = "") -> AIReview:
    """Create (or return the existing) AI documentation review for the session's current records."""
    session = DialysisSession.objects.select_related("patient", "prescription").get(pk=session_id)
    ctx = build_context(session)
    ids = record_ids(ctx)
    # Same records + same trigger => same key => a redelivered task does nothing new.
    key = hashlib.sha256(f"{session.id}|{trigger}|{nonce}|{fingerprint(ctx)}".encode()).hexdigest()
    existing = AIReview.objects.filter(idempotency_key=key).first()
    if existing:
        return existing

    findings = run_checks(ctx)
    passages = rag.retrieve(session.patient.organization_id, rag.retrieval_query(ctx, findings))
    if not passages and (ctx["events"] or findings):
        findings.append(protocol_unavailable_finding(ctx))
    try:
        review = AIReview.objects.create(
            session=session,
            trigger=trigger,
            idempotency_key=key,
            rule_findings=findings,
            protocol_passages=[{k: p[k] for k in p if k != "text"} for p in passages],
            source_record_ids=sorted(ids),
            prompt_version=REVIEW_PROMPT,
        )
    except IntegrityError:  # a concurrent duplicate delivery won the race
        return AIReview.objects.get(idempotency_key=key)

    payload = {"context": ctx, "rule_findings": findings, "protocol_passages": passages}
    output, errors, model_name = call_model(REVIEW_PROMPT, payload)
    if output is not None:
        errors = validate_review(output, str(session.id), ids, {p["id"] for p in passages})
    review.model_name = model_name
    if errors:
        review.status, review.ai_error = AIReview.Status.AI_UNAVAILABLE, errors
    else:
        review.status, review.output = AIReview.Status.PENDING_REVIEW, output
    review.save()

    with transaction.atomic():
        task, _ = ReviewTask.objects.get_or_create(session=session, status=ReviewTask.Status.OPEN)
        task.ai_review = review
        task.save()
    audit(None, "ai_review_created", review, patient=session.patient, status=review.status, trigger=trigger)
    for doctor in assigned_professionals(session.patient, Role.DOCTOR):
        notify(doctor, "review_ready", "Documentation review is ready", session, f"review:{review.id}")
    return review


def run_summary(session_id, requested_by_id=None, force: bool = False) -> AISummary:
    """Create a new summary version, or return the latest one when the records have not changed."""
    session = DialysisSession.objects.select_related("patient", "prescription").get(pk=session_id)
    ctx = build_context(session)
    ids = record_ids(ctx)
    mark = fingerprint(ctx)
    latest = session.ai_summaries.order_by("-version").first()
    if latest and latest.context_fingerprint == mark and not force:
        return latest

    summary = AISummary.objects.create(
        session=session,
        version=(latest.version + 1) if latest else 1,
        metrics=ctx["metrics"],
        source_record_ids=sorted(ids),
        context_fingerprint=mark,
        prompt_version=SUMMARY_PROMPT,
        requested_by_id=requested_by_id,
    )
    payload = {"context": ctx, "rule_findings": run_checks(ctx)}
    output, errors, model_name = call_model(SUMMARY_PROMPT, payload)
    if output is not None:
        errors = validate_summary(output, ctx, ids)
    summary.model_name = model_name
    if errors:
        summary.status, summary.ai_error = AISummary.Status.AI_UNAVAILABLE, errors
    else:
        summary.status, summary.output = AISummary.Status.UNVERIFIED, output
    summary.save()
    audit(None, "ai_summary_created", summary, patient=session.patient, status=summary.status, version=summary.version)
    return summary


def new_nonce() -> str:
    return uuid.uuid4().hex


@transaction.atomic
def verify_summary(summary_id, doctor: User, approve: bool) -> AISummary:
    summary = AISummary.objects.select_for_update(of=("self",)).select_related("session__patient").get(pk=summary_id)
    if summary.status != AISummary.Status.UNVERIFIED:
        raise Conflict(f"Summary is '{summary.status}'; only an unverified summary can be verified or rejected.")
    summary.status = AISummary.Status.VERIFIED if approve else AISummary.Status.REJECTED
    summary.verified_by, summary.verified_at = doctor, timezone.now()
    summary.save()
    audit(doctor, "summary_verified" if approve else "summary_rejected", summary, patient=summary.session.patient)
    return summary


@transaction.atomic
def release_summary(summary_id, doctor: User) -> AISummary:
    """The only path by which AI-written text becomes visible to a patient or caregiver."""
    summary = (
        AISummary.objects.select_for_update(of=("self",)).select_related("session__patient__user").get(pk=summary_id)
    )
    if summary.status != AISummary.Status.VERIFIED:
        raise Conflict("Only a summary verified by a doctor can be released to the patient.")
    if summary.released:
        raise Conflict("Summary is already released.")
    summary.released, summary.released_by, summary.released_at = True, doctor, timezone.now()
    summary.save()
    patient = summary.session.patient
    audit(doctor, "summary_released", summary, patient=patient)
    if patient.user:
        notify(
            patient.user, "summary_released", "A session summary is available", summary.session, f"release:{summary.id}"
        )
    return summary


@transaction.atomic
def mark_reviewed(review: AIReview, doctor: User) -> None:
    """A doctor responded to the review: close it and its task."""
    if review.status in (AIReview.Status.PENDING_REVIEW, AIReview.Status.AI_UNAVAILABLE):
        review.status, review.reviewed_by, review.reviewed_at = AIReview.Status.REVIEWED, doctor, timezone.now()
        review.save()
    ReviewTask.objects.filter(session=review.session, status=ReviewTask.Status.OPEN).update(
        status=ReviewTask.Status.DONE, completed_by=doctor, completed_at=timezone.now()
    )
