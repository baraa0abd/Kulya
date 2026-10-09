from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .engine import NUTRIENTS
from .models import (
    FoodItem,
    FoodLabReview,
    MealComponent,
    MealLog,
    MealRecommendation,
    NutrientEstimate,
    NutritionObservation,
    NutritionPlan,
    NutritionReport,
    Recipe,
)


class FoodSerializer(serializers.ModelSerializer):
    verified = serializers.SerializerMethodField()

    class Meta:
        model = FoodItem
        fields = ["id", "canonical_name", "localized_names", "nutrients_per_100g", "portion_grams", "allergens",
                  "nutrient_data_source", "verified"]  # fmt: skip
        read_only_fields = fields

    def get_verified(self, food: FoodItem) -> bool:
        return food.last_verified_at is not None


class RecipeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ["id", "name", "localized_names", "meal_type", "ingredients", "preparation_method", "servings",
                  "yield_weight", "allergens", "nutritional_estimate", "source"]  # fmt: skip
        read_only_fields = fields


class ComponentSerializer(serializers.ModelSerializer):
    food_name = serializers.CharField(source="food_item.canonical_name", read_only=True, default=None)
    quantity = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal("0.01"))

    class Meta:
        model = MealComponent
        fields = ["id", "food_item", "food_name", "name", "quantity", "unit", "estimated_grams", "portion_verified",
                  "preparation_details"]  # fmt: skip
        read_only_fields = ["id", "estimated_grams"]


class EstimateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NutrientEstimate
        fields = [*NUTRIENTS, "data_completeness", "estimation_method", "source_references"]
        read_only_fields = fields


class MealSerializer(serializers.ModelSerializer):
    patient = serializers.UUIDField(source="patient_id", required=False)  # scope is checked in the view
    components = ComponentSerializer(many=True, allow_empty=False, max_length=30)
    estimate = EstimateSerializer(read_only=True)
    created_by_name = serializers.CharField(source="created_by.display_name", read_only=True)
    media_used = serializers.ChoiceField(choices=["photo", "voice", ""], write_only=True, required=False)

    class Meta:
        model = MealLog
        fields = ["id", "patient", "meal_type", "consumed_at", "entry_method", "description", "confirmation_status",
                  "components", "estimate", "created_by_name", "media_used", "created_at"]  # fmt: skip
        read_only_fields = ["id", "confirmation_status", "created_at"]

    def validate_consumed_at(self, value):
        if value > timezone.now() + timedelta(days=1):
            raise serializers.ValidationError("A meal cannot be recorded for a future date.")
        return value


class PlanSerializer(serializers.ModelSerializer):
    approved_by_name = serializers.CharField(source="approved_by.display_name", read_only=True)

    class Meta:
        model = NutritionPlan
        fields = ["id", "patient", "version", "dialysis_modality", "prescribed_targets", "guidance",
                  "dietary_preferences", "allergies", "relevant_clinical_context", "approved_by_name", "approved_at",
                  "valid_from", "valid_until", "active"]  # fmt: skip
        read_only_fields = ["id", "patient", "version", "approved_by_name", "approved_at", "active"]
        extra_kwargs = {"valid_from": {"required": False}}

    def validate_prescribed_targets(self, value: dict) -> dict:
        """Only per-meal upper limits a clinician typed: {"<nutrient>_max": positive number}."""
        allowed = {f"{n}_max" for n in NUTRIENTS}
        for key, limit in value.items():
            if key not in allowed or isinstance(limit, bool) or not isinstance(limit, (int, float)) or limit <= 0:
                raise serializers.ValidationError(f"{key}: use one of {sorted(allowed)} with a positive number.")
        return value

    def _strings(self, value: list) -> list:
        if not all(isinstance(v, str) and len(v) <= 80 for v in value) or len(value) > 30:
            raise serializers.ValidationError("Expected a short list of words.")
        return [v.strip().lower() for v in value if v.strip()]

    validate_dietary_preferences = _strings

    def validate_allergies(self, value: list) -> list:
        aliases = {
            "سمك": "fish",
            "السمك": "fish",
            "أسماك": "fish",
            "حليب": "milk",
            "الحليب": "milk",
            "بيض": "egg",
            "البيض": "egg",
            "غلوتين": "gluten",
            "جلوتين": "gluten",
        }
        return sorted({aliases.get(word, word) for word in self._strings(value)})


class RecommendationSerializer(serializers.ModelSerializer):
    recipe = RecipeSerializer(read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.display_name", read_only=True, default=None)
    lab_based = serializers.SerializerMethodField()

    def get_lab_based(self, rec: MealRecommendation) -> bool:
        return rec.lab_report_id is not None

    class Meta:
        model = MealRecommendation
        fields = ["id", "patient", "nutrition_plan", "recipe", "category", "personalized", "lab_based",
                  "reasoning_summary", "nutrient_estimates", "limitations", "source_references", "review_status",
                  "reviewed_by_name", "reviewed_at", "created_at"]  # fmt: skip
        read_only_fields = fields


class FoodLabReviewSerializer(serializers.ModelSerializer):
    reviewed_by_name = serializers.CharField(source="reviewed_by.display_name", read_only=True, default=None)

    class Meta:
        model = FoodLabReview
        fields = ["id", "patient", "date_from", "date_to", "meal_data_completeness", "lab_result_references",
                  "nutrient_trends", "possible_associations", "limitations", "questions", "ai_error", "model_name",
                  "review_status", "reviewed_by_name", "review_notes", "created_at"]  # fmt: skip
        read_only_fields = fields


class ReportSerializer(serializers.ModelSerializer):
    reviewed_by_name = serializers.CharField(source="reviewed_by.display_name", read_only=True, default=None)
    patient_name = serializers.CharField(source="patient.full_name", read_only=True)

    class Meta:
        model = NutritionReport
        fields = ["id", "patient", "patient_name", "period_start", "period_end", "version", "meal_summary",
                  "nutrient_summary", "laboratory_summary", "dialysis_summary", "ai_draft", "ai_error", "model_name",
                  "clinician_review", "reviewed_by_name", "release_status", "released_at", "created_at"]  # fmt: skip
        read_only_fields = fields


class ObservationSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.display_name", read_only=True)

    class Meta:
        model = NutritionObservation
        fields = ["id", "patient", "author_name", "kind", "text", "referred", "created_at"]
        read_only_fields = ["id", "patient", "author_name", "created_at"]


class RecognizeSerializer(serializers.Serializer):
    patient = serializers.UUIDField(required=False)
    description = serializers.CharField(max_length=2000, allow_blank=True, default="")
    # Photos are resized in the browser; about 1.4 MB decoded is the ceiling here.
    image_base64 = serializers.CharField(max_length=1_900_000, required=False)
    image_media_type = serializers.ChoiceField(choices=["image/jpeg", "image/png", "image/webp"], default="image/jpeg")

    def validate(self, attrs: dict) -> dict:
        if not attrs["description"].strip() and not attrs.get("image_base64"):
            raise serializers.ValidationError("Describe the meal or attach a photo.")
        return attrs


class PeriodSerializer(serializers.Serializer):
    patient = serializers.UUIDField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)

    def validate(self, attrs: dict) -> dict:
        start, end = attrs.get("date_from"), attrs.get("date_to")
        if start and end and not (timedelta(0) <= end - start <= timedelta(days=92)):
            raise serializers.ValidationError("The period must be between 1 and 93 days.")
        return attrs


class DecisionSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    notes = serializers.CharField(max_length=2000, allow_blank=True, default="")


class ReleaseSerializer(serializers.Serializer):
    clinician_review = serializers.CharField(max_length=4000, allow_blank=True, default="")
