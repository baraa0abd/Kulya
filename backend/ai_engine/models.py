from django.conf import settings
from django.db import models


class ExtractionDraft(models.Model):
    """AI output for one note. Never part of the clinical record until a nurse approves it."""

    class Status(models.TextChoices):
        PENDING = "pending"
        APPROVED = "approved"
        REJECTED = "rejected"
        INVALID = "invalid"

    note = models.ForeignKey("clinical.Note", on_delete=models.PROTECT, related_name="extraction_drafts")
    payload = models.JSONField(default=dict)  # schema extraction_v1
    edited_payload = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    validation_errors = models.JSONField(default=list)
    model_name = models.CharField(max_length=100, blank=True)
    prompt_version = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]
