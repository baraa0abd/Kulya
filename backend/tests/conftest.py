"""Shared fixtures. Every test runs offline with MockLLMClient and an isolated fixtures directory."""

import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

import ai_engine.client
from ai_engine.client import fixture_key
from ai_engine.services import extraction_user_input
from clinical.models import Note, Patient, Session

PASSWORD = "test-pass-12345"
EXTRACTION_KEYS = ["symptoms", "access_findings", "staff_actions", "mentioned_values", "missing_info", "uncertain"]
EMPTY_EXTRACTION = {k: [] for k in EXTRACTION_KEYS}


def extraction(**lists: list) -> dict:
    return {**EMPTY_EXTRACTION, **lists}


def symptom(code: str, span: str, timing: str = "intra") -> dict:
    return {"code": code, "label_ar": code, "timing": timing, "evidence_span": span}


@pytest.fixture(autouse=True)
def llm_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, settings) -> Path:
    """Isolated mock-fixture directory with an empty-extraction default."""
    settings.LLM_PROVIDER = "mock"
    monkeypatch.setattr(ai_engine.client, "FIXTURES_DIR", tmp_path)
    (tmp_path / "extraction_v1").mkdir()
    (tmp_path / "extraction_v1" / "default.json").write_text(json.dumps(EMPTY_EXTRACTION), encoding="utf-8")
    return tmp_path


@pytest.fixture
def mock_llm(llm_dir: Path) -> Callable:
    """mock_llm(prompt_id, response, note_text=None): register a response (dict, or raw str for bad JSON)."""

    def register(prompt_id: str, response: dict | str, note_text: str | None = None) -> None:
        folder = llm_dir / prompt_id
        folder.mkdir(exist_ok=True)
        name = fixture_key(extraction_user_input(note_text)) if note_text is not None else "default"
        body = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
        (folder / f"{name}.json").write_text(body, encoding="utf-8")

    return register


def _user(username: str, role: str, **extra):
    return get_user_model().objects.create_user(username, password=PASSWORD, role=role, **extra)


@pytest.fixture
def nurse(db):
    return _user("nurse_t", "nurse")


@pytest.fixture
def doctor(db):
    return _user("doctor_t", "doctor")


@pytest.fixture
def admin_user(db):
    return _user("admin_t", "admin")


@pytest.fixture
def patient(db) -> Patient:
    return Patient.objects.create(code="SYN-T01", display_name_ar="مريض تجريبي", birth_year=1960)


@pytest.fixture
def other_patient(db) -> Patient:
    return Patient.objects.create(code="SYN-T02", display_name_ar="مريض تجريبي آخر", birth_year=1970)


@pytest.fixture
def patient_user(patient):
    return _user("patient_t", "patient", patient=patient)


@pytest.fixture
def other_patient_user(other_patient):
    return _user("patient_t2", "patient", patient=other_patient)


@pytest.fixture
def make_session(nurse) -> Callable:
    def make(patient: Patient, day: int = 1, **vitals) -> Session:
        defaults = dict(
            pre_sbp=140, pre_dbp=85, post_sbp=130, post_dbp=80, min_intra_sbp=128,
            pre_weight_kg="65.0", post_weight_kg="63.0", access_type="AVF",
        )  # fmt: skip
        return Session.objects.create(
            patient=patient,
            created_by=nurse,
            session_date=dt.date(2026, 9, 1) + dt.timedelta(days=day - 1),
            start_time=dt.time(8),
            end_time=dt.time(12),
            **{**defaults, **vitals},
        )

    return make


@pytest.fixture
def session(patient, make_session) -> Session:
    return make_session(patient)


@pytest.fixture
def make_note(nurse) -> Callable:
    def make(session: Session, text: str = "الجلسة مشت زينة.") -> Note:
        return Note.objects.create(session=session, author=nurse, text_ar=text)

    return make


@pytest.fixture
def api() -> Callable:
    """api(user) -> APIClient authenticated as that user (or anonymous when user is None)."""

    def client_for(user=None) -> APIClient:
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    return client_for
