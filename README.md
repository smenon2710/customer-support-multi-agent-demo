# 🤖 Multi-Agent Tableau Customer Support System

An enterprise-scale customer support automation system using coordinated AI agents to handle Tableau-related support requests for FinTech Analytics Corp.

## 🎯 Problem Statement

Large financial institutions with 5,000+ Tableau users face:
- **High support volume**: Hundreds of daily tickets across multiple departments
- **Complex prioritization**: Trading issues need immediate attention vs. training questions  
- **Specialized knowledge**: Different issue types require different expertise
- **24/7 availability**: Global operations require round-the-clock support

## 🏗️ Multi-Agent Solution

### Agent Architecture
- **🧭 Router Agent**: Intelligent ticket classification and routing
- **🔧 Technical Support Agent**: Tableau troubleshooting and solutions
- **👤 Account Management Agent**: User access and licensing management

### Key Features
- **Smart Classification**: Automatic categorization by issue type and priority
- **Department-Aware**: Trading dept = Critical, others = contextual priority
- **Specialist Routing**: Technical vs. account issues handled by experts
- **Escalation Logic**: Complex issues automatically escalated to humans
- **Enterprise Context**: Realistic departmental data and business logic

## 🚀 Quick Start

Running the Project with Docker (Recommended)
This project uses Docker and Docker Compose to build and run all microservices and the Streamlit demo interface easily.

Prerequisites
Install Docker Desktop (Windows/Mac) or Docker Engine and Docker Compose (Linux)
Ensure Docker daemon is running
Build and Start All Services
From the root of the cloned repository (where your docker-compose.yml file is located), run:
docker compose up --build

This command will:
Build Docker images for each AI agent and the Streamlit demo app
Start containers including Redis (message queue) and Postgres (persistence)
Run a one-off `db-seed` job that populates departments, a Faker-generated user
population, and the technical knowledge base before any agent starts

Map ports:
Router Agent on localhost:8001
Technical Agent on localhost:8002
Account Agent on localhost:8003
Streamlit Demo Interface on localhost:8501
Access the Demo Interface

Open your browser and go to:
http://localhost:8501

Use the interface to submit support tickets and see multi-agent coordination in action.
Stop the System
To stop and remove all containers, run:
docker compose down

Running Locally Without Docker
If you prefer to run services manually on your machine:

1. **Install Dependencies**
pip install -r requirements.txt

2. **Start Redis** (required — agents no longer fall back silently if Redis is
   unreachable; they log a warning and report `degraded` on their `/health` endpoint,
   and escalation messages will not be recorded)
redis-server
(or `docker run -p 6379:6379 redis:7-alpine`)

3. **Set up the database.** By default `DATABASE_URL` falls back to a local SQLite
   file (`sqlite:///./support.db`) — nothing to install. To use Postgres instead,
   run one locally (or `docker run -p 5432:5432 -e POSTGRES_PASSWORD=... postgres:16-alpine`)
   and export `DATABASE_URL=postgresql://user:pass@localhost:5432/dbname`. Either way,
   seed it once:
python -m scripts.seed_db

4. **(Optional) Enable the LLM layer.** Copy `.env.example` to `.env` and set
   `OPENROUTER_API_KEY` (free at https://openrouter.ai/keys) to turn on
   LLM-backed classification and response generation for the cases the rule
   engine can't confidently handle on its own. Without it, every agent runs in
   pure rules-only mode — nothing breaks, it's just less capable on ambiguous
   tickets. Docker Compose picks up `.env` automatically; for local runs export
   the variables in your shell instead.

   **(Optional) Enable internal-service auth.** Set `INTERNAL_API_TOKEN` (in the
   same `.env`, or exported) to require a shared-secret header between the demo
   app and the three agents. Unset by default — fine for local dev on your own
   machine; set it if you're exposing agent ports beyond localhost.

5. **Start All Agents** (run each from the project root, using `-m` so the
   `shared` package resolves correctly)
Terminal 1: Router Agent
python -m agents.router_agent.main

Terminal 2: Technical Agent
python -m agents.technical_agent.main

Terminal 3: Account Agent
python -m agents.account_agent.main


6. **Launch Demo Interface**
streamlit run demo/streamlit_interface.py

## 🧪 Running Tests

pip install -r requirements.txt
pytest

The suite covers the routing/classification, knowledge-base matching, and license-capacity
logic directly, plus FastAPI `TestClient` tests for each agent's HTTP endpoints (including
`/health`). No running Redis, Postgres, or Docker is required — the database layer is
exercised against an isolated in-memory SQLite database created fresh per test
(`tests/conftest.py`), and agents degrade gracefully when Redis is unreachable rather
than failing to start.

Lint: `pip install -r requirements-dev.txt && ruff check .` GitHub Actions
(`.github/workflows/ci.yml`) runs lint, tests, and a `docker compose build` on every push
and PR; an optional live LLM smoke test (`scripts/llm_smoke_test.py`) runs only when the
`OPENROUTER_API_KEY` repo secret is configured.

## 🗄️ Database & Seeding

Tickets, departments, users, licenses, the technical knowledge base, and escalations are
persisted via SQLAlchemy models in `shared/db/`. `scripts/seed_db.py` populates the same
departmental data the original demo hardcoded, plus a Faker-generated user population
matching each department's user count — it's idempotent, so re-running it is a no-op once
seeded. Account-related reads/writes go through `shared/tableau_service.py`'s
`TableauBackend` interface (`SimulatedTableauBackend` today); a future integration with the
real Tableau REST API can implement the same interface without touching agent code.

## 🧠 Hybrid Intelligence

Each agent tries fast, deterministic keyword rules first; only when the rule signal is
genuinely weak does it fall through to an LLM call via OpenRouter (`shared/llm_client.py`).
This keeps the system fully functional — same answers as before — with `OPENROUTER_API_KEY`
unset, and adds real capability when it's configured:

- **Router** classifies with keyword scoring and computes a real confidence from the
  score margin; below a threshold, it asks the LLM for a second opinion. Business-rule
  priority floors (e.g. Trading/Risk/Executive → at least HIGH) apply to the LLM's
  suggestion exactly as they do to the rule engine's own default — that's policy, not
  something to infer.
- **Technical agent** retrieves the best-matching knowledge base articles, then asks the
  LLM to write a grounded answer citing only those articles (RAG) — it's instructed to
  escalate rather than invent steps the KB doesn't support. If the LLM is unavailable, it
  falls back to serving the top article directly, with that article's own escalation flag
  — the same behavior the agent had before the LLM existed.
- **Account agent** uses rule keywords to detect add/remove/permission requests (and
  always extracts a literal email via regex — no LLM needed for that); only a request with
  no rule match at all goes to the LLM for intent extraction. Execution is always
  deterministic — capacity checks and provisioning run against `TableauBackend`, never the
  model's judgment.

## 🧑‍💼 Human Review

Anything an agent escalates lands in the **Human Review** tab, not a fire-and-forget queue.
For each pending escalation you see the full ticket context and the agent's draft response,
and can **Approve & Send** it as-is, **edit it** before sending, or **Reject** it (leaving the
ticket escalated for manual handling outside the system). Every decision is recorded as a
`human_review` ticket event — who reviewed it, what they decided, and the final text — so
there's a full audit trail from ticket submission through resolution.

## 🔒 Hardening

- **Service auth** — a shared-secret `X-Internal-Token` header, checked by a FastAPI
  dependency (`shared/auth.py`) on every agent's business endpoint (`/health` stays open
  for infra healthchecks). Opt-in via `INTERNAL_API_TOKEN`; unset means auth is disabled,
  so local dev and the test suite don't need to know about it.
- **Structured logging** — every log line is a JSON object (`shared/logging_config.py`),
  and every log emitted while handling a ticket carries that ticket's ID, so you can grep
  one ticket's full story across the router, technical/account agent, and orchestrator logs.
- **LLM availability tracking** — every `complete_json()` attempt (success or failure, and
  why) is logged to the database and surfaced on the System Architecture tab, so you can
  see exactly how often the LLM layer is actually available versus falling back to rules.

## 📊 Demo Scenarios

- **🚨 Critical**: Trading dashboard outages (2-second resolution)
- **👥 Account**: New user provisioning with license checking
- **🔍 Technical**: Database connectivity troubleshooting
- **📈 Training**: Chart creation guidance and resources

## 🛠️ Technology Stack

- **Backend**: FastAPI, Python 3.9+, Pydantic data models
- **Persistence**: PostgreSQL (SQLite for local dev), SQLAlchemy ORM
- **Intelligence**: Rule-based classification + OpenRouter LLM fallback (RAG for technical support)
- **Communication**: HTTP REST APIs, Redis message queuing
- **Security & Observability**: Shared-secret internal auth, structured JSON logging, LLM availability tracking
- **Frontend**: Streamlit interactive interface
- **Deployment**: Docker containers, scalable architecture
- **CI**: GitHub Actions (lint, tests, Docker build)

## 📈 Business Impact

- **87% automated resolution** rate for common issues
- **< 2 second average** response time across all agents
- **24/7 availability** without human intervention required
- **Contextual responses** based on department and user role

## 🎥 Live Demo

Access the interactive demo at `http://localhost:8501` to see agents collaborating in real-time to solve enterprise Tableau support scenarios.

## 🗺️ Roadmap

See [`docs/UPGRADE_PLAN.md`](docs/UPGRADE_PLAN.md) for the phased plan to turn this from a
demo into a working system. Done so far: a single orchestration path with env-driven config
and real failure handling (Phase 0); persistence — tickets, departments/users/licenses, and
the technical knowledge base now live in a database instead of Python literals, with a real
(simulated) Tableau backend and a dashboard that reports actual numbers (Phase 1); hybrid
intelligence — rules stay the fast/free default, an OpenRouter LLM handles ambiguous
classification and RAG-based technical responses when configured (Phase 2); a closed
escalation loop — a Human Review tab with Approve/Edit/Reject actions and a full audit trail,
so nothing an agent escalates is ever fire-and-forget (Phase 3); and hardening — internal
service auth, structured JSON logging with ticket correlation, typed LLM error handling with
availability tracking, and CI (Phase 4). Still ahead: cloud deployment.

---
*Built as a portfolio demonstration of multi-agent AI coordination and enterprise software architecture.*
