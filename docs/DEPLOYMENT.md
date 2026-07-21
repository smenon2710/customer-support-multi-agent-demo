# Deploying for $0

This deploys the system across three free platforms, none of which require a credit
card: **Neon** (Postgres), **Render** (the three agent services), and **Streamlit
Community Cloud** (the demo UI). Because no platform in this stack has a payment method
on file, there is no mechanism by which any of them could ever charge you — the
strongest guarantee available short of not using cloud services at all.

This is separate from `docker compose up` (README, local/self-hosted) — use this guide
only if you want a public URL without running anything on your own machine.

**Trade-offs, so there are no surprises:**
- Render's free web services sleep after ~15 minutes of no traffic. The first request
  after a quiet period wakes the service back up, which takes anywhere from a few
  seconds to about a minute. This is fine for a portfolio demo; it is not a experience
  for real users.
- All three platforms' free-tier terms can change, and I can't verify them at the moment
  you read this. If any signup step asks for payment details, that's a signal the free
  tier has changed since this was written — stop and reassess before continuing.
- Free-tier quotas (Neon storage, Render build minutes, Streamlit Cloud resource limits)
  are generous for a low-traffic demo but are not unlimited. Check each platform's
  current published limits if you expect meaningful traffic.

## What you'll need

- This repo pushed to GitHub (already true).
- A GitHub account (to authorize Render and Streamlit Cloud — both deploy directly from
  a repo, no separate file uploads).
- About 20 minutes.

---

## 1. Postgres — Neon

1. Sign up at [neon.tech](https://neon.tech) with GitHub (no card required for the free tier).
2. Create a project. Neon gives you a connection string that looks like:
   ```
   postgresql://user:password@ep-example-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
   Copy it — this is your `DATABASE_URL`. SQLAlchemy/psycopg2 (already in `requirements.txt`)
   handles the `sslmode=require` query param natively; no code changes needed.
3. **Seed it once, from your own machine** (Neon's free tier has no built-in job runner,
   so this step is manual):
   ```sh
   pip install -r requirements.txt
   DATABASE_URL="<your Neon connection string>" python -m scripts.seed_db
   ```
   This creates the schema and populates departments/users/KB articles. It's idempotent —
   safe to re-run, it no-ops if already seeded (see `scripts/seed_db.py`).

## 2. The three agents — Render

1. Sign up at [render.com](https://render.com) with GitHub (no card required for free
   web services).
2. **New → Blueprint**, connect this repo. Render reads `render.yaml` at the repo root
   and proposes three services: `tableau-router-agent`, `tableau-technical-agent`,
   `tableau-account-agent`. Approve — it builds each from its own Dockerfile.
3. For **each of the three services**, open its Environment tab and set:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | The Neon connection string from step 1 (same value on all three) |
   | `INTERNAL_API_TOKEN` | A random string, e.g. `openssl rand -hex 32` — **the same value on all three services** |
   | `REDIS_URL` | Leave unset (see "About Redis" below) |
   | `OPENROUTER_API_KEY` | Optional — leave unset for rules-only mode, or set to enable the LLM layer (see README's Hybrid Intelligence section) |
   | `CLASSIFIER_MODEL`, `GENERATION_MODEL` | Optional — only needed if overriding the defaults |

   Saving env vars triggers a redeploy. Render injects `PORT` automatically; each
   agent's `main.py` already binds to it (falling back to its fixed port for local/Docker use).
4. Once all three are live, note their public URLs from the Render dashboard, e.g.:
   ```
   https://tableau-router-agent.onrender.com
   https://tableau-technical-agent.onrender.com
   https://tableau-account-agent.onrender.com
   ```
   Verify each with `curl https://<service>.onrender.com/health` — expect
   `{"status": "ok", ...}` (or `"degraded"` if you skipped Redis, which is expected —
   see below).

**About Redis:** the system was built from the start to tolerate Redis being
unreachable — `MessageQueue` logs a warning and every agent's `/health` reports
`degraded`, but ticket routing, resolution, and escalation all keep working because the
database (not Redis) has been the source of truth since Phase 1. For a $0 deployment,
the simplest choice is to skip Redis entirely — leave `REDIS_URL` unset. If you want
`/health` to report fully healthy, [Upstash](https://upstash.com) has a genuinely free
serverless Redis tier (no card required); set `REDIS_URL` to the connection string it
gives you on all three Render services.

## 3. The demo UI — Streamlit Community Cloud

1. Sign up at [share.streamlit.io](https://share.streamlit.io) with GitHub (no card required).
2. **New app**, pick this repo, branch `main`, main file path `demo/streamlit_interface.py`.
3. Before or after the first deploy, open **Settings → Secrets** and paste (TOML format):
   ```toml
   ROUTER_URL = "https://tableau-router-agent.onrender.com"
   TECHNICAL_URL = "https://tableau-technical-agent.onrender.com"
   ACCOUNT_URL = "https://tableau-account-agent.onrender.com"
   DATABASE_URL = "postgresql://user:password@ep-example-123456.us-east-2.aws.neon.tech/neondb?sslmode=require"
   INTERNAL_API_TOKEN = "<the same random string you set on the three Render services>"
   ```
   `demo/streamlit_interface.py` bridges `st.secrets` into `os.environ` at startup, so
   `shared/config.py`'s ordinary `os.environ.get(...)` calls pick these up unchanged —
   the same code path used locally and in Docker.
4. Save — Streamlit Cloud redeploys automatically. Open the app URL it gives you.

**If the build fails trying to compile something from source** (`pg_config executable
not found`, `headers or library files could not be found for zlib`, a Rust/`maturin`
build error, etc.): Streamlit Cloud provisions whatever current Python release it wants
(observed jumping straight to Python 3.14 with no way to pin it — `.python-version` is
not honored by its build tool), ignoring what's pinned locally or in CI. `requirements.txt`
is pinned to versions confirmed to ship prebuilt wheels for that Python — this took two
rounds of fixes during initial testing: first `psycopg2-binary` (2.9.9, from 2023, had no
`cp314` wheel), then `pydantic`/`pydantic-core` and `streamlit`'s own `pillow` dependency
(also stuck on 2023-era pins with no `cp314` wheel), which cascaded into needing `fastapi`
and `uvicorn` bumped too since `fastapi>=0.129` requires Python >=3.10 and pulls in a newer
`starlette` that only newer `streamlit` versions tolerate. If this happens again on a
future, even-newer Python: check the failing package's PyPI file list for a release with
a `cp3<NN>` wheel matching whatever Python Streamlit Cloud is running, bump the pin, then
re-resolve the whole set locally (`pip install` the unpinned packages in a clean venv,
`pip freeze` the result, verify with `pytest`/`docker compose build` before pushing) rather
than bumping one package at a time against Streamlit Cloud's build queue.

## 4. Verify

- Submit a ticket via the **Live Demo** tab. Expect it to route and resolve — if a Render
  service was asleep, the first request will be slow (see trade-offs above); it'll be
  fast on subsequent tickets.
- Check the **System Architecture** tab's metrics — they should reflect the ticket you
  just submitted (real numbers from Neon, same as local).
- If something's stuck: check each Render service's `/health` endpoint, and check that
  service's Logs tab in the Render dashboard (structured JSON logs — see
  `shared/logging_config.py` — make it easy to find the failing request by `ticket_id`).

## Updating the deployment

All three platforms auto-deploy on push to `main` (Render and Streamlit Cloud both watch
the branch you connected). No manual redeploy step for code changes — only env var
changes require the manual step described above.
