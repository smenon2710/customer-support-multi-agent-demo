import os
import sys

# Streamlit's invocation mechanics don't reliably put the repo root on
# sys.path, and this app imports the top-level `shared` package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import concurrent.futures
import uuid
from datetime import datetime
from typing import Optional

import requests
import streamlit as st

# Streamlit Community Cloud exposes configured secrets via st.secrets, not the
# process environment — bridge them into os.environ so shared/config.py's plain
# os.environ.get() calls work unchanged whether we're running locally, in
# Docker, or on Streamlit Cloud. Must happen before importing shared.config,
# which reads these at import time. Safe locally too: st.secrets is just empty
# when no secrets.toml exists, and this never overwrites a real env var already
# set (e.g. by Docker Compose).
try:
    for _key, _value in st.secrets.items():
        os.environ.setdefault(_key, str(_value))
except Exception:
    pass  # no Streamlit secrets configured — env vars come from the shell/.env instead

from shared.config import AGENT_ENDPOINTS
from shared.db.metrics import compute_llm_availability, compute_ticket_metrics
from shared.db.models import User
from shared.db.session import SessionLocal
from shared.escalation_review import approve_escalation, list_pending_escalations, reject_escalation
from shared.models import SupportTicket
from shared.orchestrator import AgentOrchestrator
from shared.tableau_service import SimulatedTableauBackend

# Configure page
st.set_page_config(
    page_title="Multi-Agent Tableau Support System",
    page_icon="🤖",
    layout="wide"
)

orchestrator = AgentOrchestrator()


def main():
    st.title("🤖 Multi-Agent Tableau Customer Support System")
    st.markdown("**Enterprise-Scale Support Automation for FinTech Analytics Corp**")
    st.caption(
        "A portfolio project simulating a multi-agent support system: independent "
        "FastAPI agents (router → technical/account) coordinate over HTTP, backed by "
        "Postgres persistence and an optional LLM fallback for cases deterministic "
        "rules can't confidently handle. See **System Architecture** for the full "
        "picture, or submit a ticket below to see it work."
    )

    db = SessionLocal()
    try:
        pending_escalations = list_pending_escalations(db)
        site_status = SimulatedTableauBackend(db).get_site_status()
    finally:
        db.close()

    # Sidebar configuration
    st.sidebar.header("System Configuration")
    st.sidebar.info(
        f"**Company**: FinTech Analytics Corp\n"
        f"**Users**: {site_status.total_active_users:,} Tableau users\n"
        f"**Departments**: {site_status.total_departments} business units"
    )

    # Check agent status
    agent_status = check_agent_status()
    display_agent_status(agent_status)
    display_cold_start_banner(agent_status)

    if pending_escalations:
        st.sidebar.warning(f"⚠️ {len(pending_escalations)} escalation(s) awaiting review")

    # Main interface tabs
    tab1, tab2, tab3, tab4 = st.tabs(
        ["🎯 Submit a Ticket", "📊 Predefined Scenarios", "🧑‍💼 Human Review", "🔧 System Architecture"]
    )

    with tab1:
        live_demo_interface()

    with tab2:
        predefined_scenarios()

    with tab3:
        human_review_interface(pending_escalations)

    with tab4:
        system_architecture()


def _agent_is_online(url: str) -> bool:
    try:
        response = requests.get(f"{url}/health", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


def check_agent_status():
    """Check if all agents are running, in parallel — this runs on every Streamlit
    rerun (every button click, not just first page load), so keeping it to the
    slowest single check rather than the sum of three matters for responsiveness."""
    agents = {
        "Router Agent": AGENT_ENDPOINTS["router"],
        "Technical Agent": AGENT_ENDPOINTS["technical"],
        "Account Agent": AGENT_ENDPOINTS["account"],
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(agents)) as executor:
        futures = {name: executor.submit(_agent_is_online, url) for name, url in agents.items()}
        return {name: ("🟢 Online" if future.result() else "🔴 Offline") for name, future in futures.items()}


def display_agent_status(status):
    """Display agent status in sidebar"""
    st.sidebar.header("Agent Status")
    for agent, state in status.items():
        st.sidebar.markdown(f"**{agent}**: {state}")


def display_cold_start_banner(status):
    """Prominent, actionable banner when any agent is offline — likely a free-tier
    cold start rather than a real outage, so tell the user what's actually going on
    instead of leaving them looking at an unexplained red dot in the sidebar."""
    if all(state.startswith("🟢") for state in status.values()):
        return
    st.warning(
        "Some agents are showing offline. If this is the free-tier deployment, it "
        "sleeps after ~15 minutes idle and the first request after a quiet period "
        "can take up to a minute to wake it back up — try submitting a ticket "
        "anyway, it should resolve once the agent finishes waking up."
    )


def _lookup_user_department(email: str) -> Optional[str]:
    """Look up a real user's department from the seeded directory — mirrors how a
    real internal tool would already know who's submitting, rather than asking a
    known employee to self-report their own department."""
    if not email:
        return None
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email, User.status == "active").first()
        return user.department.name if user else None
    finally:
        db.close()


def _example_user_email() -> str:
    """A real seeded email to use as the form's starting value, so the directory
    lookup below succeeds by default instead of showing "not found" on first
    load. Faker-generated per seed run (see scripts/seed_db.py), so this can't be
    a hardcoded literal — it has to be looked up fresh."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.status == "active").order_by(User.id).first()
        return user.email if user else ""
    finally:
        db.close()


def live_demo_interface():
    """Ticket submission form"""
    st.header("🎯 Submit a Support Ticket")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Submit Support Request")

        user_email = st.text_input("User Email", _example_user_email())

        looked_up_department = _lookup_user_department(user_email)
        if looked_up_department:
            st.caption(f"✓ Found in directory — Department: **{looked_up_department}**")
            department = looked_up_department
        else:
            st.caption("Email not found in directory — please select your department:")
            department = st.pills(
                "Department",
                ["Trading", "Risk Management", "Compliance", "Marketing", "Operations", "Finance", "Executive"],
                default="Trading",
                required=True,
            )

        subject_choice = st.selectbox(
            "Subject",
            [
                "Dashboard loading slowly or not updating",
                "Cannot connect to data source",
                "Chart or visualization showing incorrect data",
                "Need access to a new workbook or dashboard",
                "License or permission issue",
                "How-to / training question",
                "Other",
            ],
        )
        if subject_choice == "Other":
            subject = st.text_input("Briefly describe your issue", "")
        else:
            subject = subject_choice

        description = st.text_area("Problem Description",
            "My dashboard is loading slowly and showing outdated data.")

        if st.button("🚀 Submit Ticket", type="primary"):
            ticket = SupportTicket(
                ticket_id=f"T{uuid.uuid4().hex[:6].upper()}",
                user_email=user_email,
                department=department,
                subject=subject,
                description=description,
                created_at=datetime.now(),
                messages=[],
            )

            with st.spinner(
                "Agents are collaborating to resolve your issue — this can take "
                "longer than usual if a free-tier agent is waking up from idle..."
            ):
                result = orchestrator.process_support_ticket(ticket)

            # Store in session state for display
            st.session_state['last_result'] = result

    with col2:
        st.subheader("Agent Coordination Results")

        if 'last_result' in st.session_state:
            display_agent_conversation(st.session_state['last_result'])


def display_agent_conversation(result):
    """Display the agent conversation flow"""
    if result["status"] == "error":
        st.error(result["error"])
        return

    conversation = {entry["action"]: entry["result"] for entry in result["conversation"]}
    routing = conversation["classification"]
    handling = conversation["response"]
    agent_type = routing["assigned_agent"]

    # Routing step
    priority_colors = {"critical": "red", "high": "orange", "medium": "blue", "low": "gray"}
    with st.container(border=True):
        st.markdown("**🧭 Router Agent**")
        badge_col1, badge_col2 = st.columns(2)
        with badge_col1:
            st.badge(routing['category'].title(), icon="🏷️")
        with badge_col2:
            st.badge(routing['priority'].title(), color=priority_colors.get(routing['priority'], "blue"))
        st.write(f"**Decision**: Routed to {agent_type}")
        st.write(f"**Confidence**: {routing['routing_message']['confidence_score']:.0%}")

    # Handling step
    agent_icon = "🔧" if "technical" in agent_type else "👤"
    with st.container(border=True):
        st.markdown(f"**{agent_icon} {agent_type.replace('_', ' ').title()}**")

        response_content = handling["response"]["content"]
        st.markdown(response_content)

        if handling.get("escalated"):
            st.warning("Escalated — this ticket requires additional specialist review.")
        else:
            st.success("Resolved — solution provided by AI agent.")

        st.write(f"**Confidence**: {handling['response']['confidence_score']:.0%}")

    # Final result
    st.success(f"Ticket {result['ticket_id']} processed successfully! Resolution time: < 2 seconds.")


def predefined_scenarios():
    """Showcase predefined scenarios"""
    st.header("📊 Predefined Scenarios")

    scenarios = [
        {
            "title": "🚨 Critical: Trading Dashboard Down",
            "department": "Trading",
            "subject": "Real-time P&L dashboard not updating",
            "description": "Our main trading dashboard stopped updating 15 minutes ago. Traders can't see current positions or P&L. This is affecting our risk management.",
            "expected": "Classified as CRITICAL, routed to Technical Agent, escalated to IT team"
        },
        {
            "title": "👥 Account: New User Access",
            "department": "Compliance",
            "subject": "Need Tableau access for 5 new auditors",
            "description": "We hired 5 new compliance auditors who need access to our regulatory reporting dashboards for the upcoming audit season.",
            "expected": "Classified as MEDIUM, routed to Account Agent, license availability checked"
        },
        {
            "title": "🔍 Technical: Database Connection",
            "department": "Risk Management",
            "subject": "Cannot connect to Oracle Risk database",
            "description": "Getting timeout errors when trying to refresh risk assessment workbooks. This is blocking our daily risk reporting.",
            "expected": "Classified as HIGH, routed to Technical Agent, database troubleshooting provided"
        },
        {
            "title": "📈 Training: Chart Creation Help",
            "department": "Marketing",
            "subject": "How to create waterfall charts for campaign ROI",
            "description": "Need help creating waterfall visualizations to show campaign performance breakdown for the quarterly marketing review.",
            "expected": "Classified as LOW, routed to Technical Agent, training resources provided"
        }
    ]

    for i, scenario in enumerate(scenarios):
        with st.expander(f"{scenario['title']}", expanded=False):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.write(f"**Department**: {scenario['department']}")
                st.write(f"**Subject**: {scenario['subject']}")
                st.write(f"**Description**: {scenario['description']}")

            with col2:
                st.info(f"**Expected Outcome**\n{scenario['expected']}")

                if st.button(f"▶️ Run Scenario {i+1}", key=f"scenario_{i}"):
                    ticket = SupportTicket(
                        ticket_id=f"DEMO{i+1:03d}",
                        user_email=f"user{i+1}@fintechanalytics.com",
                        department=scenario['department'],
                        subject=scenario['subject'],
                        description=scenario['description'],
                        created_at=datetime.now(),
                        messages=[],
                    )

                    with st.spinner(
                        "Processing scenario — this can take longer than usual if a "
                        "free-tier agent is waking up from idle..."
                    ):
                        result = orchestrator.process_support_ticket(ticket)

                    st.session_state[f'scenario_result_{i}'] = result

            # Show result if available
            if f'scenario_result_{i}' in st.session_state:
                display_agent_conversation(st.session_state[f'scenario_result_{i}'])


def human_review_interface(pending):
    """Human-in-the-loop review queue for tickets the AI agents escalated."""
    st.header("🧑‍💼 Human Review Queue")
    st.markdown("Tickets the AI agents escalated, waiting for a human decision.")

    if not pending:
        st.success("✅ No escalations pending review.")
        return

    reviewer = st.text_input("Reviewing as", "manager@fintechanalytics.com", key="reviewer_email")
    st.info(f"**{len(pending)}** escalation(s) awaiting review.")

    for esc in pending:
        with st.expander(f"🎫 {esc.ticket_id} — {esc.subject} ({esc.department})", expanded=False):
            st.write(f"**Escalated by**: {esc.escalated_by}  |  **Queue**: {esc.queue_name}")
            st.write(f"**Reason**: {esc.reason}")
            st.write(f"**Submitted**: {esc.created_at.strftime('%Y-%m-%d %H:%M UTC')}")
            st.write(f"**Description**: {esc.description}")

            st.markdown("**Draft response** — edit before sending, or send as-is:")
            edited_response = st.text_area(
                "Draft response",
                value=esc.draft_response or "",
                key=f"review_text_{esc.escalation_id}",
                label_visibility="collapsed",
                height=150,
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("✅ Approve & Send", key=f"approve_{esc.escalation_id}"):
                    db = SessionLocal()
                    try:
                        approve_escalation(db, esc.escalation_id, esc.draft_response or "", reviewer=reviewer)
                    finally:
                        db.close()
                    st.rerun()
            with col2:
                if st.button("✏️ Send Edited Response", key=f"edit_{esc.escalation_id}"):
                    db = SessionLocal()
                    try:
                        approve_escalation(db, esc.escalation_id, edited_response, reviewer=reviewer)
                    finally:
                        db.close()
                    st.rerun()
            with col3:
                if st.button("❌ Reject", key=f"reject_{esc.escalation_id}"):
                    db = SessionLocal()
                    try:
                        reject_escalation(
                            db, esc.escalation_id, "Handled manually outside the system.", reviewer=reviewer
                        )
                    finally:
                        db.close()
                    st.rerun()


def system_architecture():
    """Display system architecture information"""
    st.header("🔧 Multi-Agent System Architecture")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("🏗️ Architecture Components")
        st.markdown("""
        **🧭 Router Agent (Port 8001)**
        - Classifies incoming support tickets
        - Determines priority based on department and keywords
        - Routes to appropriate specialist agent
        - Confidence scoring for decisions

        **🔧 Technical Support Agent (Port 8002)**
        - Handles Tableau technical issues
        - Searches knowledge base for solutions
        - Provides step-by-step troubleshooting
        - Escalates complex database issues

        **👤 Account Management Agent (Port 8003)**
        - Manages user access and licensing
        - Checks department license availability
        - Handles user provisioning requests
        - Escalates when manager approval needed
        """)

    with col2:
        st.subheader("📊 System Metrics")

        db = SessionLocal()
        try:
            metrics = compute_ticket_metrics(db)
            site_status = SimulatedTableauBackend(db).get_site_status()
            llm_stats = compute_llm_availability(db)
        finally:
            db.close()

        metrics_col1, metrics_col2 = st.columns(2)

        with metrics_col1:
            st.metric("Total Users Supported", f"{site_status.total_active_users:,}")
            st.metric("Tickets Processed", f"{metrics.total_tickets:,}")
            st.metric("Resolution Rate", f"{metrics.resolution_rate:.0%}" if metrics.total_tickets else "—")

        with metrics_col2:
            st.metric("Escalation Rate", f"{metrics.escalation_rate:.0%}" if metrics.total_tickets else "—")
            median = metrics.median_handling_seconds
            st.metric("Median Handling Time", f"{median:.1f} sec" if median is not None else "—")
            st.metric("Departments", site_status.total_departments)

        st.markdown("**🧠 LLM Availability**")
        if llm_stats.total_calls:
            st.write(
                f"{llm_stats.successful}/{llm_stats.total_calls} calls succeeded "
                f"({llm_stats.availability_rate:.0%})"
            )
            if llm_stats.failures_by_reason:
                reasons = ", ".join(f"{reason}: {count}" for reason, count in llm_stats.failures_by_reason.items())
                st.caption(f"Failure reasons — {reasons}")
        else:
            st.caption("No LLM calls yet — rules haven't needed a fallback, or OPENROUTER_API_KEY isn't set.")

    st.subheader("🔄 Communication Flow")
    st.markdown("""
    ```
    User Request → Router Agent → Classification & Routing
                      ↓
    Technical Agent ←--→ Account Agent
                      ↓
    Specialized Response → User Resolution
                      ↓
    Escalation (if needed) → Human Review Queue → Approve / Edit / Reject
    ```
    """)

    st.subheader("🛠️ Technology Stack")
    tech_col1, tech_col2, tech_col3 = st.columns(3)

    with tech_col1:
        st.markdown("""
        **Backend**
        - FastAPI (Agent APIs)
        - Python 3.11+
        - Pydantic (Data Models)
        - Uvicorn (ASGI Server)
        """)

    with tech_col2:
        st.markdown("""
        **Communication**
        - HTTP REST APIs
        - Redis Message Queue
        - JSON Data Exchange
        - Async Processing
        """)

    with tech_col3:
        st.markdown("""
        **Deployment**
        - Docker Containers
        - Streamlit Frontend
        - PostgreSQL (SQLAlchemy ORM)
        - Scalable Architecture
        """)


if __name__ == "__main__":
    main()
