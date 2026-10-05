"""Summary pipeline: approved data -> model -> validators -> Summary draft. A doctor approves it later."""

import datetime as dt
import json
import logging

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from ai_engine.client import LLMOutputError, get_llm_client
from ai_engine.models import ExtractionDraft
from ai_engine.services import load_prompt
from ai_engine.validators import load_schema, validate_summary
from audit import services as audit
from clinical.models import Note, Patient, Session
from kulya.common.errors import ApiError
from rules.models import Flag

from .models import Summary

logger = logging.getLogger(__name__)

VITALS = [
    "pre_sbp", "pre_dbp", "post_sbp", "post_dbp", "min_intra_sbp", "pre_weight_kg", "post_weight_kg", "uf_volume_ml",
]  # fmt: skip
FACT_LISTS = ["symptoms", "access_findings", "staff_actions"]


def build_summary_input(patient: Patient, period_start: dt.date, period_end: dt.date) -> tuple[dict, set[int]]:
    """Return (LLM input, citable note ids).

    Only human-approved material goes in: sessions that have at least one note with an approved
    extraction, their typed vitals, their approved SessionFacts, and rule flags. The patient is
    identified by synthetic code only. Notes with pending/rejected/invalid drafts are left out, so a
    citation to them fails validation.
    """
    sessions = Session.objects.filter(patient=patient, session_date__range=(period_start, period_end)).select_related(
        "facts"
    )
    approved: dict[int, list[int]] = {}
    for note_id, session_id in Note.objects.filter(
        session__in=sessions, extraction_drafts__status=ExtractionDraft.Status.APPROVED
    ).values_list("id", "session_id"):
        approved.setdefault(session_id, [])
        if note_id not in approved[session_id]:
            approved[session_id].append(note_id)
    allowed = {n for ids in approved.values() for n in ids}

    session_rows = []
    for session in sorted(sessions, key=lambda s: (s.session_date, s.start_time)):
        if session.id not in approved:
            continue
        facts = getattr(session, "facts", None)
        row = {
            "session_id": session.id,
            "date": session.session_date.isoformat(),
            "note_ids": sorted(approved[session.id]),
            "vitals": {f: str(getattr(session, f)) for f in VITALS if getattr(session, f) is not None},
        }
        for name in FACT_LISTS:
            row[name] = [item for item in getattr(facts, name, []) if item.get("note_id") in allowed]
        session_rows.append(row)

    flag_rows = []
    for flag in Flag.objects.filter(patient=patient, session_id__in=approved).order_by("session__session_date", "id"):
        note_ids = sorted(set(flag.evidence.get("note_ids", [])) & allowed) or sorted(approved[flag.session_id])
        flag_rows.append(
            {
                "rule_id": flag.rule_id,
                "message_ar": flag.message_ar,
                "note_ids": note_ids,
            }
        )

    data = {
        "patient_code": patient.code,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "sessions": session_rows,
        "flags": flag_rows,
    }
    return data, allowed


def summary_user_input(data: dict) -> str:
    return f"<data>\n{json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1)}\n</data>"


def generate_summary(patient_id: int, audience: str, period_start: dt.date, period_end: dt.date) -> Summary:
    """Create a Summary with status 'draft' (valid) or 'invalid' (with errors). Never raises on model failure."""
    patient = Patient.objects.get(pk=patient_id)
    prompt_id = f"summary_{audience}_v1"
    data, allowed = build_summary_input(patient, period_start, period_end)
    payload: dict = {}
    model_name = ""
    try:
        client = get_llm_client()
        model_name = client.model_name
        payload = client.complete_json(
            prompt_id,
            load_prompt(prompt_id),
            summary_user_input(data),
            load_schema("summary_v1"),
        )
        ok, errors = validate_summary(payload, allowed)
    except LLMOutputError as exc:
        ok, errors = False, [{"code": "llm_output_error", "path": "", "message": str(exc)}]
    except Exception as exc:  # noqa: BLE001 - a model/config failure must not become a 500
        logger.exception("Summary generation failed for patient %s", patient_id)
        ok, errors = False, [{"code": "llm_error", "path": "", "message": f"{type(exc).__name__}: {exc}"}]
    sentences = payload.get("sentences") if isinstance(payload.get("sentences"), list) else []
    return Summary.objects.create(
        patient=patient,
        audience=audience,
        period_start=period_start,
        period_end=period_end,
        sentences=sentences,
        status=Summary.Status.DRAFT if ok else Summary.Status.INVALID,
        validation_errors=errors,
        model_name=model_name,
        prompt_version=prompt_id,
    )


SUMMARY_FIELDS = ("status", "sentences", "validation_errors", "approved_by", "approved_at")


def request_summary(patient: Patient, user: User, audience: str, period_start: dt.date, period_end: dt.date) -> Summary:
    """API entry point: generate the draft and record who asked for it."""
    summary = generate_summary(patient.id, audience, period_start, period_end)
    audit.log(user, "create_summary", summary, None, audit.snapshot(summary, "audience", *SUMMARY_FIELDS))
    return summary


@transaction.atomic
def review_summary(summary_id: int, doctor: User, approve: bool, reason: str = "") -> Summary:
    """Doctor decision. Only a 'draft' can be approved or rejected; approval is what makes a
    patient-audience summary visible to the patient."""
    summary = Summary.objects.select_for_update().get(pk=summary_id)
    if summary.status != Summary.Status.DRAFT:
        raise ApiError(
            "invalid_state",
            "حالة الملخص الحالية لا تسمح بهذا الإجراء.",
            f"Summary is '{summary.status}'; only a draft can be approved or rejected.",
            status_code=409,
            details={"status": summary.status},
        )
    before = audit.snapshot(summary, *SUMMARY_FIELDS)
    summary.status = Summary.Status.APPROVED if approve else Summary.Status.REJECTED
    if approve:
        summary.approved_by, summary.approved_at = doctor, timezone.now()
    summary.save()
    after = audit.snapshot(summary, *SUMMARY_FIELDS)
    audit.log(doctor, "approve_summary" if approve else "reject_summary", summary, before, after | {"reason": reason})
    return summary
