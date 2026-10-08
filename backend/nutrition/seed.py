"""Synthetic nutrition demo data, layered on the demo organization. Every meal here is invented."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from clinical.models import CareAssignment, Patient
from core.models import Organization, Role, User

from . import services
from .models import FoodItem

# (meal type, hour, [(food name, quantity, unit)]). A name outside the catalogue stays unmatched.
BREAKFAST = ("breakfast", 8, [("egg, boiled", 2, "piece"), ("flatbread (khubz)", 1, "piece"), ("cucumber", 1, "piece")])
LUNCH = (
    "lunch",
    14,
    [("chicken breast, cooked", 1, "serving"), ("white rice, cooked", 1, "cup"), ("tomato", 1, "piece")],
)
DINNER = (
    "dinner",
    20,
    [("lentils, cooked", 1, "serving"), ("samoon bread", 1, "piece"), ("yogurt, plain", 1, "serving")],
)
SNACK = ("snack", 17, [("dates", 3, "piece"), ("tea, unsweetened", 1, "glass")])
HOMEMADE = ("dinner", 20, [("homemade kubba", 2, "piece"), ("laban (yogurt drink)", 1, "cup")])
# days ago -> meals. Days 3, 8 and 9 are deliberately missing: the diary must show them as unrecorded.
DIARY = {
    13: (BREAKFAST, LUNCH), 12: (BREAKFAST, LUNCH, DINNER), 11: (LUNCH, SNACK), 10: (BREAKFAST, LUNCH),
    7: (BREAKFAST, LUNCH, HOMEMADE), 6: (BREAKFAST, DINNER), 5: (BREAKFAST, LUNCH, SNACK), 4: (LUNCH, DINNER),
    2: (BREAKFAST, LUNCH), 1: (BREAKFAST, LUNCH, DINNER), 0: (BREAKFAST,),
}  # fmt: skip


def _meal(patient: Patient, days_ago: int, meal: tuple, foods: dict[str, FoodItem]) -> None:
    meal_type, hour, parts = meal
    at = (timezone.localtime() - timedelta(days=days_ago)).replace(hour=hour, minute=0, second=0, microsecond=0)
    services.save_meal(
        patient,
        patient.user,
        {
            "meal_type": meal_type,
            "consumed_at": min(at, timezone.now()),
            "entry_method": "text",
            "description": ", ".join(name for name, _, _ in parts),
            "components": [
                {
                    "food_item": foods.get(name),
                    "name": name,
                    "quantity": quantity,
                    "unit": unit,
                    "portion_verified": True,
                }
                for name, quantity, unit in parts
            ],
        },
    )


@transaction.atomic
def seed_nutrition(password: str, organization: str) -> bool:
    """Returns False when the nutrition demo data is already there (or the demo organization is not)."""
    org = Organization.objects.filter(name=organization).first()
    if org is None or User.objects.filter(username="dietitian1").exists():
        return False
    services.load_catalog()
    foods = {f.canonical_name: f for f in FoodItem.objects.all()}
    dietitian = User(username="dietitian1", role=Role.DIETITIAN, display_name="Dietitian Demo", organization=org)
    dietitian.set_password(password)
    dietitian.save()
    patients = {p.mrn: p for p in Patient.objects.filter(organization=org)}
    for patient in patients.values():
        CareAssignment.objects.create(patient=patient, professional=dietitian)
    one, two = patients["SYN-001"], patients["SYN-002"]
    for consent in one.consents.filter(caregiver__username="family1"):
        consent.scopes = sorted({*consent.scopes, "nutrition", "nutrition_log"})
        consent.save()

    for days_ago, meals in DIARY.items():
        for meal in meals:
            _meal(one, days_ago, meal, foods)
    for days_ago in (5, 2, 1):
        _meal(two, days_ago, LUNCH, foods)

    services.approve_plan(
        one,
        dietitian,
        {
            "prescribed_targets": {"potassium_mg_max": 600, "sodium_mg_max": 600, "phosphorus_mg_max": 350},
            "guidance": "Synthetic demo plan. Per-meal limits were typed by the demo dietitian for illustration only.",
            "dietary_preferences": ["halal"],
            "allergies": ["fish"],
        },
    )
    recommendations = services.suggest(one, dietitian)  # personalized: wait for the dietitian
    for rec in [r for r in recommendations if r.category == "compatible"][:2]:
        services.review_recommendation(rec.pk, dietitian, approve=True)
    services.suggest(two, two.user)  # no plan: general ideas only

    end = timezone.localdate()
    services.analyze(one.pk, end - timedelta(days=29), end)
    services.build_report(one.pk, end - timedelta(days=29), end)
    nurse = User.objects.get(username="nurse1")
    services.observe(
        one, nurse, {"kind": "loss_of_appetite", "text": "Patient reports eating less than usual.", "referred": True}
    )
    return True
