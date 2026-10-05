"""Rules/data-role tests R-T1 .. R-T18. R-T14 lives in test_backend.py (it needs the approve API)."""

import datetime as dt
import json
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from pydantic import ValidationError

from ai_engine.forbidden_terms import find_forbidden
from ai_engine.models import ExtractionDraft
from ai_engine.validators import validate_extraction
from clinical.models import Note, Patient, Session, SessionFacts
from rules import engine
from rules.config import CONFIG_PATH, RulesConfig, load_config
from rules.engine import Fact, PendingDraft, SessionSnapshot
from rules.models import Flag
from rules.services import evaluate_patient
from tests.conftest import extraction, symptom

REPO = Path(__file__).resolve().parents[2]
CONFIG = load_config()
NOW = dt.datetime(2026, 10, 5, 12, tzinfo=dt.UTC)


def snap(session_id: int, **kwargs) -> SessionSnapshot:
    """A complete, unremarkable session unless overridden."""
    defaults = dict(
        session_date=dt.date(2026, 9, 1) + dt.timedelta(days=2 * session_id),
        pre_sbp=140, pre_dbp=85, post_sbp=132, post_dbp=80, min_intra_sbp=130,
        pre_weight_kg=64.0, post_weight_kg=62.0, note_ids=(100 + session_id,),
    )  # fmt: skip
    return SessionSnapshot(session_id=session_id, **{**defaults, **kwargs})


def with_symptom(session_id: int, code: str | None) -> SessionSnapshot:
    facts = (Fact(code, 100 + session_id),) if code else ()
    return snap(session_id, has_facts=True, symptoms=facts)


def test_r_t1_negative_threshold_rejected(tmp_path) -> None:
    bad = tmp_path / "config.yaml"
    bad.write_text(CONFIG_PATH.read_text(encoding="utf-8").replace("sbp_drop_threshold: 20", "sbp_drop_threshold: -5"))
    with pytest.raises(ValidationError):
        load_config(bad)
    with pytest.raises(ValidationError):
        RulesConfig(**{**CONFIG.model_dump(), "unknown_key": 1})


def test_r_t1b_config_has_disclaimer_defaults_and_version() -> None:
    assert "not clinical guidance" in CONFIG_PATH.read_text(encoding="utf-8")
    assert "not clinical guidance" in (REPO / "docs" / "clinical_disclaimer.md").read_text(encoding="utf-8")
    assert (CONFIG.sbp_drop_threshold, CONFIG.recurrence_min, CONFIG.recurrence_window) == (20, 3, 5)
    assert (CONFIG.gain_threshold_kg, CONFIG.review_sla_hours) == (3.0, 24)
    assert len(CONFIG.version) == 16


def test_r_t2_intra_sbp_drop() -> None:
    (flag,) = engine.r1_intra_sbp_drop([snap(1, pre_sbp=140, min_intra_sbp=118)], CONFIG)
    assert (flag.rule_id, flag.severity, flag.session_id) == ("R1_INTRA_SBP_DROP", "attention", 1)
    assert (flag.evidence["pre_sbp"], flag.evidence["low_sbp"], flag.evidence["drop_mmhg"]) == (140, 118, 22)
    assert flag.evidence["used_fallback"] is False and flag.evidence["note_ids"] == [101]
    assert "٢٢" in flag.message_ar and "من ١٤٠ إلى ١١٨" in flag.message_ar


def test_r_t3_small_drop_no_flag() -> None:
    assert engine.r1_intra_sbp_drop([snap(1, pre_sbp=140, min_intra_sbp=125)], CONFIG) == []
    # exactly at threshold flags (>=)
    assert len(engine.r1_intra_sbp_drop([snap(1, pre_sbp=140, min_intra_sbp=120)], CONFIG)) == 1


def test_r_t4_post_sbp_fallback() -> None:
    (flag,) = engine.r1_intra_sbp_drop([snap(1, pre_sbp=150, min_intra_sbp=None, post_sbp=128)], CONFIG)
    assert flag.evidence["used_fallback"] is True and flag.evidence["low_source"] == "post_sbp"
    assert flag.evidence["drop_mmhg"] == 22
    # min_intra present and small: post_sbp is NOT used even if it dropped a lot
    assert engine.r1_intra_sbp_drop([snap(1, pre_sbp=150, min_intra_sbp=140, post_sbp=120)], CONFIG) == []
    assert engine.r1_intra_sbp_drop([snap(1, pre_sbp=None), snap(2, min_intra_sbp=None, post_sbp=None)], CONFIG) == []


def test_r_t5_recurring_symptom() -> None:
    history = [with_symptom(i, "chills" if i in (1, 3, 5) else None) for i in range(1, 6)]
    (flag,) = engine.r2_recurring_symptom(history, CONFIG)
    assert (flag.rule_id, flag.severity, flag.session_id) == ("R2_RECURRING_SYMPTOM", "attention", 5)
    assert flag.evidence["session_ids"] == [1, 3, 5] and flag.evidence["note_ids"] == [101, 103, 105]
    assert "رجفة" in flag.message_ar and "٣ من آخر ٥" in flag.message_ar


def test_r_t6_two_of_five_no_flag() -> None:
    history = [with_symptom(i, "chills" if i in (2, 5) else None) for i in range(1, 6)]
    assert engine.r2_recurring_symptom(history, CONFIG) == []


def test_r_t6b_window_is_last_five_sessions_with_facts() -> None:
    # chills in 1, 2, 3 but the window is sessions 3..7 -> only one hit
    history = [with_symptom(i, "chills" if i <= 3 else None) for i in range(1, 8)]
    assert engine.r2_recurring_symptom(history, CONFIG) == []
    # sessions without approved facts do not consume window slots
    history = [with_symptom(1, "chills"), snap(2), with_symptom(3, "chills"), snap(4), with_symptom(5, "chills")]
    assert len(engine.r2_recurring_symptom(history, CONFIG)) == 1
    assert engine.r2_recurring_symptom([with_symptom(i, "other") for i in range(1, 6)], CONFIG) == []


def test_r_t8_missing_field() -> None:
    (flag,) = engine.r3_missing_required([snap(1), snap(2, post_weight_kg=None)], CONFIG, NOW)
    assert (flag.rule_id, flag.severity, flag.session_id) == ("R3_MISSING_REQUIRED", "info", 2)
    assert flag.evidence["missing_fields"] == ["post_weight_kg"] and "الوزن بعد الجلسة" in flag.message_ar


def test_r_t8b_missing_note_after_deadline() -> None:
    ended = NOW - dt.timedelta(hours=30)
    (flag,) = engine.r3_missing_required([snap(1, note_ids=(), ended_at=ended)], CONFIG, NOW)
    assert flag.evidence == {"session_ids": [1], "note_ids": [], "missing_fields": [], "missing_note": True}
    recent = snap(1, note_ids=(), ended_at=NOW - dt.timedelta(hours=2))
    assert engine.r3_missing_required([recent], CONFIG, NOW) == []


def test_r_t9_interdialytic_gain() -> None:
    history = [snap(1, post_weight_kg=62.0), snap(2, pre_weight_kg=65.4)]
    (flag,) = engine.r4_interdialytic_gain(history, CONFIG)
    assert (flag.rule_id, flag.session_id, flag.evidence["gain_kg"]) == ("R4_INTERDIALYTIC_GAIN", 2, 3.4)
    assert flag.evidence["session_ids"] == [1, 2] and "٣٫٤" in flag.message_ar
    assert engine.r4_interdialytic_gain([snap(1, post_weight_kg=62.0), snap(2, pre_weight_kg=64.9)], CONFIG) == []


def test_r_t10_first_session_and_missing_weights() -> None:
    assert engine.r4_interdialytic_gain([snap(1, pre_weight_kg=90.0)], CONFIG) == []
    assert engine.r4_interdialytic_gain([], CONFIG) == []
    assert engine.r4_interdialytic_gain([snap(1, post_weight_kg=None), snap(2, pre_weight_kg=90.0)], CONFIG) == []


def test_r_t11_recurring_access_issue() -> None:
    def access(session_id: int, *found: str) -> SessionSnapshot:
        return snap(session_id, has_facts=True, access_findings=tuple(Fact(c, 100 + session_id) for c in found))

    (flag,) = engine.r5_recurring_access_issue([access(1, "bleeding"), access(2), access(3, "bleeding")], CONFIG)
    assert (flag.rule_id, flag.severity, flag.session_id) == ("R5_RECURRING_ACCESS_ISSUE", "attention", 3)
    assert flag.evidence["session_ids"] == [1, 3] and "نزف" in flag.message_ar
    assert engine.r5_recurring_access_issue([access(1, "bleeding"), access(2), access(3), access(4)], CONFIG) == []


def test_r_t11b_pending_review_sla() -> None:
    old = PendingDraft(7, 101, NOW - dt.timedelta(hours=25))
    fresh = PendingDraft(8, 101, NOW - dt.timedelta(hours=3))
    (flag,) = engine.r6_pending_review([snap(1, pending_drafts=(old, fresh))], CONFIG, NOW)
    assert (flag.rule_id, flag.severity, flag.evidence["draft_id"]) == ("R6_PENDING_REVIEW", "info", 7)


def test_r_t12_no_advice_in_any_flag_message() -> None:
    history = [
        snap(1, has_facts=True, symptoms=(Fact("chills", 101),), access_findings=(Fact("bleeding", 101),)),
        snap(2, has_facts=True, symptoms=(Fact("chills", 102),), pre_sbp=150, min_intra_sbp=None, post_sbp=120),
        snap(3, has_facts=True, symptoms=(Fact("chills", 103),), access_findings=(Fact("bleeding", 103),),
             pre_weight_kg=70.0, post_weight_kg=None, min_intra_sbp=100, note_ids=(),
             ended_at=NOW - dt.timedelta(days=3), pending_drafts=(PendingDraft(1, 103, NOW - dt.timedelta(days=2)),)),
    ]  # fmt: skip
    flags = engine.run_all(history, CONFIG, NOW)
    assert {f.rule_id for f in flags} == {
        "R1_INTRA_SBP_DROP", "R2_RECURRING_SYMPTOM", "R3_MISSING_REQUIRED",
        "R4_INTERDIALYTIC_GAIN", "R5_RECURRING_ACCESS_ISSUE", "R6_PENDING_REVIEW",
    }  # fmt: skip
    for flag in flags:
        assert find_forbidden(flag.message_ar) == [], flag.message_ar
        assert flag.evidence["session_ids"], flag.rule_id  # every flag is machine-explainable


def flag_set(patient: Patient) -> list[tuple]:
    return sorted(
        (f.rule_id, f.session_id, f.message_ar, json.dumps(f.evidence, sort_keys=True), f.rules_version)
        for f in Flag.objects.filter(patient=patient)
    )


def test_r_t13_evaluate_is_idempotent(patient, make_session, make_note) -> None:
    make_note(make_session(patient, day=1, pre_sbp=150, min_intra_sbp=110))
    make_note(make_session(patient, day=3, post_weight_kg=None))
    evaluate_patient(patient.id)
    first = flag_set(patient)
    evaluate_patient(patient.id)
    assert flag_set(patient) == first and len(first) == 2
    assert {f[0] for f in first} == {"R1_INTRA_SBP_DROP", "R3_MISSING_REQUIRED"}
    assert all(f[4] == CONFIG.version for f in first)


def test_r_t7_pending_draft_not_counted(patient, make_session, make_note, nurse) -> None:
    text = "حسّت ببرد ورجفة بنص الجلسة"
    payload = extraction(symptoms=[symptom("chills", "ببرد ورجفة")])
    for day, status in ((1, "approved"), (3, "approved"), (5, "pending")):
        note = make_note(make_session(patient, day=day), text)
        ExtractionDraft.objects.create(note=note, payload=payload, status=status)
        if status == "approved":
            SessionFacts.objects.create(session=note.session, symptoms=[{**payload["symptoms"][0], "note_id": note.id}])
    evaluate_patient(patient.id)
    assert not Flag.objects.filter(rule_id="R2_RECURRING_SYMPTOM").exists()
    # once the third is approved too, the pattern appears
    last = Note.objects.order_by("id").last()
    SessionFacts.objects.create(session=last.session, symptoms=[{**payload["symptoms"][0], "note_id": last.id}])
    evaluate_patient(patient.id)
    assert Flag.objects.filter(rule_id="R2_RECURRING_SYMPTOM").count() == 1


@pytest.fixture
def seeded(db, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_PASSWORD", "demo-pass-12345")
    call_command("seed_demo", "--approve-facts", verbosity=0)


def test_r_t15_seed_counts(seeded) -> None:
    assert Patient.objects.count() == 3 and not Patient.objects.filter(is_synthetic=False).exists()
    assert Session.objects.count() == 45
    assert Note.objects.count() >= 45
    assert Note.objects.filter(supersedes__isnull=False).count() == 1
    assert not ExtractionDraft.objects.filter(status="pending").exists()
    assert SessionFacts.objects.count() == 45


def test_r_t15b_seed_users(seeded, django_user_model) -> None:
    roles = dict(django_user_model.objects.values_list("username", "role"))
    assert roles == {"nurse1": "nurse", "doctor1": "doctor", "admin1": "admin", "patient_syn001": "patient"}
    patient_user = django_user_model.objects.get(username="patient_syn001")
    assert patient_user.patient.code == "SYN-001" and patient_user.check_password("demo-pass-12345")


def test_r_t15c_seed_needs_password(db, monkeypatch) -> None:
    monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    with pytest.raises(CommandError):
        call_command("seed_demo", verbosity=0)


def test_r_t16_storylines_produce_expected_flags(seeded) -> None:
    def rules_for(code: str) -> set[str]:
        return set(Flag.objects.filter(patient__code=code).values_list("rule_id", flat=True))

    assert rules_for("SYN-001") == {"R1_INTRA_SBP_DROP", "R2_RECURRING_SYMPTOM"}
    assert rules_for("SYN-002") == {"R4_INTERDIALYTIC_GAIN", "R5_RECURRING_ACCESS_ISSUE"}
    assert rules_for("SYN-003") == {"R3_MISSING_REQUIRED"}
    assert Flag.objects.filter(patient__code="SYN-001", rule_id="R1_INTRA_SBP_DROP").count() == 4
    assert Flag.objects.filter(patient__code="SYN-003").count() == 2
    recurring = Flag.objects.get(rule_id="R2_RECURRING_SYMPTOM")
    assert recurring.evidence["code"] == "chills" and recurring.evidence["count"] == 3
    assert Flag.objects.get(rule_id="R5_RECURRING_ACCESS_ISSUE").evidence["code"] == "bleeding"
    assert Flag.objects.get(rule_id="R4_INTERDIALYTIC_GAIN").evidence["gain_kg"] == 3.6


def test_r_t17_seed_is_idempotent(seeded) -> None:
    def counts() -> tuple:
        models = (Patient, Session, Note, ExtractionDraft, SessionFacts, Flag)
        return tuple(m.objects.count() for m in models)

    before = counts()
    call_command("seed_demo", "--approve-facts", verbosity=0)
    assert counts() == before


def test_r_t17b_seed_data_is_grounded_and_synthetic() -> None:
    data = json.loads((REPO / "backend" / "seed" / "data" / "demo.json").read_text(encoding="utf-8"))
    assert data["synthetic"] is True and [p["code"] for p in data["patients"]] == ["SYN-001", "SYN-002", "SYN-003"]
    for patient in data["patients"]:
        assert len(patient["sessions"]) == 15
        for session in patient["sessions"]:
            for note in session["notes"]:
                assert validate_extraction(note["expected"], note["text_ar"]) == (True, [])


def test_r_t18_golden_expected_outputs_are_valid() -> None:
    golden = json.loads((REPO / "eval" / "golden" / "golden.json").read_text(encoding="utf-8"))
    assert len(golden) == 20
    for case in golden:
        assert validate_extraction(case["expected"], case["note"]) == (True, []), case["id"]
    tags = {t for case in golden for t in case["tags"]}
    assert {"negation", "past_event", "spelling_variant", "arabic_indic_digits"} <= tags
