"""Clinical API. Thin views: RolePolicy decides who may call, ScopedViewSet decides which
patients they reach, services do the writing."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from core.models import Role
from core.permissions import DOCTOR, EVERYONE, FAMILY, NURSE, PATIENT, STAFF, get_patient_or_404, patients_for
from core.services import audit, idempotent

from . import services
from .models import (
    CareAssignment,
    CaregiverConsent,
    ConsentScope,
    DeviceReading,
    DialysisPrescription,
    DialysisSession,
    LaboratoryReport,
    NursingAction,
    NursingNote,
    Patient,
    SessionEvent,
    SessionStatus,
    VitalSign,
)
from .serializers import (
    CareAssignmentSerializer,
    CompleteSessionSerializer,
    ConsentSerializer,
    DeviceReadingSerializer,
    LaboratoryReportSerializer,
    NursingActionSerializer,
    NursingNoteSerializer,
    PatientBriefSerializer,
    PatientSerializer,
    PrescriptionSerializer,
    ResolveEventSerializer,
    SessionDetailSerializer,
    SessionEventSerializer,
    SessionPublicSerializer,
    SessionSerializer,
    StartSessionSerializer,
    VitalSignSerializer,
)


class ScopedViewSet(viewsets.GenericViewSet):
    """Every queryset is cut down to the caller's patients before anything else happens, so an id
    outside that scope is a 404 on list, detail and every custom action alike."""

    patient_field = "patient"
    family_scope: str | None = None
    filters: tuple[str, ...] = ()

    def scoped(self, queryset: QuerySet) -> QuerySet:
        patients = patients_for(self.request.user, self.family_scope)
        return queryset.filter(**{f"{self.patient_field}__in": patients})

    def get_queryset(self) -> QuerySet:
        queryset = self.scoped(self.queryset)
        try:
            for name in self.filters:
                if value := self.request.query_params.get(name):
                    queryset = queryset.filter(**{name: value})
        except (DjangoValidationError, ValueError) as exc:
            raise ValidationError({"filter": "Invalid filter value."}) from exc
        return queryset

    def session_in_scope(self, serializer) -> DialysisSession:
        """The session named in a write must belong to one of the caller's patients."""
        session = serializer.validated_data["session"]
        if not patients_for(self.request.user).filter(pk=session.patient_id).exists():
            raise NotFound()
        return session


class PatientViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, ScopedViewSet):
    read_roles = EVERYONE
    queryset = Patient.objects.all()
    patient_field = "pk"

    def get_serializer_class(self):
        return PatientSerializer if self.request.user.role in STAFF else PatientBriefSerializer

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        patient = self.get_object()
        audit(request.user, "patient_viewed", patient, patient=patient)
        return Response(self.get_serializer(patient).data)


class CareAssignmentViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, ScopedViewSet):
    """Care teams. Staff see the teams of their own patients; only an organization admin changes them."""

    read_roles = (*STAFF, Role.ORG_ADMIN)
    write_roles = (Role.ORG_ADMIN,)
    action_roles = {"deactivate": (Role.ORG_ADMIN,)}
    serializer_class = CareAssignmentSerializer
    queryset = CareAssignment.objects.select_related("professional")
    filters = ("patient",)

    def scoped(self, queryset: QuerySet) -> QuerySet:
        user = self.request.user
        if user.role == Role.ORG_ADMIN:
            return queryset.filter(patient__organization_id=user.organization_id)
        return super().scoped(queryset)

    def perform_create(self, serializer) -> None:
        user, data = self.request.user, serializer.validated_data
        same_org = {data["patient"].organization_id, data["professional"].organization_id} == {user.organization_id}
        if not same_org or data["professional"].role not in STAFF:
            raise ValidationError({"professional": "Patient and professional must be staff of your organization."})
        audit(user, "care_assignment_created", serializer.save(), patient=data["patient"])

    @extend_schema(request=None, responses=CareAssignmentSerializer)
    @action(detail=True, methods=["post"])
    def deactivate(self, request: Request, pk=None) -> Response:
        assignment = self.get_object()
        assignment.active = False
        assignment.save()
        audit(request.user, "care_assignment_deactivated", assignment, patient=assignment.patient)
        return Response(self.get_serializer(assignment).data)


class ConsentViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Family sharing. A patient grants and revokes; a caregiver can only see grants made to them."""

    read_roles = (PATIENT, FAMILY)
    write_roles = (PATIENT,)
    action_roles = {"revoke": (PATIENT,)}
    serializer_class = ConsentSerializer

    def get_queryset(self) -> QuerySet:
        user = self.request.user
        consents = CaregiverConsent.objects.select_related("caregiver", "patient")
        return consents.filter(caregiver=user) if user.role == FAMILY else consents.filter(patient__user=user)

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        patient = patients_for(request.user).get()
        consent = services.grant_consent(
            patient, request.user, data["caregiver_username"], data["scopes"], data.get("expires_at")
        )
        return Response(self.get_serializer(consent).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=ConsentSerializer)
    @action(detail=True, methods=["post"])
    def revoke(self, request: Request, pk=None) -> Response:
        return Response(self.get_serializer(services.revoke_consent(self.get_object(), request.user)).data)


class PrescriptionViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, ScopedViewSet):
    read_roles = STAFF
    write_roles = (DOCTOR,)
    serializer_class = PrescriptionSerializer
    queryset = DialysisPrescription.objects.all()
    filters = ("patient", "active")

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        patient = get_patient_or_404(request.user, data.pop("patient").pk)
        rx = services.create_prescription(patient, request.user, data)
        return Response(self.get_serializer(rx).data, status=status.HTTP_201_CREATED)


class SessionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, ScopedViewSet):
    read_roles = EVERYONE
    write_roles = (NURSE,)
    action_roles = {"start": (NURSE,), "complete": (NURSE,)}
    queryset = DialysisSession.objects.select_related("patient", "prescription")
    family_scope = ConsentScope.APPOINTMENTS
    filters = ("patient", "status")
    ordering_fields = ["scheduled_start"]

    def get_queryset(self) -> QuerySet:
        sessions = super().get_queryset()
        if day := self.request.query_params.get("date"):
            try:
                sessions = sessions.filter(scheduled_start__date=day)
            except (DjangoValidationError, ValueError) as exc:
                raise ValidationError({"date": "Use YYYY-MM-DD."}) from exc
        if self.request.user.role not in STAFF:
            sessions = sessions.exclude(status=SessionStatus.CANCELLED)
        return sessions

    def get_serializer_class(self):
        if self.request.user.role not in STAFF:
            return SessionPublicSerializer
        return SessionDetailSerializer if self.action == "retrieve" else SessionSerializer

    def retrieve(self, request: Request, *args, **kwargs) -> Response:
        session = self.get_object()
        audit(request.user, "session_viewed", session)
        return Response(self.get_serializer(session).data)

    def create(self, request: Request, *args, **kwargs) -> Response:
        def handler() -> Response:
            serializer = SessionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            patient = get_patient_or_404(request.user, data["patient"].pk)
            session = services.schedule_session(patient, request.user, data["scheduled_start"], data.get("device"))
            return Response(SessionSerializer(session).data, status=status.HTTP_201_CREATED)

        return idempotent(request, handler)

    @extend_schema(request=StartSessionSerializer, responses=SessionSerializer)
    @action(detail=True, methods=["post"])
    def start(self, request: Request, pk=None) -> Response:
        body = StartSessionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        session = services.start_session(self.get_object().pk, request.user, **body.validated_data)
        return Response(SessionSerializer(session).data)

    @extend_schema(request=CompleteSessionSerializer, responses=SessionSerializer)
    @action(detail=True, methods=["post"])
    def complete(self, request: Request, pk=None) -> Response:
        body = CompleteSessionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        session = services.complete_session(self.get_object().pk, request.user, **body.validated_data)
        return Response(SessionSerializer(session).data)


class SessionRecordViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, ScopedViewSet):
    """Shared behaviour for records that hang off a session. No update and no delete exist."""

    read_roles = STAFF
    write_roles = (NURSE,)
    patient_field = "session__patient"
    filters = ("session",)
    audit_action = ""
    author_field = "recorded_by"

    def create(self, request: Request, *args, **kwargs) -> Response:
        def handler() -> Response:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            obj = self.save_record(serializer)
            return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)

        return idempotent(request, handler)

    def save_record(self, serializer):
        self.session_in_scope(serializer)
        return services.record(serializer, self.request.user, self.audit_action, self.author_field)


class AmendMixin:
    """POST /{id}/amend/ adds a corrected copy that points at the original."""

    @action(detail=True, methods=["post"])
    def amend(self, request: Request, pk=None) -> Response:
        original = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.session_in_scope(serializer)
        obj = services.amend(self.queryset.model, original.pk, serializer, request.user, self.author_field)
        return Response(self.get_serializer(obj).data, status=status.HTTP_201_CREATED)


class NursingActionViewSet(AmendMixin, SessionRecordViewSet):
    action_roles = {"amend": (NURSE,)}
    serializer_class = NursingActionSerializer
    queryset = NursingAction.objects.select_related("author")
    author_field = "author"
    ordering_fields = ["performed_at", "created_at"]

    def save_record(self, serializer):
        services.require_open(self.session_in_scope(serializer))
        return services.record_nursing_action(serializer, self.request.user)


class NursingNoteViewSet(AmendMixin, SessionRecordViewSet):
    action_roles = {"amend": (NURSE,)}
    serializer_class = NursingNoteSerializer
    queryset = NursingNote.objects.select_related("author")
    audit_action = "nursing_note_recorded"
    author_field = "author"


class DeviceReadingViewSet(SessionRecordViewSet):
    serializer_class = DeviceReadingSerializer
    queryset = DeviceReading.objects.all()
    audit_action = "device_reading_recorded"

    def save_record(self, serializer):
        session = self.session_in_scope(serializer)
        source_id = session.device.serial_number if session.device else ""
        return services.record(serializer, self.request.user, self.audit_action, "recorded_by", source_id=source_id)


class SessionEventViewSet(SessionRecordViewSet):
    action_roles = {"resolve": (NURSE,)}
    serializer_class = SessionEventSerializer
    queryset = SessionEvent.objects.all()
    audit_action = "session_event_recorded"
    author_field = "reported_by"

    @extend_schema(request=ResolveEventSerializer, responses=SessionEventSerializer)
    @action(detail=True, methods=["post"])
    def resolve(self, request: Request, pk=None) -> Response:
        body = ResolveEventSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        event = services.resolve_event(self.get_object().pk, request.user, body.validated_data["resolution"])
        return Response(self.get_serializer(event).data)


class VitalSignViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, ScopedViewSet):
    """Staff record and read session vitals. A patient may add home measurements and read only those."""

    read_roles = (*STAFF, PATIENT)
    write_roles = (NURSE, PATIENT)
    serializer_class = VitalSignSerializer
    queryset = VitalSign.objects.all()
    filters = ("session", "patient", "kind")
    ordering_fields = ["recorded_at"]

    def get_queryset(self) -> QuerySet:
        vitals = super().get_queryset()
        if self.request.user.role == PATIENT:
            vitals = vitals.filter(recorded_by=self.request.user)
        return vitals

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if user.role == PATIENT:
            serializer.validated_data.pop("session", None)
            serializer.validated_data.pop("phase", None)
            vital = services.record_home_vital(serializer, user, patients_for(user).get())
        else:
            if serializer.validated_data.get("session") is None:
                raise ValidationError({"session": "This field is required."})
            session = self.session_in_scope(serializer)
            vital = services.record(serializer, user, "vital_recorded", "recorded_by", patient=session.patient)
        return Response(self.get_serializer(vital).data, status=status.HTTP_201_CREATED)


class LabReportViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, ScopedViewSet):
    read_roles = EVERYONE
    write_roles = STAFF
    action_roles = {"release": (DOCTOR,)}
    serializer_class = LaboratoryReportSerializer
    queryset = LaboratoryReport.objects.prefetch_related("results")
    family_scope = ConsentScope.LABS
    filters = ("patient",)
    ordering_fields = ["collected_at"]

    def get_queryset(self) -> QuerySet:
        reports = super().get_queryset()
        # Patients and caregivers only ever see reports a doctor has released.
        return reports if self.request.user.role in STAFF else reports.filter(released_to_patient=True)

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        patient = get_patient_or_404(request.user, data.pop("patient").pk)
        report = services.create_lab_report(patient, request.user, data)
        return Response(self.get_serializer(report).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=LaboratoryReportSerializer)
    @action(detail=True, methods=["post"])
    def release(self, request: Request, pk=None) -> Response:
        return Response(self.get_serializer(services.release_lab_report(self.get_object(), request.user)).data)
