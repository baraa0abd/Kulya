from rest_framework import serializers

from .models import Summary


class SummarySentenceSerializer(serializers.Serializer):
    text_ar = serializers.CharField()
    citations = serializers.ListField(child=serializers.IntegerField())


class SummarySerializer(serializers.ModelSerializer):
    sentences = SummarySentenceSerializer(many=True, read_only=True)

    class Meta:
        model = Summary
        fields = [
            "id", "patient", "audience", "period_start", "period_end", "sentences", "status",
            "validation_errors", "model_name", "prompt_version", "created_at", "approved_by", "approved_at",
        ]  # fmt: skip
        read_only_fields = fields


class SummaryRequestSerializer(serializers.Serializer):
    audience = serializers.ChoiceField(choices=Summary.Audience.choices)
    period_start = serializers.DateField()
    period_end = serializers.DateField()

    def validate(self, attrs: dict) -> dict:
        if attrs["period_end"] < attrs["period_start"]:
            raise serializers.ValidationError({"period_end": "period_end must not be before period_start."})
        return attrs
