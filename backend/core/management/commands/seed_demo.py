"""Synthetic demonstration data. Every person and record here is invented.

    DEMO_PASSWORD=... python manage.py seed_demo

Idempotent: if the demo organization already exists, only account passwords are refreshed.
"""

import os
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone

from ai import rag
from ai.services import release_summary, run_review, run_summary, verify_summary
from clinical.models import (
    CareAssignment,
    CaregiverConsent,
    DeviceReading,
    DialysisDevice,
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
from core.models import Organization, Role, User

ORG, OTHER_ORG = "Demo Dialysis Center (synthetic)", "Other Clinic (synthetic)"
POLICY = Path(settings.BASE_DIR) / "ai" / "protocols" / "documentation_policy.md"
# username -> (role, display name)
STAFF = {
    **{f"doctor{i}": (Role.DOCTOR, f"Dr. Demo {'AB'[i - 1]}") for i in (1, 2)},
    **{f"nurse{i}": (Role.NURSE, f"Nurse Demo {i}") for i in range(1, 7)},
    "orgadmin1": (Role.ORG_ADMIN, "Org Admin Demo"),
    "auditor1": (Role.AUDITOR, "Auditor Demo"),
}
# mrn -> (name, birth date, access, doctor, nurses)
PATIENTS = {
    "SYN-001": ("Synthetic Patient One", date(1958, 3, 14), "AVF", "doctor1", ("nurse1", "nurse2", "nurse3")),
    "SYN-002": ("Synthetic Patient Two", date(1965, 7, 2), "AVF", "doctor1", ("nurse1", "nurse2", "nurse3")),
    "SYN-003": ("Synthetic Patient Three", date(1971, 11, 23), "CVC", "doctor2", ("nurse4", "nurse5", "nurse6")),
}
SESSION_DAYS_AGO = (13, 11, 9, 6, 4, 2)


class Command(BaseCommand):
    help = "Create the synthetic demo organization, accounts, patients, sessions, labs and protocols."

    def handle(self, *args, **options) -> None:
        password = os.environ.get("DEMO_PASSWORD")
        if not password:
            raise CommandError("Set DEMO_PASSWORD in the environment (see .env.example).")
        if Organization.objects.filter(name=ORG).exists():
            for user in User.objects.exclude(role=Role.SERVICE):
                user.set_password(password)
                user.save()
            self.stdout.write("Demo data already present; passwords refreshed.")
            return
        # Seeding always uses the offline provider: it must not spend API credit or need a network.
        with override_settings(LLM_PROVIDER="mock"):
            self.seed(password)
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {Patient.objects.count()} patients, {DialysisSession.objects.count()} sessions, "
                f"{User.objects.count()} accounts."
            )
        )

    def user(self, username: str, role: str, name: str, org: Organization | None, password: str) -> User:
        user = User(username=username, role=role, display_name=name, organization=org, is_staff=role == Role.SYS_ADMIN)
        user.set_password(password)
        user.save()
        return user

    @transaction.atomic
    def seed(self, password: str) -> None:
        org = Organization.objects.create(name=ORG)
        users = {name: self.user(name, role, label, org, password) for name, (role, label) in STAFF.items()}
        device = DialysisDevice.objects.create(organization=org, serial_number="DEMO-HD-01", model_name="Demo HD unit")
        rag.ingest_protocol(
            org,
            "Demo documentation workflow policy",
            "1.0",
            POLICY.read_text(encoding="utf-8"),
            owner="Demo clinical lead (synthetic)",
            effective=date(2026, 1, 1),
        )

        patients = {}
        for index, (mrn, (name, born, access, doctor, nurses)) in enumerate(PATIENTS.items(), start=1):
            account = self.user(f"patient{index}", Role.PATIENT, name, org, password)
            patient = Patient.objects.create(
                organization=org, mrn=mrn, full_name=name, date_of_birth=born, user=account
            )
            patients[mrn] = patient
            for member in (doctor, *nurses):
                CareAssignment.objects.create(patient=patient, professional=users[member])
            rx = DialysisPrescription.objects.create(
                patient=patient,
                version=1,
                prescribed_by=users[doctor],
                duration_minutes=240,
                blood_flow_ml_min=300,
                dialysate_flow_ml_min=500,
                target_uf_ml=2000,
                access_type=access,
            )
            self.labs(patient, users[doctor], index)
            nurse = users[nurses[0]]
            for n, days in enumerate(SESSION_DAYS_AGO):
                self.session(patient, rx, device, nurse, days, n, variant=mrn if days == 2 else "")
            start = timezone.now().replace(hour=8 + index, minute=0, second=0, microsecond=0)
            for when in (start, start + timedelta(days=2)):
                DialysisSession.objects.create(
                    patient=patient, prescription=rx, device=device, scheduled_start=when, created_by=nurse
                )

        family1 = self.user("family1", Role.FAMILY, "Family Caregiver One", None, password)
        family2 = self.user("family2", Role.FAMILY, "Family Caregiver Two", None, password)
        one, two = patients["SYN-001"], patients["SYN-002"]
        CaregiverConsent.objects.create(
            patient=one, caregiver=family1, scopes=["appointments", "summaries"], granted_by=one.user
        )
        CaregiverConsent.objects.create(  # expired grant: must give no access
            patient=two,
            caregiver=family2,
            scopes=["appointments", "labs", "summaries"],
            granted_by=two.user,
            expires_at=timezone.now() - timedelta(days=1),
        )

        # A second organization, to demonstrate tenant isolation.
        other = Organization.objects.create(name=OTHER_ORG)
        other_doctor = self.user("doctor_b1", Role.DOCTOR, "Dr. Other Clinic", other, password)
        outsider = Patient.objects.create(
            organization=other, mrn="SYN-B01", full_name="Synthetic Patient Other", date_of_birth=date(1960, 1, 1)
        )
        CareAssignment.objects.create(patient=outsider, professional=other_doctor)

        # AI drafts for every completed session; the two oldest of each patient are verified and released.
        for patient in patients.values():
            doctor = users[PATIENTS[patient.mrn][3]]
            completed = patient.sessions.filter(status="completed").order_by("scheduled_start")
            for position, session in enumerate(completed):
                run_review(session.id, "session_completed")
                summary = run_summary(session.id)
                if position < 2 and summary.status == "unverified":
                    verify_summary(summary.id, doctor, approve=True)
                    release_summary(summary.id, doctor)

    def labs(self, patient: Patient, doctor: User, index: int) -> None:
        for months_ago in (2, 1, 0):
            collected = timezone.now() - timedelta(days=30 * months_ago + 3)
            report = LaboratoryReport.objects.create(
                patient=patient,
                collected_at=collected,
                reported_at=collected + timedelta(hours=6),
                source="Demo laboratory (synthetic)",
                entered_by=doctor,
                released_to_patient=months_ago > 0,
                released_by=doctor if months_ago > 0 else None,
                released_at=collected + timedelta(days=1) if months_ago > 0 else None,
            )
            drift = Decimal(months_ago) / 10
            values = [
                ("Potassium", Decimal("4.8") + drift + Decimal(index) / 10, "mmol/L", "3.5", "5.5"),
                ("Hemoglobin", Decimal("10.6") - drift, "g/dL", "10.0", "12.0"),
                ("Phosphate", Decimal("5.1") + drift, "mg/dL", "3.5", "5.5"),
                ("Albumin", Decimal("3.8"), "g/dL", "3.5", "5.0"),
            ]
            LaboratoryResult.objects.bulk_create(
                LaboratoryResult(report=report, analyte=a, value=v, unit=u, reference_low=lo, reference_high=hi)
                for a, v, u, lo, hi in values
            )

    def session(self, patient, rx, device, nurse, days_ago: int, n: int, variant: str) -> None:
        """One completed session. `variant` plants documentation gaps in each patient's latest session."""
        start = (timezone.now() - timedelta(days=days_ago)).replace(hour=8, minute=0, second=0, microsecond=0)
        minutes = 200 if variant == "SYN-001" else 240  # SYN-001: shorter than prescribed
        end = start + timedelta(minutes=minutes)
        pre_weight = Decimal("62.0") + Decimal(n) / 10
        session = DialysisSession.objects.create(
            patient=patient,
            prescription=rx,
            device=device,
            status="completed",
            scheduled_start=start,
            started_at=start,
            ended_at=end,
            pre_weight_kg=pre_weight,
            post_weight_kg=None if variant == "SYN-002" else pre_weight - 2,  # SYN-002: post weight missing
            uf_volume_ml=2000,
            created_by=nurse,
            started_by=nurse,
            completed_by=nurse,
        )

        def vital(kind: str, value: int, unit: str, phase: str, at) -> None:
            VitalSign.objects.create(
                patient=patient,
                session=session,
                kind=kind,
                value=value,
                unit=unit,
                phase=phase,
                recorded_at=at,
                recorded_by=nurse,
            )

        vital("systolic_bp", 138 + n, "mmHg", "pre", start)
        vital("diastolic_bp", 84, "mmHg", "pre", start)
        vital("heart_rate", 76, "bpm", "pre", start)
        vital("systolic_bp", 126 + n, "mmHg", "intra", start + timedelta(minutes=120))
        vital("systolic_bp", 130 + n, "mmHg", "post", end)
        vital("diastolic_bp", 80, "mmHg", "post", end)
        for offset, kind, value, unit in ((30, "blood_flow_rate", 300, "mL/min"), (30, "venous_pressure", 140, "mmHg")):
            DeviceReading.objects.create(
                session=session,
                kind=kind,
                value=value,
                unit=unit,
                source_id=device.serial_number,
                recorded_at=start + timedelta(minutes=offset),
                recorded_by=nurse,
            )
        NursingAction.objects.create(
            session=session,
            author=nurse,
            action_type="access_care",
            description="Access site inspected and dressed before connection.",
            reason="Routine pre-connection access check.",
            performed_at=start + timedelta(minutes=5),
        )
        NursingNote.objects.create(
            session=session, author=nurse, text="Session documented by the demo seed. Patient comfortable."
        )

        if variant == "SYN-001":
            at = start + timedelta(minutes=150)
            SessionEvent.objects.create(  # left unresolved on purpose
                session=session,
                event_type="hypotension",
                description="Blood pressure reading lower than earlier readings; patient reported dizziness.",
                occurred_at=at,
                reported_by=nurse,
            )
            vital("systolic_bp", 96, "mmHg", "intra", at)
            NursingAction.objects.create(  # no reason on purpose
                session=session,
                author=nurse,
                action_type="fluid_bolus",
                description="Saline bolus 100 mL given.",
                reason="",
                performed_at=at + timedelta(minutes=5),
            )
        elif variant == "SYN-003":
            at = start + timedelta(minutes=90)
            SessionEvent.objects.create(
                session=session,
                event_type="cramps",
                description="Patient reported leg cramps.",
                occurred_at=at,
                reported_by=nurse,
                resolution="Cramps settled after position change.",
                resolved_at=at + timedelta(minutes=15),
                resolved_by=nurse,
            )
            NursingAction.objects.create(
                session=session,
                author=nurse,
                action_type="position_change",
                description="Patient repositioned.",
                reason="Reported leg cramps.",
                performed_at=at + timedelta(minutes=3),
            )
