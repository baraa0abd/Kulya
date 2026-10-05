"""Extraction draft review (nurse only). Logic lives in clinical/services.py."""

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsNurse
from clinical import services

from .models import ExtractionDraft
from .serializers import ApproveDraftSerializer, ExtractionDraftSerializer, RejectSerializer

DRAFTS = ExtractionDraft.objects.select_related("note")
Draft = ExtractionDraftSerializer


@extend_schema(parameters=[OpenApiParameter("status", str, enum=ExtractionDraft.Status.values, required=False)])
class DraftList(generics.ListAPIView):
    permission_classes = [IsNurse]
    serializer_class = Draft

    def get_queryset(self) -> QuerySet[ExtractionDraft]:
        wanted = self.request.query_params.get("status")
        return DRAFTS.filter(status=wanted) if wanted else DRAFTS.all()


class DraftDetail(generics.RetrieveAPIView):
    permission_classes = [IsNurse]
    serializer_class = Draft
    queryset = DRAFTS
    lookup_url_kwarg = "id"


class DraftApprove(APIView):
    permission_classes = [IsNurse]

    @extend_schema(request=ApproveDraftSerializer, responses=Draft)
    def post(self, request: Request, id: int) -> Response:
        get_object_or_404(ExtractionDraft, pk=id)
        body = ApproveDraftSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        draft = services.approve_draft(id, request.user, body.validated_data.get("edited_payload"))
        return Response(Draft(draft).data)


class DraftReject(APIView):
    permission_classes = [IsNurse]

    @extend_schema(request=RejectSerializer, responses=Draft)
    def post(self, request: Request, id: int) -> Response:
        get_object_or_404(ExtractionDraft, pk=id)
        body = RejectSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return Response(Draft(services.reject_draft(id, request.user, body.validated_data.get("reason", ""))).data)


class DraftRetry(APIView):
    permission_classes = [IsNurse]

    @extend_schema(request=None, responses={201: Draft})
    def post(self, request: Request, id: int) -> Response:
        get_object_or_404(ExtractionDraft, pk=id)
        return Response(Draft(services.retry_draft(id, request.user)).data, status=status.HTTP_201_CREATED)
