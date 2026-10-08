"""Model-facing side of nutrition: prompt ids, output schemas, validation, and the offline mock.

The model only ever proposes foods or writes descriptive text. It never produces a nutrient number
(those come from engine.py), never sets a limit, and anything it writes is a draft until reviewed."""

from typing import Any

from ai.validation import _LIST, _NUMBER, _STR, _TIMESTAMP, FORBIDDEN, Errors, _error, _schema, _values

from .engine import NUTRIENTS, UNITS

RECOGNIZE, ANALYZE, SUGGEST, REPORT = (
    "nutrition_recognize_v1",
    "nutrition_analyze_v1",
    "nutrition_suggest_v1",
    "nutrition_report_v1",
)

# Wording that would turn a food diary into a causal claim, a diet order or medication advice.
# Blunt on purpose; the reviewing clinician remains the real control.
NUTRITION_FORBIDDEN = [
    *FORBIDDEN,
    "caused", "causes ", "because of", "due to", "led to", "resulted in", "result of", "responsible for",
    "raised your", "lowered your", "creatinine", "binder", "medication", "medicine", "supplement", "insulin",
    "you must", "you should", "stop eating", "avoid eating", "cure", "treat ", "safe to eat", "safe for you",
]  # fmt: skip

RECOGNIZE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["items", "uncertainties"],
    "properties": {
        "items": {
            "type": "array",
            "maxItems": 20,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "quantity", "unit", "confidence"],
                "properties": {
                    "name": {"type": "string", "minLength": 1, "maxLength": 160},
                    "quantity": {"type": "number", "exclusiveMinimum": 0, "maximum": 5000},
                    "unit": {"type": "string", "minLength": 1, "maxLength": 20},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "preparation": {"type": "string", "maxLength": 200},
                },
            },
        },
        "uncertainties": _LIST,
    },
}
ANALYZE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["observations", "limitations", "questions_for_clinician", "requires_clinician_review"],
    "properties": {
        "observations": {
            "type": "array",
            "maxItems": 20,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "nutrient", "lab_result_ids"],
                "properties": {
                    "text": _STR,
                    "nutrient": {"enum": NUTRIENTS},
                    "lab_result_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 20},
                },
            },
        },
        "limitations": _LIST,
        "questions_for_clinician": _LIST,
        "requires_clinician_review": {"const": True},
    },
}
SUGGEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["explanations"],
    "properties": {
        "explanations": {
            "type": "array",
            "maxItems": 40,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["recipe_id", "text"],
                "properties": {"recipe_id": {"type": "string"}, "text": _STR},
            },
        }
    },
}
REPORT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["overview", "observations", "questions_for_care_team", "limitations", "verification_status"],
    "properties": {
        "overview": _STR,
        "observations": _LIST,
        "questions_for_care_team": _LIST,
        "limitations": _LIST,
        "verification_status": {"const": "unverified"},
    },
}


def _check_text(texts: list[tuple[str, str]], payload: dict) -> Errors:
    """No forbidden wording, and no number that is not a value in the structured input."""
    known = _values(payload, with_free_text=False)
    errors: Errors = []
    for path, text in texts:
        lowered = text.lower()
        errors += [
            _error("unsupported_clinical_claim", f"Contains wording outside the assistant's role: '{term}'.", path)
            for term in NUTRITION_FORBIDDEN
            if term in lowered
        ]
        invented = sorted({n for n in _NUMBER.findall(_TIMESTAMP.sub(" ", text)) if float(n) not in known})
        if invented:
            errors.append(_error("ungrounded_number", f"Numbers not present in the input: {invented}", path))
    return errors


def validate_recognition(output: Any) -> Errors:
    errors = _schema(output, RECOGNIZE_SCHEMA)
    if errors:
        return errors
    texts = [("uncertainties", t) for t in output["uncertainties"]]
    return [e for e in _check_text(texts, {}) if e["code"] != "ungrounded_number"]


def validate_analysis(output: Any, payload: dict) -> Errors:
    errors = _schema(output, ANALYZE_SCHEMA)
    if errors:
        return errors
    lab_ids = {lab["id"] for lab in payload["laboratory_results"]}
    texts = [(n, t) for n in ("limitations", "questions_for_clinician") for t in output[n]]
    for i, item in enumerate(output["observations"]):
        texts.append((f"observations/{i}", item["text"]))
        unknown = sorted(set(item["lab_result_ids"]) - lab_ids)
        if unknown:
            errors.append(_error("unknown_source_record", f"Cites results that were not provided: {unknown}"))
    return errors + _check_text(texts, payload)


def validate_suggestions(output: Any, payload: dict) -> Errors:
    errors = _schema(output, SUGGEST_SCHEMA)
    if errors:
        return errors
    known = {r["id"] for r in payload["recipes"]}
    unknown = sorted({e["recipe_id"] for e in output["explanations"]} - known)
    if unknown:
        errors.append(_error("unknown_source_record", f"Explains recipes that were not provided: {unknown}"))
    texts = [(f"explanations/{i}", e["text"]) for i, e in enumerate(output["explanations"])]
    return errors + _check_text(texts, payload)


def validate_report(output: Any, payload: dict) -> Errors:
    errors = _schema(output, REPORT_SCHEMA)
    if errors:
        return errors
    texts = [("overview", output["overview"])]
    texts += [(n, t) for n in ("observations", "questions_for_care_team", "limitations") for t in output[n]]
    return _check_text(texts, payload)


# --- Offline mock: a template over the structured input, not a language model. ----------------

_PORTION_WORDS = {"cup", "piece", "glass", "tablespoon", "serving", "g", "gram", "ml", "kg"}
_SEPARATORS = (",", "،", "+", " and ", " with ", " و ", " مع ")
# The lab analyte that is shown next to each nutrient. Side by side only: no cause is implied.
_PAIRS = {"potassium_mg": "potassium", "phosphorus_mg": "phosph", "sodium_mg": "sodium", "protein_g": "albumin"}


def _mock_items(description: str) -> list[dict]:
    text = f" {description} "
    for separator in _SEPARATORS:
        text = text.replace(separator, "|")
    items = []
    for part in filter(None, (p.strip() for p in text.split("|"))):
        words, quantity, unit = part.split(), 1.0, "serving"
        try:
            quantity, words = float(words[0]), words[1:]
            unit = "piece"
        except ValueError:
            pass
        if words and words[0].lower().rstrip("s") in _PORTION_WORDS and len(words) > 1:
            unit, words = words[0].lower().rstrip("s"), words[1:]
        if words and 0 < quantity <= 5000:
            items.append({"name": " ".join(words), "quantity": quantity, "unit": unit, "confidence": 0.5})
    return items


def mock_response(prompt_id: str, payload: dict, image: tuple[str, str] | None = None) -> dict:
    if prompt_id == RECOGNIZE:
        items = _mock_items(payload.get("description", ""))
        notes = ["Portion sizes are estimates. Please check each one."]
        if image and not items:
            notes = ["The offline demo provider cannot read photos. Type or say what was eaten."]
        return {"items": items, "uncertainties": notes}
    if prompt_id == SUGGEST:
        return {
            "explanations": [
                {"recipe_id": r["id"], "text": f"{r['name']}: {' '.join(r['reasons'])}"} for r in payload["recipes"]
            ]
        }
    averages = payload["diary"]["daily_average_on_complete_days"]
    known = {n: v for n, v in averages.items() if v is not None}
    if prompt_id == ANALYZE:
        observations = []
        for nutrient, needle in _PAIRS.items():
            labs = [lab for lab in payload["laboratory_results"] if needle in lab["analyte"].lower()]
            if nutrient in known and labs:
                latest = labs[-1]
                observations.append(
                    {
                        "text": f"Average recorded {nutrient.split('_')[0]} on days with complete data was "
                        f"{known[nutrient]} {UNITS[nutrient]}. "
                        f"The {latest['analyte']} result was {latest['value']} {latest['unit']}. "
                        "These are shown side by side; no cause is implied.",
                        "nutrient": nutrient,
                        "lab_result_ids": [lab["id"] for lab in labs],
                    }
                )
        return {
            "observations": observations,
            "limitations": ["Food records are self-reported and nutrient values are estimates."],
            "questions_for_clinician": ["Does the recorded diary reflect this patient's usual eating?"],
            "requires_clinician_review": True,
        }
    diary = payload["diary"]
    return {
        "overview": f"Meals were recorded on {diary['days_recorded']} of {diary['days_in_period']} days "
        f"in this period ({diary['meals_recorded']} meals).",
        "observations": [
            f"Average recorded {n.split('_')[0]} on days with complete data: {v} {UNITS[n]}." for n, v in known.items()
        ],
        "questions_for_care_team": ["Are there days in this period when meals were eaten but not recorded?"],
        "limitations": ["Food records are self-reported and nutrient values are estimates."],
        "verification_status": "unverified",
    }
