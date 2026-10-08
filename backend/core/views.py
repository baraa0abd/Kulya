from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import AuditEvent, Role, User
from .permissions import EVERYONE


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
    read_roles = (*EVERYONE, Role.ORG_ADMIN, Role.AUDITOR, Role.SYS_ADMIN)

    @extend_schema(responses=MeSerializer)
    def get(self, request: Request) -> Response:
        return Response(MeSerializer(request.user).data)


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
