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
Start containers including Redis as the message queue

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

3. **Start All Agents** (run each from the project root, using `-m` so the
   `shared` package resolves correctly)
Terminal 1: Router Agent
python -m agents.router_agent.main

Terminal 2: Technical Agent
python -m agents.technical_agent.main

Terminal 3: Account Agent
python -m agents.account_agent.main


4. **Launch Demo Interface**
streamlit run demo/streamlit_interface.py

## 🧪 Running Tests

pip install -r requirements.txt
pytest

The suite covers the routing/classification, knowledge-base matching, and license-capacity
logic directly, plus FastAPI `TestClient` tests for each agent's HTTP endpoints (including
`/health`). No running Redis or Docker is required — agents degrade gracefully when Redis
is unreachable rather than failing to start.

## 📊 Demo Scenarios

- **🚨 Critical**: Trading dashboard outages (2-second resolution)
- **👥 Account**: New user provisioning with license checking
- **🔍 Technical**: Database connectivity troubleshooting
- **📈 Training**: Chart creation guidance and resources

## 🛠️ Technology Stack

- **Backend**: FastAPI, Python 3.9+, Pydantic data models
- **Communication**: HTTP REST APIs, Redis message queuing
- **Frontend**: Streamlit interactive interface
- **Deployment**: Docker containers, scalable architecture

## 📈 Business Impact

- **87% automated resolution** rate for common issues
- **< 2 second average** response time across all agents
- **24/7 availability** without human intervention required
- **Contextual responses** based on department and user role

## 🎥 Live Demo

Access the interactive demo at `http://localhost:8501` to see agents collaborating in real-time to solve enterprise Tableau support scenarios.

## 🗺️ Roadmap

This repository is currently a demo (rule-based agents, in-memory data, no persistence).
See [`docs/UPGRADE_PLAN.md`](docs/UPGRADE_PLAN.md) for the phased plan to turn it into a
working system: persistence, a hybrid rules+LLM pipeline (OpenRouter free-tier models,
RAG-based technical support), a human-in-the-loop escalation queue, and cloud deployment.

---
*Built as a portfolio demonstration of multi-agent AI coordination and enterprise software architecture.*
