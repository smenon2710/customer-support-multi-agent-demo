# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A portfolio project simulating a multi-agent customer support system for Tableau issues at a fictional
fintech company. Three FastAPI microservices (router, technical, account) coordinate over HTTP, backed by
Redis (messaging), Postgres/SQLite (persistence), and an optional OpenRouter LLM for the cases deterministic
rules can't confidently handle, fronted by a Streamlit demo UI with a human-in-the-loop review queue for
anything an agent escalates. Internal endpoints are optionally shared-secret-protected, every log line is
JSON with ticket-ID correlation, and GitHub Actions runs lint/tests/docker-build on every push. Deployable
for $0 across Neon/Render/Streamlit Community Cloud — see Cloud deployment below and `docs/DEPLOYMENT.md`.

## Running the system

Docker Compose (recommended — service hostnames like `router-agent` only resolve inside the compose network):
```
docker compose up --build
docker compose down
```
Ports: router-agent `8001`, technical-agent `8002`, account-agent `8003`, Streamlit demo `8501`, Redis `6379`,
Postgres `5432`. A one-off `db-seed` service runs `scripts/seed_db.py` and must exit successfully
(`condition: service_completed_successfully`) before any agent starts — the three agents and `demo-app`
all depend on it.

Running locally without Docker (each agent in its own terminal, from repo root; requires Redis running —
`redis-server` or `docker run -p 6379:6379 redis:7-alpine`; `DATABASE_URL` defaults to a local SQLite file
if unset, so Postgres isn't required for local dev):
```
pip install -r requirements.txt
python -m scripts.seed_db
python -m agents.router_agent.main
python -m agents.technical_agent.main
python -m agents.account_agent.main
streamlit run demo/streamlit_interface.py
```
Use `-m agents.<agent>.main`, not `python agents/<agent>/main.py` — the latter puts the
agent's own directory (not the repo root) at the front of `sys.path`, so the `from shared...`
imports fail. All agent endpoints, Redis, and the database are configured via env vars in
`shared/config.py` (`ROUTER_URL`, `TECHNICAL_URL`, `ACCOUNT_URL`, `REDIS_URL`, `DATABASE_URL`),
defaulting to `localhost`/SQLite for local runs; Docker Compose overrides them to the compose
service hostnames and Postgres. `INTERNAL_API_TOKEN` (optional, unset by default) gates the
business endpoints — see Hardening below.

Tests: `pytest` (config in `pytest.ini`, root `conftest.py` puts the repo root on `sys.path` for
imports). Covers `RouterLogic`/`TechnicalKnowledgeBase`/`AccountManager`/`SimulatedTableauBackend`/
`resolution_cache.find_cached_resolution`/`shared/db/repository.py`/`shared/db/metrics.py`/
`shared/llm_client.py`/`shared/auth.py`/`shared/logging_config.py` directly plus FastAPI `TestClient`
tests per agent, including `/health` and auth enforcement. No Redis, Postgres, Docker, or `OPENROUTER_API_KEY` required:
`tests/conftest.py` provides `db_session` (fresh in-memory SQLite + schema) and `seeded_db` (same,
with fixture departments/users/KB articles) fixtures, API tests override the `get_db` FastAPI
dependency with them (see Persistence below), and with no API key configured every LLM-touching
test exercises the real rules-only fallback path end to end rather than needing a mock — see
Hybrid intelligence below.

Lint: `ruff check .` (config in `pyproject.toml`, default rule set — `pip install -r
requirements-dev.txt` first). CI (`.github/workflows/ci.yml`): lint, `pytest`, `docker compose
build`, and an optional live LLM smoke test (`scripts/llm_smoke_test.py`) gated on the
`OPENROUTER_API_KEY` repo secret being set.

## Architecture

**Request flow:** a `SupportTicket` (shared/models.py) is submitted to `shared/orchestrator.py`'s
`AgentOrchestrator`, the single orchestration path (both `demo/streamlit_interface.py` and any
future caller use it — there is no duplicate implementation). It POSTs to the router agent's
`/route_ticket` (classifies category + priority, determines the target agent), then POSTs to
that agent's `/handle_ticket`. Agent endpoints come from `shared/config.py`'s `AGENT_ENDPOINTS`.
Both calls carry a 90s timeout (`AGENT_REQUEST_TIMEOUT_SECONDS`) — long enough to ride out a
Render free-tier cold start (see Cloud deployment below) without hanging indefinitely if an agent
is genuinely unreachable. A `ConnectionError`/`Timeout` specifically (as opposed to any other
failure) gets a friendly `COLD_START_MESSAGE` instead of the raw exception text, since that's the
shape a sleeping free-tier service takes from the caller's side.

**Agent responsibilities** (each hybrid: deterministic rules first, LLM only when rules are weak/absent —
see Hybrid intelligence below for the shared pattern):
- **Router agent** (`agents/router_agent/main.py`, port 8001): `RouterLogic.classify_ticket()` does
  keyword-based classification into `TicketCategory` (technical/account/training) and `Priority`
  (critical/high/medium/low), plus a real confidence score from the keyword-score margin (not a hardcoded
  number). `classify()` wraps it: below `CONFIDENCE_THRESHOLD` (0.6), it asks the LLM for a second opinion.
  Department name in `critical_departments` (Trading, Risk Management, Executive) forces at least HIGH
  priority; certain keywords force CRITICAL — both apply to an LLM-suggested priority exactly as they do to
  the rule engine's own default (`_apply_priority_policy`), since those are policy, not something to infer.
  Training-category tickets are currently routed to the technical agent (no dedicated training agent
  exists). It's also the one that creates the `tickets` row (via `get_or_create_ticket`) — it's normally
  first to see a ticket.
- **Technical agent** (`agents/technical_agent/main.py`, port 8002): before anything else,
  `resolution_cache.py`'s `find_cached_resolution()` checks for a prior ticket with the exact same
  `subject` that already has a recorded resolution (any status — a past escalation is replayed too, not
  just a past resolution) — a hit skips KB retrieval *and* the LLM call entirely and reuses that ticket's
  response verbatim (`method="cache"`). This is what makes the demo UI's frequency-ranked subject dropdown
  (see `demo/streamlit_interface.py`) meaningfully reduce LLM calls over time: subjects are mostly drawn
  from a small, ranked list rather than free text, so an exact match is a real signal of the same issue, not
  a coincidental string collision — matching on the free-text description instead would rarely hit. Only on
  a cache miss does `TechnicalKnowledgeBase.retrieve()` (`technical_kb.py`) score every `kb_articles` row by
  symptom-keyword overlap and return the top 3 — the retrieval half of RAG. `rag.py`'s `generate_response()`
  asks the LLM to write an answer grounded only in those articles; if the LLM is unavailable it falls back
  to serving the top article's body directly, using *that article's own* `escalate` flag — the exact
  behavior the agent had before the LLM existed, so a missing API key never turns an already-working
  autonomous resolution into a forced escalation. Escalations are recorded in the `escalations` table and
  pushed to the `escalation_queue` in Redis (DB write happens first and is the durable record — see
  Persistence).
- **Account agent** (`agents/account_agent/main.py`, port 8003): `intent.py`'s `extract_intent()` matches
  rule keywords ("add"/"remove"/"permission") and always regex-extracts any literal email in the text (no
  LLM needed for that — it's unambiguous either way); only text matching none of the rules falls through to
  the LLM. `account_manager.py`'s `AccountManager.build_response()` takes the resulting `AccountIntent` and
  executes deterministically against `shared/tableau_service.py`'s `SimulatedTableauBackend` (constructed
  fresh per request from the injected DB session) — capacity checks, and now also actually calling
  `deactivate_user()` when a removal request includes a real email. The model never decides whether licenses
  exist; it only helps parse what the user asked for. Capacity-exceeded requests are recorded in
  `escalations` and pushed to `manager_approval_queue`.

Each agent's core logic lives in its own sibling module(s) beside `main.py` — `router_logic.py`;
`technical_kb.py` + `rag.py`; `account_manager.py` + `intent.py` — never inline in `main.py`, which stays
thin FastAPI wiring (`/health` plus the one business endpoint). Because Docker copies each agent's directory
flattened into `/app` (so these modules land as siblings with no `agents.router_agent` package), while local
runs and pytest see the full `agents.<agent>.*` package, every intra-agent import between these sibling
modules (in `main.py` and in `account_manager.py` importing from `intent.py`) uses a fallback: `try: from
.router_logic import RouterLogic / except ImportError: from router_logic import RouterLogic`. Don't
"simplify" this to a plain relative or plain absolute import — either breaks one of the two execution
contexts. `router_logic.py`, `technical_kb.py`, `rag.py`, and `intent.py` themselves only need this pattern
if they import from *another sibling module* in the same agent directory — they import `shared.*` modules
(which live in a real top-level package in both layouts) with plain absolute imports.

**Messaging:** `shared/message_queue.py`'s `MessageQueue` wraps Redis list push/pop (`lpush`/`brpop`).
There is no in-memory fallback — if Redis is unreachable at construction it logs a warning and
`is_healthy()` (exposed via each agent's `/health`) returns `False`; `send_message`/`receive_message` raise
`MessageQueueError` on failure rather than silently dropping the message. Callers that queue escalations
(technical and account agents) catch `MessageQueueError` and log it rather than failing the ticket response
— an escalation that couldn't be queued is still visible (it's already in the `escalations` table, written
before the Redis push is attempted — see Persistence and Escalation review below) rather than silently lost.
The router agent's own `{target_agent}_queue` push in `/route_ticket` is vestigial: nothing consumes it (the
actual handoff is the orchestrator's direct HTTP call to `/handle_ticket`), so it's wrapped the same way and
never blocks routing. `escalation_queue`/`manager_approval_queue` are likewise unconsumed by anything in this
codebase today — see Escalation review for why that's a deliberate, not an accidental, gap.

**Data models** (`shared/models.py`): `SupportTicket` and `AgentMessage` are the only Pydantic models;
`category`/`priority`/`assigned_agent` on a ticket start `None` and are filled in by the router. Always
serialize them with `.model_dump(mode="json")`, not `.dict()`/`.model_dump()` — `created_at` is a `datetime`,
and anything that reaches `json.dumps` (queue messages) raises `TypeError` on a plain `datetime` object.
This was previously masked by `MessageQueue`'s in-memory fallback, which never serialized to JSON at all.

**Persistence** (`shared/db/`): SQLAlchemy models in `models.py` — `Ticket`, `TicketEvent`, `Escalation`,
`Department`, `User`, `License`, `KBArticle`. `session.py` exposes `engine`/`SessionLocal` (bound to
`DATABASE_URL`), the FastAPI dependency `get_db()` (request-scoped session), `init_db()`
(`Base.metadata.create_all` — called once at each agent's module import, idempotent), and
`is_db_healthy()` (used by `/health`). `repository.py` has the shared write helpers agents use —
`get_or_create_ticket`, `record_event`, `record_resolution`, `record_escalation` — so each `main.py` stays
thin. `metrics.py`'s `compute_ticket_metrics()` backs the Streamlit dashboard's real numbers. There are no
Alembic migrations (the plan doc originally called for them) — schema is created via `create_all()` since
there's no prior schema history yet to manage; revisit if the schema needs to evolve without a wipe.

Each agent endpoint takes `db: Session = Depends(get_db)`, not a module-level session — this is what makes
`app.dependency_overrides[get_db] = lambda: fixture_session` work cleanly in tests (see `tests/conftest.py`).
Don't refactor endpoints to grab a session at import time; it breaks that override pattern.

**Simulated Tableau backend** (`shared/tableau_service.py`): `TableauBackend` is a `Protocol` —
`SimulatedTableauBackend` (DB-backed) is the only implementation; a future `TableauCloudBackend` against the
real REST API can implement the same interface without touching agent code. `AccountManager`
(`agents/account_agent/account_manager.py`) takes a `TableauBackend` in its constructor rather than owning
data itself.

**Seeding** (`scripts/seed_db.py`): populates `licenses`/`departments` from the same numbers the original
hardcoded `AccountManager.user_database` used, a Faker-generated `User` row per department up to its
`current_users` count (so capacity is backed by real rows, not a stored counter — `SimulatedTableauBackend`
computes `current_users` via `COUNT(*) WHERE status='active'`), and `kb_articles` from `data/kb_articles.json`.
Idempotent — skips if `departments` is already populated. Run via `python -m scripts.seed_db` (needs the
`-m` form for the same `sys.path` reason as the agents) or the Docker Compose `db-seed` service.

**Hybrid intelligence** (`shared/llm_client.py`): a single `complete_json(model, system, user, schema,
retries=1, client=None, db=None)` wraps every LLM call, via the OpenAI SDK pointed at OpenRouter
(`https://openrouter.ai/api/v1`). It **never raises** — no `OPENROUTER_API_KEY` configured, a rate limit
(`RateLimitError`), a network error (`APIConnectionError`), any other API error (`APIStatusError`), or output
that never validates against `schema` after one retry all return `None` (each caught with a distinct typed
`except` so the failure reason is known, plus a final broad `except Exception` for anything unforeseen).
Every call site (router, technical, account) treats `None` identically: fall back to the deterministic rule
path. This is why the whole system runs correctly with no API key at all — every hybrid method
(`RouterLogic.classify`, `rag.generate_response`, `intent.extract_intent`) is unconditionally safe to call
either way, and the test suite exercises the real fallback path (not a mock) simply by not setting the key.
The `client` param exists purely for test injection (`tests/test_llm_client.py` uses a small fake
duck-typing `.chat.completions.create(...)`) — production call sites never pass it, they get the lazily-
constructed module-level client. Models are configured via `shared/config.py`'s `CLASSIFIER_MODEL`
(router + account intent) and `GENERATION_MODEL` (technical RAG), both defaulting to a free OpenRouter
model — see `docs/UPGRADE_PLAN.md` Phase 2 for the free-tier rate-limit constraints this is designed around.

**LLM availability tracking:** `complete_json`'s optional `db` param, when given, gets a best-effort
`LLMCallLog` row per attempt (`model`, `success`, `reason` — `"success"`, `"no_api_key"`, `"rate_limited"`,
`"connection_error"`, `"api_error"`, `"invalid_response"`, or `"unknown_error"`). It only calls `db.add()`,
never `db.commit()`, so it piggybacks on whatever transaction the caller eventually commits rather than
prematurely flushing a request's in-progress work. All three agents pass `db=db` through their hybrid call
(`classify`/`generate_response`/`extract_intent` all accept and forward an optional `db` param for exactly
this). `shared/db/metrics.py`'s `compute_llm_availability()` aggregates these rows for the Streamlit
dashboard's "LLM Availability" panel — success rate and a failure-reason breakdown.

**Deviations from the plan doc, both deliberate:** (1) KB retrieval (`TechnicalKnowledgeBase.retrieve`) uses
Python-side scored keyword matching, not Postgres `tsvector` full-text search as the plan sketched — the
project also runs on SQLite (tests, local dev default), and at this KB scale the retrieval-quality
difference is negligible. (2) When the LLM is unavailable, the technical agent's fallback preserves the
matched article's *own* `escalate` flag rather than force-escalating outright (which is what the plan's
original code sketch did) — a missing/rate-limited API key must not make an already-working autonomous
resolution start escalating; the LLM only improves *how* the answer reads, not *whether* the system can
answer at all.

**Escalation review** (`shared/escalation_review.py`): `list_pending_escalations(db)` returns unresolved
`Escalation` rows (joined with their `Ticket` for context and the agent's draft `resolution` text) — this is
what backs the Streamlit "Human Review" tab. `approve_escalation(db, escalation_id, final_response,
reviewer)` sets `ticket.status="resolved"`/`resolution=final_response`/`resolved_at`, marks
`escalation.resolved=True`, and records a `human_review` `TicketEvent` (`payload: {"decision": "approved",
"final_response": ...}`). `reject_escalation(...)` marks the escalation resolved (removing it from the
pending queue) and records the audit event, but deliberately leaves `ticket.status` at `"escalated"` — reject
means "a human is handling this outside the system," not "resolved." Neither function touches
`ticket.escalated` — that flag is a historical fact ("the AI escalated this"), not a pending-review flag, so
it stays `True` even after a human closes the ticket out; `metrics.compute_ticket_metrics()`'s escalation
rate depends on that not changing after review. Both raise `ValueError` for an unknown `escalation_id` —
callers (the Streamlit tab) don't currently catch this, so a stale escalation ID would surface as an
uncaught exception in the UI; not a concern in practice since the tab always re-fetches the pending list on
each rerun.

**Deviations from the plan doc, Phase 3:** (1) the plan called for "a small worker that drains
`escalation_queue`/`manager_approval_queue` into the `escalations` table" — skipped, because Phase 1 already
writes that table synchronously and atomically *before* the best-effort Redis push, which is a stronger
durability guarantee than draining a queue asynchronously would provide (no risk of a drain worker crashing
between reading and writing). (2) the plan's `open → in_progress → resolved | escalated → closed` ticket
status lifecycle was simplified to the existing 3-state `tickets.status` field (`open`/`resolved`/
`escalated`) plus the `human_review` audit event — there's no downstream workflow (customer notification,
reopen flow, etc.) that would consume `in_progress`/`closed` states, so adding them would be speculative.

**Hardening — auth** (`shared/auth.py`): `verify_internal_token` is a FastAPI dependency checking the
`X-Internal-Token` header against `config.INTERNAL_API_TOKEN`, wired via `dependencies=[Depends(...)]` on
every agent's business endpoint (`/route_ticket`, `/handle_ticket`) — deliberately **not** on `/health`,
which needs to stay reachable for infra healthchecks without a token. It's a no-op when
`INTERNAL_API_TOKEN` is unset (the default), so local dev and the test suite never need to think about it
unless a test explicitly monkeypatches it on. It reads `config.INTERNAL_API_TOKEN` via `from shared import
config; config.INTERNAL_API_TOKEN` (module attribute access at call time), not a top-level `from
shared.config import INTERNAL_API_TOKEN` — the latter would bind the value at `auth.py`'s import time and
never see a test's `monkeypatch.setattr(config, "INTERNAL_API_TOKEN", ...)`. `shared/orchestrator.py`
attaches the same header on every request it makes to an agent when the token is configured.

**Hardening — structured logging** (`shared/logging_config.py`): `configure_logging()` replaces the root
logger's handlers with a single JSON-formatting stdout handler (idempotent — safe to call from every agent's
`main.py` and from `orchestrator.py`, even in the same process, since it replaces rather than appends).
`set_ticket_id(ticket_id)` binds a `contextvars.ContextVar` that `JSONFormatter` reads into every log
record's `ticket_id` field for the rest of that request — safe under FastAPI because each request runs in
its own asyncio Task and contextvars are isolated per Task, so concurrent requests never bleed into each
other's logs. Each agent calls `set_ticket_id` at the top of its business endpoint, right after parsing the
ticket; `orchestrator.py` calls it at the top of `process_support_ticket`.

**Cloud deployment** (`render.yaml`, `docs/DEPLOYMENT.md`): the $0 path is Neon (Postgres) + Render free web
services (the three agents) + Streamlit Community Cloud (the demo UI) — chosen over a paid VM or other
free-but-card-required platforms (Oracle Always Free, Google Cloud Run) specifically because none of these
three require a credit card, so nothing in the stack has a billing mechanism attached at all. Two small code
changes support it, both backward-compatible (no-ops for local/Docker use):
- Each agent's `uvicorn.run(...)` binds to `int(os.environ.get("PORT", <fixed port>))` — Render (like most
  PaaS free tiers) injects `PORT` and requires binding to it; `PORT` is never set locally or in Docker
  Compose, so this falls through to the existing hardcoded port there.
- `demo/streamlit_interface.py` bridges `st.secrets` into `os.environ` (wrapped in `try/except`, since
  `st.secrets` has nothing to iterate — and may error — when no `secrets.toml` exists, i.e. every non-Cloud
  run) before importing `shared/config.py`. Streamlit Community Cloud only exposes configured secrets via
  `st.secrets`, not the process environment, so without this bridge `shared/config.py`'s ordinary
  `os.environ.get(...)` calls would see nothing on Streamlit Cloud specifically.

`render.yaml` is a Blueprint (`runtime: docker`, one service per agent, `plan: free`,
`healthCheckPath: /health`); its env vars are all `sync: false` (set per-service in the Render dashboard, not
committed). `INTERNAL_API_TOKEN` — opt-in since Phase 4 with nothing that truly needed it while everything
ran on localhost/the compose network — becomes load-bearing here: once the three agents have public Render
URLs, it's the only thing gating `/route_ticket`/`/handle_ticket` from the open internet, so
`docs/DEPLOYMENT.md` makes setting it a required step. Redis is deliberately not part of this deployment —
skip it rather than add a fourth signup; the system has tolerated Redis being unreachable since Phase 0
(`/health` reports `degraded`, nothing else breaks, since the database — not Redis — has been the durable
record since Phase 1). Seeding the deployed Neon database is a manual one-time step
(`DATABASE_URL=<neon-url> python -m scripts.seed_db` from a local machine) since Neon's free tier has no
built-in job runner to automate it.

**Unused/dead code:** `data/mock_tickets.json` and `data/company_data.json` are still not read by any Python
code. `data/kb_articles.json` is now used — by `scripts/seed_db.py` only, not read at agent runtime (the
agent queries the `kb_articles` table the seed script populated from it).
