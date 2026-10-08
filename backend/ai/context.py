"""Builds the minimum-necessary, de-identified context for one session and the deterministic
metrics. All arithmetic lives here in backend code; the model never calculates anything."""

import hashlib
import json
from decimal import Decimal

from clinical.models import DialysisSession, Phase, VitalKind


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _num(value) -> float | None:
    return float(value) if isinstance(value, Decimal) else value


def build_context(session: DialysisSession) -> dict:
    """No patient name, MRN, date of birth or staff names: records are referred to by id only."""
    rx = session.prescription
    labs = session.patient.lab_reports.order_by("-collected_at").first()
    context = {
        "session": {
            "id": str(session.id),
            "status": session.status,
            "scheduled_start": _iso(session.scheduled_start),
            "started_at": _iso(session.started_at),
            "ended_at": _iso(session.ended_at),
            "pre_weight": {"value": _num(session.pre_weight_kg), "unit": "kg", "kind": "measured"},
            "post_weight": {"value": _num(session.post_weight_kg), "unit": "kg", "kind": "measured"},
            "uf_volume": {"value": session.uf_volume_ml, "unit": "mL", "kind": "measured"},
        },
        "prescription": {
            "id": str(rx.id),
            "version": rx.version,
            "duration": {"value": rx.duration_minutes, "unit": "min"},
            "target_uf": {"value": rx.target_uf_ml, "unit": "mL"},
            "blood_flow": {"value": rx.blood_flow_ml_min, "unit": "mL/min"},
            "access_type": rx.access_type,
        },
        "vitals": [
            {
                "id": str(v.id),
                "kind": v.kind,
                "value": _num(v.value),
                "unit": v.unit,
                "phase": v.phase,
                "source": v.source,
                "recorded_at": _iso(v.recorded_at),
            }
            for v in session.vitals.filter(amended_by__isnull=True)
        ],
        "device_readings": [
            {
                "id": str(r.id),
                "kind": r.kind,
                "value": _num(r.value),
                "unit": r.unit,
                "recorded_at": _iso(r.recorded_at),
            }
            for r in session.device_readings.all()
        ],
        "nursing_actions": [
            {
                "id": str(a.id),
                "action_type": a.action_type,
                "description": a.description,
                "reason": a.reason,
                "performed_at": _iso(a.performed_at),
            }
            for a in session.nursing_actions.filter(amended_by__isnull=True)
        ],
        "nursing_notes": [
            {"id": str(n.id), "text": n.text, "created_at": _iso(n.created_at)}
            for n in session.nursing_notes.filter(amended_by__isnull=True)
        ],
        "events": [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "description": e.description,
                "occurred_at": _iso(e.occurred_at),
                "resolved_at": _iso(e.resolved_at),
                "resolution": e.resolution,
            }
            for e in session.events.all()
        ],
        "labs": [
            {
                "id": str(r.id),
                "analyte": r.analyte,
                "value": _num(r.value),
                "unit": r.unit,
                "collected_at": _iso(labs.collected_at),
            }
            for r in (labs.results.all() if labs else [])
        ],
    }
    context["metrics"] = compute_metrics(session, context)
    return context


def _vital(context: dict, kind: str, phase: str, pick=lambda values: values[-1]) -> float | None:
    values = [v["value"] for v in context["vitals"] if v["kind"] == kind and v["phase"] == phase]
    return pick(values) if values else None


def compute_metrics(session: DialysisSession, context: dict) -> dict:
    """Deterministic: identical records always give identical numbers. Missing inputs give null."""

    def calculated(value, unit: str) -> dict:
        return {"value": value, "unit": unit, "kind": "calculated"}

    actual = None
    if session.started_at and session.ended_at:
        actual = round((session.ended_at - session.started_at).total_seconds() / 60)
    prescribed = session.prescription.duration_minutes
    pre, post = session.pre_weight_kg, session.post_weight_kg
    return {
        "actual_duration": calculated(actual, "min"),
        "prescribed_duration": {"value": prescribed, "unit": "min", "kind": "prescribed"},
        "duration_difference": calculated(None if actual is None else actual - prescribed, "min"),
        "weight_change": calculated(None if pre is None or post is None else float(post - pre), "kg"),
        "pre_systolic_bp": {"value": _vital(context, VitalKind.SBP, Phase.PRE), "unit": "mmHg", "kind": "measured"},
        "post_systolic_bp": {"value": _vital(context, VitalKind.SBP, Phase.POST), "unit": "mmHg", "kind": "measured"},
        "event_count": calculated(len(context["events"]), "count"),
        "nursing_action_count": calculated(len(context["nursing_actions"]), "count"),
        "lowest_intra_systolic_bp": {
            "value": _vital(context, VitalKind.SBP, Phase.INTRA, min),
            "unit": "mmHg",
            "kind": "measured",
        },
    }


RECORD_LISTS = ["vitals", "device_readings", "nursing_actions", "nursing_notes", "events", "labs"]


def record_ids(context: dict) -> set[str]:
    """Every id the model may legitimately cite."""
    ids = {context["session"]["id"], context["prescription"]["id"]}
    for name in RECORD_LISTS:
        ids.update(item["id"] for item in context[name])
    return ids


def fingerprint(context: dict) -> str:
    return hashlib.sha256(json.dumps(context, sort_keys=True, default=str).encode()).hexdigest()
