"""USDA FoodData Central lookup. Off unless USDA_API_KEY is set. Search results are cached for a day
and stored as catalogue rows that keep their FDC id as provenance."""

import hashlib
import json
import logging
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

from .engine import NUTRIENTS
from .models import FoodItem

logger = logging.getLogger("kulya")
URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
# FDC nutrient number -> our field. 208 is energy in kcal; 255 is water (g per 100 g), used as fluid mL.
NUMBERS = {"208": "energy_kcal", "203": "protein_g", "307": "sodium_mg", "306": "potassium_mg",
           "305": "phosphorus_mg", "301": "calcium_mg", "255": "fluid_ml"}  # fmt: skip


def search(query: str) -> list[FoodItem]:
    """Foods matching `query`, imported into the catalogue. Empty when off, offline or on any error."""
    query = query.strip().lower()
    if not settings.USDA_API_KEY or not query:
        return []
    key = "usda:" + hashlib.sha256(query.encode()).hexdigest()
    rows = cache.get(key)
    if rows is None:
        try:
            rows = fetch(query).get("foods", [])
        except (URLError, TimeoutError, ValueError) as exc:
            logger.warning("usda lookup failed", extra={"ctx": {"error": type(exc).__name__}})
            return []
        cache.set(key, rows, 86400)
    return [_store(row) for row in rows if row.get("fdcId") and row.get("description")]


def fetch(query: str) -> dict:
    params = urlencode({"query": query, "pageSize": 5, "dataType": "Foundation,SR Legacy"})
    # The key travels in a header, so it never lands in a URL log.
    request = Request(f"{URL}?{params}", headers={"X-Api-Key": settings.USDA_API_KEY})  # fixed https URL
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def _store(row: dict) -> FoodItem:
    nutrients = dict.fromkeys(NUTRIENTS)  # anything USDA does not report stays unknown
    for item in row.get("foodNutrients", []):
        field = NUMBERS.get(str(item.get("nutrientNumber")))
        if field and isinstance(item.get("value"), (int, float)):
            nutrients[field] = item["value"]
    fdc_id = str(row["fdcId"])
    food, _ = FoodItem.objects.update_or_create(
        food_database_id=fdc_id,
        defaults={
            "canonical_name": f"{row['description'].lower()[:90]} (USDA {fdc_id})",
            "localized_names": {"en": row["description"]},
            "nutrient_data_source": f"USDA FoodData Central, FDC ID {fdc_id}",
            "nutrients_per_100g": nutrients,
        },
    )
    return food
