"""Clinical record services. Views stay thin; anything that writes the record lives here."""

from .models import Note, SessionFacts

FACT_LISTS = ["symptoms", "access_findings", "staff_actions"]


def merge_facts(note: Note, payload: dict) -> SessionFacts:
    """Write the facts of one human-approved extraction into the session's SessionFacts.

    Callers must have validated `payload` and must only call this for an approved draft. Items from
    this note replace any earlier items from the same note; items from other notes are kept. Every
    item keeps its note_id and evidence_span. Only the three fact lists are read: `mentioned_values`
    never reach the record and Session vitals are never touched.
    """
    facts, _ = SessionFacts.objects.get_or_create(session=note.session)
    replaced = {note.id, note.supersedes_id}  # a correction also retires the facts of the note it corrects
    for name in FACT_LISTS:
        kept = [item for item in getattr(facts, name) if item.get("note_id") not in replaced]
        setattr(facts, name, kept + [{**item, "note_id": note.id} for item in payload.get(name, [])])
    facts.save()
    return facts
