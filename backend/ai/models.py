from django.conf import settings
from django.db import models
from pgvector.django import HnswIndex, VectorField

from clinical.models import DialysisSession
from core.models import Organization, UUIDModel

USER = settings.AUTH_USER_MODEL


class ClinicalProtocol(UUIDModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="protocols")
    title = models.CharField(max_length=200)
    clinical_owner = models.CharField(max_length=200)
    # Demo policies are synthetic workflow rules, NOT clinician-approved clinical protocols.
    is_synthetic = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "title"], name="unique_protocol_title")]


class ProtocolVersion(UUIDModel):
    class Approval(models.TextChoices):
        DRAFT = "draft"
        APPROVED = "approved"
        RETIRED = "retired"

    protocol = models.ForeignKey(ClinicalProtocol, on_delete=models.CASCADE, related_name="versions")
    version = models.CharField(max_length=20)
    approval_status = models.CharField(max_length=10, choices=Approval.choices, default=Approval.DRAFT)
    effective_date = models.DateField()
    expiry_date = models.DateField(null=True, blank=True)
    text = models.TextField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["protocol", "version"], name="unique_protocol_version")]


class ProtocolChunk(UUIDModel):
    """One retrievable passage of an approved protocol version, with its embedding."""

    protocol_version = models.ForeignKey(ProtocolVersion, on_delete=models.CASCADE, related_name="chunks")
    section = models.CharField(max_length=200)
    text = models.TextField()
    embedding = VectorField(dimensions=settings.EMBEDDING_DIMENSIONS)

    class Meta:
        indexes = [
            HnswIndex(
                name="chunk_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
        ]


class AIReview(UUIDModel):
    """AI nursing-documentation review for one session. Always advisory; a doctor decides."""

    class Status(models.TextChoices):
        PROCESSING = "processing"
        PENDING_REVIEW = "pending_review"  # validated AI draft waiting for a doctor
        AI_UNAVAILABLE = "ai_unavailable"  # model failed or output rejected; rule findings only
        REVIEWED = "reviewed"

    session = models.ForeignKey(DialysisSession, on_delete=models.CASCADE, related_name="ai_reviews")
    trigger = models.CharField(max_length=30)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PROCESSING)
    rule_findings = models.JSONField(default=list)  # deterministic, reproducible
    protocol_passages = models.JSONField(default=list)  # [{id, protocol, version, section}] actually retrieved
    output = models.JSONField(null=True, blank=True)  # validated model output (schema review_v1)
    ai_error = models.JSONField(default=list)  # why the AI part is missing, when it is
    source_record_ids = models.JSONField(default=list)
    model_name = models.CharField(max_length=100, blank=True)
    prompt_version = models.CharField(max_length=40, blank=True)
    # Same session + same source records + same trigger => same key => processed once.
    idempotency_key = models.CharField(max_length=64, unique=True)
    reviewed_by = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class AISummary(UUIDModel):
    """AI session summary draft. Unverified until a doctor verifies it; patients only ever see a
    summary that was verified AND explicitly released."""

    class Status(models.TextChoices):
        PROCESSING = "processing"
        UNVERIFIED = "unverified"
        VERIFIED = "verified"
        REJECTED = "rejected"
        AI_UNAVAILABLE = "ai_unavailable"

    session = models.ForeignKey(DialysisSession, on_delete=models.CASCADE, related_name="ai_summaries")
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PROCESSING)
    metrics = models.JSONField(default=dict)  # deterministic backend calculations
    output = models.JSONField(null=True, blank=True)  # validated model output (schema summary_v1)
    ai_error = models.JSONField(default=list)
    source_record_ids = models.JSONField(default=list)
    context_fingerprint = models.CharField(max_length=64)
    model_name = models.CharField(max_length=100, blank=True)
    prompt_version = models.CharField(max_length=40, blank=True)
    requested_by = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    verified_by = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    verified_at = models.DateTimeField(null=True, blank=True)
    released = models.BooleanField(default=False)
    released_by = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["session", "version"], name="unique_summary_version"),
            models.CheckConstraint(
                condition=models.Q(released=False) | models.Q(status="verified"), name="release_requires_verification"
            ),
        ]
