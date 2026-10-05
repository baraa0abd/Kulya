from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def _range(lo: float, hi: float) -> list:
    return [MinValueValidator(lo), MaxValueValidator(hi)]


# Plausible physical ranges: typo guards (e.g. sbp=1200), NOT clinical thresholds.
SBP_RANGE = _range(50, 260)
DBP_RANGE = _range(30, 160)
WEIGHT_RANGE = _range(20, 250)
UF_RANGE = _range(0, 8000)


class Patient(models.Model):
    code = models.CharField(max_length=20, unique=True)  # e.g. SYN-001
    display_name_ar = models.CharField(max_length=100)
    birth_year = models.PositiveSmallIntegerField(validators=_range(1900, 2100))
    is_synthetic = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.code


class Session(models.Model):
    class AccessType(models.TextChoices):
        AVF = "AVF"
        AVG = "AVG"
        CVC = "CVC"

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="sessions")
    session_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    # Nullable so an incomplete record can exist and be flagged by rule R3_MISSING_REQUIRED.
    pre_sbp = models.PositiveSmallIntegerField(null=True, blank=True, validators=SBP_RANGE)
    pre_dbp = models.PositiveSmallIntegerField(null=True, blank=True, validators=DBP_RANGE)
    post_sbp = models.PositiveSmallIntegerField(null=True, blank=True, validators=SBP_RANGE)
    post_dbp = models.PositiveSmallIntegerField(null=True, blank=True, validators=DBP_RANGE)
    min_intra_sbp = models.PositiveSmallIntegerField(null=True, blank=True, validators=SBP_RANGE)
    pre_weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, validators=WEIGHT_RANGE)
    post_weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, validators=WEIGHT_RANGE)
    uf_volume_ml = models.PositiveIntegerField(null=True, blank=True, validators=UF_RANGE)
    access_type = models.CharField(max_length=3, choices=AccessType.choices)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-session_date", "-start_time"]
        indexes = [models.Index(fields=["patient", "session_date"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F("start_time")), name="session_end_after_start"
            )
        ]


class NoteImmutableError(Exception):
    pass


class Note(models.Model):
    """Original Arabic note. Immutable after creation; corrections are new notes with `supersedes`."""

    session = models.ForeignKey(Session, on_delete=models.PROTECT, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    text_ar = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    supersedes = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="superseded_by"
    )

    class Meta:
        ordering = ["created_at"]

    def save(self, *args, **kwargs) -> None:
        if not self._state.adding:
            raise NoteImmutableError("Notes are immutable; create a new note that supersedes this one.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise NoteImmutableError("Notes cannot be deleted.")


class SessionFacts(models.Model):
    """Approved structured facts. Written ONLY when a human approves an ExtractionDraft."""

    session = models.OneToOneField(Session, on_delete=models.PROTECT, related_name="facts")
    # Each item keeps note_id and evidence_span.
    symptoms = models.JSONField(default=list)
    access_findings = models.JSONField(default=list)
    staff_actions = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "session facts"
