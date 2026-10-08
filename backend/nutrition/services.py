"""Nutrition workflows. Numbers are computed by engine.py from the food catalogue; the model only
proposes foods and writes descriptive drafts, and every draft waits for a clinician."""

import hashlib
import json
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from ai.services import _call_model
from clinical.models import DialysisSession, LaboratoryResult, Patient
from core.errors import Conflict
from core.models import Role, User
from core.permissions import assigned_professionals
from core.services import audit
from workflow.services import notify

from . import engine
from .ai import (
    ANALYZE,
    RECOGNIZE,
    REPORT,
    SUGGEST,
    validate_analysis,
    validate_recognition,
    validate_report,
    validate_suggestions,
)
from .models import (
    FoodItem,
    FoodLabReview,
    MealComponent,
    MealLog,
    MealMedia,
    MealRecommendation,
    NutrientEstimate,
    NutritionObservation,
    NutritionPlan,
    NutritionReport,
    Recipe,
    ReviewStatus,
)

CATALOG = Path(__file__).parent / "data" / "catalog.json"
CATALOG_LIMITATION = "Nutrient values are estimates from an unverified demo food catalogue."
NOT_CAUSAL = (
    "Food records and laboratory results are shown together. This does not show that any food changed any result."
)
_ARABIC = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه", "ـ": ""})


# --- Food catalogue ----------------------------------------------------------------------------


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
    # ponytail: scans the whole catalogue in Python; move to trigram search if it grows past a few thousand rows.
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


# --- Meal diary --------------------------------------------------------------------------------


def recognize(user: User, patient: Patient, description: str, image: tuple[str, str] | None) -> dict:
    """Ask the model what was eaten. Returns editable candidates and saves nothing: a meal exists
    only after the person confirms it through save_meal. The photo is not stored."""
    foods = list(FoodItem.objects.all())
    payload = {"description": description, "known_foods": [f.canonical_name for f in foods]}
    output, errors, _ = _call_model(RECOGNIZE, payload, image)
    if output is not None:
        errors = validate_recognition(output)
    audit(user, "meal_recognition_requested", None, patient=patient, photo=bool(image), ok=not errors)
    if errors:
        return {"ai_unavailable": True, "items": [], "uncertainties": [], "errors": errors}
    items = []
    for item in output["items"]:
        food = match_food(item["name"], foods)
        grams = engine.grams_for(item["quantity"], item["unit"], food.portion_grams if food else None)
        items.append(
            {
                "name": item["name"],
                "quantity": item["quantity"],
                "unit": item["unit"],
                "confidence": item["confidence"],
                "preparation_details": item.get("preparation", ""),
                "food_item": str(food.id) if food else None,
                "food_name": food.canonical_name if food else None,
                "estimated_grams": grams,
                "needs_confirmation": True,
            }
        )
    return {"ai_unavailable": False, "items": items, "uncertainties": output["uncertainties"], "errors": []}


@transaction.atomic
def save_meal(patient: Patient, user: User, data: dict, meal: MealLog | None = None) -> MealLog:
    """Create or correct a diary entry. The estimate is always recomputed here from the catalogue;
    nutrient values sent by a client are never accepted."""
    components, media = data.pop("components", None), data.pop("media_used", "")
    created = meal is None
    meal = meal or MealLog(patient=patient, created_by=user)
    for field, value in data.items():
        setattr(meal, field, value)
    if components is not None:
        rows, parts, verified = [], [], True
        for c in components:
            food = c.get("food_item")
            grams = engine.grams_for(float(c["quantity"]), c["unit"], food.portion_grams if food else None)
            verified &= bool(food and grams is not None and c.get("portion_verified"))
            rows.append(
                MealComponent(
                    meal=meal,
                    food_item=food,
                    name=food.canonical_name if food else c["name"],
                    quantity=c["quantity"],
                    unit=c["unit"],
                    estimated_grams=grams,
                    portion_verified=bool(c.get("portion_verified")),
                    preparation_details=c.get("preparation_details", ""),
                )
            )
            parts.append({"grams": grams, "per_100g": food.nutrients_per_100g if food else None})
        meal.confirmation_status = MealLog.Confirmation.CONFIRMED if verified else MealLog.Confirmation.NEEDS_REVIEW
    meal.save()
    if components is not None:
        meal.components.all().delete()
        MealComponent.objects.bulk_create(rows)
        result = engine.estimate(parts)
        NutrientEstimate.objects.update_or_create(
            meal=meal,
            defaults={
                **result["totals"],
                "data_completeness": result["completeness"],
                "estimation_method": "catalogue_per_100g_x_grams",
                "source_references": sorted({r.food_item.nutrient_data_source for r in rows if r.food_item}),
            },
        )
    if created and media:
        MealMedia.objects.create(meal=meal, media_type=media)  # the file itself is never stored
    audit(user, "meal_logged" if created else "meal_corrected", meal, patient=patient, method=meal.entry_method)
    return meal


def delete_meal(meal: MealLog, user: User) -> None:
    meal.deleted_at = timezone.now()
    meal.save()
    audit(user, "meal_withdrawn", meal, patient=meal.patient)


def diary(patient: Patient, start: date, end: date) -> dict:
    meals = (
        MealLog.objects.filter(patient=patient, deleted_at__isnull=True)
        .filter(consumed_at__date__gte=start, consumed_at__date__lte=end)
        .select_related("estimate")
        .prefetch_related("components__food_item")
    )
    rows = [
        {
            "day": timezone.localtime(m.consumed_at).date(),
            "meal_type": m.meal_type,
            "totals": {n: getattr(m.estimate, n) for n in engine.NUTRIENTS},
            "foods": [c.food_item.canonical_name if c.food_item else c.name for c in m.components.all()],
        }
        for m in meals
    ]
    return engine.diary_summary(rows, start, end)


# --- Plans and suggestions ---------------------------------------------------------------------


def active_plan(patient: Patient) -> NutritionPlan | None:
    today = timezone.localdate()
    current = Q(valid_until__isnull=True) | Q(valid_until__gte=today)
    return patient.nutrition_plans.filter(current, active=True, valid_from__lte=today).first()


@transaction.atomic
def approve_plan(patient: Patient, clinician: User, data: dict) -> NutritionPlan:
    """A clinician writes and approves a new plan version. The previous version is retired, never edited."""
    Patient.objects.select_for_update().get(pk=patient.pk)  # serialize version numbering
    latest = patient.nutrition_plans.order_by("-version").first()
    patient.nutrition_plans.filter(active=True).update(active=False)
    plan = NutritionPlan.objects.create(
        patient=patient,
        version=latest.version + 1 if latest else 1,
        approved_by=clinician,
        approved_at=timezone.now(),
        **{"valid_from": timezone.localdate(), **data},
    )
    audit(clinician, "nutrition_plan_approved", plan, patient=patient, version=plan.version)
    return plan


def suggest(patient: Patient, user: User) -> list[MealRecommendation]:
    """Compare catalogue recipes with the approved plan (fixed rules), then ask the model only to
    word the result. Without a plan the ideas are general and say so. Idempotent per plan."""
    plan = active_plan(patient)
    limits = {"allergies": plan.allergies, "prescribed_targets": plan.prescribed_targets} if plan else None
    done = patient.meal_recommendations.filter(nutrition_plan=plan).values_list("recipe_id", flat=True)
    picks = []
    for recipe in Recipe.objects.exclude(pk__in=list(done)):
        category, reasons = engine.classify_recipe(recipe.nutritional_estimate, recipe.allergens, limits)
        if category:  # None = contains a documented allergen: never offered
            picks.append((recipe, category, reasons))
    explanations, limitations = {}, [CATALOG_LIMITATION, "This is not a diet order. Ask your care team first."]
    if plan and picks:
        payload = {
            "plan": {**limits, "dietary_preferences": plan.dietary_preferences, "guidance": plan.guidance},
            "recipes": [
                {"id": str(r.id), "name": r.name, "nutrients": r.nutritional_estimate, "category": c, "reasons": why}
                for r, c, why in picks
            ],
        }
        output, errors, _ = _call_model(SUGGEST, payload)
        if output is not None:
            errors = validate_suggestions(output, payload)
        if errors:
            limitations = [*limitations, "The AI explanation was unavailable; the reasons shown are rule-based."]
        else:
            explanations = {e["recipe_id"]: e["text"] for e in output["explanations"]}
    created = [
        MealRecommendation.objects.create(
            patient=patient,
            nutrition_plan=plan,
            recipe=recipe,
            category=category,
            personalized=plan is not None,
            reasoning_summary=explanations.get(str(recipe.id), " ".join(reasons)),
            nutrient_estimates=recipe.nutritional_estimate,
            limitations=limitations,
            source_references=[recipe.source],
        )
        for recipe, category, reasons in picks
    ]
    if created:
        audit(user, "meal_suggestions_generated", None, patient=patient, count=len(created), plan=bool(plan))
        for dietitian in assigned_professionals(patient, Role.DIETITIAN) if plan else ():
            notify(
                dietitian, "nutrition_review", "Meal suggestions await review", None, f"sug:{created[0].id}", patient
            )
    return created


def _review(obj, clinician: User, approve: bool, action: str, patient: Patient) -> None:
    if obj.review_status not in (ReviewStatus.PENDING, ReviewStatus.AI_UNAVAILABLE):
        raise Conflict(f"Already '{obj.review_status}'.")
    obj.review_status = ReviewStatus.APPROVED if approve else ReviewStatus.REJECTED
    obj.reviewed_by = clinician
    audit(clinician, f"{action}_{obj.review_status}", obj, patient=patient)


@transaction.atomic
def review_recommendation(pk, clinician: User, approve: bool) -> MealRecommendation:
    rec = MealRecommendation.objects.select_for_update(of=("self",)).select_related("patient").get(pk=pk)
    _review(rec, clinician, approve, "meal_recommendation", rec.patient)
    rec.reviewed_at = timezone.now()
    rec.save()
    return rec


@transaction.atomic
def review_lab_review(pk, clinician: User, approve: bool, notes: str) -> FoodLabReview:
    review = FoodLabReview.objects.select_for_update(of=("self",)).select_related("patient").get(pk=pk)
    _review(review, clinician, approve, "food_lab_review", review.patient)
    review.review_notes = notes
    review.save()
    return review


# --- Food and laboratory review, periodic report ------------------------------------------------


def _number(value) -> float | None:
    return None if value is None else float(value)


def lab_facts(patient: Patient, start: date, end: date, released_only: bool = False) -> list[dict]:
    results = LaboratoryResult.objects.filter(
        report__patient=patient, report__collected_at__date__gte=start, report__collected_at__date__lte=end
    )
    if released_only:
        results = results.filter(report__released_to_patient=True)
    return [
        {
            "id": str(r.id),
            "report_id": str(r.report_id),
            "analyte": r.analyte,
            "value": float(r.value),
            "unit": r.unit,
            "reference_low": _number(r.reference_low),
            "reference_high": _number(r.reference_high),
            "collected_at": r.report.collected_at.isoformat(),
        }
        for r in results.select_related("report").order_by("report__collected_at", "analyte")
    ]


def session_facts(patient: Patient, start: date, end: date) -> list[dict]:
    sessions = DialysisSession.objects.filter(
        patient=patient, scheduled_start__date__gte=start, scheduled_start__date__lte=end
    ).order_by("scheduled_start")
    return [
        {
            "id": str(s.id),
            "date": s.scheduled_start.isoformat(),
            "status": s.status,
            "duration_minutes": round((s.ended_at - s.started_at).total_seconds() / 60)
            if s.started_at and s.ended_at
            else None,
            "uf_volume_ml": s.uf_volume_ml,
        }
        for s in sessions
    ]


def _fingerprint(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _limitations(summary: dict) -> list[str]:
    notes = [
        f"Meals were recorded on {summary['days_recorded']} of {summary['days_in_period']} days. "
        "Days without a record are unknown, not days without eating.",
        CATALOG_LIMITATION,
        NOT_CAUSAL,
    ]
    if summary["completeness"] < 0.5:
        notes.append("Fewer than half of the days have a meal record, so averages may not reflect usual eating.")
    return notes


def analyze(patient_id, start: date, end: date) -> FoodLabReview:
    """Place the diary next to laboratory results for a clinician. Same data => same review."""
    patient = Patient.objects.get(pk=patient_id)
    summary, labs = diary(patient, start, end), lab_facts(patient, start, end)
    sessions = session_facts(patient, start, end)
    samples = sorted({(lab["report_id"], lab["collected_at"]) for lab in labs}, key=lambda s: s[1])
    payload = {
        "patient": str(patient.id),
        "period": {"from": start.isoformat(), "to": end.isoformat()},
        "diary": summary,
        "laboratory_results": labs,
        "diary_before_each_sample": [
            {"report_id": report, **diary(patient, *engine.window_before(date.fromisoformat(at[:10])))}
            for report, at in samples
        ],
        "dialysis_sessions": sessions,
    }
    mark = _fingerprint(payload)
    review = FoodLabReview(
        patient=patient,
        date_from=start,
        date_to=end,
        meal_data_completeness=summary["completeness"],
        lab_result_references=[lab["id"] for lab in labs],
        dialysis_session_references=[s["id"] for s in sessions],
        nutrient_trends=summary,
        limitations=_limitations(summary),
        fingerprint=mark,
    )
    try:
        with transaction.atomic():
            review.save()
    except IntegrityError:  # already analysed (or a concurrent duplicate delivery)
        return FoodLabReview.objects.get(fingerprint=mark)

    if not labs or not summary["meals_recorded"]:
        errors, output, model_name = (
            [{"code": "insufficient_data", "path": "", "message": "Needs meals and labs."}],
            None,
            "",
        )
    else:
        output, errors, model_name = _call_model(ANALYZE, payload)
        if output is not None:
            errors = validate_analysis(output, payload)
    review.model_name = model_name
    if errors:
        review.review_status, review.ai_error = ReviewStatus.AI_UNAVAILABLE, errors
    else:
        review.possible_associations = output["observations"]
        review.questions = output["questions_for_clinician"]
        review.limitations = [*review.limitations, *output["limitations"]]
    review.save()
    audit(None, "food_lab_review_created", review, patient=patient, status=review.review_status)
    return review


def build_report(patient_id, start: date, end: date) -> NutritionReport:
    """Draft a periodic report: computed facts, plus a separate AI narrative when it passes validation."""
    patient = Patient.objects.get(pk=patient_id)
    summary, labs = diary(patient, start, end), lab_facts(patient, start, end)
    sessions, plan = session_facts(patient, start, end), active_plan(patient)
    payload = {
        "patient": str(patient.id),
        "period": {"from": start.isoformat(), "to": end.isoformat()},
        "diary": summary,
        "laboratory_results": labs,
        "dialysis_sessions": sessions,
        "counts": {"laboratory_results": len(labs), "dialysis_sessions": len(sessions)},
        "plan": {"prescribed_targets": plan.prescribed_targets, "guidance": plan.guidance} if plan else None,
    }
    mark = _fingerprint(payload)
    period = {"patient": patient, "period_start": start, "period_end": end}
    existing = NutritionReport.objects.filter(**period, fingerprint=mark).first()
    if existing:
        return existing
    averages = "daily_average_on_complete_days"
    report = NutritionReport(
        **period,
        version=NutritionReport.objects.filter(**period).count() + 1,
        meal_summary={k: v for k, v in summary.items() if k != averages},
        nutrient_summary={averages: summary[averages], "units": engine.UNITS},
        laboratory_summary=labs,
        dialysis_summary=sessions,
        fingerprint=mark,
    )
    try:
        with transaction.atomic():
            report.save()
    except IntegrityError:
        return NutritionReport.objects.get(**period, fingerprint=mark)
    output, errors, report.model_name = _call_model(REPORT, payload)
    if output is not None:
        errors = validate_report(output, payload)
    if errors:
        report.ai_error = errors
    else:
        report.ai_draft = {**output, "limitations": [*_limitations(payload["diary"]), *output["limitations"]]}
    report.save()
    audit(None, "nutrition_report_drafted", report, patient=patient, version=report.version, ai=not errors)
    return report


@transaction.atomic
def release_report(pk, clinician: User, clinician_review: str) -> NutritionReport:
    """The only path by which a nutrition report reaches the patient or a caregiver."""
    report = NutritionReport.objects.select_for_update(of=("self",)).select_related("patient__user").get(pk=pk)
    if report.release_status == "released":
        raise Conflict("Report is already released.")
    report.clinician_review, report.reviewed_by = clinician_review, clinician
    report.release_status, report.released_at = "released", timezone.now()
    report.save()
    audit(clinician, "nutrition_report_released", report, patient=report.patient)
    if report.patient.user:
        title = "A nutrition report is available"
        notify(report.patient.user, "nutrition_report", title, None, f"nr:{report.id}", report.patient)
    return report


def observe(patient: Patient, nurse: User, data: dict) -> NutritionObservation:
    observation = NutritionObservation.objects.create(patient=patient, author=nurse, **data)
    audit(nurse, "nutrition_observation_recorded", observation, patient=patient, referred=observation.referred)
    if observation.referred:
        title = "A nurse referred a nutrition concern"
        for role in (Role.DOCTOR, Role.DIETITIAN):
            for person in assigned_professionals(patient, role):
                notify(person, "nutrition_referral", title, None, f"no:{observation.id}", patient)
    return observation


def default_period(start: date | None, end: date | None) -> tuple[date, date]:
    end = end or timezone.localdate()
    return start or end - timedelta(days=29), end
