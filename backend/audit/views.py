from django.db.models import QuerySet
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics

from accounts.permissions import IsAuditor

from .models import AuditLog
from .serializers import AuditLogSerializer


@extend_schema(
    parameters=[
        OpenApiParameter("object_type", str, required=False, description="Model name, e.g. ExtractionDraft"),
        OpenApiParameter("object_id", int, required=False),
    ]
)
class AuditList(generics.ListAPIView):
    """Who did what, newest first. Read-only; there is no endpoint that edits the audit log."""

    permission_classes = [IsAuditor]
    serializer_class = AuditLogSerializer

    def get_queryset(self) -> QuerySet[AuditLog]:
        logs = AuditLog.objects.all()
        params = self.request.query_params
        if params.get("object_type"):
            logs = logs.filter(object_type=params["object_type"])
        if params.get("object_id", "").isdigit():
            logs = logs.filter(object_id=int(params["object_id"]))
        return logs
