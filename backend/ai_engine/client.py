"""LLM access. All callers go through get_llm_client(); nothing else may talk to a model."""

import hashlib
import json
import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(settings.BASE_DIR) / "tests" / "fixtures" / "llm"
DEFAULT_MODEL = "claude-opus-5-5"
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class LLMOutputError(Exception):
    """The model call failed or returned something that is not a JSON object.

    Services catch this and store an 'invalid' draft; it never reaches API callers.
    """


def parse_json_object(text: str) -> dict:
    """Strip an optional ```json fence and parse. Anything but a JSON object is an error."""
    text = text.strip()
    match = _FENCE.match(text)
    try:
        value = json.loads(match.group(1) if match else text)
    except ValueError as exc:
        raise LLMOutputError(f"Model output is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise LLMOutputError("Model output is JSON but not an object.")
    return value


def fixture_key(user: str) -> str:
    return hashlib.sha256(user.encode("utf-8")).hexdigest()[:12]


class LLMClient(ABC):
    model_name: str

    @abstractmethod
    def complete_json(self, prompt_id: str, system: str, user: str, schema: dict) -> dict:
        """Return the model's JSON answer as a dict, or raise LLMOutputError."""


class MockLLMClient(LLMClient):
    """Offline client for tests and the offline demo.

    Lookup order: {fixtures}/{prompt_id}/{sha256(user)[:12]}.json, then {prompt_id}/default.json,
    then (summary prompts only) a deterministic summary built from the input.
    """

    model_name = "mock"

    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self.fixtures_dir = fixtures_dir

    def complete_json(self, prompt_id: str, system: str, user: str, schema: dict) -> dict:
        folder = (self.fixtures_dir or FIXTURES_DIR) / prompt_id
        for path in (folder / f"{fixture_key(user)}.json", folder / "default.json"):
            if path.is_file():
                return parse_json_object(path.read_text(encoding="utf-8"))
        if prompt_id.startswith("summary_"):
            return offline_summary(user, with_flags=prompt_id.startswith("summary_clinician"))
        raise LLMOutputError(f"No mock fixture for prompt {prompt_id!r} in {folder}")


def offline_summary(user: str, *, with_flags: bool) -> dict:
    """ponytail: template summary so the demo works with no network. One sentence per session that has
    approved facts, each citing that session's notes. Not a model; switch LLM_PROVIDER=anthropic for prose.
    """
    data = json.loads(user[user.index("{") : user.rindex("}") + 1])
    sentences = []
    for session in data.get("sessions", []):
        labels = [
            item.get("label_ar") or item.get("description_ar")
            for kind in ("symptoms", "access_findings", "staff_actions")
            for item in session.get(kind, [])
        ]
        if labels and session.get("note_ids"):
            text = f"في جلسة {session['date']} وُثِّق: {'، '.join(labels)}."
            sentences.append({"text_ar": text, "citations": session["note_ids"]})
    if with_flags:
        sentences += [
            {"text_ar": flag["message_ar"], "citations": flag["note_ids"]}
            for flag in data.get("flags", [])
            if flag.get("note_ids")
        ]
    return {"sentences": sentences[:40]}


class AnthropicLLMClient(LLMClient):
    def __init__(self, client: Any = None) -> None:
        import anthropic

        self._errors = anthropic.APIError
        self.model_name = settings.LLM_MODEL or DEFAULT_MODEL
        # The SDK retries connection errors, 408/429 and 5xx with exponential backoff.
        self._client = client or anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=settings.LLM_TIMEOUT_SECONDS,
            max_retries=2,
        )

    def complete_json(self, prompt_id: str, system: str, user: str, schema: dict) -> dict:
        # No `temperature`: current Claude models reject sampling parameters (400). Determinism is not
        # assumed anywhere; every output goes through ai_engine.validators instead.
        try:
            message = self._client.messages.create(
                model=self.model_name,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": settings.LLM_EFFORT},
            )
        except self._errors as exc:
            raise LLMOutputError(f"Model call failed: {type(exc).__name__}: {exc}") from exc
        if message.stop_reason != "end_turn":
            raise LLMOutputError(f"Model stopped early (stop_reason={message.stop_reason}).")
        return parse_json_object("".join(block.text for block in message.content if block.type == "text"))


def get_llm_client() -> LLMClient:
    provider = settings.LLM_PROVIDER
    if provider == "mock":
        return MockLLMClient()
    if provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            # Demo safety: a missing key must not break the app.
            logger.warning("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is empty; falling back to MockLLMClient.")
            return MockLLMClient()
        return AnthropicLLMClient()
    raise ImproperlyConfigured(f"Unknown LLM_PROVIDER: {provider!r}")
