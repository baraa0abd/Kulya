from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import PATIENT, patients_for

from . import services
from .models import ChatMessage


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ["id", "question", "answer", "created_at"]
        read_only_fields = fields


class AskSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=500)
    language = serializers.ChoiceField(choices=["ar", "en"], default="ar")


class ChatView(APIView):
    """The signed-in patient's own conversation. The patient comes from the account, never from the
    request, so one patient can neither ask about nor read another's record."""

    read_roles = (PATIENT,)
    write_roles = (PATIENT,)
    throttle_scope = "ai"

    def patient(self, request: Request):
        patient = patients_for(request.user).first()
        if patient is None:
            raise NotFound()
        return patient

    @extend_schema(responses=ChatMessageSerializer(many=True))
    def get(self, request: Request) -> Response:
        latest = ChatMessage.objects.filter(patient=self.patient(request)).order_by("-created_at")[:30]
        return Response(ChatMessageSerializer(reversed(latest), many=True).data)

    @extend_schema(request=AskSerializer, responses=ChatMessageSerializer)
    def post(self, request: Request) -> Response:
        body = AskSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        message = services.answer(self.patient(request), request.user, **body.validated_data)
        return Response(ChatMessageSerializer(message).data, status=status.HTTP_201_CREATED)
