from django.conf import settings
from django.db import models

from clinical.models import Patient
from core.models import UUIDModel


class ChatMessage(UUIDModel):
    """One question and its answer. Every row belongs to one patient and is never read for another."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="chat_messages")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    question = models.TextField()
    answer = models.TextField()
    model_name = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["patient", "created_at"])]
