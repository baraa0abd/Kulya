"""Authorization tests: default deny, tenant and patient isolation, IDOR, consent, release rules."""

from datetime import timedelta

import pytest
from django.utils import timezone

from ai.models import AISummary
from ai.services import release_summary, verify_summary
from clinical.models import CareAssignment, CaregiverConsent, LaboratoryReport, LaboratoryResult
from core.models import AuditEvent, Role
from tests.conftest import post_action, post_vital

LIST_ENDPOINTS = [
    "patients", "care-assignments", "consent", "prescriptions", "sessions", "nursing-actions", "nursing-notes",
    "device-readings", "session-events", "vitals", "labs", "ai/reviews", "ai/summaries", "doctor/feedback",
    "doctor/review-tasks", "notifications", "audit",
]  # fmt: skip


@pytest.mark.parametrize("endpoint", [*LIST_ENDPOINTS, "auth/me"])
def test_unauthenticated_requests_are_rejected(api, db, endpoint) -> None:
    response = api().get(f"/api/{endpoint}/")
    assert response.status_code == 401
    assert set(response.json()["error"]) == {"code", "message", "details"}


def test_health_is_public_and_login_works(api, nurse) -> None:
    assert api().get("/api/health/").json() == {"status": "ok"}
    ok = api().post("/api/auth/login/", {"username": "nurse", "password": "pw-for-tests-12345"}, format="json")
    assert ok.status_code == 200 and ok.json()["user"]["role"] == "nurse" and "access" in ok.json()
    assert api().post("/api/auth/login/", {"username": "nurse", "password": "nope"}, format="json").status_code == 401


def test_service_accounts_cannot_log_in(api, make_user) -> None:
    make_user("ai_worker", Role.SERVICE)
    body = {"username": "ai_worker", "password": "pw-for-tests-12345"}
    assert api().post("/api/auth/login/", body, format="json").status_code == 401


def test_dietitian_can_restore_their_signed_in_session(api, org, make_user) -> None:
    dietitian = make_user("dietitian_restore", Role.DIETITIAN, org)
    login = api().post(
        "/api/auth/login/", {"username": dietitian.username, "password": "pw-for-tests-12345"}, format="json"
    )
    assert login.status_code == 200
    client = api()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")
    response = client.get("/api/auth/me/")
    assert response.status_code == 200
    assert response.json()["role"] == Role.DIETITIAN


def test_assigned_doctor_can_read_clinical_endpoints(api, doctor) -> None:
    for endpoint in ("patients", "sessions", "ai/reviews", "labs"):
        assert api(doctor).get(f"/api/{endpoint}/").status_code == 200


@pytest.mark.parametrize("role", [Role.ORG_ADMIN, Role.AUDITOR, Role.SYS_ADMIN])
def test_admin_roles_have_no_clinical_access(api, org, make_user, role) -> None:
    user = make_user("admin_like", role, org)
    for endpoint in ("patients", "sessions", "vitals", "labs", "ai/reviews", "ai/summaries", "nursing-actions"):
        assert api(user).get(f"/api/{endpoint}/").status_code == 403


def test_staff_see_only_assigned_patients(
    api, doctor, nurse, other_doctor, other_nurse, patient, other_patient
) -> None:
    for user in (doctor, nurse):
        listed = api(user).get("/api/patients/").json()["results"]
        assert [p["mrn"] for p in listed] == ["T-001"]
        assert api(user).get(f"/api/patients/{other_patient.id}/").status_code == 404
    for user in (other_doctor, other_nurse):  # same organization, not on the care team
        assert api(user).get("/api/patients/").json()["results"] == []
        assert api(user).get(f"/api/patients/{patient.id}/").status_code == 404


def test_cross_organization_isolation(api, foreign_doctor, patient, completed) -> None:
    client = api(foreign_doctor)
    assert client.get("/api/patients/").json()["count"] == 0
    assert client.get(f"/api/patients/{patient.id}/").status_code == 404
    assert client.get(f"/api/sessions/{completed.id}/").status_code == 404
    assert client.get(f"/api/sessions/?patient={patient.id}").json()["count"] == 0
    assert client.get(f"/api/ai/reviews/?session={completed.id}").json()["count"] == 0
    # An assignment across organizations must not grant access either.
    CareAssignment.objects.create(patient=patient, professional=foreign_doctor)
    assert client.get(f"/api/patients/{patient.id}/").status_code == 404


def test_ended_or_inactive_assignment_removes_access(api, doctor, patient) -> None:
    assignment = CareAssignment.objects.get(patient=patient, professional=doctor)
    assignment.ends_at = timezone.now() - timedelta(minutes=1)
    assignment.save()
    assert api(doctor).get(f"/api/patients/{patient.id}/").status_code == 404
    assignment.ends_at, assignment.active = None, False
    assignment.save()
    assert api(doctor).get("/api/patients/").json()["count"] == 0


def test_idor_on_writes_and_actions(api, other_nurse, other_doctor, patient, in_progress, completed) -> None:
    """Knowing an id is not enough: unassigned staff cannot write to or act on another team's records."""
    nurse_client, doctor_client = api(other_nurse), api(other_doctor)
    assert post_vital(nurse_client, in_progress, "systolic_bp", 120, "intra").status_code == 404
    assert post_action(nurse_client, in_progress).status_code == 404
    assert nurse_client.post(f"/api/sessions/{in_progress.id}/complete/", {}, format="json").status_code == 404
    future = (timezone.now() + timedelta(days=1)).isoformat()
    body = {"patient": str(patient.id), "scheduled_start": future}
    assert nurse_client.post("/api/sessions/", body, format="json").status_code == 404
    summary = completed.ai_summaries.get()
    for action in ("verify", "reject", "release"):
        assert doctor_client.post(f"/api/ai/summaries/{summary.id}/{action}/").status_code == 404
    assert (
        doctor_client.post("/api/ai/reviews/request/", {"session": str(completed.id)}, format="json").status_code == 404
    )
    feedback = {"session": str(completed.id), "text": "x"}
    assert doctor_client.post("/api/doctor/feedback/", feedback, format="json").status_code == 404


def test_vertical_privilege_escalation_is_blocked(api, nurse, doctor, patient, completed) -> None:
    summary, review = completed.ai_summaries.get(), completed.ai_reviews.first()
    nurse_client = api(nurse)
    # Nurses cannot do physician-only things, including approving AI output.
    for action in ("verify", "reject", "release"):
        assert nurse_client.post(f"/api/ai/summaries/{summary.id}/{action}/").status_code == 403
    assert nurse_client.get(f"/api/ai/reviews/{review.id}/").status_code == 403
    assert (
        nurse_client.post(
            "/api/doctor/feedback/", {"session": str(completed.id), "text": "x"}, format="json"
        ).status_code
        == 403
    )
    rx = {"patient": str(patient.id), "duration_minutes": 180, "access_type": "AVF"}
    assert nurse_client.post("/api/prescriptions/", rx, format="json").status_code == 403
    assert nurse_client.get("/api/audit/").status_code == 403
    # Doctors cannot write nursing documentation.
    assert post_action(api(doctor), completed).status_code == 403
    # The role sent by a client is ignored: it comes from the authenticated account only.
    assert nurse_client.get("/api/ai/reviews/", {"role": "doctor"}, HTTP_X_ROLE="doctor").status_code == 403


def test_signed_records_cannot_be_modified_or_deleted(api, nurse, completed) -> None:
    action = completed.nursing_actions.get()
    for method in ("put", "patch", "delete"):
        response = getattr(api(nurse), method)(
            f"/api/nursing-actions/{action.id}/", {"reason": "edited"}, format="json"
        )
        assert response.status_code == 405
    action.refresh_from_db()
    assert action.reason == "Routine check."


def test_patient_sees_only_own_released_information(api, doctor, patient, make_patient, completed) -> None:
    stranger = make_patient("T-009")
    client = api(patient.user)
    assert [p["id"] for p in client.get("/api/patients/").json()["results"]] == [str(patient.id)]
    assert set(client.get(f"/api/patients/{patient.id}/").json()) == {"id", "full_name"}
    assert client.get(f"/api/patients/{stranger.id}/").status_code == 404
    # Sessions: dates and status only, nothing clinical.
    session = client.get(f"/api/sessions/{completed.id}/").json()
    assert set(session) == {"id", "patient", "patient_name", "status", "scheduled_start", "started_at", "ended_at"}
    # Staff-only resources.
    for endpoint in (
        "nursing-actions",
        "nursing-notes",
        "session-events",
        "device-readings",
        "ai/reviews",
        "doctor/feedback",
    ):
        assert client.get(f"/api/{endpoint}/").status_code == 403
    assert client.get("/api/vitals/").json()["count"] == 0  # staff-recorded vitals are not exposed

    summary = completed.ai_summaries.get()
    assert summary.status == "unverified"
    assert client.get("/api/ai/summaries/").json()["count"] == 0
    assert client.get(f"/api/ai/summaries/{summary.id}/").status_code == 404
    verify_summary(summary.id, doctor, approve=True)
    assert client.get("/api/ai/summaries/").json()["count"] == 0  # verified is still not released
    release_summary(summary.id, doctor)
    released = client.get("/api/ai/summaries/").json()["results"]
    assert len(released) == 1 and set(released[0]) == {
        "id",
        "session",
        "session_date",
        "patient_name",
        "text",
        "released_at",
    }
    assert api(stranger.user).get(f"/api/ai/summaries/{summary.id}/").status_code == 404


def test_unauthorized_summary_release(api, doctor, nurse, patient, completed) -> None:
    summary = completed.ai_summaries.get()
    assert api(patient.user).post(f"/api/ai/summaries/{summary.id}/release/").status_code == 403
    # Even the assigned doctor cannot release before verifying.
    early = api(doctor).post(f"/api/ai/summaries/{summary.id}/release/")
    assert early.status_code == 409 and early.json()["error"]["code"] == "invalid_state"
    assert api(doctor).post(f"/api/ai/summaries/{summary.id}/reject/").status_code == 200
    assert api(doctor).post(f"/api/ai/summaries/{summary.id}/release/").status_code == 409
    assert not AISummary.objects.filter(released=True).exists()


def test_labs_are_released_per_report(api, doctor, nurse, patient) -> None:
    now = timezone.now()
    report = LaboratoryReport.objects.create(
        patient=patient, collected_at=now, reported_at=now, source="lab", entered_by=doctor
    )
    LaboratoryResult.objects.create(report=report, analyte="Potassium", value="4.9", unit="mmol/L")
    assert api(patient.user).get("/api/labs/").json()["count"] == 0
    assert api(nurse).post(f"/api/labs/{report.id}/release/").status_code == 403
    assert api(doctor).post(f"/api/labs/{report.id}/release/").status_code == 200
    shown = api(patient.user).get("/api/labs/").json()["results"]
    assert shown[0]["results"][0]["unit"] == "mmol/L"


def test_family_access_needs_a_valid_consent_grant(api, doctor, family, patient, completed) -> None:
    summary = completed.ai_summaries.get()
    verify_summary(summary.id, doctor, approve=True)
    release_summary(summary.id, doctor)
    client = api(family)
    # No grant: nothing at all.
    for endpoint in ("patients", "sessions", "ai/summaries", "labs"):
        assert client.get(f"/api/{endpoint}/").json()["count"] == 0

    grant = {"caregiver_username": "fam", "scopes": ["summaries"]}
    created = api(patient.user).post("/api/consent/", grant, format="json")
    assert created.status_code == 201, created.content
    assert client.get("/api/ai/summaries/").json()["count"] == 1
    assert client.get("/api/sessions/").json()["count"] == 0  # 'appointments' was not granted
    assert client.get("/api/labs/").json()["count"] == 0  # 'labs' was not granted
    assert client.post("/api/consent/", grant, format="json").status_code == 403  # caregivers cannot grant

    revoked = api(patient.user).post(f"/api/consent/{created.json()['id']}/revoke/")
    assert revoked.status_code == 200
    assert client.get("/api/ai/summaries/").json()["count"] == 0
    assert client.get(f"/api/ai/summaries/{summary.id}/").status_code == 404


def test_expired_consent_gives_no_access(api, family, patient, completed) -> None:
    CaregiverConsent.objects.create(
        patient=patient,
        caregiver=family,
        scopes=["summaries", "appointments", "labs"],
        granted_by=patient.user,
        expires_at=timezone.now() - timedelta(seconds=1),
    )
    for endpoint in ("patients", "sessions", "ai/summaries", "labs"):
        assert api(family).get(f"/api/{endpoint}/").json()["count"] == 0
    assert api(family).get(f"/api/sessions/{completed.id}/").status_code == 404


def test_notifications_are_private(api, doctor, nurse, completed) -> None:
    mine = api(doctor).get("/api/notifications/").json()["results"]
    assert mine and all(n["title"] for n in mine)
    assert api(nurse).post(f"/api/notifications/{mine[0]['id']}/read/").status_code == 404
    assert api(doctor).post(f"/api/notifications/{mine[0]['id']}/read/").json()["read_at"]


def test_sensitive_access_is_audited_without_clinical_text(api, org, make_user, doctor, completed) -> None:
    api(doctor).get(f"/api/sessions/{completed.id}/")
    actions = set(AuditEvent.objects.values_list("action", flat=True))
    assert {"session_started", "vital_recorded", "nursing_action_recorded", "session_completed", "session_viewed",
            "ai_review_created", "ai_summary_created"} <= actions  # fmt: skip
    assert "Access site checked" not in str(list(AuditEvent.objects.values_list("metadata", flat=True)))
    auditor = make_user("aud", Role.AUDITOR, org)
    rows = api(auditor).get("/api/audit/?action=session_viewed").json()["results"]
    assert rows[0]["actor_username"] == "doc" and rows[0]["object_id"] == str(completed.id)


def test_errors_do_not_leak_internals(api, nurse) -> None:
    bad = api(nurse).get("/api/sessions/?patient=not-a-uuid")
    assert bad.status_code == 400 and "Traceback" not in bad.content.decode()
    missing = api(nurse).get("/api/sessions/00000000-0000-0000-0000-000000000000/")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"
