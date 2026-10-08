"""Clinical review and summary output validation, including source and measurement grounding."""

from typing import Any

from .output_validation import (
    FORBIDDEN,
    NUMBER_PATTERN,
    TEXT_LIST_SCHEMA,
    TEXT_SCHEMA,
    TIMESTAMP_PATTERN,
    Errors,
    numeric_values,
    schema_errors,
    validation_error,
)

_IDS = {"type": "array", "items": {"type": "string"}, "maxItems": 100}

REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "session_id", "summary", "documentation_gaps", "protocol_discrepancies",
        "questions_for_doctor", "requires_human_review", "status",
    ],
    "properties": {
        "session_id": TEXT_SCHEMA,
        "summary": TEXT_SCHEMA,
        "documentation_gaps": {
            "type": "array",
            "maxItems": 60,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["finding_id", "description", "source_record_ids", "protocol_reference_ids"],
                "properties": {
                    "finding_id": TEXT_SCHEMA,
                    "description": TEXT_SCHEMA,
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
                    "description": TEXT_SCHEMA,
                    "evidence": {**_IDS, "minItems": 1},
                    "requires_clinician_assessment": {"const": True},
                },
            },
        },
        "questions_for_doctor": TEXT_LIST_SCHEMA,
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
        "session_id": TEXT_SCHEMA,
        "clinical_summary": TEXT_SCHEMA,
        "patient_summary": TEXT_SCHEMA,
        "treatment_duration_minutes": {"type": ["number", "null"]},
        "documented_events": TEXT_LIST_SCHEMA,
        "nursing_actions": TEXT_LIST_SCHEMA,
        "missing_information": TEXT_LIST_SCHEMA,
        "source_record_ids": {**_IDS, "minItems": 1},
        "generated_at": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}"},
        "verification_status": {"const": "unverified"},
    },
}  # fmt: skip

# Wording that would turn documentation support into diagnosis, prescribing, grading staff, or
# machine control. A blunt net: the reviewing doctor remains the real control.


def _forbidden(texts: list[tuple[str, str]]) -> Errors:
    return [
        validation_error(
            "unsupported_clinical_claim", f"Contains wording outside the assistant's role: '{term}'.", path
        )
        for path, text in texts
        for term in FORBIDDEN
        if term in text.lower()
    ]


def validate_review(output: Any, session_id: str, record_ids: set[str], passage_ids: set[str]) -> Errors:
    errors = schema_errors(output, REVIEW_SCHEMA)
    if errors:
        return errors
    if output["session_id"] != session_id:
        errors.append(validation_error("wrong_session", "Output refers to a different session.", "session_id"))
    texts = [("summary", output["summary"])] + [("questions_for_doctor", q) for q in output["questions_for_doctor"]]
    for i, gap in enumerate(output["documentation_gaps"]):
        path = f"documentation_gaps/{i}"
        texts.append((path, gap["description"]))
        unknown = sorted(set(gap["source_record_ids"]) - record_ids)
        if unknown:
            errors.append(
                validation_error("unknown_source_record", f"Cites records that were not provided: {unknown}", path)
            )
        invented = sorted(set(gap["protocol_reference_ids"]) - passage_ids)
        if invented:
            errors.append(
                validation_error(
                    "unknown_protocol_reference", f"Cites passages that were not retrieved: {invented}", path
                )
            )
    for i, item in enumerate(output["protocol_discrepancies"]):
        path = f"protocol_discrepancies/{i}"
        texts.append((path, item["description"]))
        unknown = sorted(set(item["evidence"]) - record_ids - passage_ids)
        if unknown:
            errors.append(validation_error("unknown_source_record", f"Evidence was not provided: {unknown}", path))
    return errors + _forbidden(texts)


def validate_summary(output: Any, context: dict, record_ids: set[str]) -> Errors:
    errors = schema_errors(output, SUMMARY_SCHEMA)
    if errors:
        return errors
    if output["session_id"] != context["session"]["id"]:
        errors.append(validation_error("wrong_session", "Output refers to a different session.", "session_id"))
    unknown = sorted(set(output["source_record_ids"]) - record_ids)
    if unknown:
        errors.append(validation_error("unknown_source_record", f"Cites records that were not provided: {unknown}"))
    expected = context["metrics"]["actual_duration"]["value"]
    if output["treatment_duration_minutes"] != expected:
        errors.append(
            validation_error(
                "duration_mismatch",
                f"Duration must equal the backend calculation ({expected}).",
                "treatment_duration_minutes",
            )
        )
    # No fabricated measurements. Prose may only use numbers that are actual values in structured
    # fields (metrics, vitals, readings, labs, session, prescription). A number that exists only
    # inside free text, such as a nursing note, is not accepted as a measurement there; the quoting
    # lists may repeat free text. Dates and clock times are not treated as measurements.
    structured = numeric_values(context, with_free_text=False)
    everything = numeric_values(context, with_free_text=True)
    prose = [("clinical_summary", output["clinical_summary"]), ("patient_summary", output["patient_summary"])]
    quotes = [(n, t) for n in ("documented_events", "nursing_actions", "missing_information") for t in output[n]]
    for known, texts in ((structured, prose), (everything, quotes)):
        for path, text in texts:
            invented = sorted(
                {n for n in NUMBER_PATTERN.findall(TIMESTAMP_PATTERN.sub(" ", text)) if float(n) not in known}
            )
            if invented:
                errors.append(
                    validation_error(
                        "ungrounded_number", f"Numbers not present in the session records: {invented}", path
                    )
                )
    texts = prose + quotes
    return errors + _forbidden(texts)
