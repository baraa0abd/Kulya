"""Renal nutrition: deterministic arithmetic, authorization, AI safety, review and release rules."""

from datetime import date, timedelta

import pytest
from django.utils import timezone

import ai.gateway
from ai.provider import MockProvider, ProviderError
from clinical.models import CareAssignment, CaregiverConsent, LaboratoryReport, LaboratoryResult
from core.models import Role
from nutrition import catalog, engine, services, usda
from nutrition.ai import validate_analysis, validate_recognition, validate_report, validate_suggestions
from nutrition.models import FoodItem, FoodLabReview, MealLog, MealRecommendation, NutritionReport, Recipe
from workflow.models import Notification

API = "/api/nutrition"
TODAY = timezone.localdate()


@pytest.fixture
def foods(db) -> dict[str, FoodItem]:
    catalog.load_catalog()
    return {f.canonical_name: f for f in FoodItem.objects.all()}


@pytest.fixture
def dietitian(org, make_user, patient):
    user = make_user("diet", Role.DIETITIAN, org)
    CareAssignment.objects.create(patient=patient, professional=user)
    return user


@pytest.fixture
def consent(patient, family):
    def grant(*scopes: str, **extra) -> CaregiverConsent:
        return CaregiverConsent.objects.create(
            patient=patient, caregiver=family, scopes=list(scopes), granted_by=patient.user, **extra
        )

    return grant


@pytest.fixture
def scripted(monkeypatch):
    """Replace the provider: transform the mock output, or raise."""

    def install(transform=None, error: Exception | None = None) -> None:
        class Provider(MockProvider):
            def complete_json(self, prompt_id, payload, image=None):
                if error:
                    raise error
                return transform(super().complete_json(prompt_id, payload, image))

        monkeypatch.setattr(ai.gateway, "get_provider", Provider)

    return install


def meal_body(foods, *parts, days_ago: int = 0, **extra) -> dict:
    """parts: (catalogue name or free text, quantity, unit)."""
    return {
        "meal_type": "lunch",
        "consumed_at": (timezone.now() - timedelta(days=days_ago, minutes=5)).isoformat(),
        "components": [
            {
                "food_item": str(foods[name].id) if name in foods else None,
                "name": name,
                "quantity": quantity,
                "unit": unit,
                "portion_verified": True,
            }
            for name, quantity, unit in parts
        ],
        **extra,
    }


def log(api, user, foods, *parts, **extra):
    return api(user).post(f"{API}/meals/", meal_body(foods, *parts, **extra), format="json")


def add_labs(patient, doctor, released: bool, days_ago: int = 1) -> LaboratoryReport:
    at = timezone.now() - timedelta(days=days_ago)
    report = LaboratoryReport.objects.create(
        patient=patient, collected_at=at, reported_at=at, source="t", entered_by=doctor, released_to_patient=released
    )
    for analyte, value, unit in (("Potassium", "5.2", "mmol/L"), ("Phosphate", "5.4", "mg/dL")):
        LaboratoryResult.objects.create(report=report, analyte=analyte, value=value, unit=unit)
    return report


# --- deterministic engine --------------------------------------------------------------------


def test_unknown_nutrients_stay_unknown_and_are_never_zero() -> None:
    known = {n: 10 for n in engine.NUTRIENTS}
    result = engine.estimate(
        [{"grams": 200, "per_100g": known}, {"grams": 50, "per_100g": {**known, "potassium_mg": None}}]
    )
    assert result["totals"]["protein_g"] == 25.0
    assert result["totals"]["potassium_mg"] is None and result["completeness"]["potassium_mg"] == 0.5
    unmatched = engine.estimate([{"grams": None, "per_100g": None}])
    assert set(unmatched["totals"].values()) == {None}
    assert engine.grams_for(2, "Piece", {"piece": 50}) == 100 and engine.grams_for(1, "bowl", {"piece": 50}) is None


def test_missing_diary_days_are_reported_not_counted_as_zero() -> None:
    start = date(2026, 1, 1)
    totals = dict.fromkeys(engine.NUTRIENTS, 100.0)
    meals = [
        {"day": start, "meal_type": "lunch", "totals": totals, "foods": ["rice"]},
        {"day": start + timedelta(days=2), "meal_type": "lunch", "totals": {**totals, "sodium_mg": None}, "foods": []},
    ]
    summary = engine.diary_summary(meals, start, start + timedelta(days=3))
    assert summary["days_recorded"] == 2 and summary["completeness"] == 0.5
    assert summary["missing_days"] == ["2026-01-02", "2026-01-04"]
    averages = summary["daily_average_on_complete_days"]
    assert averages["protein_g"] == 100.0  # 200 over the 2 recorded days, not over 4
    # The day with an unknown sodium value is left out of that average instead of counting as zero.
    assert averages["sodium_mg"] == 100.0 and summary["days_with_complete_data"]["sodium_mg"] == 1
    nothing_known = engine.diary_summary([{**meals[1], "day": start}], start, start)
    assert nothing_known["daily_average_on_complete_days"]["sodium_mg"] is None


def test_recipe_classification_uses_only_the_clinicians_limits() -> None:
    nutrients = {"potassium_mg": 800.0, "sodium_mg": 100.0, "phosphorus_mg": None}
    assert engine.classify_recipe(nutrients, [], None)[0] == "general"
    assert engine.classify_recipe(nutrients, ["milk"], {"allergies": ["Milk"], "prescribed_targets": {}})[0] is None
    plan = {"allergies": [], "prescribed_targets": {"potassium_mg_max": 700}}
    assert engine.classify_recipe(nutrients, [], plan)[0] == "needs_dietitian_review"
    plan["prescribed_targets"] = {"phosphorus_mg_max": 300}
    assert engine.classify_recipe(nutrients, [], plan)[0] == "check_portion"
    plan["prescribed_targets"] = {"sodium_mg_max": 600}
    assert engine.classify_recipe(nutrients, [], plan)[0] == "compatible"
    assert engine.classify_recipe(nutrients, [], {"allergies": [], "prescribed_targets": {}})[0] == "compatible"


def test_food_matching_handles_arabic_and_plurals(foods) -> None:
    assert catalog.match_food("boiled eggs").canonical_name == "egg, boiled"
    assert catalog.match_food("رز").canonical_name == "white rice, cooked"
    assert catalog.match_food("خُبز").canonical_name == "flatbread (khubz)"  # diacritics folded
    assert catalog.match_food("spaceship") is None


# --- diary ------------------------------------------------------------------------------------


def test_meal_estimate_is_computed_by_the_server(api, patient, foods) -> None:
    body = meal_body(foods, ("white rice, cooked", 1, "cup"), ("egg, boiled", 2, "piece"))
    body["estimate"] = {"potassium_mg": 1}  # a client cannot supply nutrient values
    response = api(patient.user).post(f"{API}/meals/", body, format="json")
    assert response.status_code == 201, response.content
    meal = response.json()
    assert meal["confirmation_status"] == "confirmed"
    assert meal["estimate"]["potassium_mg"] == round(158 * 35 / 100 + 100 * 126 / 100, 1)
    assert meal["estimate"]["estimation_method"] == "catalogue_per_100g_x_grams"
    assert [c["estimated_grams"] for c in meal["components"]] == ["158.0", "100.0"]


def test_linked_food_name_cannot_disagree_with_calculated_nutrients(api, patient, foods) -> None:
    body = meal_body(foods, ("cucumber", 1, "piece"))
    body["components"][0]["name"] = "unrelated food label"
    meal = api(patient.user).post(f"{API}/meals/", body, format="json").json()
    assert meal["components"][0]["name"] == "cucumber"
    assert meal["estimate"]["potassium_mg"] == 147.0


def test_arabic_portion_recognition(api, patient, foods) -> None:
    response = api(patient.user).post(f"{API}/ai/recognize/", {"description": "٢ حبة بيض، ١٫٥ كوب رز"}, "json")
    assert response.status_code == 200
    items = response.json()["items"]
    assert [(item["quantity"], item["unit"]) for item in items] == [(2.0, "piece"), (1.5, "cup")]
    assert items[0]["food_name"] == "egg, boiled"
    assert items[1]["food_name"] == "white rice, cooked"


def test_arabic_allergies_use_catalogue_codes() -> None:
    from nutrition.serializers import PlanSerializer

    plan = PlanSerializer(data={"allergies": ["سمك", "حليب", "بيض", "غلوتين"]}, partial=True)
    assert plan.is_valid(), plan.errors
    assert set(plan.validated_data["allergies"]) == {"fish", "milk", "egg", "gluten"}
    assert engine.classify_recipe({}, ["fish"], {"allergies": plan.validated_data["allergies"]})[0] is None


def test_unmatched_food_and_missing_data_are_flagged(api, patient, foods) -> None:
    meal = log(api, patient.user, foods, ("homemade kubba", 2, "piece"), ("white rice, cooked", 1, "cup")).json()
    assert meal["confirmation_status"] == "needs_review"
    assert meal["estimate"]["energy_kcal"] is None and meal["estimate"]["data_completeness"]["energy_kcal"] == 0.5
    bread = log(api, patient.user, foods, ("samoon bread", 1, "piece")).json()
    assert bread["estimate"]["sodium_mg"] == 432.0 and bread["estimate"]["potassium_mg"] is None


def test_meal_can_be_corrected_and_withdrawn(api, patient, foods) -> None:
    client = api(patient.user)
    meal = log(api, patient.user, foods, ("cucumber", 1, "piece")).json()
    fixed = client.patch(
        f"{API}/meals/{meal['id']}/", {"components": meal_body(foods, ("cucumber", 2, "piece"))["components"]}, "json"
    )
    assert fixed.status_code == 200 and fixed.json()["estimate"]["potassium_mg"] == 294.0
    assert client.delete(f"{API}/meals/{meal['id']}/").status_code == 204
    assert client.get(f"{API}/meals/").json() == []
    assert MealLog.objects.filter(pk=meal["id"], deleted_at__isnull=False).exists()  # withdrawn, not erased
    assert log(api, patient.user, foods, ("cucumber", 1, "piece"), days_ago=-3).status_code == 400  # future date


def test_recognition_proposes_and_saves_nothing(api, patient, foods) -> None:
    response = api(patient.user).post(
        f"{API}/ai/recognize/", {"description": "2 boiled eggs and 1 cup rice, bread"}, "json"
    )
    assert response.status_code == 200, response.content
    items = response.json()["items"]
    assert [(i["food_name"], i["quantity"], i["unit"]) for i in items[:2]] == [
        ("egg, boiled", 2.0, "piece"),
        ("white rice, cooked", 1.0, "cup"),
    ]
    assert all(i["needs_confirmation"] for i in items) and items[0]["estimated_grams"] == 100.0
    assert MealLog.objects.count() == 0
    photo = api(patient.user).post(f"{API}/ai/recognize/", {"image_base64": "aGVsbG8="}, "json").json()
    assert photo["items"] == [] and "cannot read photos" in photo["uncertainties"][0]
    assert api(patient.user).post(f"{API}/ai/recognize/", {"image_base64": "not base64!"}, "json").status_code == 400
    assert api(patient.user).post(f"{API}/ai/recognize/", {"description": " "}, "json").status_code == 400
    assert api(patient.user).post(f"{API}/ai/transcribe/").status_code == 501


def test_recognition_failure_or_smuggled_nutrients_fall_back_to_manual_entry(api, patient, foods, scripted) -> None:
    scripted(error=ProviderError("down"))
    body = {"description": "rice"}
    assert api(patient.user).post(f"{API}/ai/recognize/", body, "json").json()["ai_unavailable"] is True
    scripted(transform=lambda out: {**out, "items": [{**out["items"][0], "potassium_mg": 5}]})
    assert api(patient.user).post(f"{API}/ai/recognize/", body, "json").json()["ai_unavailable"] is True
    assert validate_recognition({"items": [], "uncertainties": ["You should stop eating bread."]})
    assert log(api, patient.user, foods, ("white rice, cooked", 1, "cup")).status_code == 201  # manual path works


# --- authorization ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["overview", "foods", "recipes", "meals", "ai/suggestions"])
def test_unauthenticated_is_rejected(api, db, path) -> None:
    assert api().get(f"{API}/{path}/").status_code == 401


def test_care_team_scope_and_tenant_isolation(
    api, patient, other_patient, foods, doctor, nurse, dietitian, other_doctor, foreign_doctor, make_user, org
) -> None:
    meal = log(api, patient.user, foods, ("cucumber", 1, "piece")).json()
    query = f"?patient={patient.id}"
    for member in (doctor, nurse, dietitian):
        assert len(api(member).get(f"{API}/meals/{query}").json()) == 1
        assert api(member).get(f"{API}/meals/{meal['id']}/").status_code == 200
        assert api(member).post(f"{API}/meals/", meal_body(foods), "json").status_code == 403  # diary is the patient's
    unassigned = make_user("diet2", Role.DIETITIAN, org)
    for outsider in (other_doctor, foreign_doctor, unassigned, other_patient.user):
        client = api(outsider)
        assert client.get(f"{API}/meals/{query}").status_code == 404
        assert client.get(f"{API}/meals/{meal['id']}/").status_code == 404
        assert client.get(f"{API}/overview/{query}").status_code == 404
        for sub in ("plans", "lab-trends", "reports"):
            assert client.get(f"{API}/patients/{patient.id}/{sub}/").status_code == 404
    assert api(other_patient.user).delete(f"{API}/meals/{meal['id']}/").status_code == 404
    assert [r["patient"] for r in api(dietitian).get(f"{API}/overview/").json()] == [str(patient.id)]
    assert api(doctor).get(f"{API}/meals/?patient=not-a-uuid").status_code == 404
    # The new role reaches patients through assignment only, and gains no dialysis documentation rights.
    assert len(api(dietitian).get("/api/patients/").json()["results"]) == 1
    assert api(dietitian).get("/api/sessions/").status_code == 403
    assert api(dietitian).get("/api/nursing-notes/").status_code == 403


def test_family_access_follows_consent_scopes(api, patient, family, foods, consent) -> None:
    client, query = api(family), f"?patient={patient.id}"
    log(api, patient.user, foods, ("cucumber", 1, "piece"))
    assert client.get(f"{API}/meals/{query}").status_code == 404  # no grant
    grant = consent("appointments")
    assert client.get(f"{API}/meals/{query}").status_code == 404  # a grant without the nutrition scope
    grant.scopes = ["nutrition"]
    grant.save()
    assert len(client.get(f"{API}/meals/{query}").json()) == 1
    assert client.get(f"{API}/overview/{query}").json()["can_log"] is False
    body = {**meal_body(foods, ("tomato", 1, "piece")), "patient": str(patient.id)}
    assert client.post(f"{API}/meals/", body, "json").status_code == 404  # reading is not logging
    grant.scopes = ["nutrition", "nutrition_log"]
    grant.save()
    created = client.post(f"{API}/meals/", body, "json")
    assert created.status_code == 201 and created.json()["created_by_name"] == "Fam"
    assert client.get(f"{API}/patients/{patient.id}/lab-trends/").json()["laboratory_results"] == []  # no labs scope
    grant.revoked_at = timezone.now()
    grant.save()
    assert client.get(f"{API}/meals/{query}").status_code == 404
    assert client.post(f"{API}/meals/", body, "json").status_code == 404


def test_expired_consent_gives_no_nutrition_access(api, patient, family, consent) -> None:
    consent("nutrition", "nutrition_log", expires_at=timezone.now() - timedelta(minutes=1))
    assert api(family).get(f"{API}/meals/?patient={patient.id}").status_code == 404
    assert api(family).get(f"{API}/overview/").json() == []


# --- plans and suggestions -------------------------------------------------------------------


def test_only_doctor_or_dietitian_approves_plans(api, patient, doctor, nurse, dietitian, other_doctor) -> None:
    url = f"{API}/patients/{patient.id}/plans/"
    body = {"prescribed_targets": {"potassium_mg_max": 700}, "allergies": ["Fish"], "guidance": "Demo."}
    for user, expected in ((nurse, 403), (patient.user, 403), (other_doctor, 404)):
        assert api(user).post(url, body, "json").status_code == expected
    first = api(dietitian).post(url, body, "json")
    assert first.status_code == 201 and first.json()["version"] == 1 and first.json()["allergies"] == ["fish"]
    second = api(doctor).post(url, {**body, "prescribed_targets": {"sodium_mg_max": 500}}, "json").json()
    assert second["version"] == 2 and second["approved_by_name"] == "Doc"
    plans = api(patient.user).get(url).json()
    assert [(p["version"], p["active"]) for p in plans] == [(2, True), (1, False)]  # old version kept, retired
    for bad in ({"vitamin_max": 5}, {"potassium_mg_max": -1}, {"potassium_mg_max": True}, {"potassium_mg": 5}):
        assert api(dietitian).post(url, {"prescribed_targets": bad}, "json").status_code == 400


def test_without_a_plan_suggestions_are_general(api, patient, foods) -> None:
    recs = api(patient.user).post(f"{API}/ai/suggestions/", {}, "json").json()
    assert len(recs) == Recipe.objects.count()
    assert {(r["category"], r["personalized"]) for r in recs} == {("general", False)}
    assert "not personalized" in recs[0]["reasoning_summary"]
    assert len(api(patient.user).post(f"{API}/ai/suggestions/", {}, "json").json()) == len(recs)  # idempotent
    assert MealRecommendation.objects.count() == len(recs)


def test_personalized_suggestions_wait_for_a_clinician(api, patient, foods, dietitian, nurse) -> None:
    services.approve_plan(
        patient, dietitian, {"prescribed_targets": {"potassium_mg_max": 500}, "allergies": ["fish", "milk"]}
    )
    assert api(patient.user).post(f"{API}/ai/suggestions/", {}, "json").json() == []  # nothing unreviewed is shown
    recs = api(dietitian).get(f"{API}/ai/suggestions/?patient={patient.id}").json()
    assert recs and {r["review_status"] for r in recs} == {"pending"} and all(r["personalized"] for r in recs)
    assert not {"fish", "milk"} & {a for r in recs for a in r["recipe"]["allergens"]}  # allergens never offered
    category = {r["recipe"]["name"]: r["category"] for r in recs}
    assert category["Lentil soup"] == "needs_dietitian_review"  # 597.4 mg potassium, over the 500 mg limit
    assert category["Grilled chicken with rice and cucumber"] == "compatible"  # 455.6 mg
    assert Notification.objects.filter(recipient=dietitian, kind="meal_ideas").count() == 1
    pick, other = recs[0], recs[1]
    url = f"{API}/recommendations/{pick['id']}/review/"
    assert api(nurse).post(url, {"approve": True}, "json").status_code == 403
    assert api(patient.user).post(url, {"approve": True}, "json").status_code == 403
    assert api(dietitian).post(url, {"approve": True}, "json").json()["review_status"] == "approved"
    assert api(dietitian).post(url, {"approve": True}, "json").status_code == 409
    api(dietitian).post(f"{API}/recommendations/{other['id']}/review/", {"approve": False}, "json")
    assert [r["id"] for r in api(patient.user).get(f"{API}/ai/suggestions/").json()] == [pick["id"]]


def test_suggestion_text_is_rule_based_when_the_model_fails(patient, foods, dietitian, scripted) -> None:
    services.approve_plan(patient, dietitian, {"prescribed_targets": {"potassium_mg_max": 700}})
    scripted(transform=lambda out: {"explanations": [{**out["explanations"][0], "text": "Safe for you, eat 9999 g."}]})
    recs = services.suggest(patient, dietitian)
    assert recs and all("9999" not in r.reasoning_summary for r in recs)
    assert any("rule-based" in note for note in recs[0].limitations)


# --- AI safety --------------------------------------------------------------------------------


def _analysis_payload() -> dict:
    return {
        "diary": {"daily_average_on_complete_days": {"potassium_mg": 1500.5}},
        "laboratory_results": [{"id": "lab-1", "analyte": "Potassium", "value": 5.2, "unit": "mmol/L"}],
    }


def _analysis(text: str, ids=("lab-1",)) -> dict:
    return {
        "observations": [{"text": text, "nutrient": "potassium_mg", "lab_result_ids": list(ids)}],
        "limitations": [],
        "questions_for_clinician": [],
        "requires_clinician_review": True,
    }


def test_analysis_validation_rejects_unsafe_output() -> None:
    payload = _analysis_payload()
    ok = "Average recorded potassium was 1500.5 mg; the potassium result was 5.2 mmol/L. No cause is implied."
    assert validate_analysis(_analysis(ok), payload) == []

    def codes(text: str, **kwargs) -> set[str]:
        return {e["code"] for e in validate_analysis(_analysis(text, **kwargs), payload)}

    assert codes("The bananas caused the potassium of 5.2 mmol/L.") == {"unsupported_clinical_claim"}
    assert codes("Potassium is 5.2 mmol/L due to dates.") == {"unsupported_clinical_claim"}
    assert codes("Protein intake explains the creatinine level.") == {"unsupported_clinical_claim"}
    assert codes("The patient should receive a phosphate binder.") == {"unsupported_clinical_claim"}
    assert codes("You should stop eating tomatoes.") == {"unsupported_clinical_claim"}
    assert codes("Average recorded potassium was 2400 mg.") == {"ungrounded_number"}
    assert codes(ok, ids=("lab-999",)) == {"unknown_source_record"}
    assert codes(ok, ids=()) == {"schema_invalid"}
    assert validate_analysis({**_analysis(ok), "diagnosis": "x"}, payload)[0]["code"] == "schema_invalid"


def test_report_and_suggestion_validation() -> None:
    payload = {"diary": {"days_recorded": 3}, "recipes": [{"id": "r1"}]}
    report = {"overview": "Meals were recorded on 3 days.", "observations": [], "questions_for_care_team": [],
              "limitations": [], "verification_status": "unverified"}  # fmt: skip
    assert validate_report(report, payload) == []
    assert validate_report({**report, "verification_status": "verified"}, payload)[0]["code"] == "schema_invalid"
    assert validate_report({**report, "overview": "Take the medication with 3 meals."}, payload)
    assert (
        validate_report({**report, "observations": ["Recorded on 12 days."]}, payload)[0]["code"] == "ungrounded_number"
    )
    assert (
        validate_suggestions({"explanations": [{"recipe_id": "r1", "text": "Within the plan limits."}]}, payload) == []
    )
    bad = validate_suggestions({"explanations": [{"recipe_id": "r2", "text": "This meal is safe for you."}]}, payload)
    assert {e["code"] for e in bad} == {"unknown_source_record", "unsupported_clinical_claim"}


def test_food_lab_review_is_a_grounded_draft_and_idempotent(api, patient, foods, doctor, dietitian, nurse) -> None:
    log(api, patient.user, foods, ("white rice, cooked", 1, "cup"), days_ago=2)
    add_labs(patient, doctor, released=False)
    body = {"patient": str(patient.id)}
    assert api(nurse).post(f"{API}/ai/analyze/", body, "json").status_code == 403
    assert api(patient.user).post(f"{API}/ai/analyze/", body, "json").status_code == 403
    review = api(dietitian).post(f"{API}/ai/analyze/", body, "json")
    assert review.status_code == 200, review.content
    data = review.json()
    assert data["review_status"] == "pending" and data["meal_data_completeness"] == round(1 / 30, 2)
    assert len(data["possible_associations"]) == 2 and "no cause is implied" in data["possible_associations"][0]["text"]
    assert any("does not show that any food changed" in note for note in data["limitations"])
    assert any("Fewer than half" in note for note in data["limitations"])
    assert api(doctor).post(f"{API}/ai/analyze/", body, "json").json()["id"] == data["id"]  # same data, same review
    assert FoodLabReview.objects.count() == 1

    trends = f"{API}/patients/{patient.id}/lab-trends/"
    assert len(api(doctor).get(trends).json()["laboratory_results"]) == 2
    mine = api(patient.user).get(trends).json()
    assert mine["laboratory_results"] == [] and mine["reviews"] == []  # unreleased labs, unapproved draft
    decide = f"{API}/lab-reviews/{data['id']}/review/"
    assert api(nurse).post(decide, {"approve": True}, "json").status_code == 403
    assert api(doctor).post(decide, {"approve": True, "notes": "Seen."}, "json").json()["review_status"] == "approved"
    assert len(api(patient.user).get(trends).json()["reviews"]) == 1


def test_rejected_or_failed_analysis_keeps_the_facts(patient, foods, doctor, api, scripted) -> None:
    log(api, patient.user, foods, ("white rice, cooked", 1, "cup"), days_ago=1)
    empty = services.analyze(patient.id, TODAY - timedelta(days=5), TODAY)  # no labs yet: the model is not asked
    assert empty.review_status == "ai_unavailable" and empty.ai_error[0]["code"] == "insufficient_data"
    add_labs(patient, doctor, released=True)

    def causal(out: dict) -> dict:
        out["observations"][0]["text"] = "Rice caused the high potassium."
        return out

    scripted(transform=causal)
    review = services.analyze(patient.id, TODAY - timedelta(days=6), TODAY)
    assert review.review_status == "ai_unavailable" and review.possible_associations == []
    assert review.ai_error[0]["code"] == "unsupported_clinical_claim"
    assert review.nutrient_trends["meals_recorded"] == 1  # deterministic part is still there
    scripted(error=ProviderError("timeout"))
    assert services.analyze(patient.id, TODAY - timedelta(days=7), TODAY).ai_error[0]["code"] == "provider_error"


def test_report_is_drafted_reviewed_then_released(
    api, patient, foods, doctor, dietitian, nurse, consent, family
) -> None:
    log(api, patient.user, foods, ("white rice, cooked", 1, "cup"), days_ago=1)
    released_labs, hidden_labs = add_labs(patient, doctor, True, 3), add_labs(patient, doctor, False, 2)
    base = f"{API}/patients/{patient.id}/reports/"
    assert api(nurse).post(f"{base}generate/", {}, "json").status_code == 403
    report = api(dietitian).post(f"{base}generate/", {}, "json")
    assert report.status_code == 200, report.content
    data = report.json()
    assert data["release_status"] == "draft" and data["ai_draft"]["verification_status"] == "unverified"
    assert data["meal_summary"]["days_recorded"] == 1 and len(data["laboratory_summary"]) == 4
    assert data["nutrient_summary"]["daily_average_on_complete_days"]["potassium_mg"] == 55.3
    assert api(doctor).post(f"{base}generate/", {}, "json").json()["id"] == data["id"]  # unchanged data
    assert NutritionReport.objects.count() == 1
    consent("nutrition")
    assert api(patient.user).get(base).json() == [] and api(family).get(base).json() == []  # drafts stay internal

    release = f"{API}/reports/{data['id']}/release/"
    assert api(nurse).post(release, {}, "json").status_code == 403
    assert api(patient.user).post(release, {}, "json").status_code == 403
    done = api(dietitian).post(release, {"clinician_review": "Reviewed with the patient."}, "json").json()
    assert done["release_status"] == "released" and done["reviewed_by_name"] == "Diet"
    assert api(dietitian).post(release, {}, "json").status_code == 409
    assert Notification.objects.filter(recipient=patient.user, kind="nutrition_report").count() == 1
    mine = api(patient.user).get(base).json()[0]
    assert {lab["report_id"] for lab in mine["laboratory_summary"]} == {str(released_labs.id)}  # not hidden_labs
    assert hidden_labs.id and api(family).get(base).json()[0]["laboratory_summary"] == []  # no labs scope

    log(api, patient.user, foods, ("tomato", 1, "piece"))  # new data => a new version, the old one is kept
    assert api(doctor).post(f"{base}generate/", {}, "json").json()["version"] == 2


def test_report_without_ai_still_has_the_facts(patient, foods, api, scripted) -> None:
    log(api, patient.user, foods, ("white rice, cooked", 1, "cup"))
    scripted(transform=lambda out: {**out, "overview": "The patient must take 40 mg of medicine."})
    report = services.build_report(patient.id, TODAY - timedelta(days=6), TODAY)
    assert report.ai_draft is None and {e["code"] for e in report.ai_error} >= {"unsupported_clinical_claim"}
    assert report.meal_summary["meals_recorded"] == 1


# --- nurse observations, USDA -------------------------------------------------------------------


def test_nurse_observation_and_referral(api, patient, nurse, doctor, dietitian) -> None:
    url = f"{API}/patients/{patient.id}/observations/"
    body = {"kind": "nausea", "text": "Reports nausea after meals.", "referred": True}
    assert api(doctor).post(url, body, "json").status_code == 403
    assert api(nurse).post(url, body, "json").status_code == 201
    assert api(patient.user).get(url).status_code == 403
    assert len(api(dietitian).get(url).json()) == 1
    for person in (doctor, dietitian):
        assert Notification.objects.filter(recipient=person, kind="nutrition_referral").count() == 1
    assert api(dietitian).get(f"{API}/overview/").json()[0]["referrals"] == 1


def test_usda_lookup_is_off_without_a_key_and_keeps_unknowns(api, dietitian, patient, settings, monkeypatch) -> None:
    calls = []

    def fake_fetch(query: str) -> dict:
        calls.append(query)
        nutrients = [{"nutrientNumber": "306", "value": 358}, {"nutrientNumber": "208", "value": 89}]
        return {"foods": [{"fdcId": 1105314, "description": "Bananas, raw", "foodNutrients": nutrients}]}

    monkeypatch.setattr(usda, "fetch", fake_fetch)
    assert usda.search("banana") == [] and calls == []  # no key: nothing leaves the server
    settings.USDA_API_KEY = "test-key"
    found = api(dietitian).get(f"{API}/foods/?q=banana&source=usda").json()
    assert found[0]["nutrient_data_source"] == "USDA FoodData Central, FDC ID 1105314"
    assert found[0]["nutrients_per_100g"]["potassium_mg"] == 358
    assert found[0]["nutrients_per_100g"]["phosphorus_mg"] is None  # not reported => unknown, never 0
    api(dietitian).get(f"{API}/foods/?q=banana&source=usda")
    assert calls == ["banana"] and FoodItem.objects.count() == 1  # cached, and not duplicated
    assert api(patient.user).get(f"{API}/foods/?q=banana&source=usda").status_code == 200 and calls == ["banana"]

    def broken(query: str) -> dict:
        raise TimeoutError

    monkeypatch.setattr(usda, "fetch", broken)
    assert usda.search("apple") == []
