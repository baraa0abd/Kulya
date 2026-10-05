"""Backend-role tests B-T1 .. B-T16, plus A-T15 and R-T14 (which need the approve API)."""

import datetime as dt

import pytest
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured
from rest_framework_simplejwt.tokens import AccessToken

from ai_engine.models import ExtractionDraft
from audit.models import AuditLog
from clinical.apps import check_demo_guard
from clinical.models import Note, Patient, Session, SessionFacts
from rules.models import Flag
from summaries.models import Summary
from tests.conftest import PASSWORD, extraction, symptom

CHILLS_NOTE = "حسّت ببرد ورجفة بنص الجلسة والضغط صار ١٢٠/٨٠"
CHILLS = extraction(
    symptoms=[symptom("chills", "ببرد ورجفة")],
    mentioned_values=[{"kind": "bp", "raw_text": "١٢٠/٨٠"}],
)
VITALS = {
    "session_date": "2026-10-01", "start_time": "08:00", "end_time": "12:00",
    "pre_sbp": 140, "pre_dbp": 85, "post_sbp": 125, "post_dbp": 78, "min_intra_sbp": 126,
    "pre_weight_kg": "65.4", "post_weight_kg": "62.9", "access_type": "AVF",
}  # fmt: skip
ERROR_KEYS = {"code", "message_ar", "message_en", "details"}


@pytest.fixture
def pending_draft(api, nurse, session, mock_llm) -> ExtractionDraft:
    mock_llm("extraction_v1", CHILLS, note_text=CHILLS_NOTE)
    response = api(nurse).post(f"/api/v1/sessions/{session.id}/notes/", {"text_ar": CHILLS_NOTE}, format="json")
    assert response.status_code == 201, response.content
    return ExtractionDraft.objects.get(pk=response.json()["draft_id"])


def test_b_t1_token_has_role_claim(client, nurse) -> None:
    response = client.post("/api/v1/auth/token", {"username": nurse.username, "password": PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert {"access", "refresh"} <= set(body) and body["role"] == "nurse"
    assert AccessToken(body["access"])["role"] == "nurse"
    refreshed = client.post("/api/v1/auth/token/refresh", {"refresh": body["refresh"]})
    assert refreshed.status_code == 200 and "access" in refreshed.json()
    bad = client.post("/api/v1/auth/token", {"username": nurse.username, "password": "wrong"})
    assert bad.status_code == 401 and set(bad.json()["error"]) == ERROR_KEYS


def test_b_t2_patient_role_cannot_list_patients(api, patient_user) -> None:
    response = api(patient_user).get("/api/v1/patients/")
    assert response.status_code == 403 and set(response.json()["error"]) == ERROR_KEYS
    assert api().get("/api/v1/patients/").status_code == 401


def test_b_t2b_patient_detail_scoping(api, nurse, patient, other_patient, patient_user) -> None:
    assert api(patient_user).get(f"/api/v1/patients/{patient.id}/").json()["code"] == "SYN-T01"
    assert api(patient_user).get(f"/api/v1/patients/{other_patient.id}/").status_code == 404
    listed = api(nurse).get("/api/v1/patients/").json()
    assert [p["code"] for p in listed["results"]] == ["SYN-T01", "SYN-T02"]


def test_b_t3_create_session_writes_audit(api, nurse, patient) -> None:
    response = api(nurse).post(f"/api/v1/patients/{patient.id}/sessions/", VITALS, format="json")
    assert response.status_code == 201, response.content
    session = Session.objects.get(pk=response.json()["id"])
    assert (session.patient, session.created_by, session.pre_sbp) == (patient, nurse, 140)
    log = AuditLog.objects.get(action="create_session")
    assert (log.actor, log.object_type, log.object_id) == (nurse, "Session", session.id)
    assert log.before is None and log.after["pre_sbp"] == 140
    assert api(nurse).get(f"/api/v1/sessions/{session.id}/").json()["post_weight_kg"] == "62.9"


def test_b_t4_end_before_start_rejected(api, nurse, patient) -> None:
    body = {**VITALS, "start_time": "12:00", "end_time": "08:00"}
    response = api(nurse).post(f"/api/v1/patients/{patient.id}/sessions/", body, format="json")
    assert response.status_code == 400
    error = response.json()["error"]
    assert set(error) == ERROR_KEYS and error["code"] == "validation_error" and "end_time" in error["details"]
    assert error["message_ar"] and not Session.objects.exists()


def test_b_t4b_typo_vitals_rejected_and_doctor_cannot_create(api, nurse, doctor, patient) -> None:
    url = f"/api/v1/patients/{patient.id}/sessions/"
    response = api(nurse).post(url, {**VITALS, "pre_sbp": 1200}, format="json")
    assert response.status_code == 400 and "pre_sbp" in response.json()["error"]["details"]
    assert api(doctor).post(url, VITALS, format="json").status_code == 403


def test_b_t5_posting_a_note_creates_a_pending_draft(api, nurse, session, pending_draft) -> None:
    note = Note.objects.get()
    assert (note.text_ar, note.author, note.session) == (CHILLS_NOTE, nurse, session)
    assert (pending_draft.status, pending_draft.note) == ("pending", note)
    assert not SessionFacts.objects.exists()  # nothing is in the record before approval
    assert set(AuditLog.objects.values_list("action", flat=True)) == {"create_note", "create_extraction_draft"}
    listed = api(nurse).get("/api/v1/extraction-drafts/?status=pending").json()["results"]
    assert [d["id"] for d in listed] == [pending_draft.id] and listed[0]["note_text_ar"] == CHILLS_NOTE
    assert api(nurse).get("/api/v1/extraction-drafts/?status=approved").json()["count"] == 0


def test_b_t5b_empty_note_rejected_in_arabic(api, nurse, session) -> None:
    response = api(nurse).post(f"/api/v1/sessions/{session.id}/notes/", {"text_ar": "  "}, format="json")
    assert response.status_code == 400 and response.json()["error"]["message_ar"]
    assert not Note.objects.exists()


def test_b_t5c_ai_failure_never_blocks_saving_a_note(api, nurse, session, mock_llm) -> None:
    mock_llm("extraction_v1", "not json", note_text="ملاحظة")
    response = api(nurse).post(f"/api/v1/sessions/{session.id}/notes/", {"text_ar": "ملاحظة"}, format="json")
    assert response.status_code == 201 and response.json()["draft_status"] == "invalid"
    assert Note.objects.count() == 1


def test_b_t6_approve_without_edits(api, nurse, session, pending_draft) -> None:
    response = api(nurse).post(f"/api/v1/extraction-drafts/{pending_draft.id}/approve/")
    assert response.status_code == 200, response.content
    pending_draft.refresh_from_db()
    assert (pending_draft.status, pending_draft.reviewed_by) == ("approved", nurse)
    assert pending_draft.reviewed_at is not None
    facts = SessionFacts.objects.get(session=session)
    assert facts.symptoms == [{**CHILLS["symptoms"][0], "note_id": pending_draft.note_id}]
    log = AuditLog.objects.get(action="approve_draft")
    assert (log.actor, log.before["status"], log.after["status"]) == (nurse, "pending", "approved")


def test_a_t15_mentioned_values_never_touch_vitals(api, nurse, session, pending_draft) -> None:
    before = Session.objects.filter(pk=session.pk).values().get()
    assert pending_draft.payload["mentioned_values"] == [{"kind": "bp", "raw_text": "١٢٠/٨٠"}]
    assert api(nurse).post(f"/api/v1/extraction-drafts/{pending_draft.id}/approve/").status_code == 200
    assert Session.objects.filter(pk=session.pk).values().get() == before
    assert "mentioned_values" not in SessionFacts.objects.values().get()


def test_b_t7_edit_with_ungrounded_span_rejected(api, nurse, pending_draft) -> None:
    edited = extraction(symptoms=[symptom("fainting", "أغمي عليها")])
    url = f"/api/v1/extraction-drafts/{pending_draft.id}/approve/"
    response = api(nurse).post(url, {"edited_payload": edited}, format="json")
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "invalid_edit" and error["details"]["validation_errors"][0]["code"] == "evidence_not_found"
    pending_draft.refresh_from_db()
    assert pending_draft.status == "pending" and not SessionFacts.objects.exists()


def test_b_t8_double_approve_conflicts(api, nurse, pending_draft) -> None:
    url = f"/api/v1/extraction-drafts/{pending_draft.id}/approve/"
    assert api(nurse).post(url).status_code == 200
    again = api(nurse).post(url)
    assert again.status_code == 409 and again.json()["error"]["code"] == "invalid_state"
    assert api(nurse).post(f"/api/v1/extraction-drafts/{pending_draft.id}/reject/").status_code == 409
    assert AuditLog.objects.filter(action="approve_draft").count() == 1


def test_b_t9_only_nurses_review_drafts(api, doctor, admin_user, patient_user, pending_draft) -> None:
    for user in (doctor, admin_user, patient_user):
        for action in ("approve", "reject", "retry"):
            assert api(user).post(f"/api/v1/extraction-drafts/{pending_draft.id}/{action}/").status_code == 403
        assert api(user).get("/api/v1/extraction-drafts/").status_code == 403
    pending_draft.refresh_from_db()
    assert pending_draft.status == "pending"


def test_b_t9b_reject_and_retry(api, nurse, pending_draft, mock_llm) -> None:
    url = f"/api/v1/extraction-drafts/{pending_draft.id}"
    rejected = api(nurse).post(f"{url}/reject/", {"reason": "غير دقيق"}, format="json")
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    assert AuditLog.objects.get(action="reject_draft").after["reason"] == "غير دقيق"
    retried = api(nurse).post(f"{url}/retry/")
    assert retried.status_code == 201 and retried.json()["status"] == "pending"
    assert retried.json()["id"] != pending_draft.id and retried.json()["note"] == pending_draft.note_id
    assert not SessionFacts.objects.exists()


def test_r_t14_approval_updates_flags_in_the_same_request(api, nurse, patient, make_session, mock_llm) -> None:
    mock_llm("extraction_v1", CHILLS, note_text=CHILLS_NOTE)
    for day in (1, 3, 5):
        session = make_session(patient, day=day)
        created = api(nurse).post(f"/api/v1/sessions/{session.id}/notes/", {"text_ar": CHILLS_NOTE}, format="json")
        assert not Flag.objects.filter(rule_id="R2_RECURRING_SYMPTOM").exists()  # pending drafts never count
        assert api(nurse).post(f"/api/v1/extraction-drafts/{created.json()['draft_id']}/approve/").status_code == 200
    flag = Flag.objects.get(rule_id="R2_RECURRING_SYMPTOM")
    assert flag.session == session and flag.evidence["count"] == 3
    flags = api(nurse).get(f"/api/v1/patients/{patient.id}/flags/").json()["results"]
    assert [f["rule_id"] for f in flags] == ["R2_RECURRING_SYMPTOM"] and flags[0]["message_ar"]


@pytest.fixture
def history(patient, make_session, make_note) -> list[Session]:
    sessions = [make_session(patient, day=day) for day in range(1, 16)]
    for s in sessions:
        make_note(s)
    SessionFacts.objects.create(session=sessions[-1], symptoms=[{"code": "chills", "note_id": 1}])
    Flag.objects.create(
        patient=patient, session=sessions[-1], rule_id="R1_INTRA_SBP_DROP", severity="attention",
        message_ar="x", evidence={}, rules_version="t",
    )  # fmt: skip
    return sessions


def test_b_t10_timeline(api, doctor, patient, history) -> None:
    response = api(doctor).get(f"/api/v1/patients/{patient.id}/timeline/")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 15 and body["next"] is None  # page size 20
    rows = body["results"]
    assert [r["id"] for r in rows] == [s.id for s in reversed(history)]
    newest, oldest = rows[0], rows[-1]
    assert newest["facts"]["symptoms"][0]["code"] == "chills" and newest["flags"][0]["rule_id"] == "R1_INTRA_SBP_DROP"
    assert newest["notes"][0]["text_ar"] and newest["pre_sbp"] == 140
    assert oldest["facts"] is None and oldest["flags"] == []
    missing = api(doctor).get("/api/v1/patients/999999/timeline/")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"


def test_b_t11_timeline_query_count(api, doctor, patient, history, django_assert_max_num_queries) -> None:
    client = api(doctor)
    with django_assert_max_num_queries(10):
        assert client.get(f"/api/v1/patients/{patient.id}/timeline/").status_code == 200


@pytest.fixture
def patient_summary(api, doctor, patient, session, make_note, nurse) -> Summary:
    note = make_note(session, CHILLS_NOTE)
    ExtractionDraft.objects.create(note=note, status="approved", reviewed_by=nurse)
    item = {**CHILLS["symptoms"][0], "label_ar": "برد ورجفة", "note_id": note.id}
    SessionFacts.objects.create(session=session, symptoms=[item])
    body = {"audience": "patient", "period_start": "2026-08-01", "period_end": "2026-10-31"}
    response = api(doctor).post(f"/api/v1/patients/{patient.id}/summaries/", body, format="json")
    assert response.status_code == 201, response.content
    assert response.json()["status"] == "draft" and response.json()["sentences"][0]["citations"] == [note.id]
    return Summary.objects.get(pk=response.json()["id"])


def test_b_t12_draft_summary_hidden_from_patient(api, patient_user, doctor, nurse, patient_summary) -> None:
    assert api(patient_user).get("/api/v1/me/summaries/").json()["results"] == []
    assert api(patient_user).get(f"/api/v1/summaries/{patient_summary.id}/").status_code == 404
    assert api(nurse).get(f"/api/v1/summaries/{patient_summary.id}/").json()["status"] == "draft"
    for user in (doctor, nurse):
        assert api(user).get("/api/v1/me/summaries/").status_code == 403

    approved = api(doctor).post(f"/api/v1/summaries/{patient_summary.id}/approve/")
    assert approved.status_code == 200 and approved.json()["approved_by"] == doctor.id
    mine = api(patient_user).get("/api/v1/me/summaries/").json()["results"]
    assert [s["id"] for s in mine] == [patient_summary.id]
    assert all(Note.objects.filter(pk=c).exists() for s in mine[0]["sentences"] for c in s["citations"])
    assert api(doctor).post(f"/api/v1/summaries/{patient_summary.id}/approve/").status_code == 409
    assert set(AuditLog.objects.filter(object_type="Summary").values_list("action", flat=True)) == {
        "create_summary",
        "approve_summary",
    }


def test_b_t12b_clinician_audience_never_visible_to_patient(api, patient_user, doctor, patient_summary) -> None:
    Summary.objects.filter(pk=patient_summary.pk).update(audience="clinician", status="approved")
    assert api(patient_user).get("/api/v1/me/summaries/").json()["results"] == []
    assert api(patient_user).get(f"/api/v1/summaries/{patient_summary.id}/").status_code == 404


def test_b_t13_other_patient_gets_404(api, doctor, patient_user, other_patient_user, patient_summary) -> None:
    api(doctor).post(f"/api/v1/summaries/{patient_summary.id}/approve/")
    assert api(patient_user).get(f"/api/v1/summaries/{patient_summary.id}/").status_code == 200
    assert api(other_patient_user).get(f"/api/v1/summaries/{patient_summary.id}/").status_code == 404
    assert api(other_patient_user).get("/api/v1/me/summaries/").json()["results"] == []


def test_b_t14_nurse_cannot_approve_summary(api, nurse, doctor, patient_summary) -> None:
    for action in ("approve", "reject"):
        assert api(nurse).post(f"/api/v1/summaries/{patient_summary.id}/{action}/").status_code == 403
    rejected = api(doctor).post(f"/api/v1/summaries/{patient_summary.id}/reject/", {"reason": "ناقص"}, format="json")
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"
    assert Summary.objects.get().approved_by is None


def test_b_t14b_summary_request_validation(api, nurse, patient, patient_user) -> None:
    url = f"/api/v1/patients/{patient.id}/summaries/"
    body = {"audience": "patient", "period_start": "2026-10-31", "period_end": "2026-08-01"}
    assert api(nurse).post(url, body, format="json").status_code == 400
    assert api(patient_user).post(url, body, format="json").status_code == 403


def test_b_t15_audit_shows_edit_before_and_after(api, nurse, doctor, admin_user, patient_user, pending_draft) -> None:
    edited = extraction(symptoms=[symptom("chills", "ببرد ورجفة بنص الجلسة")])
    url = f"/api/v1/extraction-drafts/{pending_draft.id}/approve/"
    assert api(nurse).post(url, {"edited_payload": edited}, format="json").status_code == 200
    assert SessionFacts.objects.get().symptoms[0]["evidence_span"] == "ببرد ورجفة بنص الجلسة"

    query = f"/api/v1/audit/?object_type=ExtractionDraft&object_id={pending_draft.id}"
    rows = api(doctor).get(query).json()["results"]
    assert [r["action"] for r in rows] == ["edit_and_approve_draft", "create_extraction_draft"]
    row = rows[0]
    assert row["actor"] == nurse.id
    assert row["before"]["status"] == "pending" and row["before"]["edited_payload"] is None
    assert row["after"]["status"] == "approved" and row["after"]["edited_payload"] == edited
    assert row["before"]["payload"] == CHILLS  # the model's original output is preserved
    assert api(admin_user).get(query).status_code == 200
    assert api(nurse).get(query).status_code == 403 and api(patient_user).get(query).status_code == 403


def test_b_t16_demo_guard(settings, patient) -> None:
    settings.DEMO_MODE = True
    check_demo_guard()  # synthetic only: fine
    Patient.objects.filter(pk=patient.pk).update(is_synthetic=False)
    with pytest.raises(ImproperlyConfigured, match="synthetic"):
        apps.get_app_config("clinical").ready()
    settings.DEMO_MODE = False
    apps.get_app_config("clinical").ready()


def test_note_correction_supersedes_and_stays_immutable(api, nurse, session, other_patient, make_session) -> None:
    url = f"/api/v1/sessions/{session.id}/notes/"
    first = api(nurse).post(url, {"text_ar": "صداع بنص الجلسة"}, format="json").json()
    second = api(nurse).post(url, {"text_ar": "تصحيح: الصداع قبل الجلسة", "supersedes": first["id"]}, format="json")
    assert second.status_code == 201 and second.json()["supersedes"] == first["id"]
    assert api(nurse).get(f"/api/v1/notes/{first['id']}/").json()["text_ar"] == "صداع بنص الجلسة"
    for method in ("put", "patch", "delete"):
        assert getattr(api(nurse), method)(f"/api/v1/notes/{first['id']}/", {"text_ar": "x"}).status_code == 405
    elsewhere = make_session(other_patient, day=dt.date(2026, 9, 2).day)
    wrong = api(nurse).post(
        f"/api/v1/sessions/{elsewhere.id}/notes/", {"text_ar": "س", "supersedes": first["id"]}, format="json"
    )
    assert wrong.status_code == 400 and wrong.json()["error"]["code"] == "invalid_supersedes"
