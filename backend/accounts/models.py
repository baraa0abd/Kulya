from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        NURSE = "nurse"
        DOCTOR = "doctor"
        PATIENT = "patient"
        ADMIN = "admin"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.NURSE)
    # Set only for role=patient: the one Patient record this user may see.
    patient = models.ForeignKey(
        "clinical.Patient", null=True, blank=True, on_delete=models.PROTECT, related_name="users"
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(role="patient") | models.Q(patient__isnull=False),
                name="patient_user_has_patient",
            )
        ]
