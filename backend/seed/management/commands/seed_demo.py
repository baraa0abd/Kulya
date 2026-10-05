"""Load the synthetic demo data. Idempotent: running it twice creates nothing new.

DEMO_PASSWORD=... python manage.py seed_demo --approve-facts
"""

import json
import os
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from ai_engine.models import ExtractionDraft
from ai_engine.validators import validate_extraction
from clinical.models import Note, Patient, Session
from clinical.services import merge_facts
from rules.services import evaluate_patient

DATA = Path(__file__).resolve().parents[2] / "data" / "demo.json"
# username -> (role, patient code or None). Two care teams by naming only: there is no team model,
# so every nurse and doctor can see every patient.
#   Team A: doctor1 + nurse1..nurse3      Team B: doctor2 + nurse4..nurse6
USERS = {
    **{f"nurse{i}": ("nurse", None) for i in range(1, 7)},
    **{f"doctor{i}": ("doctor", None) for i in range(1, 3)},
    **{f"patient_syn00{i}": ("patient", f"SYN-00{i}") for i in range(1, 4)},
    "admin1": ("admin", None),
}


class Command(BaseCommand):
    help = "Create demo users and the three synthetic patients (SYN-001..003) with sessions and notes."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--approve-facts",
            action="store_true",
            help="Also insert the hand-written expected extractions as nurse-approved facts (no LLM needed).",
        )

    @transaction.atomic
    def handle(self, *args, approve_facts: bool = False, **options) -> None:
        password = os.environ.get("DEMO_PASSWORD")
        if not password:
            raise CommandError("Set DEMO_PASSWORD in the environment (see .env.example).")
        data = json.loads(DATA.read_text(encoding="utf-8"))

        patients = {}
        for p in data["patients"]:
            patients[p["code"]], _ = Patient.objects.get_or_create(
                code=p["code"],
                defaults={"display_name_ar": p["display_name_ar"], "birth_year": p["birth_year"], "is_synthetic": True},
            )

        users = {}
        for username, (role, patient_code) in USERS.items():
            user, _ = get_user_model().objects.get_or_create(username=username)
            user.role, user.patient = role, patients.get(patient_code)
            user.is_staff = role == "admin"
            user.set_password(password)
            user.save()
            users[username] = user
        nurse = users["nurse1"]

        created = {"sessions": 0, "notes": 0, "approved": 0}
        for p in data["patients"]:
            patient = patients[p["code"]]
            for s in p["sessions"]:
                notes = s.pop("notes")
                session, new = Session.objects.get_or_create(
                    patient=patient, session_date=s.pop("session_date"), defaults={**s, "created_by": nurse}
                )
                created["sessions"] += new
                previous = None
                for n in notes:
                    note = Note.objects.filter(session=session, text_ar=n["text_ar"]).first()
                    if note is None:
                        note = Note.objects.create(
                            session=session, author=nurse, text_ar=n["text_ar"], supersedes=previous
                        )
                        created["notes"] += 1
                    previous = note
                    if approve_facts and not note.extraction_drafts.exists():
                        created["approved"] += self._approve(note, n, nurse)
            evaluate_patient(patient.id)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded: {Patient.objects.count()} patients, {Session.objects.count()} sessions, "
                f"{Note.objects.count()} notes (new: {created}). Users: {', '.join(USERS)}."
            )
        )

    def _approve(self, note: Note, entry: dict, nurse) -> bool:
        """Record the expected extraction as a draft reviewed by nurse1. Notes that were later corrected
        get a rejected draft; everything else is approved and merged into SessionFacts."""
        ok, errors = validate_extraction(entry["expected"], note.text_ar)
        if not ok:
            raise CommandError(f"Seed extraction for note {note.id} is not grounded: {errors}")
        approved = not entry["superseded"]
        ExtractionDraft.objects.create(
            note=note,
            payload=entry["expected"],
            status=ExtractionDraft.Status.APPROVED if approved else ExtractionDraft.Status.REJECTED,
            model_name="seed",
            prompt_version="extraction_v1",
            reviewed_by=nurse,
            reviewed_at=timezone.now(),
        )
        if approved:
            merge_facts(note, entry["expected"])
        return approved
