# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A portfolio project simulating a multi-agent customer support system for Tableau issues at a fictional
fintech company. Three FastAPI microservices (router, technical, account) coordinate over HTTP, backed by
Redis (messaging) and Postgres/SQLite (persistence), fronted by a Streamlit demo UI.

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
service hostnames and Postgres.

Tests: `pytest` (config in `pytest.ini`, root `conftest.py` puts the repo root on `sys.path` for
imports). Covers `RouterLogic`/`TechnicalKnowledgeBase`/`AccountManager`/`SimulatedTableauBackend`/
`shared/db/repository.py`/`shared/db/metrics.py` directly plus FastAPI `TestClient` tests per
agent, including `/health`. No Redis, Postgres, or Docker required: `tests/conftest.py` provides
`db_session` (fresh in-memory SQLite + schema) and `seeded_db` (same, with fixture departments/
users/KB articles) fixtures, and API tests override the `get_db` FastAPI dependency with them —
see Persistence below. No lint config or CI yet.

## Architecture

**Request flow:** a `SupportTicket` (shared/models.py) is submitted to `shared/orchestrator.py`'s
`AgentOrchestrator`, the single orchestration path (both `demo/streamlit_interface.py` and any
future caller use it — there is no duplicate implementation). It POSTs to the router agent's
`/route_ticket` (classifies category + priority, determines the target agent), then POSTs to
that agent's `/handle_ticket`. Agent endpoints come from `shared/config.py`'s `AGENT_ENDPOINTS`.

**Agent responsibilities:**
- **Router agent** (`agents/router_agent/main.py`, port 8001): keyword-based classification into
  `TicketCategory` (technical/account/training) and `Priority` (critical/high/medium/low). Department name
  in `critical_departments` (Trading, Risk Management, Executive) forces at least HIGH priority; certain
  keywords force CRITICAL regardless of department. Training-category tickets are currently routed to the
  technical agent (no dedicated training agent exists). It's also the one that creates the `tickets` row
  (via `get_or_create_ticket`) — it's normally first to see a ticket.
- **Technical agent** (`agents/technical_agent/main.py`, port 8002): matches ticket text against the
  `kb_articles` table (`TechnicalKnowledgeBase`, queried via an injected DB session — one per request) and
  returns the best-matching article's remediation text. Database-connection issues and unmatched tickets are
  recorded in the `escalations` table and pushed to the `escalation_queue` in Redis (DB write happens first
  and is the durable record — see Persistence).
- **Account agent** (`agents/account_agent/main.py`, port 8003): parses free-text ticket descriptions
  (regex-extracts a user count, string-matches on "add"/"remove"/"permission") and calls
  `shared/tableau_service.py`'s `SimulatedTableauBackend` (constructed fresh per request from the injected
  DB session) to check department capacity against real `departments`/`users` rows. Capacity-exceeded
  requests are recorded in `escalations` and pushed to `manager_approval_queue`.

Each agent's core logic class (`RouterLogic`, `TechnicalKnowledgeBase`, `AccountManager`) lives in its own
sibling module (`router_logic.py`, `technical_kb.py`, `account_manager.py`); `main.py` is thin FastAPI
wiring — `/health` plus the one business endpoint. Because Docker copies each agent's directory flattened
into `/app` (so `main.py` and `router_logic.py` land as siblings with no `agents.router_agent` package),
while local runs and pytest see the full `agents.<agent>.*` package, each `main.py` imports its logic module
with a fallback: `try: from .router_logic import RouterLogic / except ImportError: from router_logic import
RouterLogic`. Don't "simplify" this to a plain relative or plain absolute import — either breaks one of the
two execution contexts.

**Messaging:** `shared/message_queue.py`'s `MessageQueue` wraps Redis list push/pop (`lpush`/`brpop`).
There is no in-memory fallback — if Redis is unreachable at construction it logs a warning and
`is_healthy()` (exposed via each agent's `/health`) returns `False`; `send_message`/`receive_message` raise
`MessageQueueError` on failure rather than silently dropping the message. Callers that queue escalations
(technical and account agents) catch `MessageQueueError` and log it rather than failing the ticket response
— an escalation that couldn't be queued is visible in logs, not silently lost. The router agent's own
`{target_agent}_queue` push in `/route_ticket` is vestigial: nothing consumes it (the actual handoff is the
orchestrator's direct HTTP call to `/handle_ticket`), so it's wrapped the same way and never blocks routing.

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

**Unused/dead code:** `data/mock_tickets.json` and `data/company_data.json` are still not read by any Python
code. `data/kb_articles.json` is now used — by `scripts/seed_db.py` only, not read at agent runtime (the
agent queries the `kb_articles` table the seed script populated from it).
