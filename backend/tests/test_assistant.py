"""Laboratory-based meal ideas (doctor approval) and the patient's record assistant (isolation, grounding)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from assistant.chat import mock_answer, record_facts, validate_answer
from assistant.models import ChatMessage
from clinical.models import CareAssignment, LaboratoryReport, LaboratoryResult
from core.models import Role
from nutrition import catalog, engine
from nutrition.models import Recipe
from workflow.models import Notification

CHAT = "/api/assistant/chat/"
IDEAS = "/api/nutrition/ai/suggestions/"


@pytest.fixture
def recipes(db) -> None:
    catalog.load_catalog()


def add_report(patient, doctor, released: bool, phosphate: str = "5.3") -> LaboratoryReport:
    at = timezone.now() - timedelta(days=1)
    report = LaboratoryReport.objects.create(
        patient=patient, collected_at=at, reported_at=at, source="t", entered_by=doctor, released_to_patient=released
    )
    for analyte, value, unit, low, high in (
        ("Phosphate", phosphate, "mg/dL", "3.5", "5.5"),
        ("Potassium", "4.0", "mmol/L", "3.5", "5.5"),
        ("Urea", "21.0", "mmol/L", "2.5", "7.8"),
    ):
        LaboratoryResult.objects.create(
            report=report, analyte=analyte, value=value, unit=unit, reference_low=low, reference_high=high
        )
    return report


def test_lab_watch_uses_only_the_laboratory_range() -> None:
    lab = {"analyte": "Phosphate", "value": 5.3, "unit": "mg/dL", "reference_low": 3.5, "reference_high": 5.5}
    assert [w["position"] for w in engine.lab_watch([lab])] == ["in the upper part of"]
    assert [w["position"] for w in engine.lab_watch([{**lab, "value": 6.0}])] == ["above"]
    assert engine.lab_watch([{**lab, "value": 4.0}]) == []  # mid-range: nothing to order by
    assert engine.lab_watch([{**lab, "reference_high": None}]) == []  # no range reported: no judgement
    assert engine.lab_watch([{**lab, "analyte": "Hemoglobin", "value": 99}]) == []  # not a food nutrient


def test_lab_based_ideas_reach_the_patient_only_after_a_doctor_approves(
    api, patient, doctor, make_user, recipes
) -> None:
    dietitian = make_user("diet", Role.DIETITIAN, patient.organization)
    CareAssignment.objects.create(patient=patient, professional=dietitian)
    add_report(patient, doctor, released=False)
    assert api(patient.user).post(IDEAS, {}, "json").json() == []  # drafted, but nothing unreviewed is shown
    recs = api(doctor).get(f"{IDEAS}?patient={patient.id}").json()
    assert len(recs) == Recipe.objects.count()
    assert all(r["lab_based"] and r["personalized"] and r["review_status"] == "pending" for r in recs)
    assert (
        "Latest Phosphate result 5.3 mg/dL is in the upper part of the laboratory reference range"
        in (recs[0]["reasoning_summary"])
    )
    assert "Potassium" not in recs[0]["reasoning_summary"]  # mid-range result is not a basis
    phosphorus = [r["nutrient_estimates"]["phosphorus_mg"] for r in recs]
    known = [v for v in phosphorus if v is not None]
    assert known == sorted(known) and phosphorus[: len(known)] == known  # lowest first, unknown last
    assert Notification.objects.filter(recipient=doctor, kind="meal_ideas").count() == 1
    url = f"/api/nutrition/recommendations/{recs[0]['id']}/review/"
    assert api(dietitian).post(url, {"approve": True}, "json").status_code == 403  # quotes a lab value
    assert api(doctor).post(url, {"approve": True}, "json").json()["review_status"] == "approved"
    assert [r["id"] for r in api(patient.user).get(IDEAS).json()] == [recs[0]["id"]]
    assert Notification.objects.filter(recipient=patient.user, kind="meal_ideas").count() == 1
    assert api(patient.user).post(IDEAS, {}, "json").json()[0]["id"] == recs[0]["id"]  # idempotent per report
    assert patient.meal_recommendations.count() == len(recs)


def test_assistant_reads_back_only_released_results(api, patient, doctor) -> None:
    add_report(patient, doctor, released=True)
    add_report(patient, doctor, released=False, phosphate="9.9")
    asked = api(patient.user).post(CHAT, {"question": "What is the urea in the last blood test?", "language": "en"})
    assert asked.status_code == 201, asked.content
    assert "Urea: 21.0 mmol/L" in asked.json()["answer"] and "2.5 to 7.8" in asked.json()["answer"]
    phosphate = api(patient.user).post(CHAT, {"question": "phosphate?", "language": "en"}).json()["answer"]
    assert "5.3" in phosphate and "9.9" not in phosphate  # the unreleased report stays out
    missing = api(patient.user).post(CHAT, {"question": "creatinine?", "language": "en"}).json()["answer"]
    assert "can't find a released creatinine result" in missing
    arabic = api(patient.user).post(CHAT, {"question": "كم اليوريا في آخر تحليل؟", "language": "ar"}).json()["answer"]
    assert "اليوريا: 21.0 mmol/L" in arabic
    tea = api(patient.user).post(CHAT, {"question": "Is it OK to drink tea today?", "language": "en"}).json()["answer"]
    assert "can't decide" in tea and "care team" in tea and "count toward your fluid" in tea


def test_each_patient_has_a_separate_conversation(api, patient, other_patient, doctor, nurse) -> None:
    add_report(patient, doctor, released=True)
    api(patient.user).post(CHAT, {"question": "urea?", "language": "en"})
    assert len(api(patient.user).get(CHAT).json()) == 1
    assert api(other_patient.user).get(CHAT).json() == []
    other = api(other_patient.user).post(CHAT, {"question": "urea?", "language": "en"}).json()["answer"]
    assert "21.0" not in other and "can't find" in other  # answered from their own record only
    assert ChatMessage.objects.filter(patient=other_patient).count() == 1
    for staff in (doctor, nurse):  # the assistant is the patient's own; staff use the clinical screens
        assert api(staff).get(CHAT).status_code == 403
        assert api(staff).post(CHAT, {"question": "urea?"}).status_code == 403
    assert api().get(CHAT).status_code == 401
    assert api(patient.user).post(CHAT, {"question": ""}).status_code == 400


def test_rule_based_answers_pass_their_own_checks_and_unsafe_model_text_is_replaced(
    api, patient, doctor, monkeypatch
) -> None:
    add_report(patient, doctor, released=True)
    record = record_facts(patient)
    for language in ("en", "ar"):
        for question in ("urea", "summarize everything", "can I drink tea", "next session", "blood test", "meals"):
            payload = {"question": question, "language": language, "record": record}
            assert validate_answer({"answer": mock_answer(payload)}, payload) == [], (language, question)
    payload = {"question": "urea", "language": "en", "record": record}
    assert validate_answer({"answer": "Your urea is 55 mmol/L."}, payload)[0]["code"] == "ungrounded_number"
    assert validate_answer({"answer": "It is safe to drink tea."}, payload)[0]["code"] == "unsupported_clinical_claim"
    monkeypatch.setattr("assistant.chat.call_model", lambda *a: ({"answer": "You should drink 3 cups."}, [], "x"))
    reply = api(patient.user).post(CHAT, {"question": "can I drink tea", "language": "en"}).json()["answer"]
    assert "You should" not in reply and "can't decide" in reply
