"""Strict validation of model output. A response that fails any check here is rejected: it is
never stored as a successful AI result."""

import json
import re
from typing import Any

from jsonschema import Draft202012Validator

_STR = {"type": "string", "minLength": 1, "maxLength": 2000}
_IDS = {"type": "array", "items": {"type": "string"}, "maxItems": 100}
_LIST = {"type": "array", "items": _STR, "maxItems": 60}

REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "session_id", "summary", "documentation_gaps", "protocol_discrepancies",
        "questions_for_doctor", "requires_human_review", "status",
    ],
    "properties": {
        "session_id": _STR,
        "summary": _STR,
        "documentation_gaps": {
            "type": "array",
            "maxItems": 60,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["finding_id", "description", "source_record_ids", "protocol_reference_ids"],
                "properties": {
                    "finding_id": _STR,
                    "description": _STR,
                    "source_record_ids": {**_IDS, "minItems": 1},
                    "protocol_reference_ids": _IDS,
                },
            },
        },
        "protocol_discrepancies": {
            "type": "array",
            "maxItems": 30,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["description", "evidence", "requires_clinician_assessment"],
                "properties": {
                    "description": _STR,
                    "evidence": {**_IDS, "minItems": 1},
                    "requires_clinician_assessment": {"const": True},
                },
            },
        },
        "questions_for_doctor": _LIST,
        "requires_human_review": {"const": True},
        "status": {"const": "pending_review"},
    },
}  # fmt: skip

SUMMARY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "session_id", "clinical_summary", "patient_summary", "treatment_duration_minutes", "documented_events",
        "nursing_actions", "missing_information", "source_record_ids", "generated_at", "verification_status",
    ],
    "properties": {
        "session_id": _STR,
        "clinical_summary": _STR,
        "patient_summary": _STR,
        "treatment_duration_minutes": {"type": ["number", "null"]},
        "documented_events": _LIST,
        "nursing_actions": _LIST,
        "missing_information": _LIST,
        "source_record_ids": {**_IDS, "minItems": 1},
        "generated_at": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}"},
        "verification_status": {"const": "unverified"},
    },
}  # fmt: skip

# Wording that would turn documentation support into diagnosis, prescribing, grading staff, or
# machine control. A blunt net: the reviewing doctor remains the real control.
FORBIDDEN = [
    "diagnos", "we prescribe", "i prescribe", "should be prescribed", "recommend prescribing",
    "we recommend", "is recommended", "should administer", "should receive",
    "increase the dose", "decrease the dose", "reduce the dose", "start taking", "stop taking",
    "incompetent", "negligen", "malpractice", "set the machine", "adjust the machine", "set the dialysate",
]  # fmt: skip
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
Errors = list[dict[str, str]]


def _error(code: str, message: str, path: str = "") -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def _schema(payload: Any, schema: dict) -> Errors:
    return [
        _error("schema_invalid", e.message[:300], "/".join(map(str, e.absolute_path)))
        for e in Draft202012Validator(schema).iter_errors(payload)
    ]


def _forbidden(texts: list[tuple[str, str]]) -> Errors:
    return [
        _error("unsupported_clinical_claim", f"Contains wording outside the assistant's role: '{term}'.", path)
        for path, text in texts
        for term in FORBIDDEN
        if term in text.lower()
    ]


FREE_TEXT_KEYS = {"description", "reason", "text", "resolution"}


def _without_free_text(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _without_free_text(v) for k, v in value.items() if k not in FREE_TEXT_KEYS}
    if isinstance(value, list):
        return [_without_free_text(v) for v in value]
    return value


def validate_review(output: Any, session_id: str, record_ids: set[str], passage_ids: set[str]) -> Errors:
    errors = _schema(output, REVIEW_SCHEMA)
    if errors:
        return errors
    if output["session_id"] != session_id:
        errors.append(_error("wrong_session", "Output refers to a different session.", "session_id"))
    texts = [("summary", output["summary"])] + [("questions_for_doctor", q) for q in output["questions_for_doctor"]]
    for i, gap in enumerate(output["documentation_gaps"]):
        path = f"documentation_gaps/{i}"
        texts.append((path, gap["description"]))
        unknown = sorted(set(gap["source_record_ids"]) - record_ids)
        if unknown:
            errors.append(_error("unknown_source_record", f"Cites records that were not provided: {unknown}", path))
        invented = sorted(set(gap["protocol_reference_ids"]) - passage_ids)
        if invented:
            errors.append(
                _error("unknown_protocol_reference", f"Cites passages that were not retrieved: {invented}", path)
            )
    for i, item in enumerate(output["protocol_discrepancies"]):
        path = f"protocol_discrepancies/{i}"
        texts.append((path, item["description"]))
        unknown = sorted(set(item["evidence"]) - record_ids - passage_ids)
        if unknown:
            errors.append(_error("unknown_source_record", f"Evidence was not provided: {unknown}", path))
    return errors + _forbidden(texts)


def validate_summary(output: Any, context: dict, record_ids: set[str]) -> Errors:
    errors = _schema(output, SUMMARY_SCHEMA)
    if errors:
        return errors
    if output["session_id"] != context["session"]["id"]:
        errors.append(_error("wrong_session", "Output refers to a different session.", "session_id"))
    unknown = sorted(set(output["source_record_ids"]) - record_ids)
    if unknown:
        errors.append(_error("unknown_source_record", f"Cites records that were not provided: {unknown}"))
    expected = context["metrics"]["actual_duration"]["value"]
    if output["treatment_duration_minutes"] != expected:
        errors.append(
            _error(
                "duration_mismatch",
                f"Duration must equal the backend calculation ({expected}).",
                "treatment_duration_minutes",
            )
        )
    # No fabricated measurements. Prose may only use numbers from structured fields (metrics, vitals,
    # readings, labs, session, prescription): a number that exists only inside free text, such as a
    # nursing note, is not accepted as a measurement. The quoting lists may repeat any record.
    everything = set(_NUMBER.findall(json.dumps(context, default=str)))
    structured = set(_NUMBER.findall(json.dumps(_without_free_text(context), default=str)))
    prose = [("clinical_summary", output["clinical_summary"]), ("patient_summary", output["patient_summary"])]
    quotes = [(n, t) for n in ("documented_events", "nursing_actions", "missing_information") for t in output[n]]
    for known, texts in ((structured, prose), (everything, quotes)):
        for path, text in texts:
            invented = sorted(set(_NUMBER.findall(text)) - known)
            if invented:
                errors.append(
                    _error("ungrounded_number", f"Numbers not present in the session records: {invented}", path)
                )
    texts = prose + quotes
    return errors + _forbidden(texts)
