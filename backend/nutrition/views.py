"""Nutrition API. RolePolicy decides who may call each endpoint; `patient_or_404` decides which
patients they reach (care assignment, own record, or family consent). Out of scope answers 404."""

import base64
import binascii
from datetime import date, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from clinical.models import ConsentScope, Patient
from core.errors import ApiError
from core.permissions import ALL_ROLES, CARE_TEAM, DIETITIAN, DOCTOR, FAMILY, NURSE, PATIENT, patients_for
from core.services import audit, dispatch, idempotent

from . import services, tasks, usda
from .models import (
    FoodLabReview,
    MealLog,
    MealRecommendation,
    NutritionObservation,
    NutritionReport,
    Recipe,
    ReviewStatus,
)
from .serializers import (
    DecisionSerializer,
    FoodLabReviewSerializer,
    FoodSerializer,
    MealSerializer,
    ObservationSerializer,
    PeriodSerializer,
    PlanSerializer,
    RecipeSerializer,
    RecognizeSerializer,
    RecommendationSerializer,
    ReleaseSerializer,
    ReportSerializer,
)

HOUSEHOLD = (PATIENT, FAMILY)
CLINICIANS = (DOCTOR, DIETITIAN)  # approve plans, review AI drafts, release reports. Nurses cannot.
READ, LOG = ConsentScope.NUTRITION, ConsentScope.NUTRITION_LOG  # what a family grant must include


def patient_or_404(request: Request, patient_id=None, scope: str = READ) -> Patient:
    """The patient this call is about, or 404. A patient (or a caregiver with one grant) may omit the id."""
    patients = patients_for(request.user, scope)
    try:
        if patient_id:
            patient = patients.filter(pk=patient_id).first()
        else:
            found = list(patients[:2]) if request.user.role in HOUSEHOLD else []
            patient = found[0] if len(found) == 1 else None
    except (DjangoValidationError, ValueError):
        patient = None
    if patient is None:
        raise NotFound()
    return patient


def _day(request: Request, name: str) -> date | None:
    try:
        return date.fromisoformat(value) if (value := request.query_params.get(name)) else None
    except ValueError as exc:
        raise ValidationError({name: "Use YYYY-MM-DD."}) from exc


def _valid(serializer_class, request: Request) -> dict:
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class OverviewView(APIView):
    """One patient's nutrition picture (`?patient=`), or one row per reachable patient."""

    read_roles = ALL_ROLES

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        user, today = request.user, timezone.localdate()
        if request.query_params.get("patient") or user.role == PATIENT:
            patient = patient_or_404(request, request.query_params.get("patient"))
            plan = services.active_plan(patient)
            return Response(
                {
                    "patient": patient.id,
                    "patient_name": patient.full_name,
                    "today": services.diary(patient, today, today),
                    "last_7_days": services.diary(patient, today - timedelta(days=6), today),
                    "active_plan": PlanSerializer(plan).data if plan else None,
                    "can_log": patients_for(user, LOG).filter(pk=patient.pk).exists() and user.role in HOUSEHOLD,
                    "photo_recognition_available": settings.LLM_PROVIDER == "anthropic"
                    and bool(settings.ANTHROPIC_API_KEY),
                }
            )
        rows = []
        # ponytail: a few queries per patient; fine for a care team's list, aggregate if lists grow large.
        for patient in patients_for(user, READ):
            row = {
                "patient": patient.id,
                "patient_name": patient.full_name,
                "has_active_plan": services.active_plan(patient) is not None,
                "days_recorded_last_7": services.diary(patient, today - timedelta(days=6), today)["days_recorded"],
            }
            if user.role in CARE_TEAM:
                pending = {"review_status": ReviewStatus.PENDING}
                row |= {
                    "pending_recommendations": patient.meal_recommendations.filter(**pending).count(),
                    "pending_lab_reviews": patient.food_lab_reviews.filter(**pending).count(),
                    "draft_reports": patient.nutrition_reports.exclude(release_status="released").count(),
                    "referrals": patient.nutrition_observations.filter(referred=True).count(),
                }
            rows.append(row)
        return Response(rows)


class FoodListView(APIView):
    """Catalogue search (`?q=`). `?source=usda` also imports matches from USDA FoodData Central."""

    read_roles = ALL_ROLES

    @extend_schema(responses=FoodSerializer(many=True))
    def get(self, request: Request) -> Response:
        query = request.query_params.get("q", "")[:100]
        if request.query_params.get("source") == "usda" and request.user.role in CLINICIANS:
            return Response(FoodSerializer(usda.search(query), many=True).data)
        return Response(FoodSerializer(services.search_foods(query), many=True).data)


class RecipeListView(APIView):
    read_roles = ALL_ROLES

    @extend_schema(responses=RecipeSerializer(many=True))
    def get(self, request: Request) -> Response:
        return Response(RecipeSerializer(Recipe.objects.all(), many=True).data)


def _meals(request: Request, scope: str = READ):
    return (
        MealLog.objects.filter(patient__in=patients_for(request.user, scope), deleted_at__isnull=True)
        .select_related("estimate", "created_by")
        .prefetch_related("components__food_item")
    )


class MealListView(APIView):
    """The food diary. Only the patient, or a caregiver the patient allowed to log meals, may write."""

    read_roles = ALL_ROLES
    write_roles = HOUSEHOLD

    @extend_schema(responses=MealSerializer(many=True))
    def get(self, request: Request) -> Response:
        patient = patient_or_404(request, request.query_params.get("patient"))
        start, end = services.default_period(_day(request, "from"), _day(request, "to"))
        meals = _meals(request).filter(patient=patient, consumed_at__date__gte=start, consumed_at__date__lte=end)
        return Response(MealSerializer(meals[:300], many=True).data)

    @extend_schema(request=MealSerializer, responses=MealSerializer)
    def post(self, request: Request) -> Response:
        def handler() -> Response:
            data = dict(_valid(MealSerializer, request))
            patient = patient_or_404(request, data.pop("patient_id", None), LOG)
            meal = services.save_meal(patient, request.user, data)
            return Response(MealSerializer(meal).data, status=status.HTTP_201_CREATED)

        return idempotent(request, handler)


class MealDetailView(APIView):
    read_roles = ALL_ROLES
    write_roles = HOUSEHOLD

    def meal(self, request: Request, pk, scope: str) -> MealLog:
        meal = _meals(request, scope).filter(pk=pk).first()
        if meal is None:
            raise NotFound()
        return meal

    @extend_schema(responses=MealSerializer)
    def get(self, request: Request, pk) -> Response:
        return Response(MealSerializer(self.meal(request, pk, READ)).data)

    @extend_schema(request=MealSerializer, responses=MealSerializer)
    def patch(self, request: Request, pk) -> Response:
        meal = self.meal(request, pk, LOG)
        serializer = MealSerializer(meal, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        data.pop("patient_id", None)  # a diary entry never moves to another patient
        services.save_meal(meal.patient, request.user, data, meal)
        return Response(MealSerializer(self.meal(request, pk, LOG)).data)

    @extend_schema(responses={204: None})
    def delete(self, request: Request, pk) -> Response:
        services.delete_meal(self.meal(request, pk, LOG), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RecognizeView(APIView):
    """Text, speech transcript or photo -> editable food candidates. Nothing is saved here."""

    write_roles = HOUSEHOLD
    throttle_scope = "ai"

    @extend_schema(request=RecognizeSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        data = _valid(RecognizeSerializer, request)
        patient = patient_or_404(request, data.get("patient"), LOG)
        image = None
        if encoded := data.get("image_base64"):
            try:
                base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ValidationError({"image_base64": "Not valid base64."}) from exc
            image = (data["image_media_type"], encoded)
        return Response(services.recognize(request.user, patient, data["description"], image))


class TranscribeView(APIView):
    """Server-side speech-to-text is not built: the web app uses the browser's own recognition and
    sends the resulting text to /ai/recognize/. This endpoint says so instead of pretending."""

    write_roles = HOUSEHOLD

    @extend_schema(request=None, responses={501: OpenApiTypes.OBJECT})
    def post(self, request: Request) -> Response:
        raise ApiError("transcription_not_configured", "No server-side transcriber is configured.", 501)


class AnalyzeView(APIView):
    """Draft a food-and-laboratory review for a clinician."""

    write_roles = CLINICIANS
    throttle_scope = "ai"

    @extend_schema(request=PeriodSerializer, responses=FoodLabReviewSerializer)
    def post(self, request: Request) -> Response:
        data = _valid(PeriodSerializer, request)
        patient = patient_or_404(request, data.get("patient"))
        start, end = services.default_period(data.get("date_from"), data.get("date_to"))
        dispatch(tasks.analyze, str(patient.id), start.isoformat(), end.isoformat())
        review = patient.food_lab_reviews.filter(date_from=start, date_to=end).first()
        if review is None:  # queued on a worker
            return Response({"queued": True}, status=status.HTTP_202_ACCEPTED)
        return Response(FoodLabReviewSerializer(review).data)


def _visible_recommendations(request: Request, patient: Patient):
    recs = patient.meal_recommendations.select_related("recipe", "reviewed_by")
    if request.user.role in CARE_TEAM:
        return recs
    # A patient sees general ideas (rule-based text only) and personalized ones a clinician approved.
    approved = Q(review_status=ReviewStatus.APPROVED)
    return recs.filter(approved | Q(personalized=False)).exclude(review_status=ReviewStatus.REJECTED)


class SuggestionsView(APIView):
    read_roles = ALL_ROLES
    write_roles = (PATIENT, FAMILY, DOCTOR, DIETITIAN)
    throttle_scope = "ai"

    @extend_schema(responses=RecommendationSerializer(many=True))
    def get(self, request: Request) -> Response:
        patient = patient_or_404(request, request.query_params.get("patient"))
        return Response(RecommendationSerializer(_visible_recommendations(request, patient)[:100], many=True).data)

    @extend_schema(request=PeriodSerializer, responses=RecommendationSerializer(many=True))
    def post(self, request: Request) -> Response:
        patient = patient_or_404(request, _valid(PeriodSerializer, request).get("patient"))
        services.suggest(patient, request.user)
        return Response(RecommendationSerializer(_visible_recommendations(request, patient)[:100], many=True).data)


class RecommendationReviewView(APIView):
    write_roles = CLINICIANS

    @extend_schema(request=DecisionSerializer, responses=RecommendationSerializer)
    def post(self, request: Request, pk) -> Response:
        rec = MealRecommendation.objects.filter(pk=pk, patient__in=patients_for(request.user)).first()
        if rec is None:
            raise NotFound()
        rec = services.review_recommendation(rec.pk, request.user, _valid(DecisionSerializer, request)["approve"])
        return Response(RecommendationSerializer(rec).data)


class LabReviewDecisionView(APIView):
    write_roles = CLINICIANS

    @extend_schema(request=DecisionSerializer, responses=FoodLabReviewSerializer)
    def post(self, request: Request, pk) -> Response:
        review = FoodLabReview.objects.filter(pk=pk, patient__in=patients_for(request.user)).first()
        if review is None:
            raise NotFound()
        data = _valid(DecisionSerializer, request)
        review = services.review_lab_review(review.pk, request.user, data["approve"], data["notes"])
        return Response(FoodLabReviewSerializer(review).data)


class PlanView(APIView):
    """Nutrition plans. Written and approved by a doctor or dietitian only; each save is a new version."""

    read_roles = ALL_ROLES
    write_roles = CLINICIANS

    @extend_schema(responses=PlanSerializer(many=True))
    def get(self, request: Request, pk) -> Response:
        patient = patient_or_404(request, pk)
        return Response(PlanSerializer(patient.nutrition_plans.select_related("approved_by"), many=True).data)

    @extend_schema(request=PlanSerializer, responses=PlanSerializer)
    def post(self, request: Request, pk) -> Response:
        patient = patient_or_404(request, pk)
        plan = services.approve_plan(patient, request.user, dict(_valid(PlanSerializer, request)))
        return Response(PlanSerializer(plan).data, status=status.HTTP_201_CREATED)


class LabTrendsView(APIView):
    """Laboratory results next to diary averages, plus the food-and-lab reviews written about them."""

    read_roles = ALL_ROLES

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, pk) -> Response:
        patient, user = patient_or_404(request, pk), request.user
        start, end = services.default_period(_day(request, "from"), _day(request, "to"))
        staff = user.role in CARE_TEAM
        # A caregiver needs the separate "labs" grant; patients and caregivers see released results only.
        may_see_labs = staff or patients_for(user, ConsentScope.LABS).filter(pk=patient.pk).exists()
        reviews = patient.food_lab_reviews.select_related("reviewed_by")
        if not staff:
            reviews = reviews.filter(review_status=ReviewStatus.APPROVED) if may_see_labs else reviews.none()
        audit(user, "nutrition_lab_trends_viewed", None, patient=patient)
        return Response(
            {
                "period": {"from": start, "to": end},
                "diary": services.diary(patient, start, end),
                "laboratory_results": services.lab_facts(patient, start, end, not staff) if may_see_labs else [],
                "reviews": FoodLabReviewSerializer(reviews[:20], many=True).data,
            }
        )


class ReportListView(APIView):
    read_roles = ALL_ROLES

    @extend_schema(responses=ReportSerializer(many=True))
    def get(self, request: Request, pk) -> Response:
        patient, user = patient_or_404(request, pk), request.user
        reports = patient.nutrition_reports.select_related("reviewed_by", "patient")
        if user.role in CARE_TEAM:
            return Response(ReportSerializer(reports[:50], many=True).data)
        # Patients and caregivers: released reports only, and inside them only laboratory results
        # that a doctor has separately released (and, for a caregiver, that the grant covers).
        rows = ReportSerializer(reports.filter(release_status="released")[:50], many=True).data
        labs_ok = patients_for(user, ConsentScope.LABS).filter(pk=patient.pk).exists()
        released = set()
        if labs_ok:
            released = {
                str(i) for i in patient.lab_reports.filter(released_to_patient=True).values_list("id", flat=True)
            }
        for row in rows:
            row["laboratory_summary"] = [lab for lab in row["laboratory_summary"] if lab["report_id"] in released]
            row["ai_error"], row["model_name"] = [], ""
        return Response(rows)


class ReportGenerateView(APIView):
    write_roles = CLINICIANS
    throttle_scope = "ai"

    @extend_schema(request=PeriodSerializer, responses=ReportSerializer)
    def post(self, request: Request, pk) -> Response:
        patient, data = patient_or_404(request, pk), _valid(PeriodSerializer, request)
        start, end = services.default_period(data.get("date_from"), data.get("date_to"))
        dispatch(tasks.build_report, str(patient.id), start.isoformat(), end.isoformat())
        report = patient.nutrition_reports.filter(period_start=start, period_end=end).first()
        if report is None:  # queued on a worker
            return Response({"queued": True}, status=status.HTTP_202_ACCEPTED)
        return Response(ReportSerializer(report).data)


class ReportReleaseView(APIView):
    write_roles = CLINICIANS

    @extend_schema(request=ReleaseSerializer, responses=ReportSerializer)
    def post(self, request: Request, pk) -> Response:
        report = NutritionReport.objects.filter(pk=pk, patient__in=patients_for(request.user)).first()
        if report is None:
            raise NotFound()
        notes = _valid(ReleaseSerializer, request)["clinician_review"]
        return Response(ReportSerializer(services.release_report(report.pk, request.user, notes)).data)


class ObservationView(APIView):
    """What a nurse notices about eating. A nurse may refer it; a nurse can never approve a plan."""

    read_roles = CARE_TEAM
    write_roles = (NURSE,)

    @extend_schema(responses=ObservationSerializer(many=True))
    def get(self, request: Request, pk) -> Response:
        observations = NutritionObservation.objects.filter(patient=patient_or_404(request, pk))
        return Response(ObservationSerializer(observations.select_related("author")[:100], many=True).data)

    @extend_schema(request=ObservationSerializer, responses=ObservationSerializer)
    def post(self, request: Request, pk) -> Response:
        patient = patient_or_404(request, pk)
        observation = services.observe(patient, request.user, dict(_valid(ObservationSerializer, request)))
        return Response(ObservationSerializer(observation).data, status=status.HTTP_201_CREATED)
