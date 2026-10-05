"""LLM access. All callers go through get_llm_client(); nothing else may talk to a model."""

import json
from abc import ABC, abstractmethod
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

FIXTURES_DIR = Path(settings.BASE_DIR) / "tests" / "fixtures" / "llm"


class LLMOutputError(Exception):
    """The model returned something that is not usable JSON. Services catch this; it never reaches API callers."""


class LLMClient(ABC):
    model_name: str

    @abstractmethod
    def complete_json(self, prompt_id: str, system: str, user: str, schema: dict) -> dict:
        """Return the model's JSON answer as a dict, or raise LLMOutputError."""


class MockLLMClient(LLMClient):
    """Offline client for tests and demos. Stub: the AI role adds per-input fixtures (task A4)."""

    model_name = "mock"

    def complete_json(self, prompt_id: str, system: str, user: str, schema: dict) -> dict:
        path = FIXTURES_DIR / prompt_id / "default.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise LLMOutputError(f"No usable mock fixture at {path}") from exc


def get_llm_client() -> LLMClient:
    provider = settings.LLM_PROVIDER
    if provider == "mock":
        return MockLLMClient()
    # The AI role registers AnthropicLLMClient here (task A4).
    raise ImproperlyConfigured(f"Unknown LLM_PROVIDER: {provider!r}")
