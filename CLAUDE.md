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

Running locally without Docker (each agent in its own terminal, from repo root):
```
pip install -r requirements.txt
python agents/router_agent/main.py
python agents/technical_agent/main.py
python agents/account_agent/main.py
streamlit run demo/streamlit_interface.py
```
Note: `shared/message_queue.py`'s `MessageQueue` defaults to `host='localhost'`, but `shared/orchestrator.py`
and `demo/streamlit_interface.py` hardcode compose service hostnames (`router-agent`, `technical-agent`,
`account-agent`) when calling agent HTTP endpoints — those only resolve when running under Docker Compose,
not when running agents as bare local processes.

There is no test runner, lint config, or CI. `test_system.py` and `simple_test.py` are standalone scripts
(not pytest suites) that POST sample tickets to running agent endpoints — run them with `python test_system.py`
after the relevant agents are up.

## Architecture

**Request flow:** a `SupportTicket` (shared/models.py) is submitted to the router agent, which classifies
it (category + priority) and determines the target agent, then either the caller or the router forwards the
ticket to that agent's `/handle_ticket` endpoint. There are two parallel orchestration paths that duplicate
this flow independently:
- `shared/orchestrator.py` (`AgentOrchestrator`) — used by `test_system.py`.
- `demo/streamlit_interface.py`'s `process_ticket_with_orchestrator()` — used by the Streamlit UI.

Both call the same two HTTP hops (`POST /route_ticket` then `POST /handle_ticket`) but are separate code
paths; a change to the routing/handling contract needs to be reflected in both.

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

Each agent's core logic class (`RouterLogic`, `TechnicalKnowledgeBase`, `AccountManager`) is defined and
used entirely inline within that agent's `main.py`, not in the sibling module that its name suggests
(`router_logic.py`, `technical_kb.py`, `account_manager.py`, and `shared/knowledge_base.py` are all empty
placeholder files left over from the original scaffold — do not assume logic lives there).

**Messaging:** `shared/message_queue.py`'s `MessageQueue` wraps Redis list push/pop (`lpush`/`brpop`) and
transparently falls back to a process-local in-memory dict if Redis is unreachable at construction time —
this fallback means "queued" escalation messages can silently vanish (never persisted, not shared across
processes) when Redis isn't available, which matters if you're debugging why an escalation queue appears
empty.

**Data models** (`shared/models.py`): `SupportTicket` and `AgentMessage` are the only Pydantic models;
`category`/`priority`/`assigned_agent` on a ticket start `None` and are filled in by the router.

**Unused/dead code:** `data/*.json` (mock tickets, KB articles, company data) are not read by any Python
code — all sample data used at runtime is hardcoded inline in the agent classes instead.
