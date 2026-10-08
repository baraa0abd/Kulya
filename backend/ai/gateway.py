"""Provider boundary shared by clinical and nutrition workflows.

Provider failures become structured errors; callers still validate domain-specific output.
"""

import logging

from .provider import ProviderError, get_provider

logger = logging.getLogger("kulya.ai")


def call_model(
    prompt_id: str, payload: dict, image: tuple[str, str] | None = None
) -> tuple[dict | None, list[dict], str]:
    """Returns (output, errors, model_name). Never raises: every failure becomes a recorded error."""
    try:
        provider = get_provider()
        output = (
            provider.complete_json(prompt_id, payload, image) if image else provider.complete_json(prompt_id, payload)
        )
        return output, [], provider.model_name
    except ProviderError as exc:
        return None, [{"code": "provider_error", "path": "", "message": str(exc)}], ""
    except Exception as exc:  # noqa: BLE001 - timeouts, config errors, anything else
        logger.exception("ai call failed", extra={"ctx": {"prompt": prompt_id}})
        return None, [{"code": "provider_error", "path": "", "message": type(exc).__name__}], ""
