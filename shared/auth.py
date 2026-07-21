from typing import Optional

from fastapi import Header, HTTPException, status

from shared import config


async def verify_internal_token(x_internal_token: Optional[str] = Header(None)) -> None:
    """FastAPI dependency enforcing the shared-secret header between internal services.

    A no-op when INTERNAL_API_TOKEN isn't configured — auth is opt-in, so local dev
    and tests don't need to know about it unless it's explicitly enabled. Reads
    `config.INTERNAL_API_TOKEN` via module attribute access (not a top-level `from
    shared.config import INTERNAL_API_TOKEN`) so it picks up the current value each
    call — required for tests to monkeypatch it.
    """
    if config.INTERNAL_API_TOKEN is None:
        return
    if x_internal_token != config.INTERNAL_API_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing internal token")
