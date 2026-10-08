from django.conf import settings
from django.db import models
from django.db.models import Q

from clinical.models import DialysisSession, NursingAction, Patient
from core.models import ImmutableModel, UUIDModel

USER = settings.AUTH_USER_MODEL


class FeedbackKind(models.TextChoices):
    FEEDBACK = "feedback"
    CLARIFICATION = "clarification_request"


class DoctorFeedback(ImmutableModel):
    """A physician's written response to nursing documentation or to an AI review."""

    session = models.ForeignKey(DialysisSession, on_delete=models.PROTECT, related_name="feedback")
    author = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="+")
    kind = models.CharField(max_length=24, choices=FeedbackKind.choices, default=FeedbackKind.FEEDBACK)
    text = models.TextField()
    nursing_action = models.ForeignKey(
        NursingAction, null=True, blank=True, on_delete=models.PROTECT, related_name="feedback"
    )
    ai_review = models.ForeignKey(
        "ai.AIReview", null=True, blank=True, on_delete=models.PROTECT, related_name="feedback"
    )

    class Meta:
        ordering = ["-created_at"]


class ReviewTask(UUIDModel):
    """Physician to-do for one session. At most one open task per session."""

    class Status(models.TextChoices):
        OPEN = "open"
        DONE = "done"

    session = models.ForeignKey(DialysisSession, on_delete=models.CASCADE, related_name="review_tasks")
    ai_review = models.ForeignKey("ai.AIReview", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=6, choices=Status.choices, default=Status.OPEN)
    completed_by = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["session"], condition=Q(status="open"), name="one_open_task_per_session")
        ]


class Notification(UUIDModel):
    recipient = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=40)
    title = models.CharField(max_length=200)
    patient = models.ForeignKey(Patient, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    session = models.ForeignKey(DialysisSession, null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    read_at = models.DateTimeField(null=True, blank=True)
    # Makes delivery idempotent: the same event never notifies the same person twice.
    dedupe_key = models.CharField(max_length=160, unique=True)

    class Meta:
        ordering = ["-created_at"]
