"""Lead-role tests L-T1 .. L-T7 (docs/team_prompts.json)."""

import datetime as dt
import json
import re
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.db import connection

from ai_engine.client import MockLLMClient, get_llm_client
from clinical.models import Note, NoteImmutableError, Patient, Session
from clinical.serializers import SessionSerializer
from kulya.common.arabic import normalize_ar

VITALS = {
    "session_date": "2026-10-01", "start_time": "08:00", "end_time": "12:00",
    "pre_sbp": 140, "pre_dbp": 85, "post_sbp": 125, "post_dbp": 78,
    "pre_weight_kg": "65.4", "post_weight_kg": "62.9", "access_type": "AVF",
}  # fmt: skip


@pytest.fixture
def note(db) -> Note:
    nurse = get_user_model().objects.create_user("nurse_t", password="x", role="nurse")
    patient = Patient.objects.create(code="SYN-T01", display_name_ar="مريض تجريبي", birth_year=1960)
    session = Session.objects.create(
        patient=patient, created_by=nurse, session_date=dt.date(2026, 10, 1),
        start_time=dt.time(8), end_time=dt.time(12), access_type="AVF",
    )  # fmt: skip
    return Note.objects.create(session=session, author=nurse, text_ar="حسّت ببرد ورجفة بنص الجلسة")


def test_l_t1_note_is_immutable(note: Note) -> None:
    original = note.text_ar
    note.text_ar = "نص معدّل"
    with pytest.raises(NoteImmutableError):
        note.save()
    assert Note.objects.get(pk=note.pk).text_ar == original


def test_l_t1_note_is_immutable_at_db_level(note: Note) -> None:
    with pytest.raises(Exception, match="immutable"), connection.cursor() as cur:
        cur.execute("UPDATE clinical_note SET text_ar = 'x' WHERE id = %s", [note.pk])


def test_l_t2_sbp_typo_rejected() -> None:
    serializer = SessionSerializer(data={**VITALS, "pre_sbp": 1200})
    assert not serializer.is_valid()
    assert "pre_sbp" in serializer.errors
    assert SessionSerializer(data=VITALS).is_valid()


@pytest.mark.django_db
def test_l_t3_patient_synthetic_by_default() -> None:
    assert Patient.objects.create(code="SYN-T02", display_name_ar="م", birth_year=1970).is_synthetic is True


def test_l_t4_diacritics_and_alef_forms() -> None:
    assert normalize_ar("أُغمِيَ عليها") == normalize_ar("اغمي عليها")
    assert normalize_ar("مستشفى  كبير") == "مستشفي كبير"


def test_l_t5_tatweel_removed() -> None:
    assert normalize_ar("بـــرد") == "برد"


def test_l_t6_mock_client_no_network(settings, monkeypatch) -> None:
    import socket

    def no_network(*args, **kwargs):
        raise AssertionError("network call attempted")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    settings.LLM_PROVIDER = "mock"
    assert isinstance(get_llm_client(), MockLLMClient)


def contract_paths() -> set[tuple[str, str]]:
    contract = json.loads((Path(__file__).parents[2] / "docs" / "team_prompts.json").read_text(encoding="utf-8"))
    api = contract["shared_context"]["api_contract"]
    found = {("POST", f"{api['base']}{p}") for p in re.findall(r"POST (/[\w/]+)", api["auth"])}
    for line in api["endpoints"]:
        method, path = line.split()[:2]
        found.add((method, api["base"] + path.split("?")[0]))
    return found


def test_l_t7_schema_lists_every_contract_endpoint(client) -> None:
    response = client.get("/api/schema/?format=json")
    assert response.status_code == 200
    schema_paths = {(m.upper(), p) for p, ops in response.json()["paths"].items() for m in ops}
    assert schema_paths == contract_paths()  # exact: nothing missing, nothing extra


@pytest.mark.django_db
def test_shared_error_format(client) -> None:
    response = client.get("/api/v1/patients/")
    assert response.status_code == 401
    assert set(response.json()["error"]) == {"code", "message_ar", "message_en", "details"}
