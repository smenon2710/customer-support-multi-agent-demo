"""Optional live check that OPENROUTER_API_KEY actually works end to end.

Not part of the pytest suite, which never makes real network calls (see
shared/llm_client.py and tests/test_llm_client.py). Run this manually after
setting OPENROUTER_API_KEY, or let CI run it when the OPENROUTER_API_KEY secret
is configured (see .github/workflows/ci.yml).
"""
import sys

from pydantic import BaseModel

from shared.config import CLASSIFIER_MODEL, OPENROUTER_API_KEY
from shared.llm_client import complete_json


class _Ping(BaseModel):
    ok: bool


def main() -> int:
    if not OPENROUTER_API_KEY:
        print("OPENROUTER_API_KEY not set — skipping live smoke test.")
        return 0

    result = complete_json(
        CLASSIFIER_MODEL,
        'Respond with exactly this JSON and nothing else: {"ok": true}',
        "ping",
        _Ping,
    )
    if result is None or not result.ok:
        print(f"LLM smoke test FAILED against {CLASSIFIER_MODEL}: got {result!r}")
        return 1

    print(f"LLM smoke test passed against {CLASSIFIER_MODEL}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
