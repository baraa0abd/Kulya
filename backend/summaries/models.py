from django.conf import settings
from django.db import models


class Summary(models.Model):
    class Audience(models.TextChoices):
        CLINICIAN = "clinician"
        PATIENT = "patient"

    class Status(models.TextChoices):
        DRAFT = "draft"
        APPROVED = "approved"
        REJECTED = "rejected"
        INVALID = "invalid"

    patient = models.ForeignKey("clinical.Patient", on_delete=models.PROTECT, related_name="summaries")
    audience = models.CharField(max_length=10, choices=Audience.choices)
    period_start = models.DateField()
    period_end = models.DateField()
    sentences = models.JSONField(default=list)  # [{text_ar, citations: [note_id]}]
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    validation_errors = models.JSONField(default=list)
    model_name = models.CharField(max_length=100, blank=True)
    prompt_version = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "summaries"
        indexes = [models.Index(fields=["patient", "audience", "status"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(period_end__gte=models.F("period_start")), name="summary_period_ordered"
            )
        ]
