"""ORM adapter for the rules engine."""

import datetime as dt

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from ai_engine.models import ExtractionDraft
from clinical.models import Note, Session

from .config import load_config
from .engine import Fact, PendingDraft, SessionSnapshot, run_all
from .models import Flag


def _facts(items: list[dict]) -> tuple[Fact, ...]:
    return tuple(Fact(item["code"], item.get("note_id")) for item in items)


def _as_float(value: object) -> float | None:
    return None if value is None else float(value)


def build_snapshots(patient_id: int) -> list[SessionSnapshot]:
    """Sessions oldest -> newest. Symptoms and access findings come only from approved SessionFacts."""
    pending = ExtractionDraft.objects.filter(status=ExtractionDraft.Status.PENDING)
    notes = Note.objects.prefetch_related(Prefetch("extraction_drafts", queryset=pending, to_attr="pending"))
    sessions = (
        Session.objects.filter(patient_id=patient_id)
        .select_related("facts")
        .prefetch_related(Prefetch("notes", queryset=notes))
        .order_by("session_date", "start_time", "id")
    )
    snapshots = []
    for s in sessions:
        facts = getattr(s, "facts", None)
        session_notes = list(s.notes.all())
        ended_at = timezone.make_aware(dt.datetime.combine(s.session_date, s.end_time))
        snapshots.append(
            SessionSnapshot(
                session_id=s.id,
                session_date=s.session_date,
                ended_at=ended_at,
                pre_sbp=s.pre_sbp,
                pre_dbp=s.pre_dbp,
                post_sbp=s.post_sbp,
                post_dbp=s.post_dbp,
                min_intra_sbp=s.min_intra_sbp,
                pre_weight_kg=_as_float(s.pre_weight_kg),
                post_weight_kg=_as_float(s.post_weight_kg),
                has_facts=facts is not None,
                symptoms=_facts(facts.symptoms) if facts else (),
                access_findings=_facts(facts.access_findings) if facts else (),
                note_ids=tuple(n.id for n in session_notes),
                pending_drafts=tuple(PendingDraft(d.id, n.id, d.created_at) for n in session_notes for d in n.pending),
            )
        )
    return snapshots


def evaluate_patient(patient_id: int, now: dt.datetime | None = None) -> list[Flag]:
    """Recompute every flag for one patient and replace the stored set atomically (idempotent).

    ponytail: R3 (late note) and R6 (pending review) depend on the clock but are only re-checked when
    something calls this (session/note creation, draft approval, seeding). Add a periodic job if
    time-based flags must appear without any activity.
    """
    config = load_config()
    results = run_all(build_snapshots(patient_id), config, now or timezone.now())
    with transaction.atomic():
        Flag.objects.filter(patient_id=patient_id).delete()
        return Flag.objects.bulk_create(
            Flag(
                patient_id=patient_id,
                session_id=r.session_id,
                rule_id=r.rule_id,
                severity=r.severity,
                message_ar=r.message_ar,
                evidence=r.evidence,
                rules_version=config.version,
            )
            for r in results
        )
