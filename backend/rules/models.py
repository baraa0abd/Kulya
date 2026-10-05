from django.db import models


class Flag(models.Model):
    """Output of the deterministic rules engine. Never produced by the LLM."""

    class Severity(models.TextChoices):
        INFO = "info"
        ATTENTION = "attention"

    patient = models.ForeignKey("clinical.Patient", on_delete=models.CASCADE, related_name="flags")
    session = models.ForeignKey(
        "clinical.Session", null=True, blank=True, on_delete=models.CASCADE, related_name="flags"
    )
    rule_id = models.CharField(max_length=40)
    severity = models.CharField(max_length=10, choices=Severity.choices)
    message_ar = models.TextField()
    evidence = models.JSONField(default=dict)  # session ids, values, note ids
    created_at = models.DateTimeField(auto_now_add=True)
    rules_version = models.CharField(max_length=64)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["patient", "rule_id"])]
