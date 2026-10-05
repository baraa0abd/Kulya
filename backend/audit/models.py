from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Written for every create, approve, reject, edit."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    action = models.CharField(max_length=50)
    object_type = models.CharField(max_length=50)
    object_id = models.PositiveBigIntegerField()
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["object_type", "object_id"])]
