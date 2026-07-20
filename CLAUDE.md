# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A portfolio project simulating a multi-agent customer support system for Tableau issues at a fictional
fintech company. Three FastAPI microservices (router, technical, account) coordinate over HTTP and Redis
to classify and resolve support tickets, fronted by a Streamlit demo UI.

## Running the system

Docker Compose (recommended — service hostnames like `router-agent` only resolve inside the compose network):
```
docker compose up --build
docker compose down
```
Ports: router-agent `8001`, technical-agent `8002`, account-agent `8003`, Streamlit demo `8501`, Redis `6379`.

Running locally without Docker (each agent in its own terminal, from repo root; requires
Redis running — `redis-server` or `docker run -p 6379:6379 redis:7-alpine`):
```
pip install -r requirements.txt
python -m agents.router_agent.main
python -m agents.technical_agent.main
python -m agents.account_agent.main
streamlit run demo/streamlit_interface.py
```
Use `-m agents.<agent>.main`, not `python agents/<agent>/main.py` — the latter puts the
agent's own directory (not the repo root) at the front of `sys.path`, so the `from shared...`
imports fail. All agent endpoints and Redis are configured via env vars in `shared/config.py`
(`ROUTER_URL`, `TECHNICAL_URL`, `ACCOUNT_URL`, `REDIS_URL`), defaulting to `localhost` for
local runs; Docker Compose overrides them to the compose service hostnames.

Tests: `pytest` (config in `pytest.ini`, root `conftest.py` puts the repo root on `sys.path`
for imports). Covers `RouterLogic`/`TechnicalKnowledgeBase`/`AccountManager` directly plus
FastAPI `TestClient` tests per agent, including `/health`. No Redis or Docker required — see
Messaging below for why. No lint config or CI yet.

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
  technical agent (no dedicated training agent exists).
- **Technical agent** (`agents/technical_agent/main.py`, port 8002): matches ticket text against a small
  hardcoded symptom-keyword table (`TechnicalKnowledgeBase.solutions`) and returns canned remediation steps.
  Database-connection issues and unmatched tickets are pushed to the `escalation_queue` in Redis.
- **Account agent** (`agents/account_agent/main.py`, port 8003): parses free-text ticket descriptions
  (regex-extracts a user count, string-matches on "add"/"remove"/"permission") against a hardcoded
  per-department license/capacity table (`AccountManager.user_database`) to approve/deny/escalate access
  requests. Capacity-exceeded requests are pushed to `manager_approval_queue`.

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

**Unused/dead code:** `data/*.json` (mock tickets, KB articles, company data) are not read by any Python
code — all sample data used at runtime is hardcoded inline in the agent classes instead.
