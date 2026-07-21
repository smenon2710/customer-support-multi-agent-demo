import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

_ticket_id_var: ContextVar[Optional[str]] = ContextVar("ticket_id", default=None)


def set_ticket_id(ticket_id: Optional[str]) -> None:
    """Bind a ticket ID to every log record emitted for the rest of this request.

    Safe under FastAPI: each request runs in its own asyncio Task, and contextvars
    are isolated per Task, so concurrent requests never see each other's ticket_id.
    """
    _ticket_id_var.set(ticket_id)


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        ticket_id = _ticket_id_var.get()
        if ticket_id is not None:
            payload["ticket_id"] = ticket_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: int = logging.INFO) -> None:
    """Replace the root logger's handlers with a single JSON-formatted stdout handler.

    Idempotent — safe to call from multiple modules (each agent's main.py, the
    orchestrator) even within the same process, since it replaces rather than
    appends handlers.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
