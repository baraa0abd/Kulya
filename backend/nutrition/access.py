"""Patient and diary query scope. Uses server-side identity and current consent only."""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import NotFound

from clinical.models import ConsentScope, Patient
from core.models import User
from core.permissions import FAMILY, PATIENT, patients_for

from .models import MealLog

HOUSEHOLD = (PATIENT, FAMILY)
READ, LOG = ConsentScope.NUTRITION, ConsentScope.NUTRITION_LOG


def patient_for(user: User, patient_id=None, scope: str = READ) -> Patient:
    """The patient this call is about, or 404. A patient (or a caregiver with one grant) may omit the id."""
    patients = patients_for(user, scope)
    try:
        if patient_id:
            patient = patients.filter(pk=patient_id).first()
        else:
            found = list(patients[:2]) if user.role in HOUSEHOLD else []
            patient = found[0] if len(found) == 1 else None
    except (DjangoValidationError, ValueError):
        patient = None
    if patient is None:
        raise NotFound()
    return patient


def meals_for(user: User, scope: str = READ):
    return (
        MealLog.objects.filter(patient__in=patients_for(user, scope), deleted_at__isnull=True)
        .select_related("estimate", "created_by")
        .prefetch_related("components__food_item")
    )
