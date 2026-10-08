"""Clinical workflow: models, session lifecycle, documentation, and the full
nurse -> AI -> doctor -> patient path through the API."""

from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

import clinical.services
from ai.models import AISummary
from clinical.models import DialysisSession, NursingAction, VitalSign
from core.models import AuditEvent, ImmutableError
from tests.conftest import post_action, post_vital
from workflow.models import Notification, ReviewTask


def test_model_constraints(patient, nurse, completed) -> None:
    import uuid

    assert isinstance(patient.id, uuid.UUID) and patient.created_at.tzinfo is not None
    action = completed.nursing_actions.get()
    action.reason = "changed"
    with pytest.raises(ImmutableError):
        action.save()
    with pytest.raises(ImmutableError):
        action.delete()
    with pytest.raises(ImmutableError):
        AuditEvent.objects.first().save()
    with pytest.raises(IntegrityError), transaction.atomic():
        ReviewTask.objects.create(session=completed)  # second open task for one session
    with pytest.raises(IntegrityError), transaction.atomic():
        AISummary.objects.filter(session=completed).update(released=True)  # unverified cannot be released
    with pytest.raises(IntegrityError), transaction.atomic():
        DialysisSession.objects.filter(pk=completed.pk).update(ended_at=completed.started_at - timedelta(minutes=1))


def test_session_lifecycle_and_idempotent_scheduling(api, nurse, patient) -> None:
    client = api(nurse)
    body = {"patient": str(patient.id), "scheduled_start": (timezone.now() + timedelta(hours=1)).isoformat()}
    first = client.post("/api/sessions/", body, format="json", HTTP_IDEMPOTENCY_KEY="abc-1")
    retry = client.post("/api/sessions/", body, format="json", HTTP_IDEMPOTENCY_KEY="abc-1")
    assert first.status_code == retry.status_code == 201 and first.json()["id"] == retry.json()["id"]
    assert DialysisSession.objects.count() == 1
    session_id = first.json()["id"]
    assert first.json()["prescribed_duration_minutes"] == 240 and first.json()["status"] == "scheduled"

    # Documentation and completion need a started session.
    session = DialysisSession.objects.get()
    assert post_vital(client, session, "systolic_bp", 130, "pre").status_code == 409
    assert client.post(f"/api/sessions/{session_id}/complete/", {}, format="json").status_code == 409
    assert (
        client.post(f"/api/sessions/{session_id}/start/", {"pre_weight_kg": "64.5"}, format="json").status_code == 200
    )
    assert client.post(f"/api/sessions/{session_id}/start/", {}, format="json").status_code == 409
    done = client.post(
        f"/api/sessions/{session_id}/complete/", {"post_weight_kg": "62.4", "uf_volume_ml": 2100}, format="json"
    )
    assert done.json()["status"] == "completed" and done.json()["post_weight_kg"] == "62.4"
    assert client.get(f"/api/sessions/?status=completed&patient={patient.id}").json()["count"] == 1
    today = timezone.localdate().isoformat()
    assert client.get(f"/api/sessions/?date={today}").json()["count"] == 1


def test_measurements_carry_units_source_and_plausible_values(api, nurse, patient, in_progress) -> None:
    client = api(nurse)
    ok = post_vital(client, in_progress, "systolic_bp", 142, "pre")
    assert ok.status_code == 201
    assert {k: ok.json()[k] for k in ("unit", "source", "verification_status")} == {
        "unit": "mmHg", "source": "measured", "verification_status": "verified"}  # fmt: skip
    wrong_unit = post_vital(client, in_progress, "systolic_bp", 19, "pre", unit="kPa")
    assert wrong_unit.status_code == 400 and "unit" in wrong_unit.json()["error"]["details"]
    assert post_vital(client, in_progress, "systolic_bp", 1420, "pre").status_code == 400
    reading = {
        "session": str(in_progress.id),
        "kind": "blood_flow_rate",
        "value": 300,
        "recorded_at": timezone.now().isoformat(),
    }
    made = client.post("/api/device-readings/", reading, format="json")
    assert made.status_code == 201 and made.json()["unit"] == "mL/min" and made.json()["source"] == "device"
    assert client.post("/api/device-readings/", {**reading, "unit": "L/min"}, format="json").status_code == 400

    home = {"kind": "weight", "value": "63.2", "phase": "post", "recorded_at": timezone.now().isoformat()}
    mine = api(patient.user).post("/api/vitals/", home, format="json")
    assert mine.status_code == 201
    got = mine.json()
    assert (got["source"], got["phase"], got["verification_status"], got["session"]) == (
        "patient_reported", "home", "unverified", None)  # fmt: skip
    assert api(patient.user).get("/api/vitals/").json()["count"] == 1
    assert VitalSign.objects.count() == 2


def test_medication_needs_a_valid_order_and_corrections_are_amendments(api, nurse, patient, in_progress) -> None:
    client = api(nurse)
    med = {"action_type": "medication_administration", "description": "Heparin given per order."}
    assert post_action(client, in_progress, **med).status_code == 400
    order = patient.prescriptions.get()
    assert post_action(client, in_progress, **med, order=str(order.id)).status_code == 201

    original = post_action(client, in_progress, reason="").json()
    body = {"session": str(in_progress.id), "action_type": "access_care", "description": "Access site checked.",
            "reason": "Routine pre-connection check.", "performed_at": timezone.now().isoformat()}  # fmt: skip
    amended = client.post(f"/api/nursing-actions/{original['id']}/amend/", body, format="json")
    assert amended.status_code == 201 and amended.json()["amends"] == original["id"]
    assert NursingAction.objects.get(pk=original["id"]).reason == ""  # original preserved
    assert client.post(f"/api/nursing-actions/{original['id']}/amend/", body, format="json").status_code == 409
    assert AuditEvent.objects.filter(action="record_amended").count() == 1

    event = {"session": str(in_progress.id), "event_type": "incident", "description": "Line disconnected briefly.",
             "occurred_at": timezone.now().isoformat()}  # fmt: skip
    created = client.post("/api/session-events/", event, format="json").json()
    resolved = client.post(
        f"/api/session-events/{created['id']}/resolve/", {"resolution": "Reconnected."}, format="json"
    )
    assert resolved.json()["resolved_at"] and resolved.json()["resolution"] == "Reconnected."
    assert (
        client.post(f"/api/session-events/{created['id']}/resolve/", {"resolution": "x"}, format="json").status_code
        == 409
    )


def test_doctor_orders_are_versioned(api, doctor, patient) -> None:
    body = {"patient": str(patient.id), "duration_minutes": 210, "target_uf_ml": 1500, "access_type": "AVF"}
    created = api(doctor).post("/api/prescriptions/", body, format="json")
    assert created.status_code == 201 and created.json()["version"] == 2 and created.json()["active"] is True
    assert list(patient.prescriptions.order_by("version").values_list("version", "active")) == [(1, False), (2, True)]


def test_transaction_failure_leaves_no_partial_write(api, nurse, in_progress, monkeypatch) -> None:
    def broken(*args, **kwargs):
        raise RuntimeError("audit store down")

    monkeypatch.setattr(clinical.services, "audit", broken)
    with pytest.raises(RuntimeError):
        api(nurse).post(f"/api/sessions/{in_progress.id}/complete/", {"post_weight_kg": "62.0"}, format="json")
    in_progress.refresh_from_db()
    assert in_progress.status == "in_progress" and in_progress.ended_at is None and in_progress.post_weight_kg is None


def test_full_nurse_ai_doctor_patient_workflow(api, nurse, doctor, other_doctor, patient, family, scheduled) -> None:
    n, d, p = api(nurse), api(doctor), api(patient.user)
    sid = str(scheduled.id)

    # 1. Nurse runs the session and documents it, leaving one action without a reason.
    assert n.post(f"/api/sessions/{sid}/start/", {"pre_weight_kg": "64.0"}, format="json").status_code == 200
    for kind, value in (("systolic_bp", 140), ("diastolic_bp", 85)):
        assert post_vital(n, scheduled, kind, value, "pre").status_code == 201
        assert post_vital(n, scheduled, kind, value - 10, "post").status_code == 201
    action = post_action(n, scheduled, reason="", action_type="uf_adjustment", description="UF goal lowered.")
    assert action.status_code == 201
    note = {"session": sid, "text": "Patient tolerated the session."}
    assert n.post("/api/nursing-notes/", note, format="json").status_code == 201

    # 2. The assigned doctor is notified and can see the action; an unassigned doctor cannot.
    inbox = d.get("/api/notifications/?unread=true").json()["results"]
    assert "nursing_action" in {i["kind"] for i in inbox}
    assert d.get(f"/api/nursing-actions/?session={sid}").json()["results"][0]["id"] == action.json()["id"]
    assert api(other_doctor).get(f"/api/nursing-actions/?session={sid}").json()["count"] == 0
    assert api(other_doctor).get("/api/notifications/").json()["count"] == 0

    # 3. The AI review ran in the background on submission; the nurse sees completeness only.
    completeness = n.get(f"/api/ai/reviews/completeness/?session={sid}").json()
    assert "action_without_reason" in {f["check"] for f in completeness["rule_findings"]}
    assert (
        n.post(
            f"/api/sessions/{sid}/complete/", {"post_weight_kg": "62.0", "uf_volume_ml": 2000}, format="json"
        ).status_code
        == 200
    )

    # 4. Doctor works the review task.
    tasks = d.get("/api/doctor/review-tasks/?status=open").json()["results"]
    assert len(tasks) == 1 and tasks[0]["session"] == sid and tasks[0]["review_status"] == "pending_review"
    review = d.get(f"/api/ai/reviews/{tasks[0]['ai_review']}/").json()
    assert review["status"] == "pending_review" and "AI-generated" in review["label"]
    assert review["output"]["documentation_gaps"][0]["finding_id"].startswith("action_without_reason:")
    assert review["protocol_passages"] and review["output"]["requires_human_review"] is True
    assert d.post("/api/ai/reviews/request/", {"session": sid}, format="json").status_code == 202

    # 5. Doctor asks for clarification; the nurse is notified and can read it.
    feedback = {"session": sid, "kind": "clarification_request", "text": "Please document why the UF goal was lowered.",
                "nursing_action": action.json()["id"], "ai_review": review["id"]}  # fmt: skip
    assert d.post("/api/doctor/feedback/", feedback, format="json").status_code == 201
    assert "doctor_feedback" in {i["kind"] for i in n.get("/api/notifications/").json()["results"]}
    seen = n.get(f"/api/doctor/feedback/?session={sid}").json()["results"]
    assert seen[0]["text"].startswith("Please document") and seen[0]["author_name"] == "Doc"
    assert d.get(f"/api/ai/reviews/{review['id']}/").json()["status"] == "reviewed"
    assert d.get("/api/doctor/review-tasks/?status=done").json()["count"] >= 1

    # 6. Summary: generated unverified, hidden from the patient until verified AND released.
    summary = d.get(f"/api/ai/summaries/?session={sid}").json()["results"][0]
    assert summary["status"] == "unverified" and summary["output"]["verification_status"] == "unverified"
    assert p.get("/api/ai/summaries/").json()["count"] == 0
    assert d.post(f"/api/ai/summaries/{summary['id']}/verify/").json()["status"] == "verified"
    assert p.get("/api/ai/summaries/").json()["count"] == 0
    released = d.post(f"/api/ai/summaries/{summary['id']}/release/")
    assert released.status_code == 200 and released.json()["released"] is True

    # 7. Patient sees the released plain-language text and gets a notification.
    mine = p.get("/api/ai/summaries/").json()["results"]
    assert len(mine) == 1 and mine[0]["text"].startswith("Your dialysis session") and "output" not in mine[0]
    assert "summary_released" in {i["kind"] for i in p.get("/api/notifications/").json()["results"]}
    assert p.get("/api/sessions/?status=completed").json()["count"] == 1

    # 8. The whole chain is in the audit trail, and notifications were not duplicated.
    actions = set(AuditEvent.objects.values_list("action", flat=True))
    assert {"session_started", "nursing_action_recorded", "session_completed", "ai_review_created",
            "doctor_feedback_created", "summary_verified", "summary_released"} <= actions  # fmt: skip
    keys = list(Notification.objects.values_list("dedupe_key", flat=True))
    assert len(keys) == len(set(keys))


def test_seed_demo_builds_the_demonstration_dataset(db, monkeypatch) -> None:
    from django.core.management import call_command

    from clinical.models import Patient
    from core.models import User

    monkeypatch.setenv("DEMO_PASSWORD", "demo-pass-12345")
    call_command("seed_demo", verbosity=0)
    assert Patient.objects.filter(is_synthetic=False).count() == 0 and Patient.objects.count() == 4
    roles = dict(User.objects.values_list("username", "role"))
    assert sum(r == "nurse" for r in roles.values()) == 6 and sum(r == "doctor" for r in roles.values()) == 3
    latest = DialysisSession.objects.filter(patient__mrn="SYN-001", status="completed").first()
    assert {f["check"] for f in latest.ai_reviews.get().rule_findings} == {
        "action_without_reason", "duration_differs_from_prescription", "event_without_resolution"}  # fmt: skip
    assert AISummary.objects.filter(released=True).count() == 6
    before = (Patient.objects.count(), DialysisSession.objects.count())
    call_command("seed_demo", verbosity=0)
    assert (Patient.objects.count(), DialysisSession.objects.count()) == before
