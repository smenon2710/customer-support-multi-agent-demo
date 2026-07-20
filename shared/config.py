import os

ROUTER_URL = os.environ.get("ROUTER_URL", "http://localhost:8001")
TECHNICAL_URL = os.environ.get("TECHNICAL_URL", "http://localhost:8002")
ACCOUNT_URL = os.environ.get("ACCOUNT_URL", "http://localhost:8003")

AGENT_ENDPOINTS = {
    "router": ROUTER_URL,
    "technical": TECHNICAL_URL,
    "account": ACCOUNT_URL,
}

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./support.db")

# Unused until the hybrid rules+LLM pipeline lands (see docs/UPGRADE_PLAN.md Phase 2).
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
CLASSIFIER_MODEL = os.environ.get("CLASSIFIER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
GENERATION_MODEL = os.environ.get("GENERATION_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
