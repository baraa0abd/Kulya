"""AI-role tests A-T1 .. A-T19 (docs/team_prompts.json). A-T15 lives in test_backend.py (needs the approve API)."""

import datetime as dt
import importlib.util
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import summaries.services
from ai_engine.client import (
    AnthropicLLMClient,
    LLMOutputError,
    MockLLMClient,
    get_llm_client,
)
from ai_engine.models import ExtractionDraft
from ai_engine.services import load_prompt, request_extraction
from ai_engine.validators import validate_extraction, validate_summary
from clinical.models import SessionFacts
from summaries.models import Summary
from summaries.services import generate_summary
from tests.conftest import EMPTY_EXTRACTION, extraction, symptom

NOTE = "حسّت ببرد ورجفة بنص الجلسة"
REPO = Path(__file__).resolve().parents[2]


def codes(errors: list[dict]) -> set[str]:
    return {e["code"] for e in errors}


def test_a_t1_extra_field_rejected() -> None:
    ok, errors = validate_extraction({**EMPTY_EXTRACTION, "diagnosis": "x"}, NOTE)
    assert not ok and codes(errors) == {"schema_invalid"}


def test_a_t2_unknown_symptom_code_rejected() -> None:
    ok, errors = validate_extraction(extraction(symptoms=[symptom("stroke", "ببرد ورجفة")]), NOTE)
    assert not ok and codes(errors) == {"schema_invalid"}


def test_a_t2b_overlong_evidence_span_rejected() -> None:
    long_note = "برد " * 100
    ok, errors = validate_extraction(extraction(symptoms=[symptom("chills", long_note.strip())]), long_note)
    assert not ok and codes(errors) == {"schema_invalid"}


def test_a_t3_prompt_examples_are_valid() -> None:
    prompt = load_prompt("extraction_v1")
    assert prompt.startswith("<!-- prompt_id: extraction_v1")
    examples = re.findall(r"<note>\n(.*?)\n</note>\s*```json\n(.*?)\n```", prompt, re.DOTALL)
    assert len(examples) == 4
    for note, output in examples:
        ok, errors = validate_extraction(json.loads(output), note)
        assert ok, errors
    assert all(v == [] for v in json.loads(examples[3][1]).values())  # the "nothing notable" example


def test_a_t4_grounded_span_ok() -> None:
    assert validate_extraction(extraction(symptoms=[symptom("chills", "ببرد ورجفة")]), NOTE) == (True, [])


def test_a_t5_ungrounded_span_fails() -> None:
    ok, errors = validate_extraction(extraction(symptoms=[symptom("fainting", "إغماء")]), NOTE)
    assert not ok and codes(errors) == {"evidence_not_found"}
    assert errors[0]["path"] == "symptoms/0/evidence_span"


def test_a_t6_normalization_on_both_sides() -> None:
    assert validate_extraction(extraction(symptoms=[symptom("chills", "بِبَـــرد ورجفة")]), NOTE)[0]
    note_with_marks = "أُغمِيَ عليها بـــنص الجلسة"
    assert validate_extraction(extraction(symptoms=[symptom("fainting", "اغمي عليها بنص")]), note_with_marks)[0]


def test_a_t6b_all_verbatim_fields_are_checked() -> None:
    payload = extraction(
        mentioned_values=[{"kind": "bp", "raw_text": "١٢٠/٨٠"}],
        uncertain=[{"text": "كلام غير موجود", "reason_ar": "س"}],
    )
    ok, errors = validate_extraction(payload, NOTE)
    assert not ok and {e["path"] for e in errors} == {
        "mentioned_values/0/raw_text",
        "uncertain/0/text",
    }


def test_a_t7_missing_citation() -> None:
    ok, errors = validate_summary({"sentences": [{"text_ar": "وُثقت رجفة.", "citations": []}]}, {11})
    assert not ok and codes(errors) == {"missing_citation"}


def test_a_t8_unknown_citation() -> None:
    ok, errors = validate_summary({"sentences": [{"text_ar": "وُثقت رجفة.", "citations": [11, 999]}]}, {11})
    assert not ok and codes(errors) == {"unknown_citation"}


@pytest.mark.parametrize(
    "text",
    ["نوصي بزيادة الجرعة", "نُوصِي بزيادة الجرعة", "We recommend to Increase Dose"],
)
def test_a_t9_forbidden_advice(text: str) -> None:
    ok, errors = validate_summary({"sentences": [{"text_ar": text, "citations": [11]}]}, {11})
    assert not ok and codes(errors) == {"forbidden_advice"}


def test_a_t10_valid_summary() -> None:
    payload = {
        "sentences": [
            {
                "text_ar": "وُثقت رجفة أثناء الجلسة وأوقف الفريق السحب.",
                "citations": [11, 12],
            }
        ]
    }
    assert validate_summary(payload, {11, 12, 15}) == (True, [])


def test_a_t11_mock_invalid_json_raises(mock_llm) -> None:
    mock_llm("extraction_v1", "this is not json {", note_text=NOTE)
    with pytest.raises(LLMOutputError):
        MockLLMClient().complete_json("extraction_v1", "", f"<note>\n{NOTE}\n</note>", {})
    # other inputs still fall back to default.json
    assert MockLLMClient().complete_json("extraction_v1", "", "<note>\nx\n</note>", {}) == EMPTY_EXTRACTION


def fake_anthropic(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    def create(**kwargs) -> SimpleNamespace:
        fake_anthropic.last_kwargs = kwargs
        return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)])

    return SimpleNamespace(messages=SimpleNamespace(create=create))


def test_a_t12_anthropic_client_strips_fences(settings) -> None:
    settings.LLM_MODEL = "some-model"
    client = AnthropicLLMClient(client=fake_anthropic('```json\n{"sentences": []}\n```'))
    assert client.complete_json("summary_patient_v1", "sys", "user", {}) == {"sentences": []}
    sent = fake_anthropic.last_kwargs
    assert sent["model"] == "some-model" and sent["system"] == "sys"
    assert "temperature" not in sent  # rejected by current models


@pytest.mark.parametrize("text,stop", [("not json", "end_turn"), ("[1, 2]", "end_turn"), ("{}", "refusal")])
def test_a_t12b_anthropic_client_bad_output_raises(text: str, stop: str) -> None:
    with pytest.raises(LLMOutputError):
        AnthropicLLMClient(client=fake_anthropic(text, stop)).complete_json("p", "s", "u", {})


def test_a_t12c_missing_api_key_falls_back_to_mock(settings, caplog) -> None:
    settings.LLM_PROVIDER, settings.ANTHROPIC_API_KEY = "anthropic", ""
    assert isinstance(get_llm_client(), MockLLMClient)
    assert "falling back to MockLLMClient" in caplog.text


def test_a_t13_valid_extraction_is_pending(session, make_note, mock_llm) -> None:
    note = make_note(session, NOTE)
    mock_llm(
        "extraction_v1",
        extraction(symptoms=[symptom("chills", "ببرد ورجفة")]),
        note_text=NOTE,
    )
    draft = request_extraction(note.id)
    assert (draft.status, draft.prompt_version, draft.model_name) == (
        "pending",
        "extraction_v1",
        "mock",
    )
    assert draft.payload["symptoms"][0]["code"] == "chills" and draft.validation_errors == []
    assert not SessionFacts.objects.exists()  # a draft is never the record


def test_a_t14_ungrounded_extraction_is_invalid(session, make_note, mock_llm) -> None:
    note = make_note(session, NOTE)
    mock_llm(
        "extraction_v1",
        extraction(symptoms=[symptom("fainting", "إغماء")]),
        note_text=NOTE,
    )
    draft = request_extraction(note.id)
    assert draft.status == "invalid" and codes(draft.validation_errors) == {"evidence_not_found"}
    assert not SessionFacts.objects.exists()


@pytest.mark.parametrize("bad", ["not json", '{"symptoms": []}'])
def test_a_t14b_model_failures_never_raise(session, make_note, mock_llm, bad: str) -> None:
    note = make_note(session, NOTE)
    mock_llm("extraction_v1", bad, note_text=NOTE)
    assert request_extraction(note.id).status == "invalid"


def test_a_t14c_client_crash_never_raises(session, make_note, monkeypatch) -> None:
    def boom():
        raise RuntimeError("network down")

    monkeypatch.setattr("ai_engine.services.get_llm_client", boom)
    draft = request_extraction(make_note(session, NOTE).id)
    assert draft.status == "invalid" and codes(draft.validation_errors) == {"llm_error"}


class RecordingClient(MockLLMClient):
    def __init__(self, response: dict) -> None:
        super().__init__()
        self.response, self.calls = response, []

    def complete_json(self, prompt_id: str, system: str, user: str, schema: dict) -> dict:
        self.calls.append({"prompt_id": prompt_id, "system": system, "user": user})
        return self.response


@pytest.fixture
def approved_history(patient, make_session, make_note, nurse):
    """Three sessions with approved facts and one session whose draft is still pending."""
    notes = []
    for day in (1, 3, 5, 8):
        session = make_session(patient, day=day)
        note = make_note(session, NOTE)
        approved = day != 8
        ExtractionDraft.objects.create(note=note, status="approved" if approved else "pending", reviewed_by=nurse)
        if approved:
            item = {
                **symptom("chills", "ببرد ورجفة"),
                "label_ar": "برد ورجفة",
                "note_id": note.id,
            }
            SessionFacts.objects.create(session=session, symptoms=[item])
        notes.append(note)
    return notes


PERIOD = (dt.date(2026, 9, 1), dt.date(2026, 9, 30))


def test_a_t16_only_approved_notes_reach_the_model(patient, approved_history, monkeypatch) -> None:
    *approved, pending = approved_history
    client = RecordingClient({"sentences": [{"text_ar": "وُثقت رجفة.", "citations": [approved[0].id]}]})
    monkeypatch.setattr(summaries.services, "get_llm_client", lambda: client)
    assert generate_summary(patient.id, "clinician", *PERIOD).status == "draft"

    sent = json.loads(client.calls[0]["user"].removeprefix("<data>\n").removesuffix("\n</data>"))
    sent_note_ids = {n for s in sent["sessions"] for n in s["note_ids"]}
    assert sent_note_ids == {n.id for n in approved} and pending.id not in sent_note_ids
    assert patient.display_name_ar not in client.calls[0]["user"]  # synthetic code only, no names
    assert NOTE not in client.calls[0]["user"]  # approved facts, not raw note text

    client.response = {"sentences": [{"text_ar": "وُثقت رجفة.", "citations": [pending.id]}]}
    summary = generate_summary(patient.id, "clinician", *PERIOD)
    assert summary.status == "invalid" and codes(summary.validation_errors) == {"unknown_citation"}


def test_a_t17_patient_summary_starts_as_draft(patient, approved_history) -> None:
    summary = generate_summary(patient.id, "patient", *PERIOD)  # offline mock summary
    assert (summary.status, summary.prompt_version, summary.approved_by) == (
        "draft",
        "summary_patient_v1",
        None,
    )
    assert len(summary.sentences) == 3
    allowed = {n.id for n in approved_history[:3]}
    assert all(s["citations"] and set(s["citations"]) <= allowed for s in summary.sentences)


def test_a_t17b_advice_from_model_makes_summary_invalid(patient, approved_history, monkeypatch) -> None:
    client = RecordingClient(
        {
            "sentences": [
                {
                    "text_ar": "ننصح بتقليل السوائل.",
                    "citations": [approved_history[0].id],
                }
            ]
        }
    )
    monkeypatch.setattr(summaries.services, "get_llm_client", lambda: client)
    summary = generate_summary(patient.id, "patient", *PERIOD)
    assert summary.status == "invalid" and codes(summary.validation_errors) == {"forbidden_advice"}
    assert Summary.objects.filter(status="approved").count() == 0


def test_a_t18_patient_prompt_content() -> None:
    prompt = load_prompt("summary_patient_v1")
    assert "Do not give advice" in prompt
    assert "ناقش أي سؤال مع فريقك الطبي" in prompt
    assert "Every sentence must have at least one citation" in load_prompt("summary_clinician_v1")


def load_run_eval():
    spec = importlib.util.spec_from_file_location("run_eval", REPO / "eval" / "run_eval.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_t19_eval_harness_sanity(tmp_path) -> None:
    run_eval = load_run_eval()
    golden = run_eval.load_golden()
    assert len(golden) == 20
    result = run_eval.evaluate(run_eval.perfect_mock_client(golden, tmp_path / "perfect"), golden)
    for metric in result["metrics"].values():
        assert metric["precision"] == 1.0 and metric["recall"] == 1.0
    assert result["evidence_failures"] == 0 and result["invalid"] == 0
    assert "| symptoms | 1.00 | 1.00 |" in run_eval.render_report(result)


def test_a_t19b_eval_detects_a_bad_model(tmp_path) -> None:
    run_eval = load_run_eval()
    golden = run_eval.load_golden()
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "extraction_v1").mkdir()
    (empty / "extraction_v1" / "default.json").write_text(json.dumps(EMPTY_EXTRACTION), encoding="utf-8")
    result = run_eval.evaluate(MockLLMClient(fixtures_dir=empty), golden)
    assert result["metrics"]["symptoms"]["recall"] == 0.0
