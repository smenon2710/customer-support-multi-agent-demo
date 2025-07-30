import streamlit as st
import requests
import json
from datetime import datetime
import time
import uuid

# Configure page
st.set_page_config(
    page_title="Multi-Agent Tableau Support System",
    page_icon="🤖",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .agent-card {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid #ff6b6b;
    }
    .router-card { border-left-color: #4ecdc4; }
    .technical-card { border-left-color: #45b7d1; }
    .account-card { border-left-color: #96ceb4; }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 0.25rem;
        color: #155724;
    }
</style>
""", unsafe_allow_html=True)

def main():
    st.title("🤖 Multi-Agent Tableau Customer Support System")
    st.markdown("**Enterprise-Scale Support Automation for FinTech Analytics Corp**")
    
    # Sidebar configuration
    st.sidebar.header("System Configuration")
    st.sidebar.info("**Company**: FinTech Analytics Corp\n**Users**: 5,200+ Tableau users\n**Departments**: 8 business units")
    
    # Check agent status
    agent_status = check_agent_status()
    display_agent_status(agent_status)
    
    # Main interface tabs
    tab1, tab2, tab3 = st.tabs(["🎯 Live Demo", "📊 Predefined Scenarios", "🔧 System Architecture"])
    
    with tab1:
        live_demo_interface()
    
    with tab2:
        predefined_scenarios()
    
    with tab3:
        system_architecture()

def check_agent_status():
    """Check if all agents are running"""
    agents = {
        "Router Agent": "http://router-agent:8001",
        "Technical Agent": "http://technical-agent:8002", 
        "Account Agent": "http://account-agent:8003"
    }
    
    status = {}
    for name, url in agents.items():
        try:
            response = requests.get(f"{url}/docs", timeout=2)
            status[name] = "🟢 Online" if response.status_code == 200 else "🔴 Offline"
        except:
            status[name] = "🔴 Offline"
    
    return status

def display_agent_status(status):
    """Display agent status in sidebar"""
    st.sidebar.header("Agent Status")
    for agent, state in status.items():
        st.sidebar.markdown(f"**{agent}**: {state}")

def live_demo_interface():
    """Interactive demo interface"""
    st.header("🎯 Live Support Ticket Demo")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Submit Support Request")
        
        # User input form
        user_email = st.text_input("User Email", "john.analyst@fintechanalytics.com")
        department = st.selectbox("Department", 
            ["Trading", "Risk Management", "Compliance", "Marketing", "Operations", "Finance", "Executive"])
        subject = st.text_input("Subject", "Dashboard performance issue")
        description = st.text_area("Problem Description", 
            "My trading dashboard is loading slowly and showing outdated data during market hours.")
        
        if st.button("🚀 Submit Ticket", type="primary"):
            # Create ticket
            ticket = {
                "ticket_id": f"T{uuid.uuid4().hex[:6].upper()}",
                "user_email": user_email,
                "department": department,
                "subject": subject,
                "description": description,
                "created_at": datetime.now().isoformat(),
                "messages": []
            }
            
            # Process with orchestrator
            with st.spinner("🤖 Agents are collaborating to resolve your issue..."):
                result = process_ticket_with_orchestrator(ticket)
            
            # Store in session state for display
            st.session_state['last_result'] = result
    
    with col2:
        st.subheader("Agent Coordination Results")
        
        if 'last_result' in st.session_state:
            display_agent_conversation(st.session_state['last_result'])

def process_ticket_with_orchestrator(ticket):
    """Process ticket through the multi-agent system"""
    try:
        # Step 1: Route ticket
        routing_response = requests.post("http://router-agent:8001/route_ticket", json=ticket)
        routing_result = routing_response.json()
        
        # Step 2: Handle with appropriate agent
        assigned_agent = routing_result["assigned_agent"]
        agent_urls = {"technical_agent": "http://technical-agent:8002", "account_agent": "http://account-agent:8003"}
        
        handling_response = requests.post(f"{agent_urls[assigned_agent]}/handle_ticket", 
                                        json={"ticket": ticket})
        handling_result = handling_response.json()
        
        return {
            "status": "completed",
            "ticket_id": ticket["ticket_id"],
            "routing": routing_result,
            "handling": handling_result
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "ticket_id": ticket["ticket_id"]
        }

def display_agent_conversation(result):
    """Display the agent conversation flow"""
    if result["status"] == "error":
        st.error(f"❌ Error: {result['error']}")
        return
    
    # Routing step
    st.markdown('<div class="agent-card router-card">', unsafe_allow_html=True)
    st.markdown("**🧭 Router Agent**")
    routing = result["routing"]
    st.write(f"**Classification**: {routing['category']} | **Priority**: {routing['priority']}")
    st.write(f"**Decision**: Routed to {routing['assigned_agent']}")
    st.write(f"**Confidence**: {routing['routing_message']['confidence_score']:.0%}")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Handling step
    agent_type = result["routing"]["assigned_agent"]
    card_class = "technical-card" if "technical" in agent_type else "account-card"
    agent_icon = "🔧" if "technical" in agent_type else "👤"
    
    st.markdown(f'<div class="agent-card {card_class}">', unsafe_allow_html=True)
    st.markdown(f"**{agent_icon} {agent_type.replace('_', ' ').title()}**")
    
    handling = result["handling"]
    response_content = handling["response"]["content"]
    st.markdown(response_content)
    
    if handling.get("escalated"):
        st.warning("⚠️ **Escalated**: This ticket requires additional specialist review.")
    else:
        st.success("✅ **Resolved**: Solution provided by AI agent.")
    
    st.write(f"**Confidence**: {handling['response']['confidence_score']:.0%}")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Final result
    st.markdown('<div class="success-box">', unsafe_allow_html=True)
    st.markdown(f"**✅ Ticket {result['ticket_id']} processed successfully!**")
    st.markdown("**Resolution Time**: < 2 seconds | **Agent Coordination**: Successful")
    st.markdown('</div>', unsafe_allow_html=True)

def predefined_scenarios():
    """Showcase predefined scenarios"""
    st.header("📊 Predefined Demo Scenarios")
    
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
                    ticket = {
                        "ticket_id": f"DEMO{i+1:03d}",
                        "user_email": f"user{i+1}@fintechanalytics.com",
                        "department": scenario['department'],
                        "subject": scenario['subject'],
                        "description": scenario['description'],
                        "created_at": datetime.now().isoformat(),
                        "messages": []
                    }
                    
                    with st.spinner("🤖 Processing scenario..."):
                        result = process_ticket_with_orchestrator(ticket)
                    
                    st.session_state[f'scenario_result_{i}'] = result
            
            # Show result if available
            if f'scenario_result_{i}' in st.session_state:
                st.markdown("**🤖 Agent Response:**")
                display_agent_conversation(st.session_state[f'scenario_result_{i}'])

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
        
        # Mock metrics for demonstration
        metrics_col1, metrics_col2 = st.columns(2)
        
        with metrics_col1:
            st.metric("Total Users Supported", "5,200+", "+12%")
            st.metric("Average Response Time", "< 2 sec", "-45%")
            st.metric("Resolution Rate", "87%", "+23%")
        
        with metrics_col2:
            st.metric("Agent Uptime", "99.8%", "+0.3%")
            st.metric("Escalation Rate", "13%", "-8%")
            st.metric("User Satisfaction", "4.6/5", "+0.4")
    
    st.subheader("🔄 Communication Flow")
    st.markdown("""
    ```
    User Request → Router Agent → Classification & Routing
                      ↓
    Technical Agent ←--→ Account Agent
                      ↓
    Specialized Response → User Resolution
                      ↓
    Escalation (if needed) → Human Specialist
    ```
    """)
    
    st.subheader("🛠️ Technology Stack")
    tech_col1, tech_col2, tech_col3 = st.columns(3)
    
    with tech_col1:
        st.markdown("""
        **Backend**
        - FastAPI (Agent APIs)
        - Python 3.9+
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
        - SQLite Database
        - Scalable Architecture
        """)

if __name__ == "__main__":
    main()
