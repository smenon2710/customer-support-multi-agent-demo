# UI/UX Improvement Plan

Status tracker for the UI/UX pass on `demo/streamlit_interface.py` (and the small
`shared/orchestrator.py` change P0 requires). Written so this can be picked up in a
fresh session if implementation stops partway through — check the Status column below
before assuming something is or isn't done.

**P0 and P1 are complete and verified as of this writing** (see Verification checklist
— all boxes checked). P2 remains deferred; see that section before starting it.

**Decisions locked in before implementation started** (see conversation for full
rationale — don't re-litigate these without asking):
- Goal: both portfolio polish and real usability, weighted equally.
- Scope: staying within the current single-page 4-tab layout — no multi-page
  (`st.navigation`/`st.Page`) restructuring. Revisit only if the app grows substantially.
- Human Review tab: staying open, no passcode gate. Not in this plan.
- Cold-start handling: explicitly high priority (P0).
- P2 is intentionally deferred — implement P0 and P1 only for now.

## P0 — Reliability signaling (cold starts) + stale copy

| # | Item | Status | File(s) |
|---|---|---|---|
| 1 | Bound the orchestrator's inter-agent HTTP calls with a timeout, and turn a connection/timeout failure into a friendly "agents may be waking up from idle, try again" message instead of a raw exception string | **Done** | `shared/orchestrator.py` |
| 2 | Parallelize `check_agent_status()`'s 3 sequential health checks (currently up to 6s added to *every* Streamlit rerun, not just first load) | **Done** | `demo/streamlit_interface.py` |
| 3 | Add a prominent banner (not just a sidebar dot) when any agent is offline, explaining free-tier cold starts | **Done** | `demo/streamlit_interface.py` |
| 4 | Fix sidebar's hardcoded "5,200+ users" / "8 business units" — real seeded data is 3,870 users / 7 departments (verified against `scripts/seed_db.py`); pull the real number from `SimulatedTableauBackend.get_site_status()` instead of hardcoding, so it can never drift from the System Architecture tab's real metric again | **Done** | `demo/streamlit_interface.py` |
| 5 | Fix stale "Python 3.9+" in the System Architecture tab's tech-stack panel (README was already fixed to 3.11+ in the deployment-debugging session; this in-app copy was missed) | **Done** | `demo/streamlit_interface.py` |

## P1 — Visual modernization + first impression

| # | Item | Status | File(s) |
|---|---|---|---|
| 6 | Replace the `unsafe_allow_html` agent-card `<div>` string-concatenation hack with native `st.container(border=True)` (safe since Streamlit 1.59.2, which we're already pinned to) | **Done** | `demo/streamlit_interface.py` |
| 7 | Replace the hardcoded light-mode-only `.success-box` CSS (`background-color: #d4edda`) with native `st.success()` — the custom CSS renders wrong in dark mode since it never adapts | **Done** | `demo/streamlit_interface.py` |
| 8 | Trim emoji density in body copy — keep emoji on tab labels/section headers (aid scannability) but remove from inline sentences where they're just noise | **Done** | `demo/streamlit_interface.py` |
| 9 | Add a short intro block above the tabs framing what the project demonstrates (multi-agent coordination, hybrid rules+LLM, real persistence) — this context currently only exists buried in the last tab | **Done** | `demo/streamlit_interface.py` |

## Verification checklist (run after implementation, before calling this done)

- [x] `pytest` — full suite still passes (77 passed, 1 pre-existing unrelated `StarletteDeprecationWarning`)
- [x] `ruff check .` — clean
- [x] Browser-equivalent verification via Streamlit's own `AppTest` harness (`streamlit.testing.v1.AppTest`), run against the real dockerized agents + seeded Postgres (no mocks): confirmed no exceptions, sidebar shows the real `3,870 Tableau users` / `7 business units` (matches seed data, no longer the stale `5,200+` / `8`), a real ticket submit round-trips through the router → technical agent and renders inside the new `st.container(border=True)` cards with no raw HTML, and — after deliberately stopping `technical-agent` — the cold-start banner appeared with the expected wording and disappeared again once the agent was restarted and re-checked.
- [x] `CLAUDE.md` updated — the Request flow section now documents `AGENT_REQUEST_TIMEOUT_SECONDS` and the cold-start-specific friendly error message.

## P2 — Deferred (not started, do not implement without explicit go-ahead)

- Defensive access in `display_agent_conversation()` (currently direct nested-dict indexing with no guard against an unexpected response shape)
- De-duplicate ticket-creation/display logic shared between `live_demo_interface()` and `predefined_scenarios()`
- Lightweight ticket history in the Live Demo tab (currently only the single last result is kept in session state)

## Follow-up: theming pass (done, separate from P0/P1 above)

Requested afterward, not part of the original P0/P1 scope, but recorded here for the same
resumability reason:

- Added `.streamlit/config.toml` with a single `[theme] primaryColor` — deliberately not
  setting `backgroundColor`/`textColor`/`base`, so the app keeps following the viewer's
  light/dark preference automatically (the project previously had zero theme config at all).
- Swapped the Live Demo tab's department `st.selectbox` for `st.pills` (`required=True`,
  `default="Trading"` — preserves the old "always has a value" behavior).
- Swapped the Router Agent card's plain "Classification: X | Priority: Y" text for
  `st.badge` elements (priority color-coded: critical=red, high=orange, medium=blue,
  low=gray).
- Verified via `streamlit.testing.v1.AppTest` against the real Docker Compose backend:
  no exceptions, pills widget defaults and submits correctly, and badge markdown
  (`:blue-badge[...]`, `:red-badge[...]`) confirmed rendering with correct label/color by
  walking the raw element proto tree (AppTest has no first-class `.badge` accessor, unlike
  `.success`/`.warning`/`.button`/`.pills`).

## Follow-up 2: "make it look like a real tool, not a demo"

- **User email → directory lookup**: `_lookup_user_department()` queries the real seeded
  `users` table (`shared.db.models.User`, joined to `Department`) by email. If found, the
  department is derived and shown read-only (`✓ Found in directory — Department: **X**`)
  instead of asking a known employee to self-report it. Only falls back to the manual
  `st.pills` department selector when the email isn't found. The form's default email value
  is no longer a hardcoded literal — `_example_user_email()` looks up a real seeded user at
  render time, since `scripts/seed_db.py`'s Faker-generated emails aren't deterministic
  across seed runs, so a hardcoded string would eventually point at a nonexistent user.
- **Subject** changed from free text to a dropdown of 7 common issues plus "Other" at the
  end; selecting "Other" reveals a second text input ("Briefly describe your issue") for
  the ticket's actual subject.
- Removed all user-facing "Demo" wording: tab label ("Live Demo" → "Submit a Ticket"),
  the Live Demo tab's header ("Live Support Ticket Demo" → "Submit a Support Ticket"), and
  the Predefined Scenarios tab's header ("Predefined Demo Scenarios" → "Predefined
  Scenarios", matching its already-Demo-free tab label). The "Predefined Scenarios" tab
  itself was kept (not asked to be removed) — only the literal word "Demo" was targeted.
- Verified via `AppTest` against the real backend: default email resolves to a real seeded
  user and shows the found-in-directory caption; an unknown email correctly falls back to
  the manual department pills; selecting "Other" in the subject dropdown correctly reveals
  the extra text field; a full ticket submission with the looked-up department still routes
  and resolves end-to-end with no exceptions.
