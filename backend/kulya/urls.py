from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.serializers import KulyaTokenObtainPairSerializer
from ai_engine import views as drafts
from audit.views import AuditList
from clinical import views as clinical
from summaries import views as summaries

# Frozen api_contract (docs/team_prompts.json). tests/test_lead.py fails if these paths drift from it.
v1 = [
    path("auth/token", TokenObtainPairView.as_view(serializer_class=KulyaTokenObtainPairSerializer)),
    path("auth/token/refresh", TokenRefreshView.as_view()),
    path("patients/", clinical.PatientList.as_view()),
    path("patients/<int:id>/", clinical.PatientDetail.as_view()),
    path("patients/<int:id>/timeline/", clinical.PatientTimeline.as_view()),
    path("patients/<int:id>/sessions/", clinical.SessionCreate.as_view()),
    path("patients/<int:id>/flags/", clinical.PatientFlags.as_view()),
    path("patients/<int:id>/summaries/", summaries.SummaryCreate.as_view()),
    path("sessions/<int:id>/", clinical.SessionDetail.as_view()),
    path("sessions/<int:id>/notes/", clinical.NoteCreate.as_view()),
    path("notes/<int:id>/", clinical.NoteDetail.as_view()),
    path("extraction-drafts/", drafts.DraftList.as_view()),
    path("extraction-drafts/<int:id>/", drafts.DraftDetail.as_view()),
    path("extraction-drafts/<int:id>/approve/", drafts.DraftApprove.as_view()),
    path("extraction-drafts/<int:id>/reject/", drafts.DraftReject.as_view()),
    path("extraction-drafts/<int:id>/retry/", drafts.DraftRetry.as_view()),
    path("summaries/<int:id>/", summaries.SummaryDetail.as_view()),
    path("summaries/<int:id>/approve/", summaries.SummaryApprove.as_view()),
    path("summaries/<int:id>/reject/", summaries.SummaryReject.as_view()),
    path("me/summaries/", summaries.MySummaries.as_view()),
    path("audit/", AuditList.as_view()),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(v1)),
    path("api/schema/", SpectacularAPIView.as_view(permission_classes=[]), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[])),
]

if settings.DEBUG:
    # Local development only: serve the built Flutter app from the same origin as the API, so one
    # server runs everything and no CORS setup is needed. In docker, nginx does this instead.
    WEB_BUILD = settings.BASE_DIR.parent / "frontend" / "kulya_app" / "build" / "web"
    urlpatterns += [
        path("", serve, {"path": "index.html", "document_root": WEB_BUILD}),
        re_path(r"^(?P<path>.+)$", serve, {"document_root": WEB_BUILD}),
    ]
