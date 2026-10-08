from rest_framework import serializers

from .models import (
    READING_UNITS,
    VITAL_SPECS,
    CareAssignment,
    CaregiverConsent,
    ConsentScope,
    DeviceReading,
    DialysisPrescription,
    DialysisSession,
    LaboratoryReport,
    LaboratoryResult,
    NursingAction,
    NursingNote,
    Patient,
    SessionEvent,
    VitalSign,
)

AUDIT_FIELDS = ["id", "created_at"]


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ["id", "mrn", "full_name", "date_of_birth", "is_synthetic"]
        read_only_fields = fields


class PatientBriefSerializer(serializers.ModelSerializer):
    """What a patient or caregiver sees of the patient record."""

    class Meta:
        model = Patient
        fields = ["id", "full_name"]
        read_only_fields = fields


class CareAssignmentSerializer(serializers.ModelSerializer):
    professional_name = serializers.CharField(source="professional.display_name", read_only=True)
    professional_role = serializers.CharField(source="professional.role", read_only=True)

    class Meta:
        model = CareAssignment
        fields = [
            "id",
            "patient",
            "professional",
            "professional_name",
            "professional_role",
            "active",
            "starts_at",
            "ends_at",
        ]
        read_only_fields = ["id", "starts_at", "professional_name", "professional_role"]


class ConsentSerializer(serializers.ModelSerializer):
    caregiver_username = serializers.CharField(write_only=True)
    caregiver_name = serializers.CharField(source="caregiver.display_name", read_only=True)
    patient_name = serializers.CharField(source="patient.full_name", read_only=True)
    scopes = serializers.ListField(child=serializers.ChoiceField(choices=ConsentScope.choices), allow_empty=False)

    class Meta:
        model = CaregiverConsent
        fields = [
            "id", "patient", "patient_name", "caregiver_username", "caregiver_name", "scopes",
            "expires_at", "revoked_at", "created_at",
        ]  # fmt: skip
        read_only_fields = ["id", "patient", "revoked_at", "created_at"]


class PrescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DialysisPrescription
        fields = [
            "id", "patient", "version", "prescribed_by", "duration_minutes", "blood_flow_ml_min",
            "dialysate_flow_ml_min", "target_uf_ml", "access_type", "active", "notes", "created_at",
        ]  # fmt: skip
        read_only_fields = ["id", "version", "prescribed_by", "active", "created_at"]


class VitalSignSerializer(serializers.ModelSerializer):
    unit = serializers.CharField(required=False)

    class Meta:
        model = VitalSign
        fields = [
            "id", "patient", "session", "kind", "value", "unit", "phase", "source", "verification_status",
            "recorded_at", "recorded_by", "amends", "created_at",
        ]  # fmt: skip
        read_only_fields = ["id", "patient", "source", "verification_status", "recorded_by", "amends", "created_at"]

    def validate(self, attrs: dict) -> dict:
        unit, low, high = VITAL_SPECS[attrs["kind"]]
        # One unit per measurement kind. A different unit is rejected, never silently converted.
        if attrs.setdefault("unit", unit) != unit:
            raise serializers.ValidationError({"unit": f"{attrs['kind']} must be recorded in {unit}."})
        if not low <= attrs["value"] <= high:
            raise serializers.ValidationError({"value": f"Outside the plausible range {low}-{high} {unit}."})
        return attrs


class DeviceReadingSerializer(serializers.ModelSerializer):
    unit = serializers.CharField(required=False)

    class Meta:
        model = DeviceReading
        fields = [
            "id", "session", "kind", "value", "unit", "source", "source_id", "verification_status",
            "recorded_at", "recorded_by", "created_at",
        ]  # fmt: skip
        read_only_fields = ["id", "source", "source_id", "verification_status", "recorded_by", "created_at"]

    def validate(self, attrs: dict) -> dict:
        unit = READING_UNITS[attrs["kind"]]
        if attrs.setdefault("unit", unit) != unit:
            raise serializers.ValidationError({"unit": f"{attrs['kind']} must be recorded in {unit}."})
        return attrs


class NursingActionSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.display_name", read_only=True)

    class Meta:
        model = NursingAction
        fields = [
            "id", "session", "author", "author_name", "action_type", "description", "reason", "order",
            "performed_at", "amends", "created_at",
        ]  # fmt: skip
        read_only_fields = ["id", "author", "author_name", "amends", "created_at"]

    def validate(self, attrs: dict) -> dict:
        if attrs["action_type"] == "medication_administration":
            order = attrs.get("order")
            if order is None or not order.active or order.patient_id != attrs["session"].patient_id:
                raise serializers.ValidationError(
                    {"order": "Medication administration needs an active physician order for this patient."}
                )
        return attrs


class NursingNoteSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.display_name", read_only=True)

    class Meta:
        model = NursingNote
        fields = ["id", "session", "author", "author_name", "text", "amends", "created_at"]
        read_only_fields = ["id", "author", "author_name", "amends", "created_at"]


class SessionEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionEvent
        fields = [
            "id", "session", "event_type", "description", "occurred_at", "reported_by",
            "resolution", "resolved_at", "resolved_by", "created_at",
        ]  # fmt: skip
        read_only_fields = ["id", "reported_by", "resolution", "resolved_at", "resolved_by", "created_at"]


class ResolveEventSerializer(serializers.Serializer):
    resolution = serializers.CharField()


class SessionSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source="patient.full_name", read_only=True)
    patient_mrn = serializers.CharField(source="patient.mrn", read_only=True)
    prescribed_duration_minutes = serializers.IntegerField(source="prescription.duration_minutes", read_only=True)

    class Meta:
        model = DialysisSession
        fields = [
            "id", "patient", "patient_name", "patient_mrn", "prescription", "prescribed_duration_minutes", "device",
            "status", "scheduled_start", "started_at", "ended_at", "pre_weight_kg", "post_weight_kg", "uf_volume_ml",
        ]  # fmt: skip
        read_only_fields = [
            "id", "patient_name", "patient_mrn", "prescription", "prescribed_duration_minutes", "status",
            "started_at", "ended_at", "pre_weight_kg", "post_weight_kg", "uf_volume_ml",
        ]  # fmt: skip


class SessionDetailSerializer(SessionSerializer):
    vitals = VitalSignSerializer(many=True, read_only=True)
    device_readings = DeviceReadingSerializer(many=True, read_only=True)
    nursing_actions = NursingActionSerializer(many=True, read_only=True)
    nursing_notes = NursingNoteSerializer(many=True, read_only=True)
    events = SessionEventSerializer(many=True, read_only=True)

    class Meta(SessionSerializer.Meta):
        fields = [
            *SessionSerializer.Meta.fields,
            "vitals",
            "device_readings",
            "nursing_actions",
            "nursing_notes",
            "events",
        ]


class SessionPublicSerializer(serializers.ModelSerializer):
    """Patient and caregiver view of a session: when it is or was, nothing clinical."""

    patient_name = serializers.CharField(source="patient.full_name", read_only=True)

    class Meta:
        model = DialysisSession
        fields = ["id", "patient", "patient_name", "status", "scheduled_start", "started_at", "ended_at"]
        read_only_fields = fields


class StartSessionSerializer(serializers.Serializer):
    pre_weight_kg = serializers.DecimalField(
        max_digits=5, decimal_places=1, min_value=20, max_value=300, required=False
    )


class CompleteSessionSerializer(serializers.Serializer):
    post_weight_kg = serializers.DecimalField(
        max_digits=5, decimal_places=1, min_value=20, max_value=300, required=False
    )
    uf_volume_ml = serializers.IntegerField(min_value=0, max_value=10000, required=False)


class LaboratoryResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = LaboratoryResult
        fields = ["id", "analyte", "value", "unit", "reference_low", "reference_high"]
        read_only_fields = ["id"]


class LaboratoryReportSerializer(serializers.ModelSerializer):
    results = LaboratoryResultSerializer(many=True)

    class Meta:
        model = LaboratoryReport
        fields = [
            "id",
            "patient",
            "collected_at",
            "reported_at",
            "source",
            "released_to_patient",
            "released_at",
            "results",
        ]
        read_only_fields = ["id", "released_to_patient", "released_at"]

    def validate_results(self, results: list) -> list:
        if not results:
            raise serializers.ValidationError("A laboratory report needs at least one result.")
        return results
