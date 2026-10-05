"""Advice / diagnosis wording that must never appear in a summary sentence or a rule flag message.

Matched as substrings after normalize_ar() + lowercase on both sides. This is a blunt net, not a
classifier: a doctor still reviews every summary. Extend the lists when a new phrasing slips through.
"""

from kulya.common.arabic import normalize_ar

FORBIDDEN_AR = [
    "يجب أن يتناول",
    "يجب أن تتناول",
    "يجب عليك",
    "يجب على المريض",
    "نوصي",
    "ننصح",
    "ينصح",
    "يُفضل أن",
    "من الأفضل أن",
    "عليك أن",
    "ينبغي",
    "زيادة الجرعة",
    "تقليل الجرعة",
    "تغيير الجرعة",
    "تعديل الجرعة",
    "تغيير الدواء",
    "إيقاف الدواء",
    "وصف دواء",
    "التشخيص",
    "تشخيص",
    "يحتاج إلى علاج",
    "تحتاج إلى علاج",
]

FORBIDDEN_EN = [
    "diagnosis",
    "diagnose",
    "increase dose",
    "decrease dose",
    "reduce dose",
    "change dose",
    "adjust dose",
    "we recommend",
    "recommended",
    "you should",
    "should take",
    "must take",
    "prescribe",
    "start taking",
    "stop taking",
]


def _norm(text: str) -> str:
    return normalize_ar(text).lower()


_TERMS = [_norm(t) for t in FORBIDDEN_AR + FORBIDDEN_EN]


def find_forbidden(text: str) -> list[str]:
    """Return the forbidden terms found in `text` (empty list when clean)."""
    haystack = _norm(text)
    return [term for term in _TERMS if term in haystack]
