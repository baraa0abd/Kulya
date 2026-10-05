"""Role permissions (roles_permissions_matrix). Views combine these with queryset scoping, so a
record a user may not see answers 404 rather than revealing that it exists."""

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from clinical.models import Patient


class RolePermission(BasePermission):
    roles: tuple[str, ...] = ()

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.role in self.roles)


class IsNurse(RolePermission):
    roles = ("nurse",)


class IsDoctor(RolePermission):
    roles = ("doctor",)


class IsClinician(RolePermission):
    roles = ("nurse", "doctor")


class IsAdmin(RolePermission):
    roles = ("admin",)


class IsAuditor(RolePermission):
    """Audit log readers: admin and doctor."""

    roles = ("admin", "doctor")


class IsPatientOwner(RolePermission):
    """A patient-role user, and only for objects belonging to their own Patient record."""

    roles = ("patient",)

    def has_object_permission(self, request: Request, view: APIView, obj: object) -> bool:
        patient_id = obj.id if isinstance(obj, Patient) else getattr(obj, "patient_id", None)
        return patient_id is not None and patient_id == request.user.patient_id
