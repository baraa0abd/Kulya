"""Writes to the clinical record. Views stay thin; every function here audits what it did."""

from django.db import models, transaction
from django.utils import timezone

from ai.tasks import review_session, summarize_session
from core.errors import ApiError, Conflict
from core.models import Role, User
from core.permissions import assigned_professionals
from core.services import audit, dispatch
from workflow.services import notify

from .models import (
    CaregiverConsent,
    DialysisPrescription,
    DialysisSession,
    LaboratoryReport,
    LaboratoryResult,
    NursingAction,
    Patient,
    Phase,
    SessionEvent,
    SessionStatus,
    Source,
    Verification,
    VitalSign,
)

OPEN_FOR_DOCUMENTATION = (SessionStatus.IN_PROGRESS, SessionStatus.COMPLETED)


@transaction.atomic
def schedule_session(patient: Patient, nurse: User, scheduled_start, device=None) -> DialysisSession:
    prescription = patient.prescriptions.filter(active=True).first()
    if prescription is None:
        raise ApiError("no_active_prescription", "This patient has no active dialysis prescription.")
    if device is not None and device.organization_id != patient.organization_id:
        raise ApiError("invalid_device", "Unknown device.")
    session = DialysisSession.objects.create(
        patient=patient, prescription=prescription, device=device, scheduled_start=scheduled_start, created_by=nurse
    )
    audit(nurse, "session_scheduled", session)
    return session


def _locked(session_id, expected: str) -> DialysisSession:
    session = DialysisSession.objects.select_for_update().get(pk=session_id)
    if session.status != expected:
        raise Conflict(f"Session is '{session.status}'; this action needs '{expected}'.", {"status": session.status})
    return session


@transaction.atomic
def start_session(session_id, nurse: User, pre_weight_kg=None) -> DialysisSession:
    session = _locked(session_id, SessionStatus.SCHEDULED)
    session.status, session.started_at, session.started_by = SessionStatus.IN_PROGRESS, timezone.now(), nurse
    session.pre_weight_kg = pre_weight_kg
    session.save()
    audit(nurse, "session_started", session)
    return session


def complete_session(session_id, nurse: User, post_weight_kg=None, uf_volume_ml=None) -> DialysisSession:
    with transaction.atomic():
        session = _locked(session_id, SessionStatus.IN_PROGRESS)
        session.status, session.ended_at, session.completed_by = SessionStatus.COMPLETED, timezone.now(), nurse
        session.post_weight_kg, session.uf_volume_ml = post_weight_kg, uf_volume_ml
        session.save()
        audit(nurse, "session_completed", session)
    # Queued after commit. A missing worker or broker never undoes or blocks the clinical write.
    dispatch(review_session, str(session.id), "session_completed")
    dispatch(summarize_session, str(session.id), str(nurse.id))
    return session


def require_open(session: DialysisSession) -> None:
    if session.status not in OPEN_FOR_DOCUMENTATION:
        raise Conflict(f"Session is '{session.status}'; start it before documenting.", {"status": session.status})


@transaction.atomic
def record(serializer, user: User, action: str, author_field: str, **extra) -> models.Model:
    """Persist one validated session record (vital, reading, note, event) with its author."""
    session = serializer.validated_data.get("session")
    if session is not None:
        require_open(session)
    obj = serializer.save(**{author_field: user}, **extra)
    audit(user, action, obj, patient=session.patient if session else extra.get("patient"))
    return obj


def record_nursing_action(serializer, nurse: User) -> NursingAction:
    action = record(serializer, nurse, "nursing_action_recorded", "author")
    session = action.session
    for doctor in assigned_professionals(session.patient, Role.DOCTOR):
        notify(doctor, "nursing_action", "New nursing action documented", session, f"action:{action.id}")
    dispatch(review_session, str(session.id), "nursing_action_submitted")
    return action


@transaction.atomic
def amend(model: type[models.Model], original_id, serializer, user: User, author_field: str) -> models.Model:
    """Correct a signed record by adding a new one that points at it. The original is untouched."""
    original = model.objects.select_for_update().get(pk=original_id)
    if original.amended_by.exists():
        raise Conflict("This record was already amended; amend the latest version instead.")
    if serializer.validated_data["session"] != original.session:
        raise ApiError("invalid_amendment", "An amendment must stay in the same session.")
    obj = serializer.save(**{author_field: user}, amends=original)
    audit(user, "record_amended", obj, patient=original.session.patient, amends=str(original.pk))
    return obj


@transaction.atomic
def record_home_vital(serializer, patient_user: User, patient: Patient) -> VitalSign:
    obj = serializer.save(
        patient=patient,
        session=None,
        phase=Phase.HOME,
        source=Source.PATIENT_REPORTED,
        verification_status=Verification.UNVERIFIED,
        recorded_by=patient_user,
    )
    audit(patient_user, "home_measurement_submitted", obj, patient=patient)
    return obj


@transaction.atomic
def resolve_event(event_id, nurse: User, resolution: str) -> SessionEvent:
    event = SessionEvent.objects.select_for_update(of=("self",)).select_related("session__patient").get(pk=event_id)
    if event.resolved_at:
        raise Conflict("This event already has a documented resolution.")
    event.resolution, event.resolved_at, event.resolved_by = resolution, timezone.now(), nurse
    event.save()
    audit(nurse, "event_resolved", event, patient=event.session.patient)
    return event


@transaction.atomic
def create_prescription(patient: Patient, doctor: User, data: dict) -> DialysisPrescription:
    """A new version replaces the active one; earlier versions stay for the sessions that used them."""
    latest = patient.prescriptions.select_for_update().order_by("-version").first()
    patient.prescriptions.filter(active=True).update(active=False)
    rx = DialysisPrescription.objects.create(
        patient=patient, prescribed_by=doctor, version=(latest.version + 1) if latest else 1, **data
    )
    audit(doctor, "prescription_created", rx, version=rx.version)
    return rx


@transaction.atomic
def create_lab_report(patient: Patient, user: User, data: dict) -> LaboratoryReport:
    results = data.pop("results")
    report = LaboratoryReport.objects.create(patient=patient, entered_by=user, **data)
    LaboratoryResult.objects.bulk_create(LaboratoryResult(report=report, **r) for r in results)
    audit(user, "lab_report_entered", report)
    return report


@transaction.atomic
def release_lab_report(report: LaboratoryReport, doctor: User) -> LaboratoryReport:
    if report.released_to_patient:
        raise Conflict("Report is already released.")
    report.released_to_patient, report.released_by, report.released_at = True, doctor, timezone.now()
    report.save()
    audit(doctor, "lab_report_released", report)
    return report


@transaction.atomic
def grant_consent(
    patient: Patient, patient_user: User, caregiver_username: str, scopes, expires_at
) -> CaregiverConsent:
    caregiver = User.objects.filter(username=caregiver_username, role=Role.FAMILY, is_active=True).first()
    if caregiver is None:
        raise ApiError("unknown_caregiver", "No caregiver account with that username.")
    consent = CaregiverConsent.objects.create(
        patient=patient, caregiver=caregiver, scopes=sorted(set(scopes)), expires_at=expires_at, granted_by=patient_user
    )
    audit(patient_user, "consent_granted", consent, scopes=consent.scopes)
    return consent


@transaction.atomic
def revoke_consent(consent: CaregiverConsent, patient_user: User) -> CaregiverConsent:
    if consent.revoked_at:
        raise Conflict("Consent is already revoked.")
    consent.revoked_at = timezone.now()
    consent.save()
    audit(patient_user, "consent_revoked", consent)
    return consent
