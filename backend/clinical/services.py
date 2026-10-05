"""Clinical record services. Views stay thin; anything that writes the record lives here."""

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from ai_engine.models import ExtractionDraft
from ai_engine.services import request_extraction
from ai_engine.validators import validate_extraction
from audit import services as audit
from kulya.common.errors import ApiError
from rules.services import evaluate_patient

from .models import Note, Patient, Session, SessionFacts

FACT_LISTS = ["symptoms", "access_findings", "staff_actions"]
DRAFT_FIELDS = ("status", "payload", "edited_payload", "validation_errors", "reviewed_by", "reviewed_at")
Status = ExtractionDraft.Status


def merge_facts(note: Note, payload: dict) -> SessionFacts:
    """Write the facts of one human-approved extraction into the session's SessionFacts.

    Callers must have validated `payload` and must only call this for an approved draft. Items from
    this note replace any earlier items from the same note; items from other notes are kept. Every
    item keeps its note_id and evidence_span. Only the three fact lists are read: `mentioned_values`
    never reach the record and Session vitals are never touched.
    """
    facts, _ = SessionFacts.objects.get_or_create(session=note.session)
    replaced = {note.id, note.supersedes_id}  # a correction also retires the facts of the note it corrects
    for name in FACT_LISTS:
        kept = [item for item in getattr(facts, name) if item.get("note_id") not in replaced]
        setattr(facts, name, kept + [{**item, "note_id": note.id} for item in payload.get(name, [])])
    facts.save()
    return facts


@transaction.atomic
def create_session(patient: Patient, user: User, data: dict) -> Session:
    session = Session.objects.create(patient=patient, created_by=user, **data)
    audit.log(user, "create_session", session, None, audit.snapshot(session))
    evaluate_patient(patient.id)
    return session


def create_note(session: Session, user: User, text_ar: str, supersedes: Note | None = None) -> ExtractionDraft:
    """Save the note, then run extraction. Returns the draft (its `.note` is the new note).

    The note is committed before the model is called, and request_extraction never raises, so an AI
    failure can never lose a nurse's note.
    ponytail: extraction runs inline (simple and reliable for the demo). To scale, enqueue
    request_extraction(note.id) here instead and return the note with no draft yet.
    """
    if supersedes is not None and supersedes.session.patient_id != session.patient_id:
        raise ApiError(
            "invalid_supersedes",
            "الملاحظة المصحَّحة لا تعود لهذا المريض.",
            "The superseded note belongs to another patient.",
            details={"supersedes": supersedes.id},
        )
    with transaction.atomic():
        note = Note.objects.create(session=session, author=user, text_ar=text_ar, supersedes=supersedes)
        audit.log(user, "create_note", note, None, audit.snapshot(note))
    draft = request_extraction(note.id)
    with transaction.atomic():
        audit.log(user, "create_extraction_draft", draft, None, audit.snapshot(draft, *DRAFT_FIELDS))
        evaluate_patient(session.patient_id)
    return draft


def _locked_draft(draft_id: int, allowed: tuple[str, ...]) -> ExtractionDraft:
    draft = ExtractionDraft.objects.select_for_update().select_related("note__session").get(pk=draft_id)
    if draft.status not in allowed:
        raise ApiError(
            "invalid_state",
            "حالة المسودة الحالية لا تسمح بهذا الإجراء.",
            f"Draft is '{draft.status}'; this action needs one of: {', '.join(allowed)}.",
            status_code=409,
            details={"status": draft.status},
        )
    return draft


@transaction.atomic
def approve_draft(draft_id: int, user: User, edited_payload: dict | None = None) -> ExtractionDraft:
    """Nurse approval: the only path by which extracted facts enter the clinical record."""
    draft = _locked_draft(draft_id, (Status.PENDING,))
    note = draft.note
    if edited_payload is not None:
        # A human edit gets the same grounding checks as model output.
        ok, errors = validate_extraction(edited_payload, note.text_ar)
        if not ok:
            raise ApiError(
                "invalid_edit",
                "التعديل يحتوي على عناصر غير موجودة حرفياً في نص الملاحظة.",
                "The edited payload failed validation.",
                details={"validation_errors": errors},
            )
    before = audit.snapshot(draft, *DRAFT_FIELDS)
    draft.edited_payload = edited_payload
    draft.status = Status.APPROVED
    draft.reviewed_by, draft.reviewed_at = user, timezone.now()
    draft.save()
    merge_facts(note, edited_payload if edited_payload is not None else draft.payload)
    action = "approve_draft" if edited_payload is None else "edit_and_approve_draft"
    audit.log(user, action, draft, before, audit.snapshot(draft, *DRAFT_FIELDS))
    evaluate_patient(note.session.patient_id)
    return draft


@transaction.atomic
def reject_draft(draft_id: int, user: User, reason: str = "") -> ExtractionDraft:
    draft = _locked_draft(draft_id, (Status.PENDING, Status.INVALID))
    before = audit.snapshot(draft, *DRAFT_FIELDS)
    draft.status = Status.REJECTED
    draft.reviewed_by, draft.reviewed_at = user, timezone.now()
    draft.save()
    audit.log(user, "reject_draft", draft, before, {**audit.snapshot(draft, *DRAFT_FIELDS), "reason": reason})
    evaluate_patient(draft.note.session.patient_id)
    return draft


def retry_draft(draft_id: int, user: User) -> ExtractionDraft:
    """Re-run extraction for the draft's note. The old draft is closed as rejected; returns the new one."""
    with transaction.atomic():
        old = _locked_draft(draft_id, (Status.PENDING, Status.INVALID, Status.REJECTED))
        if old.status != Status.REJECTED:
            before = audit.snapshot(old, *DRAFT_FIELDS)
            old.status = Status.REJECTED
            old.reviewed_by, old.reviewed_at = user, timezone.now()
            old.save()
            after = {**audit.snapshot(old, *DRAFT_FIELDS), "reason": "retry"}
            audit.log(user, "reject_draft", old, before, after)
    new = request_extraction(old.note_id)
    with transaction.atomic():
        after = {**audit.snapshot(new, *DRAFT_FIELDS), "previous_draft_id": old.id}
        audit.log(user, "retry_extraction", new, None, after)
        evaluate_patient(old.note.session.patient_id)
    return new
