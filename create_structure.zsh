#!/bin/zsh

# Create directories
mkdir -p agents/router_agent
mkdir -p agents/technical_agent
mkdir -p agents/account_agent
mkdir -p shared
mkdir -p data
mkdir -p demo

# Create Python files
for file in \
  agents/__init__.py \
  agents/router_agent/__init__.py \
  agents/router_agent/main.py \
  agents/router_agent/router_logic.py \
  agents/technical_agent/__init__.py \
  agents/technical_agent/main.py \
  agents/technical_agent/technical_kb.py \
  agents/account_agent/__init__.py \
  agents/account_agent/main.py \
  agents/account_agent/account_manager.py \
  shared/__init__.py \
  shared/message_queue.py \
  shared/models.py \
  shared/knowledge_base.py \
  demo/streamlit_interface.py
  do
    touch "$file"
done

# Create data files
for file in \
  data/mock_tickets.json \
  data/kb_articles.json \
  data/company_data.json
  do
    touch "$file"
done

# Create root-level files
for file in requirements.txt docker-compose.yml README.md
  do
    touch "$file"
done

echo "Directory structure created successfully!" 