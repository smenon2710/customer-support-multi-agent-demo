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

## Follow-up 3: email autocomplete + self-learning subject ranking

- **Email field** changed from free text to `st.selectbox` populated from every active
  seeded user (`_user_directory()`, `st.cache_data(ttl=300)`) — since every option is drawn
  from the same directory used to derive department, every selection is by construction a
  real, found user. The department pills fallback from Follow-up 2 was removed entirely
  (no longer reachable — an unfound email can no longer be entered). Streamlit's selectbox
  supports typing to filter, which covers the "autocomplete" ask without a custom component.
- **Subject dropdown is now frequency-ranked** (`_top_subjects()`, also cached 300s):
  `GROUP BY subject, COUNT(*)` over the real `tickets` table, blended with the same static
  baseline list from Follow-up 1 (baseline entries act as a cold-start placeholder with an
  implicit count of 0, so the list is never empty before real history accumulates). Verified
  this is genuinely self-learning, not just plumbing: subjects from earlier test tickets
  submitted this session (e.g. "Dashboard performance issue", "Dashboard timeout") already
  rank above the static baseline in a live `AppTest` run against the real Postgres backend.
  Top-10 limit, "Other" always appended after (not counted against the limit).
- **Known trade-off, not a bug**: both caches have a 5-minute TTL, so a subject submitted
  just now can take up to 5 minutes to affect the ranking other users see — deliberate,
  to avoid re-aggregating ~3,800 users / the whole tickets table on every Streamlit rerun
  (which happens on every single widget interaction, not just page load).

## Follow-up 3b: cache resolutions to cut LLM calls (done)

Requested alongside Follow-up 3, and a real change to core agent logic, not just the
frontend — confirmed scope with the user first (technical agent only; trust a cached
resolution on the first repeat, no occurrence threshold) before implementing.

- New `agents/technical_agent/resolution_cache.py`: `find_cached_resolution(db, subject)`
  looks for the most recent already-processed ticket (`tickets.resolution IS NOT NULL`)
  with the exact same `subject`, ordered by `resolved_at` desc. No new table — reuses
  `tickets.subject`/`tickets.resolution`, which were already being persisted for every
  ticket. Returns `None` on no match.
- Wired into `agents/technical_agent/main.py`'s `/handle_ticket`, checked *before*
  `TechnicalKnowledgeBase.retrieve()`/`generate_response()` — a hit skips both KB retrieval
  and the LLM call, tagged `method="cache"` (alongside the existing `"rules"`/`"llm"`).
  A hit replays whatever the prior ticket's outcome was, escalation included — deliberate:
  if a subject consistently has no KB coverage, immediately escalating repeats is correct,
  not a bug; re-attempting every time would defeat the point of caching.
- Cache key is `subject` alone, not `subject + description` — the free-text description
  would rarely repeat verbatim across tickets, while subjects are now mostly drawn from
  the frequency-ranked dropdown (Follow-up 3), a small closed-ish set that actually repeats.
- Tests: `tests/test_resolution_cache.py` (direct unit tests — no match, exact match, a
  ticket with no resolution yet is correctly ignored, escalation outcomes replay too, most
  recent wins when multiple prior tickets share a subject) and a new test in
  `tests/test_technical_api.py` (`test_second_ticket_with_same_subject_uses_cache`,
  through the real FastAPI endpoint).
- Verified against the real Docker Compose backend, not just tests: submitted two tickets
  with the same subject but *deliberately unrelated descriptions* (the second one's
  description matched zero KB symptom keywords, which would have escalated with "I need to
  research this issue further" if processed fresh) — the second ticket returned the exact
  same resolution text as the first, and the logs confirmed `"Resolved ticket via rules"`
  then `"Resolved ticket via cache"`, proving the cache path was taken rather than a
  coincidence.
- `CLAUDE.md`'s Technical agent section updated to describe the cache-first flow.

## Follow-up 4: form reset + confirmation after submit

Identified as the top usability gap in a follow-up review: after submitting, the form kept
its old values with no signal it was ready for a new ticket — a real user could be unsure
whether to resubmit, risking an accidental duplicate.

- `Subject`, `description`, and the "Other" text field are now keyed widgets
  (`ticket_subject_choice`, `ticket_description`, `ticket_other_subject`) and get reset to
  their defaults after a successful submission, plus an `st.success("Ticket submitted — form
  is reset and ready for a new one.")` confirmation.
- **A real Streamlit constraint discovered during verification, not assumed**: you cannot
  write to `st.session_state[key]` for a key that already backs a widget instantiated
  *earlier in the same script run* — doing so immediately after `orchestrator.process_support_ticket()`
  raised `StreamlitAPIException` in a live `AppTest` run against the real backend. Fixed by
  setting a `_reset_ticket_form` flag before `st.rerun()` instead, and applying the actual
  resets at the very top of `live_demo_interface()` on the *next* run, before any widget in
  the function has been instantiated.
- Email and department are deliberately not reset — a user submitting multiple tickets is
  likely doing so on behalf of the same identity.
- Verified via `AppTest` against the real backend: changed the description to custom text,
  submitted, and confirmed the description field cleared, the subject dropdown reset to the
  top-ranked choice, the confirmation message appeared, and the result still rendered
  correctly in the right-hand column — all with no exception.
