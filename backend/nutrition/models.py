"""Renal nutrition: food diary, nutrient estimates, clinician-approved plans, AI drafts.

Everything the AI writes here (recommendations, food/lab reviews, reports) is a draft until a
dietitian or doctor reviews it. Nutrient numbers always come from the food catalogue through
deterministic arithmetic, and an unknown nutrient stays unknown (null), never zero."""

from django.conf import settings
from django.db import models

from clinical.models import Patient
from core.models import UUIDModel

USER = settings.AUTH_USER_MODEL
NUTRIENTS = ["energy_kcal", "protein_g", "sodium_mg", "potassium_mg", "phosphorus_mg", "calcium_mg", "fluid_ml"]


class FoodItem(UUIDModel):
    canonical_name = models.CharField(max_length=120, unique=True)
    localized_names = models.JSONField(default=dict)  # {"ar": ..., "ckb": ..., "en": ...}
    food_database_id = models.CharField(max_length=60, blank=True)  # e.g. USDA FDC id when imported
    nutrient_data_source = models.CharField(max_length=120)  # provenance of the numbers below
    nutrients_per_100g = models.JSONField(default=dict)  # NUTRIENTS keys; null = not available
    portion_grams = models.JSONField(default=dict)  # {"piece": 50, "cup": 158, ...}
    allergens = models.JSONField(default=list)
    last_verified_at = models.DateTimeField(null=True, blank=True)  # null = not verified by anyone

    class Meta:
        ordering = ["canonical_name"]

    def __str__(self) -> str:
        return self.canonical_name


class MealType(models.TextChoices):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class Recipe(UUIDModel):
    name = models.CharField(max_length=160, unique=True)
    localized_names = models.JSONField(default=dict)
    meal_type = models.CharField(max_length=10, choices=MealType.choices)
    ingredients = models.JSONField(default=list)  # [{"food": canonical_name, "grams": n}]
    preparation_method = models.JSONField(default=list)  # ordered steps
    servings = models.PositiveSmallIntegerField(default=1)
    yield_weight = models.PositiveIntegerField(null=True, blank=True)  # grams, when known
    allergens = models.JSONField(default=list)
    nutritional_estimate = models.JSONField(default=dict)  # per serving, computed from ingredients
    source = models.CharField(max_length=160)

    class Meta:
        ordering = ["name"]


class MealLog(UUIDModel):
    """One meal in a patient's diary. Saved only after the person confirmed what the AI proposed."""

    class EntryMethod(models.TextChoices):
        TEXT = "text"
        VOICE = "voice"
        PHOTO = "photo"
        SAVED = "saved_meal"

    class Confirmation(models.TextChoices):
        CONFIRMED = "confirmed"  # the patient or caregiver checked foods and portions
        NEEDS_REVIEW = "needs_review"  # saved with at least one unconfirmed portion or unknown food

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="meals")
    created_by = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="+")
    meal_type = models.CharField(max_length=10, choices=MealType.choices)
    consumed_at = models.DateTimeField()
    entry_method = models.CharField(max_length=12, choices=EntryMethod.choices, default=EntryMethod.TEXT)
    description = models.TextField(blank=True)
    confirmation_status = models.CharField(max_length=14, choices=Confirmation.choices)
    deleted_at = models.DateTimeField(null=True, blank=True)  # diary entries are withdrawn, not erased

    class Meta:
        ordering = ["-consumed_at"]
        indexes = [models.Index(fields=["patient", "consumed_at"])]


class MealComponent(UUIDModel):
    meal = models.ForeignKey(MealLog, on_delete=models.CASCADE, related_name="components")
    # Null when the food could not be matched to the catalogue: its nutrients are then unknown.
    food_item = models.ForeignKey(FoodItem, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    name = models.CharField(max_length=160)  # what the person called it
    quantity = models.DecimalField(max_digits=7, decimal_places=2)
    unit = models.CharField(max_length=20)
    estimated_grams = models.DecimalField(max_digits=7, decimal_places=1, null=True, blank=True)
    portion_verified = models.BooleanField(default=False)
    preparation_details = models.CharField(max_length=200, blank=True)


class MealMedia(UUIDModel):
    """Records that a photo or voice clip was used. The file itself is not kept by default."""

    meal = models.ForeignKey(MealLog, on_delete=models.CASCADE, related_name="media")
    media_type = models.CharField(max_length=10)  # photo | voice
    storage_reference = models.CharField(max_length=300, blank=True)  # empty = not stored
    consent_status = models.CharField(max_length=20, default="processing_only")
    retention_policy = models.CharField(max_length=40, default="not_stored")


class NutrientEstimate(UUIDModel):
    meal = models.OneToOneField(MealLog, on_delete=models.CASCADE, related_name="estimate")
    energy_kcal = models.FloatField(null=True)
    protein_g = models.FloatField(null=True)
    sodium_mg = models.FloatField(null=True)
    potassium_mg = models.FloatField(null=True)
    phosphorus_mg = models.FloatField(null=True)
    calcium_mg = models.FloatField(null=True)
    fluid_ml = models.FloatField(null=True)
    data_completeness = models.JSONField(default=dict)  # nutrient -> share of components with data (0..1)
    estimation_method = models.CharField(max_length=60)
    source_references = models.JSONField(default=list)
    calculated_at = models.DateTimeField(auto_now=True)


class NutritionPlan(UUIDModel):
    """Individual plan written and approved by a clinician. Versioned; AI never creates or edits one."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="nutrition_plans")
    version = models.PositiveIntegerField()
    dialysis_modality = models.CharField(max_length=40, default="hemodialysis")
    # Hard per-meal limits chosen by the clinician, e.g. {"potassium_mg_max": 700}. Empty = none set.
    prescribed_targets = models.JSONField(default=dict)
    guidance = models.TextField(blank=True)  # the clinician's own words, shown to the patient
    dietary_preferences = models.JSONField(default=list)
    allergies = models.JSONField(default=list)
    relevant_clinical_context = models.TextField(blank=True)
    approved_by = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="+")
    approved_at = models.DateTimeField()
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-version"]
        constraints = [models.UniqueConstraint(fields=["patient", "version"], name="unique_nutrition_plan_version")]


class ReviewStatus(models.TextChoices):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AI_UNAVAILABLE = "ai_unavailable"


class MealRecommendation(UUIDModel):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="meal_recommendations")
    nutrition_plan = models.ForeignKey(NutritionPlan, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    recipe = models.ForeignKey(Recipe, on_delete=models.PROTECT, related_name="+")
    # Set when the idea was ordered by this laboratory report. Such an idea quotes laboratory values,
    # so only a doctor may approve it for the patient.
    lab_report = models.ForeignKey(
        "clinical.LaboratoryReport", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    category = models.CharField(max_length=30)  # compatible | check_portion | needs_dietitian_review | general
    personalized = models.BooleanField(default=False)  # false = general idea, no approved plan
    reasoning_summary = models.TextField(blank=True)
    nutrient_estimates = models.JSONField(default=dict)
    limitations = models.JSONField(default=list)
    source_references = models.JSONField(default=list)
    review_status = models.CharField(max_length=16, choices=ReviewStatus.choices, default=ReviewStatus.PENDING)
    reviewed_by = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class FoodLabReview(UUIDModel):
    """Descriptive comparison of the food diary with laboratory results. Unverified AI draft."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="food_lab_reviews")
    date_from = models.DateField()
    date_to = models.DateField()
    meal_data_completeness = models.FloatField()  # share of days in the period with a recorded meal
    lab_result_references = models.JSONField(default=list)
    dialysis_session_references = models.JSONField(default=list)
    nutrient_trends = models.JSONField(default=dict)  # deterministic daily averages
    possible_associations = models.JSONField(default=list)  # model output, descriptive only
    limitations = models.JSONField(default=list)
    questions = models.JSONField(default=list)
    ai_error = models.JSONField(default=list)
    model_name = models.CharField(max_length=100, blank=True)
    fingerprint = models.CharField(max_length=64, unique=True)  # same data => same review
    review_status = models.CharField(max_length=16, choices=ReviewStatus.choices, default=ReviewStatus.PENDING)
    reviewed_by = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    review_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]


class NutritionReport(UUIDModel):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="nutrition_reports")
    period_start = models.DateField()
    period_end = models.DateField()
    version = models.PositiveIntegerField(default=1)
    meal_summary = models.JSONField(default=dict)  # facts, computed
    nutrient_summary = models.JSONField(default=dict)  # facts, computed
    laboratory_summary = models.JSONField(default=list)  # facts, copied with units and timestamps
    dialysis_summary = models.JSONField(default=list)
    ai_draft = models.JSONField(null=True, blank=True)  # interpretation, kept apart from the facts
    ai_error = models.JSONField(default=list)
    model_name = models.CharField(max_length=100, blank=True)
    fingerprint = models.CharField(max_length=64)
    clinician_review = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    release_status = models.CharField(max_length=12, default="draft")  # draft | reviewed | released
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-period_end", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "period_start", "period_end", "fingerprint"], name="unique_report_data"
            )
        ]


class NutritionObservation(UUIDModel):
    """What a nurse hears or sees about eating (appetite, nausea). Can be referred to the clinician."""

    class Kind(models.TextChoices):
        EATING_DIFFICULTY = "eating_difficulty"
        NAUSEA = "nausea"
        LOSS_OF_APPETITE = "loss_of_appetite"
        OTHER = "other"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="nutrition_observations")
    author = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    text = models.TextField()
    referred = models.BooleanField(default=False)  # sent to the doctor and dietitian for follow-up

    class Meta:
        ordering = ["-created_at"]
