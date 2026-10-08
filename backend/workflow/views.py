from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from ai.services import mark_reviewed
from clinical.views import ScopedViewSet
from core.models import Role
from core.permissions import ALL_ROLES, DOCTOR, NURSE, STAFF, assigned_professionals
from core.services import audit

from .models import DoctorFeedback, Notification, ReviewTask
from .services import notify


class DoctorFeedbackSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.display_name", read_only=True)

    class Meta:
        model = DoctorFeedback
        fields = ["id", "session", "author", "author_name", "kind", "text", "nursing_action", "ai_review", "created_at"]
        read_only_fields = ["id", "author", "author_name", "created_at"]

    def validate(self, attrs: dict) -> dict:
        for field in ("nursing_action", "ai_review"):
            target = attrs.get(field)
            if target is not None and target.session_id != attrs["session"].id:
                raise serializers.ValidationError({field: "Must belong to the same session."})
        return attrs


class DoctorFeedbackViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, ScopedViewSet):
    """Doctors write feedback or ask for clarification; the session's nurses can read it."""

    read_roles = STAFF
    write_roles = (DOCTOR,)
    serializer_class = DoctorFeedbackSerializer
    queryset = DoctorFeedback.objects.select_related("author")
    patient_field = "session__patient"
    filters = ("session", "nursing_action", "kind")

    @transaction.atomic
    def perform_create(self, serializer) -> None:
        session = self.session_in_scope(serializer)
        doctor = self.request.user
        feedback = serializer.save(author=doctor)
        audit(doctor, "doctor_feedback_created", feedback, patient=session.patient, kind=feedback.kind)
        if feedback.ai_review:
            mark_reviewed(feedback.ai_review, doctor)
        # Tell the nurses who documented this session, plus the rest of the patient's nursing team.
        nurses = set(assigned_professionals(session.patient, Role.NURSE))
        nurses.update(a.author for a in session.nursing_actions.select_related("author"))
        for nurse in nurses:
            notify(nurse, "doctor_feedback", "A doctor left feedback on a session", session, f"feedback:{feedback.id}")


class ReviewTaskSerializer(serializers.ModelSerializer):
    patient = serializers.UUIDField(source="session.patient_id", read_only=True)
    patient_name = serializers.CharField(source="session.patient.full_name", read_only=True)
    session_date = serializers.DateTimeField(source="session.scheduled_start", read_only=True)
    review_status = serializers.CharField(source="ai_review.status", read_only=True, default=None)
    finding_count = serializers.SerializerMethodField()

    class Meta:
        model = ReviewTask
        fields = [
            "id", "session", "session_date", "patient", "patient_name", "ai_review", "review_status",
            "finding_count", "status", "created_at", "completed_at",
        ]  # fmt: skip
        read_only_fields = fields

    def get_finding_count(self, task: ReviewTask) -> int:
        return len(task.ai_review.rule_findings) if task.ai_review else 0


class ReviewTaskViewSet(mixins.ListModelMixin, ScopedViewSet):
    read_roles = (DOCTOR,)
    action_roles = {"complete": (DOCTOR,)}
    serializer_class = ReviewTaskSerializer
    queryset = ReviewTask.objects.select_related("session__patient", "ai_review")
    patient_field = "session__patient"
    filters = ("status", "session")

    @extend_schema(request=None, responses=ReviewTaskSerializer)
    @action(detail=True, methods=["post"])
    def complete(self, request: Request, pk=None) -> Response:
        """Close a task without written feedback (normal physician review also works with no AI)."""
        task = self.get_object()
        if task.status != ReviewTask.Status.OPEN:
            raise ValidationError({"status": "Task is already done."})
        if task.ai_review:
            mark_reviewed(task.ai_review, request.user)
        else:
            ReviewTask.objects.filter(pk=task.pk).update(
                status=ReviewTask.Status.DONE, completed_by=request.user, completed_at=timezone.now()
            )
        audit(request.user, "review_task_completed", task, patient=task.session.patient)
        task.refresh_from_db()
        return Response(self.get_serializer(task).data)


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "kind", "title", "patient", "session", "read_at", "created_at"]
        read_only_fields = fields


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """A user's own inbox. There is no way to address another user's notifications."""

    read_roles = ALL_ROLES
    action_roles = {"read": ALL_ROLES, "read_all": ALL_ROLES}
    serializer_class = NotificationSerializer

    def get_queryset(self) -> QuerySet:
        inbox = Notification.objects.filter(recipient=self.request.user)
        return inbox.filter(read_at__isnull=True) if self.request.query_params.get("unread") == "true" else inbox

    @extend_schema(request=None, responses=NotificationSerializer)
    @action(detail=True, methods=["post"])
    def read(self, request: Request, pk=None) -> Response:
        notification = self.get_object()
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save()
        return Response(self.get_serializer(notification).data)

    @extend_schema(request=None, responses={204: None})
    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request: Request) -> Response:
        self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response(status=status.HTTP_204_NO_CONTENT)


__all__ = ["DoctorFeedbackViewSet", "NotificationViewSet", "ReviewTaskViewSet", "NURSE"]
