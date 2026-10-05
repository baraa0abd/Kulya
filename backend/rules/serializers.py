from rest_framework import serializers

from .models import Flag


class FlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Flag
        fields = [
            "id", "patient", "session", "rule_id", "severity", "message_ar", "evidence", "created_at", "rules_version",
        ]  # fmt: skip
        read_only_fields = fields
