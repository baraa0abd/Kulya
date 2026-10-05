"""Mechanical checks on AI output. Deterministic, offline, and the only gate between a model and a draft."""

import json
from collections.abc import Iterable
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from kulya.common.arabic import normalize_ar

from .forbidden_terms import find_forbidden

SCHEMAS_DIR = Path(__file__).parent / "schemas"

# (list name, field holding text that must appear verbatim in the note)
EVIDENCE_FIELDS = [
    ("symptoms", "evidence_span"),
    ("access_findings", "evidence_span"),
    ("staff_actions", "evidence_span"),
    ("mentioned_values", "raw_text"),
    ("uncertain", "text"),
]

Errors = list[dict[str, str]]


@cache
def load_schema(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _schema_errors(payload: Any, schema_name: str) -> Errors:
    validator = Draft202012Validator(load_schema(schema_name))
    return [
        {
            "code": "schema_invalid",
            "path": "/".join(map(str, e.absolute_path)),
            "message": e.message,
        }
        for e in sorted(
            validator.iter_errors(payload),
            key=lambda e: list(map(str, e.absolute_path)),
        )
    ]


def validate_extraction(payload: Any, note_text: str) -> tuple[bool, Errors]:
    """Schema check, then: every evidence span is a verbatim substring of the note (after normalize_ar)."""
    errors = _schema_errors(payload, "extraction_v1")
    if errors:
        return False, errors
    note = normalize_ar(note_text)
    for list_name, field in EVIDENCE_FIELDS:
        for i, item in enumerate(payload[list_name]):
            span = normalize_ar(item[field])
            if not span or span not in note:
                errors.append(
                    {
                        "code": "evidence_not_found",
                        "path": f"{list_name}/{i}/{field}",
                        "message": f"Text not found verbatim in the note: {item[field]!r}",
                    }
                )
    return not errors, errors


def validate_summary(payload: Any, allowed_note_ids: Iterable[int]) -> tuple[bool, Errors]:
    """Schema check, then per sentence: >=1 citation, citations within the input notes, no advice wording."""
    errors = _schema_errors(payload, "summary_v1")
    if errors:
        return False, errors
    allowed = set(allowed_note_ids)
    for i, sentence in enumerate(payload["sentences"]):
        path = f"sentences/{i}"
        if not sentence["citations"]:
            errors.append(
                {
                    "code": "missing_citation",
                    "path": path,
                    "message": "Sentence has no citation.",
                }
            )
        unknown = sorted(set(sentence["citations"]) - allowed)
        if unknown:
            errors.append(
                {
                    "code": "unknown_citation",
                    "path": path,
                    "message": f"Cites notes not in the input: {unknown}",
                }
            )
        terms = find_forbidden(sentence["text_ar"])
        if terms:
            errors.append(
                {
                    "code": "forbidden_advice",
                    "path": path,
                    "message": f"Contains advice wording: {terms}",
                }
            )
    return not errors, errors
