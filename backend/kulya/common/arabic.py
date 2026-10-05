"""Shared Arabic text normalization. Every Arabic string compared in code goes through normalize_ar()."""

import re
import unicodedata

_TATWEEL_AND_DIACRITICS = re.compile("[ـً-ْ]")
_ALEF_FORMS = str.maketrans("أإآ", "ااا")
_FINAL_ALEF_MAQSURA = re.compile(r"ى(?!\w)")
_WHITESPACE = re.compile(r"\s+")


def normalize_ar(text: str) -> str:
    """NFC, drop tatweel and diacritics, unify alef forms and word-final ى -> ي, collapse whitespace."""
    text = unicodedata.normalize("NFC", text)
    text = _TATWEEL_AND_DIACRITICS.sub("", text)
    text = text.translate(_ALEF_FORMS)
    text = _FINAL_ALEF_MAQSURA.sub("ي", text)
    return _WHITESPACE.sub(" ", text).strip()
