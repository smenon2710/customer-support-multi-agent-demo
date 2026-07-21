# Upgrade Plan: Demo → Working Model

Target state: a deployable multi-agent Tableau support system with **hybrid intelligence**
(deterministic rules for routing, an LLM — via OpenRouter free-tier models — for response
generation and ambiguous cases), a **simulated Tableau backend** behind a swappable service
interface, and **cloud deployment**.

This plan is ordered so each phase leaves the system runnable. Phases 0–2 are the core
upgrade; 3–5 make it production-shaped.

---

## Phase 0 — Foundations (cleanup and config) ✅ Done

Goal: remove demo shortcuts that will fight every later phase.

1. **Single orchestrator.** Delete the duplicated flow in `demo/streamlit_interface.py`
   (`process_ticket_with_orchestrator`) and make the Streamlit app call
   `shared/orchestrator.py`. One code path for route → handle.
2. **Config via environment variables.** Replace all hardcoded URLs
   (`http://router-agent:8001`, `localhost`) with env vars read in one place:
   ```python
   # shared/config.py
   import os

   ROUTER_URL = os.environ.get("ROUTER_URL", "http://localhost:8001")
   TECHNICAL_URL = os.environ.get("TECHNICAL_URL", "http://localhost:8002")
   ACCOUNT_URL = os.environ.get("ACCOUNT_URL", "http://localhost:8003")
   REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
   DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./support.db")
   OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]  # required in Phase 2
   CLASSIFIER_MODEL = os.environ.get("CLASSIFIER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
   GENERATION_MODEL = os.environ.get("GENERATION_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
   ```
   Docker Compose sets the container-network values; local dev uses the defaults.
3. **Remove the silent Redis fallback.** `shared/message_queue.py` currently swallows a
   Redis outage into an in-memory dict, which silently drops escalations. Fail loudly at
   startup instead (raise if Redis is unreachable), or log a prominent warning and expose
   a `/health` endpoint per agent that reports queue connectivity.
4. **Delete dead files** (`router_logic.py`, `technical_kb.py`, `account_manager.py`,
   `shared/knowledge_base.py` — all empty) or move the inline classes into them. Pick one;
   recommendation: move the classes into the named modules so `main.py` files are thin
   FastAPI wiring.
5. **Real tests.** Convert `test_system.py`/`simple_test.py` into a `pytest` suite using
   FastAPI's `TestClient` so the classification/handling logic is testable without running
   servers. Target: unit tests for `RouterLogic.classify_ticket`, KB matching, and license
   capacity logic; one integration test against docker compose in CI.

Deliverable: same behavior as today, but one orchestration path, env-driven config, pytest green.

---

## Phase 1 — Persistence and the simulated Tableau backend ✅ Done

Goal: tickets and enterprise data live in a database, not in Python literals.

1. **Database.** Postgres in `docker-compose.yml` (SQLite for local dev via `DATABASE_URL`,
   the default when unset). SQLAlchemy models in `shared/db/models.py`:
   - `tickets` — everything in `SupportTicket` plus `status`, `resolution`, `escalated`,
     `resolved_at`. The router agent creates the row (`get_or_create_ticket`); handling
     agents update it via `record_resolution`.
   - `ticket_events` — the conversation log (agent, action, payload, timestamp) that used
     to be thrown away after each request.
   - `departments`, `users`, `licenses` — replaces `AccountManager.user_database`.
     `current_users` isn't a stored counter — `SimulatedTableauBackend` computes it as
     `COUNT(*) WHERE status='active'` against real `User` rows, so capacity checks reflect
     actual provisioned users, not a number that can drift.
   - `kb_articles` — replaces `TechnicalKnowledgeBase.solutions`; seeded from
     `data/kb_articles.json` (now populated) by `scripts/seed_db.py`, not read from the
     JSON file at agent runtime.
   - `escalations` — durable record of anything pushed to an escalation queue. Written
     *before* the Redis push is attempted, so an escalation survives even if Redis is down
     — Redis is now just a notification signal, not the record of truth.

   **Deviation from the original plan: no Alembic.** The plan called for SQLAlchemy +
   Alembic migrations; this uses `Base.metadata.create_all()` (idempotent, called at each
   agent's startup) instead. There's no prior schema to migrate *from* yet, so a migration
   tool has no history to manage — it would be pure scaffolding. Revisit this when the
   schema needs to change without a full wipe (add Alembic then, generate an initial
   migration from the current models, and apply it via a `db-migrate` step in
   `docker-compose.yml` the same way `db-seed` works today).
2. **Simulated Tableau service.** `shared/tableau_service.py` defines the interface the
   account agent talks to, with a database-backed implementation:
   ```python
   class TableauBackend(Protocol):
       def get_department(self, name: str) -> Optional[DepartmentInfo]: ...
       def check_capacity(self, department: str, requested_users: int) -> ProvisionResult: ...
       def provision_user(self, email: str, department: str) -> bool: ...
       def deactivate_user(self, email: str) -> bool: ...
       def get_site_status(self) -> SiteStatus: ...
   ```
   (`check_capacity` replaced the plan's original `provision_user(..., license: str)` shape
   — actual provisioning needs a concrete email, which the ticket text doesn't have at
   submission time; `provision_user` here takes just `email`/`department` for when Phase 3's
   human-review approval flow has one.) The DB-backed `SimulatedTableauBackend` is the only
   implementation now; a future `TableauCloudBackend` (REST API) slots in behind the same
   interface without touching agent code. Seeded with the existing department/license
   numbers plus a Faker-generated user population (`scripts/seed_db.py`).
3. **Real metrics.** The Streamlit "System Metrics" tab now calls `shared/db/metrics.py`'s
   `compute_ticket_metrics()` (resolution rate, escalation rate, tickets by department/
   priority, median handling time) and `SimulatedTableauBackend.get_site_status()` (real
   user/department counts) instead of showing hardcoded numbers — including removing the
   fabricated `+12%`/`-45%`-style deltas, since there's no historical baseline to compare
   against yet.

Deliverable: submit a ticket → it's in Postgres with its full event log; account agent
reads/writes real (simulated) license state; dashboard shows real numbers.

---

## Phase 2 — Hybrid intelligence (the core upgrade) ✅ Done

Goal: rules stay for the cheap/fast path; Claude handles what rules can't.

**Implementation notes vs. the sketch below:** the shipped `shared/llm_client.py` matches this section's
`complete_json` closely, with two additions — a `client` param for test injection (no network access needed
to test the retry/validation logic) and a broad `except Exception` catch (not just rate-limit/connection
errors) so *any* provider failure degrades gracefully, never raises. Two deliberate deviations, documented
in `CLAUDE.md`: (1) the technical agent's retrieval step is Python-side scored keyword matching, not
Postgres `tsvector`, so it works identically on the SQLite fallback this project also runs on; (2) the
technical agent's LLM-unavailable fallback preserves the matched article's own `escalate` flag (matching
Phase 1's already-working autonomous resolution) rather than force-escalating — a missing API key must not
make a working resolution start escalating. The router's and account agent's rules-first/LLM-fallback
pattern matches the sketch as written.

### 2a. Router: rules first, LLM for ambiguous cases

**LLM provider: OpenRouter (free-tier models).** All LLM calls go through one wrapper,
`shared/llm_client.py`, built on the OpenAI-compatible API pointed at OpenRouter. This keeps
agent code provider-ignorant — swapping models (or providers) is an env change:

```python
# shared/llm_client.py
from openai import OpenAI
from pydantic import BaseModel, ValidationError
from shared.config import OPENROUTER_API_KEY

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)

def complete_json(model: str, system: str, user: str, schema: type[BaseModel],
                  retries: int = 1) -> BaseModel | None:
    """Ask for JSON, validate with Pydantic, retry once, return None on failure.

    Callers MUST handle None by falling back to the deterministic path —
    free-tier models do not reliably honor JSON schemas.
    """
    for attempt in range(retries + 1):
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            max_tokens=1024,
        )
        try:
            return schema.model_validate_json(resp.choices[0].message.content)
        except ValidationError:
            continue
    return None
```

Keep keyword scoring, but make it emit a **real confidence** (today's 0.85 is hardcoded).
When the rule signal is weak (e.g. score margin < 2, or zero keyword hits), fall through to
an LLM classification call:

```python
class Classification(BaseModel):
    category: str        # "technical" | "account" | "training"
    priority: str        # "critical" | "high" | "medium" | "low"
    reasoning: str
    confidence: float

result = complete_json(CLASSIFIER_MODEL, CLASSIFIER_SYSTEM_PROMPT,
                       f"Department: {department}\n\n{ticket_text}", Classification)
if result is None:
    result = rule_based_fallback(ticket)  # rules are the safety net, always
```

Business rules stay authoritative where they're policy, not inference: Trading/Risk/Executive
department floors the priority at HIGH regardless of what the model says. And the rules path
is not just a fallback for weak signals — it's the fallback for **every** LLM failure mode
(invalid JSON, rate limit, model unavailable).

### 2b. Technical agent: RAG over the knowledge base

Replace the 4-entry symptom table with retrieval + generation:

1. **Retrieval.** Start simple: Postgres full-text search (`tsvector`) over `kb_articles`
   returning the top 3–5 articles. This is good enough at KB scale (dozens–hundreds of
   articles) and avoids an embedding pipeline; add pgvector later only if retrieval quality
   demands it.
2. **Generation.** Pass the retrieved articles + ticket to the model; it writes the
   response grounded in them and decides whether to escalate:

```python
class AgentResponse(BaseModel):
    response: str          # markdown answer for the user
    escalate: bool
    escalation_reason: str | None
    kb_articles_used: list[str]

def generate_response(ticket_text: str, articles: list[KBArticle]) -> AgentResponse:
    kb_context = "\n\n".join(f"## {a.title}\n{a.body}" for a in articles)
    result = complete_json(
        GENERATION_MODEL, TECH_AGENT_SYSTEM_PROMPT,
        f"<knowledge_base>\n{kb_context}\n</knowledge_base>\n\n"
        f"<ticket>\n{ticket_text}\n</ticket>",
        AgentResponse,
    )
    if result is None:
        # LLM unavailable/unparseable → serve the top KB article verbatim + escalate
        return AgentResponse(
            response=f"**Suggested article:** {articles[0].title}\n\n{articles[0].body}"
                     if articles else "A specialist will follow up shortly.",
            escalate=True, escalation_reason="llm_unavailable",
            kb_articles_used=[a.id for a in articles[:1]],
        )
    return result
```

The system prompt instructs: answer only from the KB context; if the KB doesn't cover it,
set `escalate=true` rather than inventing steps. Escalations are persisted (Phase 1) and
queued (Phase 3). Free-tier models are weaker than frontier models, so keep the task narrow:
the model rewrites retrieved KB content into a grounded answer — it never invents
troubleshooting steps, and retrieval quality (not model quality) does the heavy lifting.

### 2c. Account agent: LLM intent extraction, deterministic execution

The fragile regex (`re.findall(r'\d+', text)` grabs any number, including "Tableau 2024")
becomes an LLM extraction step with a strict schema (intent: add/remove/modify-permissions,
user count, target emails). **Execution stays deterministic**: capacity checks, provisioning,
and escalation thresholds run against the `TableauBackend` — the model never decides whether
licenses exist, it only parses what the user asked for.

### Model selection and free-tier constraints

Models are config values (`CLASSIFIER_MODEL`, `GENERATION_MODEL`) pointing at OpenRouter
`:free` model IDs — free offerings rotate, so check openrouter.ai/models for what's
currently available and pick the strongest instruct model on offer (a 70B-class model for
generation; the same or smaller for classification). Swapping is an env change.

**Free-tier realities to design around (not merely handle):**

- **Rate limits.** OpenRouter free tier is roughly 20 requests/min with a daily cap
  (~50/day without purchased credits, ~1000/day with a small one-time credit balance).
  The rules-first design is what makes this workable: most tickets never touch the LLM.
  Track daily usage in Redis and switch to rules-only mode when approaching the cap.
- **429s are routine, not exceptional.** On rate limit: no retry storm — go straight to
  the deterministic fallback and mark the ticket for async retry or escalation.
- **No schema guarantees.** Free models honor `response_format: json_object` inconsistently
  and don't support strict JSON-schema enforcement — hence the validate-and-fallback
  pattern in `complete_json` above.
- **Model churn.** Free models get deprecated or degraded without notice. Because model IDs
  are env vars and every call site has a deterministic fallback, a dead model degrades
  service quality but never availability.

Cost is $0 by design; the levers above are about **staying within quota**, not spend.
If the project later moves to paid models (OpenRouter paid tier or a direct provider),
only `shared/llm_client.py` and two env vars change.

Deliverable: any realistically-phrased ticket gets classified correctly and receives a
grounded, non-canned response; the demo scenarios still pass; a nonsense ticket escalates
instead of hallucinating steps.

---

## Phase 3 — Close the escalation loop ✅ Done

Goal: escalations go somewhere a human can see and act on.

**Implementation notes vs. the sketch above, two deliberate deviations (documented in `CLAUDE.md`):**
(1) **No escalation-consumer worker.** Step 1 below assumed the `escalations` table would be populated by
draining the Redis queue — but Phase 1 already writes that table synchronously and atomically, *before* the
best-effort Redis push, which is a stronger durability guarantee than an async drain would give (no window
where a crashed drain worker loses a message between read and write). `escalation_queue`/
`manager_approval_queue` remain genuinely unconsumed today — they're notification-only infrastructure for a
future integration (Slack, email) that doesn't exist yet. (2) **Simplified status lifecycle.** Step 3's
`open → in_progress → resolved | escalated → closed` became the existing 3-state `tickets.status`
(`open`/`resolved`/`escalated`) plus a `human_review` audit event recording who reviewed what and when —
there's no downstream workflow that would act on `in_progress`/`closed` distinctly, so adding them was
speculative complexity with no consumer.

1. ~~**Escalation consumer.**~~ Superseded by Phase 1 — see above.
2. **Human review UI.** New Streamlit tab (`demo/streamlit_interface.py`'s `human_review_interface`,
   backed by `shared/escalation_review.py`): pending escalations (`list_pending_escalations`), ticket
   context, the agent's draft response, and **Approve & Send** / **Send Edited Response** / **Reject**
   actions. Approve/Edit call `approve_escalation` (`ticket.status="resolved"`, `resolution=<final text>`,
   `escalation.resolved=True`); Reject calls `reject_escalation` (`escalation.resolved=True` only — the
   ticket stays `escalated` for manual handling outside the system). Both record a `human_review`
   `TicketEvent` for audit. A sidebar badge shows the pending count.
3. ~~**Ticket status lifecycle.**~~ Simplified — see above.

Deliverable: no message is ever fire-and-forget; every escalation is visible and actionable.

---

## Phase 4 — Hardening ✅ Done

1. **Service auth.** `shared/auth.py`'s `verify_internal_token` FastAPI dependency checks a
   shared-secret `X-Internal-Token` header, wired onto every agent's business endpoint
   (`/route_ticket`, `/handle_ticket`) — **not** `/health`, which stays open for infra
   healthchecks. Opt-in via `INTERNAL_API_TOKEN`: unset (the default) disables auth
   entirely, so local dev and the test suite don't need to know about it.
   `shared/orchestrator.py` attaches the header on every agent call when configured.
2. **Structured logging.** `shared/logging_config.py`'s `configure_logging()` (JSON stdout
   handler) plus `set_ticket_id()` (a `contextvars.ContextVar`, correctly isolated per
   request under FastAPI's per-request asyncio Tasks) — every log line during a ticket's
   handling carries its `ticket_id`, across all three agents and the orchestrator.
3. **Error handling for the LLM API.** `shared/llm_client.py`'s `complete_json` now has a
   typed exception chain (`RateLimitError` → `APIConnectionError` → `APIStatusError` → a
   final broad `Exception` catch-all), each logging a distinct reason code. Went further
   than "log every fallback" — attempts (success or failure, with reason) are recorded to
   a new `llm_call_log` table via an optional `db` param threaded through `complete_json`
   and the three hybrid methods (`RouterLogic.classify`, `rag.generate_response`,
   `intent.extract_intent`), aggregated by `shared/db/metrics.py`'s
   `compute_llm_availability()` and shown on the Streamlit dashboard's "LLM Availability"
   panel — a real, queryable answer to "how often is the LLM actually available," not just
   log lines to grep.
4. **CI.** `.github/workflows/ci.yml`: `ruff check .` (lint), `pytest` (test — already
   never makes real network calls, satisfying "LLM calls mocked" by construction, not by
   explicit mocking), `docker compose build`, and `scripts/llm_smoke_test.py` as an
   optional live smoke test gated on the `OPENROUTER_API_KEY` repo secret.

---

## Phase 5 — Cloud deployment

Recommended: **a single small VM running Docker Compose** (e.g. EC2 t3.small / Lightsail /
DigitalOcean droplet, ~$10–20/mo). The system is 5 small containers with modest traffic;
a managed-container platform (Cloud Run/ECS) adds cost and complexity without benefit at
this scale, and Redis + Postgres run fine as compose services with volume mounts.

Steps:

1. **Production compose file** (`docker-compose.prod.yml`): adds Postgres with a volume,
   removes host port mappings for internal services (only Streamlit/gateway exposed),
   `restart: unless-stopped`, healthchecks on all services.
2. **Secrets.** `OPENROUTER_API_KEY`, DB password, internal token via an `.env` file on the
   VM (never committed) or the provider's secret store.
3. **TLS + entry point.** Caddy (simplest — automatic HTTPS) or nginx in front of Streamlit,
   with basic auth or an allowlist if the demo shouldn't be public.
4. **Deploy flow.** Push to `main` → GitHub Action builds images, SSHes to the VM,
   `docker compose pull && docker compose up -d`. Tag images by git SHA for rollback.
5. **Monitoring.** Container healthchecks + a free uptime pinger (e.g. UptimeRobot) on the
   public URL; logs via `docker compose logs` initially, ship to a hosted sink later if needed.

Migration path: because config is env-driven (Phase 0), moving to ECS/Cloud Run later is a
packaging change, not a code change.

---

## Suggested order of attack

| Phase | Effort (rough) | Depends on |
|---|---|---|
| 0 — Foundations | 1–2 days | — |
| 1 — Persistence + simulated backend | 2–4 days | 0 |
| 2 — Hybrid intelligence | 3–5 days | 1 (KB + tickets in DB) |
| 3 — Escalation loop | 2–3 days | 1 |
| 4 — Hardening | 2–3 days | 2, 3 |
| 5 — Cloud deployment | 1–2 days | 4 (auth/secrets) |

Phases 2 and 3 can proceed in parallel after Phase 1. The first end-to-end "working model"
milestone is **0 + 1 + 2**: real persistence, real intelligence, honestly-computed metrics.
