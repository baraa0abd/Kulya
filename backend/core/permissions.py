"""Authorization. Default deny, enforced on the server for every read and write.

Two layers, both required:
1. RolePolicy  - may this role call this endpoint/action at all?
2. patients_for - which patients may this user touch? Every queryset is filtered through it, so a
   record outside the user's scope answers 404 (its existence is not revealed). Nothing the client
   sends (role, organization, patient id) is trusted for this decision.
"""

from django.db.models import Q, QuerySet
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Role, User

DOCTOR, NURSE, PATIENT, FAMILY = Role.DOCTOR, Role.NURSE, Role.PATIENT, Role.FAMILY
STAFF = (DOCTOR, NURSE)
EVERYONE = (DOCTOR, NURSE, PATIENT, FAMILY)


class RolePolicy(BasePermission):
    """Views declare `read_roles`, `write_roles`, and optionally `action_roles = {"action": roles}`.
    A view that declares nothing is closed to everyone."""

    def has_permission(self, request, view) -> bool:  # noqa: ANN001 - DRF types would import views circularly
        user = request.user
        if not (user and user.is_authenticated):
            return False
        action = getattr(view, "action", None)
        by_action = getattr(view, "action_roles", {})
        if action in by_action:
            allowed = by_action[action]
        elif request.method in SAFE_METHODS:
            allowed = getattr(view, "read_roles", ())
        else:
            allowed = getattr(view, "write_roles", ())
        return user.role in allowed


def patients_for(user: User, scope: str | None = None) -> QuerySet:
    """The patients this user may access right now. `scope` narrows a family caregiver to patients
    whose consent grant includes that scope; it has no effect on other roles."""
    from clinical.models import Patient

    now = timezone.now()
    if user.role in STAFF:
        # Same organization AND an active care-team assignment.
        active = Q(assignments__professional=user, assignments__active=True) & (
            Q(assignments__ends_at__isnull=True) | Q(assignments__ends_at__gt=now)
        )
        return Patient.objects.filter(active, organization_id=user.organization_id).distinct()
    if user.role == PATIENT:
        return Patient.objects.filter(user=user)
    if user.role == FAMILY:
        grants = consent_filter(user, now)
        if scope:
            grants &= Q(consents__scopes__contains=[scope])
        return Patient.objects.filter(grants).distinct()
    return Patient.objects.none()


def consent_filter(user: User, now=None) -> Q:
    now = now or timezone.now()
    return Q(consents__caregiver=user, consents__revoked_at__isnull=True) & (
        Q(consents__expires_at__isnull=True) | Q(consents__expires_at__gt=now)
    )


def consent_scopes(user: User, patient) -> set[str]:
    """Scopes a family caregiver currently holds for one patient (empty when none or expired)."""
    now = timezone.now()
    scopes: set[str] = set()
    for consent in patient.consents.filter(caregiver=user, revoked_at__isnull=True):
        if consent.expires_at is None or consent.expires_at > now:
            scopes.update(consent.scopes)
    return scopes


def get_patient_or_404(user: User, patient_id):
    patient = patients_for(user).filter(pk=patient_id).first()
    if patient is None:
        raise NotFound()
    return patient


def assigned_professionals(patient, role: str) -> QuerySet:
    now = timezone.now()
    return User.objects.filter(
        Q(assignments__ends_at__isnull=True) | Q(assignments__ends_at__gt=now),
        assignments__patient=patient,
        assignments__active=True,
        role=role,
        is_active=True,
    ).distinct()
