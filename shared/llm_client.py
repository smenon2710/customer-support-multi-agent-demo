import logging
from typing import Optional, Type, TypeVar

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from shared.config import OPENROUTER_API_KEY
from shared.db.models import LLMCallLog

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


def _record(db: Optional[Session], model: str, success: bool, reason: str) -> None:
    """Best-effort attempt logging for the dashboard's LLM-availability metric.

    Never raises, never commits — `db.add()` only, so it piggybacks on whatever
    transaction the caller eventually commits. If that never happens (or `db` is
    None), the call simply isn't recorded; this is an observability aid, not part
    of the correctness contract.
    """
    if db is None:
        return
    try:
        db.add(LLMCallLog(model=model, success=success, reason=reason))
    except Exception:
        logger.debug("Failed to record LLM call log entry", exc_info=True)


def complete_json(
    model: str,
    system: str,
    user: str,
    schema: Type[T],
    retries: int = 1,
    client: Optional[OpenAI] = None,
    db: Optional[Session] = None,
) -> Optional[T]:
    """Ask the model for JSON matching `schema`; validate; retry once on a bad parse.

    Returns None — never raises — on any failure: no API key configured, a rate
    limit, a network/server error, or output that never validates. Every caller
    MUST treat None as "fall back to the deterministic path" — free-tier models
    don't reliably honor `response_format` or produce schema-valid output.

    `db`, if given, gets a best-effort `LLMCallLog` row per attempt (see `_record`)
    so the dashboard can show real LLM availability, broken down by failure reason.
    """
    resolved_client = client if client is not None else _default_client()
    if resolved_client is None:
        _record(db, model, success=False, reason="no_api_key")
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
        except RateLimitError as e:
            # Expected routinely on a free tier — no retry storm, straight to fallback.
            logger.warning("OpenRouter rate limited (model=%s): %s", model, e)
            _record(db, model, success=False, reason="rate_limited")
            return None
        except APIConnectionError as e:
            logger.warning("OpenRouter connection error (model=%s): %s", model, e)
            _record(db, model, success=False, reason="connection_error")
            return None
        except APIStatusError as e:
            logger.warning("OpenRouter API error (model=%s, status=%s): %s", model, e.status_code, e)
            _record(db, model, success=False, reason="api_error")
            return None
        except Exception as e:
            # Anything else the provider or transport can throw. Still degrade,
            # never raise, but keep this distinct from the typed cases above so a
            # persistently high "unknown_error" count is a signal something in this
            # integration needs attention, not just free-tier flakiness.
            logger.warning("Unexpected OpenRouter failure (model=%s): %s", model, e)
            _record(db, model, success=False, reason="unknown_error")
            return None

        try:
            result = schema.model_validate_json(content)
        except ValidationError as e:
            logger.info(
                "LLM output failed schema validation (model=%s, attempt=%d/%d): %s",
                model, attempt + 1, retries + 1, e,
            )
            continue

        _record(db, model, success=True, reason="success")
        return result

    logger.warning(
        "LLM output never validated against %s after %d attempt(s)",
        schema.__name__, retries + 1,
    )
    _record(db, model, success=False, reason="invalid_response")
    return None
