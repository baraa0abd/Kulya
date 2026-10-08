from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from ai.views import AIReviewViewSet, AISummaryViewSet
from clinical import views as clinical
from core.views import AuditViewSet, HealthView, LoginView, MeView
from workflow.views import DoctorFeedbackViewSet, NotificationViewSet, ReviewTaskViewSet

router = DefaultRouter()
router.register("patients", clinical.PatientViewSet, basename="patient")
router.register("care-assignments", clinical.CareAssignmentViewSet, basename="care-assignment")
router.register("consent", clinical.ConsentViewSet, basename="consent")
router.register("prescriptions", clinical.PrescriptionViewSet, basename="prescription")
router.register("sessions", clinical.SessionViewSet, basename="session")
router.register("nursing-actions", clinical.NursingActionViewSet, basename="nursing-action")
router.register("nursing-notes", clinical.NursingNoteViewSet, basename="nursing-note")
router.register("device-readings", clinical.DeviceReadingViewSet, basename="device-reading")
router.register("session-events", clinical.SessionEventViewSet, basename="session-event")
router.register("vitals", clinical.VitalSignViewSet, basename="vital")
router.register("labs", clinical.LabReportViewSet, basename="lab")
router.register("ai/reviews", AIReviewViewSet, basename="ai-review")
router.register("ai/summaries", AISummaryViewSet, basename="ai-summary")
router.register("doctor/feedback", DoctorFeedbackViewSet, basename="doctor-feedback")
router.register("doctor/review-tasks", ReviewTaskViewSet, basename="review-task")
router.register("notifications", NotificationViewSet, basename="notification")
router.register("audit", AuditViewSet, basename="audit")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", HealthView.as_view()),
    path("api/auth/login/", LoginView.as_view()),
    path("api/auth/refresh/", TokenRefreshView.as_view()),
    path("api/auth/me/", MeView.as_view()),
    path("api/", include(router.urls)),
    path("api/schema/", SpectacularAPIView.as_view(permission_classes=[]), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[])),
]
