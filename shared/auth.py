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

    Checks falsiness, not `is None`: Docker Compose's `${INTERNAL_API_TOKEN:-}`
    substitution always sets the env var in the container (to an empty string when
    unset on the host), it never leaves it truly unset — so `os.environ.get(...)`
    returns `""`, not `None`, by default in Docker Compose. Treating only `None` as
    "disabled" would enforce auth with an unsatisfiable empty-string secret out of
    the box.
    """
    if not config.INTERNAL_API_TOKEN:
        return
    if x_internal_token != config.INTERNAL_API_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing internal token")
