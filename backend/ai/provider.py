"""LLM provider adapters. Nothing else in the codebase talks to a model. Providers get text in and
return a JSON object; they have no tools and take no part in authorization."""

import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger("kulya.ai")
PROMPTS_DIR = Path(__file__).parent / "prompts"
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class ProviderError(Exception):
    """The provider failed or returned something unusable. Callers record it and fall back to
    rule-based findings; it is never shown as a successful AI result."""


def load_prompt(prompt_id: str) -> str:
    return (PROMPTS_DIR / f"{prompt_id}.md").read_text(encoding="utf-8")


def parse_json_object(text: str) -> dict:
    text = text.strip()
    match = _FENCE.match(text)
    try:
        value = json.loads(match.group(1) if match else text)
    except ValueError as exc:
        raise ProviderError(f"Model output is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ProviderError("Model output is JSON but not an object.")
    return value


class LLMProvider(ABC):
    model_name: str

    @abstractmethod
    def complete_json(self, prompt_id: str, payload: dict, image: tuple[str, str] | None = None) -> dict:
        """`payload` is the structured input; `image` is an optional (media_type, base64) photo.
        Returns the model's JSON object or raises ProviderError."""


def user_message(payload: dict) -> str:
    # Everything inside <data> is untrusted clinical text; the prompt tells the model so.
    return f"<data>\n{json.dumps(payload, ensure_ascii=False, indent=1, default=str)}\n</data>"


class AnthropicProvider(LLMProvider):
    def __init__(self, client: Any = None) -> None:
        import anthropic

        self._error = anthropic.APIError
        self.model_name = settings.LLM_MODEL
        # The SDK retries connection errors, 408/409/429 and 5xx twice with backoff (bounded).
        self._client = client or anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY, timeout=settings.LLM_TIMEOUT_SECONDS, max_retries=2
        )

    def complete_json(self, prompt_id: str, payload: dict, image: tuple[str, str] | None = None) -> dict:
        content: Any = user_message(payload)
        if image:
            source = {"type": "base64", "media_type": image[0], "data": image[1]}
            content = [{"type": "image", "source": source}, {"type": "text", "text": content}]
        try:
            message = self._client.messages.create(
                model=self.model_name,
                max_tokens=8000,
                system=load_prompt(prompt_id),
                messages=[{"role": "user", "content": content}],
                output_config={"effort": settings.LLM_EFFORT},
            )
        except self._error as exc:
            raise ProviderError(f"Provider call failed: {type(exc).__name__}") from exc
        if message.stop_reason != "end_turn":
            raise ProviderError(f"Model stopped early (stop_reason={message.stop_reason}).")
        return parse_json_object("".join(block.text for block in message.content if block.type == "text"))


class MockProvider(LLMProvider):
    """Offline provider for tests and the demo. It composes schema-valid output from the structured
    input only, so the full workflow runs with no network. It is a template, not a language model."""

    model_name = "mock"

    def complete_json(self, prompt_id: str, payload: dict, image: tuple[str, str] | None = None) -> dict:
        if prompt_id.startswith("nutrition"):
            from nutrition.ai import mock_response  # lazy: nutrition imports this module

            return mock_response(prompt_id, payload, image)
        if prompt_id.startswith("patient_chat"):
            from assistant.chat import mock_answer  # lazy: assistant imports the gateway

            return {"answer": mock_answer(payload)}
        ctx = payload["context"]
        session_id = ctx["session"]["id"]
        if prompt_id.startswith("review"):
            passages = payload["protocol_passages"]
            findings = [f for f in payload["rule_findings"] if f["check"] != "protocol_reference_unavailable"]
            return {
                "session_id": session_id,
                "summary": f"{len(findings)} documentation item(s) need attention for this session."
                if findings
                else "No documentation gaps were detected by the automated checks.",
                "documentation_gaps": [
                    {
                        "finding_id": f["finding_id"],
                        "description": f["description"],
                        "source_record_ids": f["source_record_ids"],
                        "protocol_reference_ids": [p["id"] for p in passages[:1]],
                    }
                    for f in findings
                ],
                "protocol_discrepancies": [],
                "questions_for_doctor": [f"Please review: {f['description']}" for f in findings[:3]],
                "requires_human_review": True,
                "status": "pending_review",
            }
        metrics = ctx["metrics"]
        duration = metrics["actual_duration"]["value"]
        events = [f"{e['event_type']}: {e['description']}" for e in ctx["events"]]
        actions = [f"{a['action_type']}: {a['description']}" for a in ctx["nursing_actions"]]
        missing = [f["description"] for f in payload["rule_findings"] if f["check"] == "required_field_missing"]
        overview = (
            f"Documented treatment duration {duration} min (prescribed {metrics['prescribed_duration']['value']} min)."
            if duration is not None
            else "Treatment duration is not documented."
        )
        used = [ctx["session"]["id"], ctx["prescription"]["id"]]
        used += [e["id"] for e in ctx["events"]] + [a["id"] for a in ctx["nursing_actions"]]
        return {
            "session_id": session_id,
            "clinical_summary": f"{overview} {len(events)} event(s) and {len(actions)} nursing action(s) recorded.",
            "patient_summary": f"Your dialysis session was recorded. {len(actions)} nursing step(s) were documented."
            " Please discuss any question with your care team.",
            "treatment_duration_minutes": duration,
            "documented_events": events,
            "nursing_actions": actions,
            "missing_information": missing,
            "source_record_ids": used,
            "generated_at": datetime.now(UTC).isoformat(),
            "verification_status": "unverified",
        }


def get_provider() -> LLMProvider:
    if settings.LLM_PROVIDER == "mock":
        return MockProvider()
    if settings.LLM_PROVIDER == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            logger.warning("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is empty; using MockProvider.")
            return MockProvider()
        return AnthropicProvider()
    raise ImproperlyConfigured(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER!r}")
