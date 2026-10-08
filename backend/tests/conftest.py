"""Shared fixtures. Tests run against PostgreSQL (pgvector) with the offline MockProvider and
Celery in eager mode: no network, no API key."""

from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

import pytest
from django.conf import settings as dj_settings
from django.utils import timezone
from rest_framework.test import APIClient

from ai import rag
from clinical.models import CareAssignment, DialysisPrescription, DialysisSession, Patient
from core.models import Organization, Role, User

POLICY = (Path(dj_settings.BASE_DIR) / "ai" / "protocols" / "documentation_policy.md").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _offline(settings) -> None:
    settings.LLM_PROVIDER = "mock"
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}


@pytest.fixture
def org(db) -> Organization:
    organization = Organization.objects.create(name="Test Org")
    rag.ingest_protocol(organization, "Demo policy", "1.0", POLICY, owner="t", effective=date(2026, 1, 1))
    return organization


@pytest.fixture
def other_org(db) -> Organization:
    return Organization.objects.create(name="Other Org")


@pytest.fixture
def make_user(db) -> Callable[..., User]:
    def make(username: str, role: str, organization: Organization | None = None) -> User:
        return User.objects.create_user(username, password="pw-for-tests-12345", role=role, organization=organization,
                                        display_name=username.title())  # fmt: skip

    return make


@pytest.fixture
def doctor(org, make_user) -> User:
    return make_user("doc", Role.DOCTOR, org)


@pytest.fixture
def nurse(org, make_user) -> User:
    return make_user("nurse", Role.NURSE, org)


@pytest.fixture
def other_doctor(org, make_user) -> User:
    """Same organization, but not on this patient's care team."""
    return make_user("doc_unassigned", Role.DOCTOR, org)


@pytest.fixture
def other_nurse(org, make_user) -> User:
    return make_user("nurse_unassigned", Role.NURSE, org)


@pytest.fixture
def foreign_doctor(other_org, make_user) -> User:
    return make_user("doc_foreign", Role.DOCTOR, other_org)


@pytest.fixture
def make_patient(org, make_user, doctor, nurse) -> Callable[..., Patient]:
    def make(mrn: str = "T-001", organization: Organization | None = None, team=None) -> Patient:
        organization = organization or org
        account = make_user(f"pt_{mrn.lower()}", Role.PATIENT, organization)
        patient = Patient.objects.create(
            organization=organization, mrn=mrn, full_name=f"Patient {mrn}", date_of_birth=date(1960, 1, 1), user=account
        )
        for member in team if team is not None else (doctor, nurse):
            CareAssignment.objects.create(patient=patient, professional=member)
        DialysisPrescription.objects.create(
            patient=patient, version=1, prescribed_by=doctor, duration_minutes=240, target_uf_ml=2000, access_type="AVF"
        )
        return patient

    return make


@pytest.fixture
def patient(make_patient) -> Patient:
    return make_patient()


@pytest.fixture
def other_patient(make_patient) -> Patient:
    """Same organization, no shared care team with `doctor` / `nurse`."""
    return make_patient("T-002", team=())


@pytest.fixture
def family(make_user) -> User:
    return make_user("fam", Role.FAMILY)


@pytest.fixture
def api() -> Callable[..., APIClient]:
    def client_for(user: User | None = None) -> APIClient:
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    return client_for


@pytest.fixture
def scheduled(patient, nurse) -> DialysisSession:
    return DialysisSession.objects.create(
        patient=patient,
        prescription=patient.prescriptions.get(),
        scheduled_start=timezone.now() + timedelta(minutes=5),
        created_by=nurse,
    )


@pytest.fixture
def in_progress(api, nurse, scheduled) -> DialysisSession:
    response = api(nurse).post(f"/api/sessions/{scheduled.id}/start/", {"pre_weight_kg": "64.0"}, format="json")
    assert response.status_code == 200, response.content
    # Backdate the start so a session completed "now" has the prescribed 240-minute duration.
    DialysisSession.objects.filter(pk=scheduled.pk).update(started_at=timezone.now() - timedelta(minutes=240))
    scheduled.refresh_from_db()
    return scheduled


def post_vital(client: APIClient, session: DialysisSession, kind: str, value, phase: str, **extra):
    body = {"session": str(session.id), "kind": kind, "value": value, "phase": phase,
            "recorded_at": timezone.now().isoformat(), **extra}  # fmt: skip
    return client.post("/api/vitals/", body, format="json")


def post_action(client: APIClient, session: DialysisSession, reason: str = "Routine check.", **extra):
    body = {"session": str(session.id), "action_type": "access_care", "description": "Access site checked.",
            "reason": reason, "performed_at": timezone.now().isoformat(), **extra}  # fmt: skip
    return client.post("/api/nursing-actions/", body, format="json")


@pytest.fixture
def completed(api, nurse, in_progress) -> DialysisSession:
    """A fully documented, completed session (so the only findings are the ones a test adds)."""
    client = api(nurse)
    for kind, value in (("systolic_bp", 140), ("diastolic_bp", 85)):
        assert post_vital(client, in_progress, kind, value, "pre").status_code == 201
        assert post_vital(client, in_progress, kind, value - 8, "post").status_code == 201
    assert post_action(client, in_progress).status_code == 201
    body = {"post_weight_kg": "62.0", "uf_volume_ml": 2000}
    assert client.post(f"/api/sessions/{in_progress.id}/complete/", body, format="json").status_code == 200
    in_progress.refresh_from_db()
    return in_progress
