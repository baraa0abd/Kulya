"""Deterministic nutrition arithmetic. Pure functions: no database, no model, no clock.

Rules that hold everywhere: an unknown nutrient is None, never 0; a total is only given when every
contributing item has a value; a day with no recorded meal is "not recorded", never "ate nothing"."""

from collections import Counter
from datetime import date, timedelta

NUTRIENTS = ["energy_kcal", "protein_g", "sodium_mg", "potassium_mg", "phosphorus_mg", "calcium_mg", "fluid_ml"]
UNITS = {"energy_kcal": "kcal", "protein_g": "g", "sodium_mg": "mg", "potassium_mg": "mg", "phosphorus_mg": "mg",
         "calcium_mg": "mg", "fluid_ml": "mL"}  # fmt: skip
GRAM_UNITS = {"g": 1.0, "gram": 1.0, "grams": 1.0, "kg": 1000.0, "ml": 1.0}  # ml ~ g for watery foods


def grams_for(quantity: float, unit: str, portion_grams: dict | None) -> float | None:
    """Convert a stated portion to grams. None when the unit is unknown for this food."""
    unit = unit.strip().lower()
    if unit in GRAM_UNITS:
        return round(quantity * GRAM_UNITS[unit], 1)
    per_unit = (portion_grams or {}).get(unit)
    return None if per_unit is None else round(quantity * per_unit, 1)


def estimate(components: list[dict]) -> dict:
    """components: [{"grams": float|None, "per_100g": {nutrient: value|None} | None}].

    Returns {"totals": {nutrient: float|None}, "completeness": {nutrient: 0..1}}. A total is None
    unless every component contributed a value for that nutrient."""
    totals: dict[str, float | None] = {}
    completeness: dict[str, float] = {}
    for nutrient in NUTRIENTS:
        known = [
            c["grams"] * c["per_100g"][nutrient] / 100
            for c in components
            if c.get("grams") is not None and c.get("per_100g") and c["per_100g"].get(nutrient) is not None
        ]
        completeness[nutrient] = round(len(known) / len(components), 2) if components else 0.0
        totals[nutrient] = round(sum(known), 1) if components and len(known) == len(components) else None
    return {"totals": totals, "completeness": completeness}


def days_between(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def diary_summary(meals: list[dict], start: date, end: date) -> dict:
    """meals: [{"day": date, "meal_type": str, "totals": {...}, "foods": [names]}].

    A daily average uses only COMPLETE days for that nutrient: days with a record on which every meal
    has a value. A day with a meal of unknown content is left out rather than undercounted, and a day
    with no record is reported as missing, never treated as zero intake."""
    days = days_between(start, end)
    recorded = sorted({m["day"] for m in meals if start <= m["day"] <= end})
    in_period = [m for m in meals if start <= m["day"] <= end]
    averages: dict[str, float | None] = {}
    complete_days: dict[str, int] = {}
    for nutrient in NUTRIENTS:
        by_day: dict[date, list] = {}
        for m in in_period:
            by_day.setdefault(m["day"], []).append(m["totals"].get(nutrient))
        totals = [sum(values) for values in by_day.values() if None not in values]
        complete_days[nutrient] = len(totals)
        averages[nutrient] = round(sum(totals) / len(totals), 1) if totals else None
    foods = Counter(name for m in in_period for name in m["foods"])
    return {
        "days_in_period": len(days),
        "days_recorded": len(recorded),
        "missing_days": [d.isoformat() for d in days if d not in set(recorded)],
        "completeness": round(len(recorded) / len(days), 2) if days else 0.0,
        "meals_recorded": len(in_period),
        "meals_by_type": dict(Counter(m["meal_type"] for m in in_period)),
        "daily_average_on_complete_days": averages,
        "days_with_complete_data": complete_days,
        "most_recorded_foods": [name for name, _ in foods.most_common(5)],
        "units": UNITS,
    }


# Laboratory analyte (name fragment) -> the recipe nutrient shown against it.
LAB_NUTRIENT = {"potassium": "potassium_mg", "phosph": "phosphorus_mg", "sodium": "sodium_mg"}
# ponytail: ordering heuristic, not a clinical limit. A doctor approves every laboratory-based idea;
# replace with thresholds from the plan if the care team starts writing them there.
UPPER_SHARE = 0.75


def lab_watch(results: list[dict]) -> list[dict]:
    """Results of one laboratory report that are above, or in the upper part of, the laboratory's
    own reference range. Only the reported range is used: no limit is invented here."""
    watch = []
    for result in results:
        nutrient = next((n for needle, n in LAB_NUTRIENT.items() if needle in result["analyte"].lower()), None)
        low, high = result.get("reference_low"), result.get("reference_high")
        if nutrient is None or low is None or high is None or high <= low:
            continue
        if result["value"] > high:
            position = "above"
        elif result["value"] >= low + UPPER_SHARE * (high - low):
            position = "in the upper part of"
        else:
            continue
        watch.append({**result, "nutrient": nutrient, "position": position})
    return watch


def lab_reasons(nutrients: dict, watch: list[dict], medians: dict[str, float]) -> list[str]:
    """Where a recipe sits among the listed recipes for each watched nutrient. Descriptive only."""
    reasons = []
    for lab in watch:
        nutrient, value = lab["nutrient"], nutrients.get(lab["nutrient"])
        reasons.append(
            f"Latest {lab['analyte']} result {lab['value']} {lab['unit']} is {lab['position']} the laboratory "
            f"reference range {lab['reference_low']} to {lab['reference_high']}."
        )
        if value is None or nutrient not in medians:
            reasons.append(f"{nutrient} is not available for this recipe, so it cannot be compared.")
        else:
            half = "lower" if value <= medians[nutrient] else "higher"
            reasons.append(f"Estimated {nutrient} {value} is in the {half} half of the listed recipes.")
    return reasons


def window_before(collected: date, days: int = 7) -> tuple[date, date]:
    """The diary days that precede a laboratory sample (the sample day itself excluded)."""
    return collected - timedelta(days=days), collected - timedelta(days=1)


def classify_recipe(nutrients: dict, allergens: list[str], plan: dict | None) -> tuple[str | None, list[str]]:
    """Decide how a recipe relates to a clinician-approved plan.

    plan: {"allergies": [...], "prescribed_targets": {"<nutrient>_max": n}} or None.
    Returns (category, reasons). category None = excluded (allergy). Limits come only from the plan:
    this function never invents one."""
    if plan is None:
        return "general", ["No approved nutrition plan: this is a general idea, not personalized."]
    clash = sorted(set(allergens) & {a.lower() for a in plan.get("allergies", [])})
    if clash:
        return None, [f"Contains a documented allergen: {', '.join(clash)}."]
    reasons, over, unknown = [], False, False
    for key, limit in plan.get("prescribed_targets", {}).items():
        if not key.endswith("_max"):
            continue
        nutrient = key[: -len("_max")]
        value = nutrients.get(nutrient)
        if value is None:
            unknown = True
            reasons.append(f"{nutrient} is not available for every ingredient, so the plan limit cannot be checked.")
        elif value > limit:
            over = True
            reasons.append(f"Estimated {nutrient} {value} is above the plan limit {limit} per meal.")
    if over:
        return "needs_dietitian_review", reasons
    if unknown:
        return "check_portion", reasons
    return "compatible", reasons or ["Within every per-meal limit set in the approved plan."]
