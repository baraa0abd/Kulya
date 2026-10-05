"""Patients, sessions, notes, timeline, flags. Thin views: logic lives in clinical/services.py."""

from django.db.models import Count, Q, QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsClinician, IsNurse, IsPatientOwner
from rules.models import Flag
from rules.serializers import FlagSerializer

from . import services
from .models import Note, Patient, Session
from .serializers import (
    NoteCreatedSerializer,
    NoteSerializer,
    PatientSerializer,
    SessionSerializer,
    TimelineSessionSerializer,
)

ATTENTION_FLAGS = Count("flags", filter=Q(flags__severity=Flag.Severity.ATTENTION))


class PatientList(generics.ListAPIView):
    permission_classes = [IsClinician]
    serializer_class = PatientSerializer
    queryset = Patient.objects.annotate(attention_flag_count=ATTENTION_FLAGS).order_by("code")


class PatientDetail(generics.RetrieveAPIView):
    permission_classes = [IsClinician | IsPatientOwner]
    serializer_class = PatientSerializer
    lookup_url_kwarg = "id"

    def get_queryset(self) -> QuerySet[Patient]:
        patients = Patient.objects.annotate(attention_flag_count=ATTENTION_FLAGS)
        user = self.request.user
        # A patient asking for someone else's record gets 404, not 403: existence is not revealed.
        return patients.filter(id=user.patient_id) if user.role == "patient" else patients


class PatientTimeline(generics.ListAPIView):
    """Sessions newest first, each with vitals, notes, approved facts, and its flags. 20 per page."""

    permission_classes = [IsClinician]
    serializer_class = TimelineSessionSerializer

    def get_queryset(self) -> QuerySet[Session]:
        patient = get_object_or_404(Patient, pk=self.kwargs["id"])
        return (
            Session.objects.filter(patient=patient)
            .select_related("facts")
            .prefetch_related("notes", "flags")
            .order_by("-session_date", "-start_time", "-id")
        )


class PatientFlags(generics.ListAPIView):
    permission_classes = [IsClinician]
    serializer_class = FlagSerializer

    def get_queryset(self) -> QuerySet[Flag]:
        patient = get_object_or_404(Patient, pk=self.kwargs["id"])
        return Flag.objects.filter(patient=patient).order_by("-session__session_date", "rule_id", "id")


class SessionCreate(APIView):
    permission_classes = [IsNurse]

    @extend_schema(request=SessionSerializer, responses={201: SessionSerializer})
    def post(self, request: Request, id: int) -> Response:
        patient = get_object_or_404(Patient, pk=id)
        serializer = SessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = services.create_session(patient, request.user, serializer.validated_data)
        return Response(SessionSerializer(session).data, status=status.HTTP_201_CREATED)


class SessionDetail(generics.RetrieveAPIView):
    permission_classes = [IsClinician]
    serializer_class = SessionSerializer
    queryset = Session.objects.all()
    lookup_url_kwarg = "id"


class NoteCreate(APIView):
    permission_classes = [IsNurse]

    @extend_schema(request=NoteSerializer, responses={201: NoteCreatedSerializer})
    def post(self, request: Request, id: int) -> Response:
        session = get_object_or_404(Session, pk=id)
        serializer = NoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        draft = services.create_note(session, request.user, **serializer.validated_data)
        note = draft.note
        note.draft_id, note.draft_status = draft.id, draft.status
        return Response(NoteCreatedSerializer(note).data, status=status.HTTP_201_CREATED)


class NoteDetail(generics.RetrieveAPIView):
    permission_classes = [IsClinician]
    serializer_class = NoteSerializer
    queryset = Note.objects.all()
    lookup_url_kwarg = "id"
