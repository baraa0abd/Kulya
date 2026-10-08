"""Shared model-output schemas and grounding helpers. No patient workflow or database access."""

import re
from typing import Any

from jsonschema import Draft202012Validator

TEXT_SCHEMA = {"type": "string", "minLength": 1, "maxLength": 2000}


TEXT_LIST_SCHEMA = {"type": "array", "items": TEXT_SCHEMA, "maxItems": 60}


FORBIDDEN = [
    "diagnos", "we prescribe", "i prescribe", "should be prescribed", "recommend prescribing",
    "we recommend", "is recommended", "should administer", "should receive",
    "increase the dose", "decrease the dose", "reduce the dose", "start taking", "stop taking",
    "incompetent", "negligen", "malpractice", "set the machine", "adjust the machine", "set the dialysate",
]  # fmt: skip


NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")


TIMESTAMP_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?|\d{1,2}:\d{2}")


Errors = list[dict[str, str]]


def validation_error(code: str, message: str, path: str = "") -> dict[str, str]:
    return {"code": code, "path": path, "message": message}


def schema_errors(payload: Any, schema: dict) -> Errors:
    return [
        validation_error("schema_invalid", e.message[:300], "/".join(map(str, e.absolute_path)))
        for e in Draft202012Validator(schema).iter_errors(payload)
    ]


FREE_TEXT_KEYS = {"description", "reason", "text", "resolution"}


def numeric_values(node: Any, with_free_text: bool, key: str = "") -> set[float]:
    """Every numeric value in the context (as magnitudes), optionally plus numbers quoted in free text.
    Ids and timestamps are strings and are deliberately not a source of numbers."""
    if isinstance(node, dict):
        return set().union(*(numeric_values(v, with_free_text, k) for k, v in node.items()))
    if isinstance(node, list):
        return set().union(*(numeric_values(v, with_free_text, key) for v in node))
    if isinstance(node, (int, float)) and not isinstance(node, bool):
        return {abs(float(node))}
    if isinstance(node, str) and with_free_text and key in FREE_TEXT_KEYS:
        return {float(n) for n in NUMBER_PATTERN.findall(node)}
    return set()
