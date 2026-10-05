"""Extraction pipeline: note -> model -> validators -> ExtractionDraft. Never writes the clinical record."""

import logging
from functools import cache
from pathlib import Path

from clinical.models import Note

from .client import LLMOutputError, get_llm_client
from .models import ExtractionDraft
from .validators import load_schema, validate_extraction

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
EXTRACTION_PROMPT = "extraction_v1"


@cache
def load_prompt(prompt_id: str) -> str:
    return (PROMPTS_DIR / f"{prompt_id}.md").read_text(encoding="utf-8")


def extraction_user_input(note_text: str) -> str:
    """Exact user message sent to the model (also the MockLLMClient fixture key input)."""
    return f"<note>\n{note_text}\n</note>"


def request_extraction(note_id: int) -> ExtractionDraft:
    """Run extraction for one note and store the result as a draft.

    Valid output -> status 'pending' (awaits a nurse). Anything else -> status 'invalid' with errors.
    Model and configuration failures are recorded, never raised: saving a note must not depend on the AI.
    Only ExtractionDraft is written here; Session vitals and SessionFacts are never touched.
    """
    note = Note.objects.get(pk=note_id)
    payload: dict = {}
    model_name = ""
    try:
        client = get_llm_client()
        model_name = client.model_name
        payload = client.complete_json(
            EXTRACTION_PROMPT,
            load_prompt(EXTRACTION_PROMPT),
            extraction_user_input(note.text_ar),
            load_schema(EXTRACTION_PROMPT),
        )
        ok, errors = validate_extraction(payload, note.text_ar)
    except LLMOutputError as exc:
        ok, errors = False, [{"code": "llm_output_error", "path": "", "message": str(exc)}]
    except Exception as exc:  # noqa: BLE001 - see docstring: nothing here may break note saving
        logger.exception("Extraction failed for note %s", note_id)
        ok, errors = False, [{"code": "llm_error", "path": "", "message": f"{type(exc).__name__}: {exc}"}]
    return ExtractionDraft.objects.create(
        note=note,
        payload=payload,
        status=ExtractionDraft.Status.PENDING if ok else ExtractionDraft.Status.INVALID,
        validation_errors=errors,
        model_name=model_name,
        prompt_version=EXTRACTION_PROMPT,
    )
