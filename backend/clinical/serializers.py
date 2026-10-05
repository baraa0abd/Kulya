from rest_framework import serializers

from rules.serializers import FlagSerializer

from .models import Note, Patient, Session, SessionFacts


class PatientSerializer(serializers.ModelSerializer):
    attention_flag_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Patient
        fields = ["id", "code", "display_name_ar", "birth_year", "is_synthetic", "created_at", "attention_flag_count"]
        read_only_fields = fields


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = [
            "id", "patient", "session_date", "start_time", "end_time",
            "pre_sbp", "pre_dbp", "post_sbp", "post_dbp", "min_intra_sbp",
            "pre_weight_kg", "post_weight_kg", "uf_volume_ml", "access_type",
            "created_by", "created_at",
        ]  # fmt: skip
        read_only_fields = ["id", "patient", "created_by", "created_at"]

    def validate(self, attrs: dict) -> dict:
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError({"end_time": "end_time must be after start_time."})
        return attrs


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ["id", "session", "author", "text_ar", "created_at", "supersedes"]
        read_only_fields = ["id", "session", "author", "created_at"]


class NoteCreatedSerializer(NoteSerializer):
    """Response of POST /sessions/{id}/notes/: the note plus the extraction draft it triggered."""

    draft_id = serializers.IntegerField(read_only=True, allow_null=True)
    draft_status = serializers.CharField(read_only=True, allow_null=True)

    class Meta(NoteSerializer.Meta):
        fields = [*NoteSerializer.Meta.fields, "draft_id", "draft_status"]


class SessionFactsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionFacts
        fields = ["symptoms", "access_findings", "staff_actions", "updated_at"]
        read_only_fields = fields


class TimelineSessionSerializer(SessionSerializer):
    """One timeline entry: session vitals + notes + approved facts + flags."""

    notes = NoteSerializer(many=True, read_only=True)
    facts = SessionFactsSerializer(read_only=True, allow_null=True)
    flags = FlagSerializer(many=True, read_only=True)

    class Meta(SessionSerializer.Meta):
        fields = [*SessionSerializer.Meta.fields, "notes", "facts", "flags"]
