"""Deterministic documentation checks. Pure functions over the session context: no database, no
model, no clock. They look only at whether documentation is complete and internally consistent;
they never judge clinical decisions or nursing competence."""

from datetime import datetime, timedelta

from django.conf import settings

GRACE = timedelta(minutes=30)  # records may be written shortly before/after the session window


def _finding(check: str, record_id: str, description: str, extra_ids: tuple[str, ...] = ()) -> dict:
    return {
        "finding_id": f"{check}:{record_id}",  # stable across reruns
        "check": check,
        "description": description,
        "source_record_ids": [record_id, *extra_ids],
    }


def _time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def check_required_fields(ctx: dict) -> list[dict]:
    session = ctx["session"]
    if session["status"] != "completed":
        return []
    missing = [name for name in ("pre_weight", "post_weight", "uf_volume") if session[name]["value"] is None]
    missing += [name for name in ("started_at", "ended_at") if session[name] is None]
    for phase in ("pre", "post"):
        for kind in ("systolic_bp", "diastolic_bp"):
            if not any(v["kind"] == kind and v["phase"] == phase for v in ctx["vitals"]):
                missing.append(f"{phase}_{kind}")
    return [
        _finding("required_field_missing", session["id"], f"Required documentation field is missing: {name}.")
        for name in missing
    ]


def check_duration(ctx: dict) -> list[dict]:
    difference = ctx["metrics"]["duration_difference"]["value"]
    if difference is None or abs(difference) <= settings.DURATION_TOLERANCE_MINUTES:
        return []
    actual = ctx["metrics"]["actual_duration"]["value"]
    prescribed = ctx["metrics"]["prescribed_duration"]["value"]
    return [
        _finding(
            "duration_differs_from_prescription",
            ctx["session"]["id"],
            f"Documented treatment duration ({actual} min) differs from the prescribed duration "
            f"({prescribed} min) by {difference} min.",
            (ctx["prescription"]["id"],),
        )
    ]


def check_action_reasons(ctx: dict) -> list[dict]:
    return [
        _finding("action_without_reason", a["id"], f"Nursing action '{a['action_type']}' has no documented reason.")
        for a in ctx["nursing_actions"]
        if not a["reason"].strip()
    ]


# Demo workflow policy (synthetic, see ai/protocols): these events/actions need a blood-pressure
# reading documented afterwards.
FOLLOW_UP_AFTER = {"hypotension", "fluid_bolus"}


def check_follow_up(ctx: dict) -> list[dict]:
    bp_times = [_time(v["recorded_at"]) for v in ctx["vitals"] if v["kind"] == "systolic_bp"]
    triggers = [(e["id"], e["event_type"], e["occurred_at"]) for e in ctx["events"]]
    triggers += [(a["id"], a["action_type"], a["performed_at"]) for a in ctx["nursing_actions"]]
    findings = []
    for record_id, kind, at in triggers:
        if kind in FOLLOW_UP_AFTER and not any(t and t > _time(at) for t in bp_times):
            findings.append(
                _finding(
                    "follow_up_missing",
                    record_id,
                    f"No blood-pressure reading is documented after '{kind}'.",
                )
            )
    return findings


def check_conflicts(ctx: dict) -> list[dict]:
    session = ctx["session"]
    findings = []
    pre, post, uf = (session[k]["value"] for k in ("pre_weight", "post_weight", "uf_volume"))
    if None not in (pre, post, uf) and uf > 0 and post > pre:
        findings.append(
            _finding(
                "conflicting_records",
                session["id"],
                f"Post-treatment weight ({post} kg) is higher than pre-treatment weight ({pre} kg) "
                f"although {uf} mL of ultrafiltration is documented.",
            )
        )
    start, end = _time(session["started_at"]), _time(session["ended_at"])
    timed = [(v["id"], v["recorded_at"]) for v in ctx["vitals"] if v["phase"] == "intra"]
    timed += [(a["id"], a["performed_at"]) for a in ctx["nursing_actions"]]
    timed += [(e["id"], e["occurred_at"]) for e in ctx["events"]]
    for record_id, at in timed:
        when = _time(at)
        if (start and when < start - GRACE) or (end and when > end + GRACE):
            findings.append(
                _finding(
                    "conflicting_records", record_id, "Record timestamp falls outside the documented session time."
                )
            )
    return findings


def check_unresolved_events(ctx: dict) -> list[dict]:
    if ctx["session"]["status"] != "completed":
        return []
    return [
        _finding(
            "event_without_resolution", e["id"], f"Recorded event '{e['event_type']}' has no documented resolution."
        )
        for e in ctx["events"]
        if not e["resolved_at"]
    ]


def run_checks(ctx: dict) -> list[dict]:
    findings = [
        *check_required_fields(ctx),
        *check_duration(ctx),
        *check_action_reasons(ctx),
        *check_follow_up(ctx),
        *check_conflicts(ctx),
        *check_unresolved_events(ctx),
    ]
    return sorted(findings, key=lambda f: f["finding_id"])


def protocol_unavailable_finding(ctx: dict) -> dict:
    return _finding(
        "protocol_reference_unavailable",
        ctx["session"]["id"],
        "insufficient_protocol_evidence: no approved, currently applicable protocol passage matched "
        "this session's documented events.",
    )
