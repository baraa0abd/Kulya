"""Deterministic rules R1-R6 as pure functions over plain dataclasses. No ORM, no LLM, no clock:
`now` is passed in. Messages are factual Arabic with no advice; evidence carries the exact values and
ids that triggered each flag.
"""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field

from .config import RulesConfig

ATTENTION, INFO = "attention", "info"

REQUIRED_FIELDS_AR = {
    "pre_sbp": "الضغط الانقباضي قبل الجلسة",
    "pre_dbp": "الضغط الانبساطي قبل الجلسة",
    "post_sbp": "الضغط الانقباضي بعد الجلسة",
    "post_dbp": "الضغط الانبساطي بعد الجلسة",
    "pre_weight_kg": "الوزن قبل الجلسة",
    "post_weight_kg": "الوزن بعد الجلسة",
}
SYMPTOMS_AR = {
    "chills": "رجفة/برد",
    "dizziness": "دوخة",
    "fainting": "إغماء",
    "cramps": "شد عضلي",
    "nausea": "غثيان",
    "vomiting": "تقيؤ",
    "headache": "صداع",
    "chest_pain": "ألم في الصدر",
    "shortness_of_breath": "ضيق نفس",
    "itching": "حكة",
    "fatigue": "تعب",
}
ACCESS_AR = {
    "bleeding": "نزف",
    "swelling": "تورم",
    "pain": "ألم",
    "poor_flow": "ضعف الجريان",
    "redness": "احمرار",
    "clotting": "تخثر",
}
_AR_DIGITS = str.maketrans("0123456789.", "٠١٢٣٤٥٦٧٨٩٫")


def ar(number: float | int) -> str:
    """Format a number with Arabic-Indic digits (display only; evidence keeps the raw value)."""
    return str(number).translate(_AR_DIGITS)


@dataclass(frozen=True)
class Fact:
    code: str
    note_id: int | None = None


@dataclass(frozen=True)
class PendingDraft:
    draft_id: int
    note_id: int
    created_at: dt.datetime


@dataclass(frozen=True)
class SessionSnapshot:
    """One session as the rules see it. `symptoms`/`access_findings` come ONLY from approved SessionFacts."""

    session_id: int
    session_date: dt.date
    ended_at: dt.datetime | None = None
    pre_sbp: int | None = None
    pre_dbp: int | None = None
    post_sbp: int | None = None
    post_dbp: int | None = None
    min_intra_sbp: int | None = None
    pre_weight_kg: float | None = None
    post_weight_kg: float | None = None
    has_facts: bool = False
    symptoms: tuple[Fact, ...] = ()
    access_findings: tuple[Fact, ...] = ()
    note_ids: tuple[int, ...] = ()
    pending_drafts: tuple[PendingDraft, ...] = ()


@dataclass(frozen=True)
class FlagResult:
    rule_id: str
    severity: str
    session_id: int
    message_ar: str
    evidence: dict = field(default_factory=dict)


Snapshots = Sequence[SessionSnapshot]  # ordered oldest -> newest


def r1_intra_sbp_drop(snapshots: Snapshots, config: RulesConfig) -> list[FlagResult]:
    flags = []
    for s in snapshots:
        fallback = s.min_intra_sbp is None
        low = s.post_sbp if fallback else s.min_intra_sbp
        if s.pre_sbp is None or low is None:
            continue
        drop = s.pre_sbp - low
        if drop < config.sbp_drop_threshold:
            continue
        if fallback:
            message = (
                f"انخفاض ضغط الدم الانقباضي بين بداية الجلسة ونهايتها بمقدار {ar(drop)} ملم زئبق "
                f"(من {ar(s.pre_sbp)} إلى {ar(low)})؛ لم يُسجَّل أدنى ضغط أثناء الجلسة"
            )
        else:
            message = (
                f"انخفاض ضغط الدم الانقباضي أثناء الجلسة بمقدار {ar(drop)} ملم زئبق "
                f"(من {ar(s.pre_sbp)} إلى {ar(low)})"
            )
        evidence = {
            "session_ids": [s.session_id],
            "note_ids": list(s.note_ids),
            "pre_sbp": s.pre_sbp,
            "low_sbp": low,
            "low_source": "post_sbp" if fallback else "min_intra_sbp",
            "used_fallback": fallback,
            "drop_mmhg": drop,
            "threshold_mmhg": config.sbp_drop_threshold,
        }
        flags.append(FlagResult("R1_INTRA_SBP_DROP", ATTENTION, s.session_id, message, evidence))
    return flags


def _recurring(
    snapshots: Snapshots, attr: str, rule_id: str, minimum: int, window: int, labels: dict[str, str], noun: str
) -> list[FlagResult]:
    """Same code in >= minimum of the last `window` sessions that have approved facts. One flag per
    code, attached to the latest of those sessions. Code 'other' is skipped: it groups unrelated things."""
    recent = [s for s in snapshots if s.has_facts][-window:]
    if not recent:
        return []
    hits: dict[str, list[tuple[SessionSnapshot, list[int]]]] = {}
    for s in recent:
        by_code: dict[str, list[int]] = {}
        for fact in getattr(s, attr):
            by_code.setdefault(fact.code, [])
            if fact.note_id is not None and fact.note_id not in by_code[fact.code]:
                by_code[fact.code].append(fact.note_id)
        for code, note_ids in by_code.items():
            hits.setdefault(code, []).append((s, note_ids))
    flags = []
    for code in sorted(hits):
        sessions = hits[code]
        if code == "other" or len(sessions) < minimum:
            continue
        message = (
            f"تكرر {noun} «{labels.get(code, code)}» في {ar(len(sessions))} من آخر {ar(len(recent))} جلسات موثَّقة"
        )
        evidence = {
            "code": code,
            "session_ids": [s.session_id for s, _ in sessions],
            "note_ids": [n for _, note_ids in sessions for n in note_ids],
            "count": len(sessions),
            "window_sessions": len(recent),
            "minimum": minimum,
            "window": window,
        }
        flags.append(FlagResult(rule_id, ATTENTION, recent[-1].session_id, message, evidence))
    return flags


def r2_recurring_symptom(snapshots: Snapshots, config: RulesConfig) -> list[FlagResult]:
    return _recurring(
        snapshots,
        "symptoms",
        "R2_RECURRING_SYMPTOM",
        config.recurrence_min,
        config.recurrence_window,
        SYMPTOMS_AR,
        "العرَض",
    )


def r3_missing_required(snapshots: Snapshots, config: RulesConfig, now: dt.datetime) -> list[FlagResult]:
    flags = []
    for s in snapshots:
        missing = [f for f in REQUIRED_FIELDS_AR if getattr(s, f) is None]
        deadline = dt.timedelta(hours=config.note_deadline_hours)
        missing_note = not s.note_ids and s.ended_at is not None and now - s.ended_at > deadline
        if not missing and not missing_note:
            continue
        parts = []
        if missing:
            parts.append("بيانات غير مسجَّلة: " + "، ".join(REQUIRED_FIELDS_AR[f] for f in missing))
        if missing_note:
            parts.append(f"لا توجد ملاحظة تمريضية بعد مرور {ar(config.note_deadline_hours)} ساعة على انتهاء الجلسة")
        evidence = {
            "session_ids": [s.session_id],
            "note_ids": list(s.note_ids),
            "missing_fields": missing,
            "missing_note": missing_note,
        }
        flags.append(FlagResult("R3_MISSING_REQUIRED", INFO, s.session_id, "؛ ".join(parts), evidence))
    return flags


def r4_interdialytic_gain(snapshots: Snapshots, config: RulesConfig) -> list[FlagResult]:
    flags = []
    for previous, current in zip(snapshots, snapshots[1:], strict=False):
        if previous.post_weight_kg is None or current.pre_weight_kg is None:
            continue
        gain = round(current.pre_weight_kg - previous.post_weight_kg, 1)
        if gain < config.gain_threshold_kg:
            continue
        message = (
            f"زيادة الوزن بين الجلستين {ar(gain)} كغم "
            f"(من {ar(previous.post_weight_kg)} بعد الجلسة السابقة إلى {ar(current.pre_weight_kg)} قبل هذه الجلسة)"
        )
        evidence = {
            "session_ids": [previous.session_id, current.session_id],
            "note_ids": list(current.note_ids),
            "previous_post_weight_kg": previous.post_weight_kg,
            "current_pre_weight_kg": current.pre_weight_kg,
            "gain_kg": gain,
            "threshold_kg": config.gain_threshold_kg,
        }
        flags.append(FlagResult("R4_INTERDIALYTIC_GAIN", ATTENTION, current.session_id, message, evidence))
    return flags


def r5_recurring_access_issue(snapshots: Snapshots, config: RulesConfig) -> list[FlagResult]:
    return _recurring(
        snapshots,
        "access_findings",
        "R5_RECURRING_ACCESS_ISSUE",
        config.access_recurrence_min,
        config.access_recurrence_window,
        ACCESS_AR,
        "ملاحظة المدخل الوعائي",
    )


def r6_pending_review(snapshots: Snapshots, config: RulesConfig, now: dt.datetime) -> list[FlagResult]:
    flags = []
    for s in snapshots:
        for draft in s.pending_drafts:
            if now - draft.created_at <= dt.timedelta(hours=config.review_sla_hours):
                continue
            message = f"مسودة استخلاص بانتظار مراجعة التمريض منذ أكثر من {ar(config.review_sla_hours)} ساعة"
            evidence = {
                "session_ids": [s.session_id],
                "note_ids": [draft.note_id],
                "draft_id": draft.draft_id,
                "pending_since": draft.created_at.isoformat(),
                "sla_hours": config.review_sla_hours,
            }
            flags.append(FlagResult("R6_PENDING_REVIEW", INFO, s.session_id, message, evidence))
    return flags


def run_all(snapshots: Snapshots, config: RulesConfig, now: dt.datetime) -> list[FlagResult]:
    return [
        *r1_intra_sbp_drop(snapshots, config),
        *r2_recurring_symptom(snapshots, config),
        *r3_missing_required(snapshots, config, now),
        *r4_interdialytic_gain(snapshots, config),
        *r5_recurring_access_issue(snapshots, config),
        *r6_pending_review(snapshots, config, now),
    ]
