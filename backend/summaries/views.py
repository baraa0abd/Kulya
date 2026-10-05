"""Summaries. Patients can only ever reach approved, patient-audience summaries of their own record."""

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsClinician, IsDoctor, IsPatientOwner
from ai_engine.serializers import RejectSerializer
from clinical.models import Patient

from . import services
from .models import Summary
from .serializers import SummaryRequestSerializer, SummarySerializer


def visible_to_patient(user) -> QuerySet[Summary]:
    return Summary.objects.filter(
        patient_id=user.patient_id, audience=Summary.Audience.PATIENT, status=Summary.Status.APPROVED
    )


class SummaryCreate(APIView):
    permission_classes = [IsClinician]

    @extend_schema(request=SummaryRequestSerializer, responses={201: SummarySerializer})
    def post(self, request: Request, id: int) -> Response:
        patient = get_object_or_404(Patient, pk=id)
        body = SummaryRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        summary = services.request_summary(patient, request.user, **body.validated_data)
        return Response(SummarySerializer(summary).data, status=status.HTTP_201_CREATED)


class SummaryDetail(generics.RetrieveAPIView):
    permission_classes = [IsClinician | IsPatientOwner]
    serializer_class = SummarySerializer
    lookup_url_kwarg = "id"

    def get_queryset(self) -> QuerySet[Summary]:
        user = self.request.user
        # Anything a patient may not see is a 404, so drafts and other patients' summaries are invisible.
        return visible_to_patient(user) if user.role == "patient" else Summary.objects.all()


class MySummaries(generics.ListAPIView):
    permission_classes = [IsPatientOwner]
    serializer_class = SummarySerializer

    def get_queryset(self) -> QuerySet[Summary]:
        return visible_to_patient(self.request.user)


class SummaryApprove(APIView):
    permission_classes = [IsDoctor]

    @extend_schema(request=None, responses=SummarySerializer)
    def post(self, request: Request, id: int) -> Response:
        get_object_or_404(Summary, pk=id)
        return Response(SummarySerializer(services.review_summary(id, request.user, approve=True)).data)


class SummaryReject(APIView):
    permission_classes = [IsDoctor]

    @extend_schema(request=RejectSerializer, responses=SummarySerializer)
    def post(self, request: Request, id: int) -> Response:
        get_object_or_404(Summary, pk=id)
        body = RejectSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        reason = body.validated_data.get("reason", "")
        return Response(SummarySerializer(services.review_summary(id, request.user, False, reason)).data)
