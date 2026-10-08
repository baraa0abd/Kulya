from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from clinical.models import ConsentScope, DialysisSession
from clinical.views import ScopedViewSet
from core.permissions import DOCTOR, EVERYONE, NURSE, STAFF, patients_for
from core.services import audit, dispatch

from . import services
from .models import AIReview, AISummary
from .tasks import review_session, summarize_session

AI_LABEL = "AI-generated draft. Advisory only; requires review by an authorized clinician."


class SessionRequestSerializer(serializers.Serializer):
    session = serializers.UUIDField()


class AIReviewSerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()

    class Meta:
        model = AIReview
        fields = [
            "id", "session", "trigger", "status", "label", "rule_findings", "protocol_passages", "output",
            "ai_error", "model_name", "prompt_version", "created_at", "reviewed_by", "reviewed_at",
        ]  # fmt: skip
        read_only_fields = fields

    def get_label(self, review: AIReview) -> str:
        return AI_LABEL


class CompletenessSerializer(serializers.Serializer):
    """What a nurse sees: the deterministic documentation checks only, never the AI assessment."""

    session = serializers.UUIDField()
    rule_findings = serializers.ListField()
    checked_at = serializers.DateTimeField(allow_null=True)


class AISummarySerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()

    class Meta:
        model = AISummary
        fields = [
            "id", "session", "version", "status", "label", "metrics", "output", "ai_error", "model_name",
            "prompt_version", "created_at", "verified_by", "verified_at", "released", "released_at",
        ]  # fmt: skip
        read_only_fields = fields

    def get_label(self, summary: AISummary) -> str:
        return AI_LABEL


class ReleasedSummarySerializer(serializers.ModelSerializer):
    """Patient and caregiver view: the doctor-released plain-language text and nothing else."""

    text = serializers.CharField(source="output.patient_summary", read_only=True)
    session_date = serializers.DateTimeField(source="session.scheduled_start", read_only=True)
    patient_name = serializers.CharField(source="session.patient.full_name", read_only=True)

    class Meta:
        model = AISummary
        fields = ["id", "session", "session_date", "patient_name", "text", "released_at"]
        read_only_fields = fields


class SessionScoped(ScopedViewSet):
    patient_field = "session__patient"
    filters = ("session", "status")
    throttle_scope = "ai"

    def requested_session(self, request: Request) -> DialysisSession:
        body = SessionRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        sessions = DialysisSession.objects.filter(patient__in=patients_for(request.user))
        return self.get_object_or_404(sessions, body.validated_data["session"])

    @staticmethod
    def get_object_or_404(queryset: QuerySet, pk):
        from rest_framework.exceptions import NotFound

        obj = queryset.filter(pk=pk).first()
        if obj is None:
            raise NotFound()
        return obj


class AIReviewViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, SessionScoped):
    """AI documentation reviews. Only doctors read them; nurses get the completeness checks."""

    read_roles = (DOCTOR,)
    action_roles = {"request_review": (DOCTOR,), "completeness": (NURSE, DOCTOR)}
    serializer_class = AIReviewSerializer
    queryset = AIReview.objects.all()

    @extend_schema(request=SessionRequestSerializer, responses={202: dict})
    @action(detail=False, methods=["post"], url_path="request")
    def request_review(self, request: Request) -> Response:
        """Doctor asks for a fresh analysis. Runs in the background; poll the list for the result."""
        session = self.requested_session(request)
        audit(request.user, "ai_review_requested", session)
        queued = dispatch(review_session, str(session.id), "doctor_requested", services.new_nonce())
        return Response({"queued": queued}, status=status.HTTP_202_ACCEPTED)

    @extend_schema(responses=CompletenessSerializer)
    @action(detail=False, methods=["get"])
    def completeness(self, request: Request) -> Response:
        session = self.get_object_or_404(
            DialysisSession.objects.filter(patient__in=patients_for(request.user)),
            request.query_params.get("session") or "00000000-0000-0000-0000-000000000000",
        )
        latest = session.ai_reviews.first()
        return Response(
            {
                "session": session.id,
                "rule_findings": latest.rule_findings if latest else [],
                "checked_at": latest.created_at if latest else None,
            }
        )


class AISummaryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, SessionScoped):
    read_roles = EVERYONE
    action_roles = {"generate": STAFF, "verify": (DOCTOR,), "reject": (DOCTOR,), "release": (DOCTOR,)}
    queryset = AISummary.objects.select_related("session__patient")
    family_scope = ConsentScope.SUMMARIES

    def get_queryset(self) -> QuerySet:
        summaries = super().get_queryset()
        if self.request.user.role in STAFF:
            return summaries
        # Unverified or unreleased AI text never reaches a patient or caregiver.
        return summaries.filter(released=True, status=AISummary.Status.VERIFIED)

    def get_serializer_class(self):
        return AISummarySerializer if self.request.user.role in STAFF else ReleasedSummarySerializer

    @extend_schema(request=SessionRequestSerializer, responses={202: dict})
    @action(detail=False, methods=["post"])
    def generate(self, request: Request) -> Response:
        session = self.requested_session(request)
        audit(request.user, "ai_summary_requested", session)
        queued = dispatch(summarize_session, str(session.id), str(request.user.id), True)
        return Response({"queued": queued}, status=status.HTTP_202_ACCEPTED)

    @extend_schema(request=None, responses=AISummarySerializer)
    @action(detail=True, methods=["post"])
    def verify(self, request: Request, pk=None) -> Response:
        return Response(AISummarySerializer(services.verify_summary(self.get_object().pk, request.user, True)).data)

    @extend_schema(request=None, responses=AISummarySerializer)
    @action(detail=True, methods=["post"])
    def reject(self, request: Request, pk=None) -> Response:
        return Response(AISummarySerializer(services.verify_summary(self.get_object().pk, request.user, False)).data)

    @extend_schema(request=None, responses=AISummarySerializer)
    @action(detail=True, methods=["post"])
    def release(self, request: Request, pk=None) -> Response:
        return Response(AISummarySerializer(services.release_summary(self.get_object().pk, request.user)).data)
