from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from ai_engine.serializers import ApproveDraftSerializer, ExtractionDraftSerializer, RejectSerializer
from audit.serializers import AuditLogSerializer
from clinical.serializers import (
    NoteCreatedSerializer,
    NoteSerializer,
    PatientSerializer,
    SessionSerializer,
    TimelineSessionSerializer,
)
from kulya.common.stubs import stub
from rules.serializers import FlagSerializer
from summaries.serializers import SummaryRequestSerializer, SummarySerializer

Draft, Summary = ExtractionDraftSerializer, SummarySerializer

# Frozen api_contract (docs/team_prompts.json). Owning roles replace each stub with a real view; paths must not change.
v1 = [
    path("auth/token", TokenObtainPairView.as_view()),
    path("auth/token/refresh", TokenRefreshView.as_view()),
    path("patients/", stub("PatientList", PatientSerializer, many=True, roles="nurse, doctor")),
    path("patients/<int:id>/", stub("PatientDetail", PatientSerializer, roles="nurse, doctor, own patient")),
    path("patients/<int:id>/timeline/", stub("PatientTimeline", TimelineSessionSerializer, many=True, roles="nurse, doctor")),
    path("patients/<int:id>/sessions/", stub("SessionCreate", SessionSerializer, method="post", request=SessionSerializer, roles="nurse")),
    path("sessions/<int:id>/", stub("SessionDetail", SessionSerializer, roles="nurse, doctor")),
    path("sessions/<int:id>/notes/", stub("NoteCreate", NoteCreatedSerializer, method="post", request=NoteSerializer, roles="nurse")),
    path("notes/<int:id>/", stub("NoteDetail", NoteSerializer, roles="nurse, doctor")),
    path("extraction-drafts/", stub("DraftList", Draft, many=True, roles="nurse", query=("status",))),
    path("extraction-drafts/<int:id>/", stub("DraftDetail", Draft, roles="nurse")),
    path("extraction-drafts/<int:id>/approve/", stub("DraftApprove", Draft, method="post", request=ApproveDraftSerializer, roles="nurse")),
    path("extraction-drafts/<int:id>/reject/", stub("DraftReject", Draft, method="post", request=RejectSerializer, roles="nurse")),
    path("extraction-drafts/<int:id>/retry/", stub("DraftRetry", Draft, method="post", roles="nurse")),
    path("patients/<int:id>/flags/", stub("PatientFlags", FlagSerializer, many=True, roles="nurse, doctor")),
    path("patients/<int:id>/summaries/", stub("SummaryCreate", Summary, method="post", request=SummaryRequestSerializer, roles="nurse, doctor")),
    path("summaries/<int:id>/", stub("SummaryDetail", Summary, roles="nurse, doctor; patient only if audience=patient, approved, own record")),
    path("summaries/<int:id>/approve/", stub("SummaryApprove", Summary, method="post", roles="doctor")),
    path("summaries/<int:id>/reject/", stub("SummaryReject", Summary, method="post", request=RejectSerializer, roles="doctor")),
    path("me/summaries/", stub("MySummaries", Summary, many=True, roles="patient")),
    path("audit/", stub("AuditList", AuditLogSerializer, many=True, roles="admin, doctor", query=("object_type", "object_id"))),
]  # fmt: skip

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(v1)),
    path("api/schema/", SpectacularAPIView.as_view(permission_classes=[]), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[])),
]
