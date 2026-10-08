"""Demo catalogue import and bilingual food matching, separate from patient workflows."""

import json
import re
import unicodedata
from pathlib import Path

from . import engine
from .models import FoodItem, Recipe

CATALOG = Path(__file__).parent / "data" / "catalog.json"
_ARABIC = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ـ": ""})


def load_catalog() -> int:
    """Load the bundled demo catalogue. Idempotent. Recipe nutrients are computed, never typed."""
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    foods = {}
    for row in data["foods"]:
        foods[row["name"]], _ = FoodItem.objects.update_or_create(
            canonical_name=row["name"],
            defaults={
                "localized_names": {"en": row["name"], "ar": row["ar"], "ckb": row["ckb"]},
                "nutrient_data_source": data["source"],
                "nutrients_per_100g": dict(zip(engine.NUTRIENTS, row["n"], strict=True)),
                "portion_grams": row["portions"],
                "allergens": row["allergens"],
            },
        )
    for row in data["recipes"]:
        parts = [{"grams": grams, "per_100g": foods[name].nutrients_per_100g} for name, grams in row["ingredients"]]
        Recipe.objects.update_or_create(
            name=row["name"],
            defaults={
                "localized_names": {"en": row["name"], "ar": row["ar"]},
                "meal_type": row["meal_type"],
                "ingredients": [{"food": name, "grams": grams} for name, grams in row["ingredients"]],
                "preparation_method": row["steps"],
                "yield_weight": round(sum(grams for _, grams in row["ingredients"])),
                "allergens": sorted({a for name, _ in row["ingredients"] for a in foods[name].allergens}),
                "nutritional_estimate": engine.estimate(parts)["totals"],
                "source": data["source"],
            },
        )
    return len(foods)


def _tokens(text: str) -> set[str]:
    """Comparable word set: case, Arabic letter variants, diacritics and English plurals folded."""
    text = "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))
    words = re.sub(r"[^\w\s]", " ", text.translate(_ARABIC)).split()
    return {w[:-1] if w.isascii() and len(w) > 3 and w.endswith("s") else w for w in words}


def match_food(name: str, foods: list[FoodItem] | None = None) -> FoodItem | None:
    """Best catalogue match for a spoken or typed food name, or None. The person confirms it."""
    # The bundled catalogue is small enough for deterministic in-memory matching.
    wanted, best, best_score = _tokens(name), None, (0.0, 0.0)
    if not wanted:
        return None
    for food in foods if foods is not None else FoodItem.objects.all():
        for label in {food.canonical_name, *food.localized_names.values()}:
            have = _tokens(label)
            shared = len(wanted & have)
            score = (shared / len(wanted), shared / len(have)) if have else (0.0, 0.0)
            if score[0] >= 0.5 and score > best_score:
                best, best_score = food, score
    return best


def search_foods(query: str) -> list[FoodItem]:
    foods = list(FoodItem.objects.all())
    wanted = _tokens(query)
    if not wanted:
        return foods
    return [f for f in foods if any(wanted & _tokens(n) for n in (f.canonical_name, *f.localized_names.values()))]
