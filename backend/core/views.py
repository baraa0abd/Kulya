from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import AuditEvent, Role, User
from .permissions import ALL_ROLES
from .services import audit

EVERY_ACCOUNT = (*ALL_ROLES, Role.ORG_ADMIN, Role.AUDITOR, Role.SYS_ADMIN)
# Accounts an organization administrator may open. Administrators and auditors are created on the server.
ASSIGNABLE = (Role.DOCTOR, Role.NURSE, Role.DIETITIAN, Role.PATIENT, Role.FAMILY)


def _checked_password(value: str, user: User | None = None) -> str:
    try:
        validate_password(value, user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages)) from exc
    return value


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs)
        if self.user.role == Role.SERVICE:
            raise AuthenticationFailed("Service accounts cannot sign in.")
        data["user"] = MeSerializer(self.user).data
        return data


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_scope = "login"


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "display_name", "role", "organization"]
        read_only_fields = fields


class MeView(APIView):
    read_roles = EVERY_ACCOUNT

    @extend_schema(responses=MeSerializer)
    def get(self, request: Request) -> Response:
        return Response(MeSerializer(request.user).data)


class PasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)


class PasswordView(APIView):
    """Change your own password. Tokens already issued stay valid until they expire."""

    write_roles = EVERY_ACCOUNT
    throttle_scope = "login"

    @extend_schema(request=PasswordSerializer, responses={204: None})
    def post(self, request: Request) -> Response:
        body = PasswordSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(body.validated_data["current_password"]):
            raise ValidationError({"current_password": "The current password is not correct."})
        try:
            user.set_password(_checked_password(body.validated_data["new_password"], user))
        except serializers.ValidationError as exc:
            raise ValidationError({"new_password": exc.detail}) from exc
        user.save()
        audit(user, "password_changed", user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccountSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    role = serializers.ChoiceField(choices=[(role.value, role.label) for role in ASSIGNABLE])

    class Meta:
        model = User
        fields = ["id", "username", "display_name", "role", "password", "is_active"]
        read_only_fields = ["id", "is_active"]

    def validate_password(self, value: str) -> str:
        return _checked_password(value)


class AccountViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Staff, patient and caregiver accounts of the administrator's own organization."""

    read_roles = (Role.ORG_ADMIN,)
    write_roles = (Role.ORG_ADMIN,)
    action_roles = {"deactivate": (Role.ORG_ADMIN,)}
    serializer_class = AccountSerializer

    def get_queryset(self):
        accounts = User.objects.filter(organization_id=self.request.user.organization_id, role__in=ASSIGNABLE)
        return accounts.order_by("role", "username")

    def perform_create(self, serializer) -> None:
        admin = self.request.user
        serializer.instance = User.objects.create_user(organization=admin.organization, **serializer.validated_data)
        audit(admin, "account_created", serializer.instance, role=serializer.instance.role)

    @extend_schema(request=None, responses=AccountSerializer)
    @action(detail=True, methods=["post"])
    def deactivate(self, request: Request, pk=None) -> Response:
        account = self.get_object()
        account.is_active = False
        account.save()
        audit(request.user, "account_deactivated", account)
        return Response(self.get_serializer(account).data)


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(responses={200: dict})
    def get(self, request: Request) -> Response:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return Response({"status": "ok"})


class AuditEventSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True, default=None)

    class Meta:
        model = AuditEvent
        fields = ["id", "created_at", "actor", "actor_username", "action", "object_type", "object_id", "patient_id"]
        read_only_fields = fields


class AuditViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Read-only audit trail, limited to the reviewer's own organization."""

    read_roles = (Role.AUDITOR, Role.ORG_ADMIN)
    serializer_class = AuditEventSerializer

    def get_queryset(self):
        events = AuditEvent.objects.filter(organization_id=self.request.user.organization_id).select_related("actor")
        params = self.request.query_params
        for field in ("object_type", "object_id", "patient_id", "action"):
            if params.get(field):
                events = events.filter(**{field: params[field]})
        return events
