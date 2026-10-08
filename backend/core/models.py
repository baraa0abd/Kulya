import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class UUIDModel(models.Model):
    """Base for every table: UUID primary key and timezone-aware timestamps."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ImmutableError(Exception):
    """Raised when code tries to overwrite or delete a signed clinical record."""


class ImmutableModel(UUIDModel):
    """Clinical records are never overwritten. A correction is a new row that points at the old one."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs) -> None:
        if not self._state.adding:
            raise ImmutableError(f"{type(self).__name__} records are immutable; create an amendment instead.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableError(f"{type(self).__name__} records cannot be deleted.")


class Organization(UUIDModel):
    """Tenant. Every patient, protocol and staff account belongs to exactly one organization."""

    name = models.CharField(max_length=200, unique=True)

    def __str__(self) -> str:
        return self.name


class Role(models.TextChoices):
    DOCTOR = "doctor"
    NURSE = "nurse"
    PATIENT = "patient"
    FAMILY = "family"
    DIETITIAN = "dietitian"  # renal dietitian: nutrition plans and reviews for assigned patients
    ORG_ADMIN = "org_admin"
    SYS_ADMIN = "sys_admin"
    AUDITOR = "auditor"
    SERVICE = "service"  # AI background processing; cannot log in through the API


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=12, choices=Role.choices)
    organization = models.ForeignKey(
        Organization, null=True, blank=True, on_delete=models.PROTECT, related_name="users"
    )
    display_name = models.CharField(max_length=200, blank=True)

    @property
    def is_clinician(self) -> bool:
        return self.role in (Role.DOCTOR, Role.NURSE)


class AuditEvent(models.Model):
    """Append-only trail of sensitive reads and every write. No clinical free text is stored here."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(User, null=True, on_delete=models.PROTECT, related_name="+")
    organization = models.ForeignKey(Organization, null=True, on_delete=models.PROTECT, related_name="+")
    action = models.CharField(max_length=60)
    object_type = models.CharField(max_length=60)
    object_id = models.CharField(max_length=64, blank=True)
    patient_id = models.UUIDField(null=True, db_index=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["object_type", "object_id"])]

    def save(self, *args, **kwargs) -> None:
        if not self._state.adding:
            raise ImmutableError("Audit events are append-only.")
        super().save(*args, **kwargs)


class IdempotencyKey(models.Model):
    """Stored response for a retried POST carrying the same Idempotency-Key header."""

    key = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    path = models.CharField(max_length=300)
    status_code = models.PositiveSmallIntegerField()
    response = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["key", "user", "path"], name="unique_idempotency_key")]
