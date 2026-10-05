from rest_framework import serializers

from .models import ExtractionDraft


class ExtractionDraftSerializer(serializers.ModelSerializer):
    note_text_ar = serializers.CharField(source="note.text_ar", read_only=True)
    session = serializers.IntegerField(source="note.session_id", read_only=True)

    class Meta:
        model = ExtractionDraft
        fields = [
            "id", "note", "note_text_ar", "session", "payload", "edited_payload", "status",
            "validation_errors", "model_name", "prompt_version", "created_at", "reviewed_by", "reviewed_at",
        ]  # fmt: skip
        read_only_fields = fields


class ApproveDraftSerializer(serializers.Serializer):
    edited_payload = serializers.JSONField(required=False, allow_null=True)


class RejectSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)
