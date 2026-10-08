"""Clinical record. Measurements always carry an explicit unit, source and verification status.
Signed records (vitals, readings, actions, notes) are immutable; corrections are amendments."""

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from core.models import ImmutableModel, Organization, UUIDModel

USER = settings.AUTH_USER_MODEL


class Patient(UUIDModel):
    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="patients")
    mrn = models.CharField(max_length=40)  # synthetic record number, e.g. SYN-001
    full_name = models.CharField(max_length=200)
    date_of_birth = models.DateField()
    user = models.OneToOneField(USER, null=True, blank=True, on_delete=models.PROTECT, related_name="patient_record")
    is_synthetic = models.BooleanField(default=True)

    class Meta:
        ordering = ["mrn"]
        constraints = [models.UniqueConstraint(fields=["organization", "mrn"], name="unique_mrn_per_org")]

    def __str__(self) -> str:
        return self.mrn


class CareAssignment(UUIDModel):
    """Connects one professional to one patient. Access exists only while this is active."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="assignments")
    professional = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="assignments")
    active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(auto_now_add=True)
    ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["patient", "professional"], name="unique_assignment")]


class ConsentScope(models.TextChoices):
    SUMMARIES = "summaries"
    APPOINTMENTS = "appointments"
    LABS = "labs"
    NUTRITION = "nutrition"  # read the food diary, plan and released nutrition reports
    NUTRITION_LOG = "nutrition_log"  # record meals on the patient's behalf


class CaregiverConsent(UUIDModel):
    """A patient-specific grant to one family caregiver. Nothing is shared without one."""

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="consents")
    caregiver = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="consents_received")
    scopes = models.JSONField(default=list)  # list of ConsentScope values
    granted_by = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="+")
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class DialysisDevice(UUIDModel):
    """Inventory record only. The MVP never connects to or controls dialysis hardware."""

    organization = models.ForeignKey(Organization, on_delete=models.PROTECT, related_name="devices")
    serial_number = models.CharField(max_length=80)
    model_name = models.CharField(max_length=120)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "serial_number"], name="unique_device")]


class AccessType(models.TextChoices):
    AVF = "AVF"
    AVG = "AVG"
    CVC = "CVC"


class DialysisPrescription(UUIDModel):
    """Physician order for dialysis. Versioned: a change is a new version, never an overwrite."""

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="prescriptions")
    version = models.PositiveIntegerField()
    prescribed_by = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="+")
    duration_minutes = models.PositiveIntegerField()
    blood_flow_ml_min = models.PositiveIntegerField(null=True, blank=True)
    dialysate_flow_ml_min = models.PositiveIntegerField(null=True, blank=True)
    target_uf_ml = models.PositiveIntegerField(null=True, blank=True)
    access_type = models.CharField(max_length=3, choices=AccessType.choices)
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-version"]
        constraints = [models.UniqueConstraint(fields=["patient", "version"], name="unique_prescription_version")]


class SessionStatus(models.TextChoices):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DialysisSession(UUIDModel):
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="sessions")
    prescription = models.ForeignKey(DialysisPrescription, on_delete=models.PROTECT, related_name="sessions")
    device = models.ForeignKey(DialysisDevice, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    status = models.CharField(max_length=12, choices=SessionStatus.choices, default=SessionStatus.SCHEDULED)
    scheduled_start = models.DateTimeField()
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    pre_weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    post_weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    uf_volume_ml = models.PositiveIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="+")
    started_by = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    completed_by = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-scheduled_start"]
        indexes = [models.Index(fields=["patient", "scheduled_start"]), models.Index(fields=["status"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(ended_at__isnull=True) | Q(started_at__isnull=True) | Q(ended_at__gte=F("started_at")),
                name="session_end_not_before_start",
            )
        ]


class Source(models.TextChoices):
    MEASURED = "measured"  # taken by staff
    DEVICE = "device"  # read off the machine display and typed in
    PATIENT_REPORTED = "patient_reported"
    CALCULATED = "calculated"


class Verification(models.TextChoices):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"


class Phase(models.TextChoices):
    PRE = "pre"
    INTRA = "intra"
    POST = "post"
    HOME = "home"


class VitalKind(models.TextChoices):
    SBP = "systolic_bp"
    DBP = "diastolic_bp"
    HEART_RATE = "heart_rate"
    TEMPERATURE = "temperature"
    SPO2 = "spo2"
    WEIGHT = "weight"


# kind -> (unit, plausible minimum, plausible maximum). Typo guards, not clinical thresholds.
VITAL_SPECS = {
    VitalKind.SBP: ("mmHg", 40, 300),
    VitalKind.DBP: ("mmHg", 20, 200),
    VitalKind.HEART_RATE: ("bpm", 20, 250),
    VitalKind.TEMPERATURE: ("degC", 30, 45),
    VitalKind.SPO2: ("%", 50, 100),
    VitalKind.WEIGHT: ("kg", 20, 300),
}


class VitalSign(ImmutableModel):
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="vitals")
    session = models.ForeignKey(DialysisSession, null=True, blank=True, on_delete=models.PROTECT, related_name="vitals")
    kind = models.CharField(max_length=20, choices=VitalKind.choices)
    value = models.DecimalField(max_digits=7, decimal_places=2)
    unit = models.CharField(max_length=10)
    phase = models.CharField(max_length=6, choices=Phase.choices)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MEASURED)
    verification_status = models.CharField(max_length=12, choices=Verification.choices, default=Verification.VERIFIED)
    recorded_at = models.DateTimeField()
    recorded_by = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="+")
    amends = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="amended_by")

    class Meta:
        ordering = ["recorded_at"]
        indexes = [models.Index(fields=["patient", "kind", "recorded_at"])]


class ReadingKind(models.TextChoices):
    BLOOD_FLOW = "blood_flow_rate"
    DIALYSATE_FLOW = "dialysate_flow_rate"
    VENOUS_PRESSURE = "venous_pressure"
    ARTERIAL_PRESSURE = "arterial_pressure"
    UF_RATE = "uf_rate"
    UF_REMOVED = "uf_removed"


READING_UNITS = {
    ReadingKind.BLOOD_FLOW: "mL/min",
    ReadingKind.DIALYSATE_FLOW: "mL/min",
    ReadingKind.VENOUS_PRESSURE: "mmHg",
    ReadingKind.ARTERIAL_PRESSURE: "mmHg",
    ReadingKind.UF_RATE: "mL/h",
    ReadingKind.UF_REMOVED: "mL",
}


class DeviceReading(ImmutableModel):
    """A machine measurement typed in by a nurse. `source_id` names where it came from."""

    session = models.ForeignKey(DialysisSession, on_delete=models.PROTECT, related_name="device_readings")
    kind = models.CharField(max_length=24, choices=ReadingKind.choices)
    value = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.CharField(max_length=10)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.DEVICE)
    source_id = models.CharField(max_length=80, blank=True)  # device serial when known
    verification_status = models.CharField(max_length=12, choices=Verification.choices, default=Verification.VERIFIED)
    recorded_at = models.DateTimeField()
    recorded_by = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["recorded_at"]


class LaboratoryReport(UUIDModel):
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="lab_reports")
    collected_at = models.DateTimeField()
    reported_at = models.DateTimeField()
    source = models.CharField(max_length=120)  # laboratory name / system
    entered_by = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="+")
    released_to_patient = models.BooleanField(default=False)
    released_by = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-collected_at"]


class LaboratoryResult(UUIDModel):
    report = models.ForeignKey(LaboratoryReport, on_delete=models.CASCADE, related_name="results")
    analyte = models.CharField(max_length=60)
    value = models.DecimalField(max_digits=10, decimal_places=3)
    unit = models.CharField(max_length=20)
    reference_low = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    reference_high = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)

    class Meta:
        ordering = ["analyte"]


class ActionType(models.TextChoices):
    MEDICATION = "medication_administration"
    UF_ADJUSTMENT = "uf_adjustment"
    TREATMENT_PAUSE = "treatment_pause"
    FLUID_BOLUS = "fluid_bolus"
    ACCESS_CARE = "access_care"
    POSITION_CHANGE = "position_change"
    PHYSICIAN_NOTIFIED = "physician_notified"
    OTHER = "other"


class NursingAction(ImmutableModel):
    session = models.ForeignKey(DialysisSession, on_delete=models.PROTECT, related_name="nursing_actions")
    author = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="nursing_actions")
    action_type = models.CharField(max_length=30, choices=ActionType.choices)
    description = models.TextField()
    reason = models.TextField(blank=True)
    # Medication may only be recorded against a valid order.
    order = models.ForeignKey(DialysisPrescription, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    performed_at = models.DateTimeField()
    amends = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="amended_by")

    class Meta:
        ordering = ["performed_at"]


class NursingNote(ImmutableModel):
    session = models.ForeignKey(DialysisSession, on_delete=models.PROTECT, related_name="nursing_notes")
    author = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="+")
    text = models.TextField()
    amends = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="amended_by")

    class Meta:
        ordering = ["created_at"]


class EventType(models.TextChoices):
    HYPOTENSION = "hypotension"
    CRAMPS = "cramps"
    CLOTTING = "clotting"
    MACHINE_ALARM = "machine_alarm"
    ACCESS_ISSUE = "access_issue"
    SYMPTOM = "symptom"
    INCIDENT = "incident"
    OTHER = "other"


class SessionEvent(UUIDModel):
    """Something that happened during a session. The description is fixed; only the resolution may
    be added later, once, through the resolve endpoint."""

    session = models.ForeignKey(DialysisSession, on_delete=models.PROTECT, related_name="events")
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    description = models.TextField()
    occurred_at = models.DateTimeField()
    reported_by = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="+")
    resolution = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["occurred_at"]
