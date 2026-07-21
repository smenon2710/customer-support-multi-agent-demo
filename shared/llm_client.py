import logging
from typing import Optional, Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from shared.config import OPENROUTER_API_KEY

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_client: Optional[OpenAI] = None


def _default_client() -> Optional[OpenAI]:
    """Lazily construct the shared OpenRouter client. Returns None if no API key is
    configured — every caller treats "no client" and "the LLM call failed" the same
    way: fall back to the deterministic path.
    """
    global _client
    if not OPENROUTER_API_KEY:
        return None
    if _client is None:
        _client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
    return _client


def complete_json(
    model: str,
    system: str,
    user: str,
    schema: Type[T],
    retries: int = 1,
    client: Optional[OpenAI] = None,
) -> Optional[T]:
    """Ask the model for JSON matching `schema`; validate; retry once on a bad parse.

    Returns None — never raises — on any failure: no API key configured, a rate
    limit, a network/server error, or output that never validates. Every caller
    MUST treat None as "fall back to the deterministic path" — free-tier models
    don't reliably honor `response_format` or produce schema-valid output.
    """
    resolved_client = client if client is not None else _default_client()
    if resolved_client is None:
        return None

    for attempt in range(retries + 1):
        try:
            response = resolved_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                max_tokens=1024,
            )
            content = response.choices[0].message.content
        except Exception as e:
            # Covers rate limits, network errors, server errors, and anything else a
            # provider can throw. The plan is explicit that 429s are routine on a free
            # tier, not exceptional — no retry storm, just fall back immediately.
            logger.warning(
                "OpenRouter call failed (model=%s, attempt=%d/%d): %s",
                model, attempt + 1, retries + 1, e,
            )
            return None

        try:
            return schema.model_validate_json(content)
        except ValidationError as e:
            logger.info(
                "LLM output failed schema validation (model=%s, attempt=%d/%d): %s",
                model, attempt + 1, retries + 1, e,
            )
            continue

    logger.warning(
        "LLM output never validated against %s after %d attempt(s)",
        schema.__name__, retries + 1,
    )
    return None
