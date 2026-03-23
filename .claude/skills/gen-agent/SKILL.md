---
name: gen-agent
description: Generate AI agent code using CrewAI/LangGraph for the multi-agent DB monitoring system. Creates agents for anomaly detection, RCA, auto-tuning, playbook generation, and NL2SQL based on the 5-level Adaptive Autonomy model.
argument-hint: "[agent-name] [autonomy-level: 1-5]"
allowed-tools: Read, Write, Glob, Grep, Edit, Bash
---

# Generate AI Agent

You are generating an AI agent for the **NeuralDB** multi-agent system.

## Arguments
- Agent name: $0
- Autonomy level: $1 (default: 3)

## Architecture Reference
Read `ai-db-monitor-architecture-spec-v3.md` for:
- Multi-agent architecture (CrewAI + LangGraph)
- MCP (Model Context Protocol) server implementation
- A2A (Agent-to-Agent) protocol integration
- 5-level Adaptive Autonomy model

## Autonomy Levels
| Level | Mode | Description |
|-------|------|-------------|
| 1 | Manual | Alert only, human executes all actions |
| 2 | Suggestion | AI suggests, human approves each action |
| 3 | Approved Execution | AI executes pre-approved playbooks |
| 4 | Supervised Autonomous | AI acts autonomously, human monitors |
| 5 | Full Autonomous | AI handles everything, escalates edge cases |

## Agent Types

| Agent | Role | Frameworks |
|-------|------|-----------|
| anomaly_detector | Detect anomalies using STL + Isolation Forest | scikit-learn, Prophet |
| rca_analyzer | Root cause analysis with topology awareness | LangGraph, RAG |
| auto_tuner | Index/query/parameter optimization | LangChain, SQLAlchemy |
| playbook_generator | Auto-generate YAML playbooks from incidents | CrewAI, LangChain |
| nl2sql_agent | Natural language to SQL translation | LangChain, vLLM |
| self_healing | Closed-loop remediation orchestrator | LangGraph, CrewAI |
| baseline_learner | Learn normal DB behavior patterns | Prophet, scikit-learn |
| schema_tracker | Track DDL changes and impact analysis | SQLAlchemy |
| collector_agent | 1-second metric collection orchestrator | Celery, asyncio |

## Agent File Structure
```
engine/app/agents/{agent_name}/
├── __init__.py
├── agent.py              # Main agent class
├── tools.py              # Agent tools (MCP tools)
├── prompts.py            # LLM prompts/templates
├── state.py              # LangGraph state definition
├── config.py             # Agent configuration
└── tests/
    └── test_{agent_name}.py
```

## Code Standards
- Python 3.11+ with full type hints
- Async/await for I/O operations
- Pydantic v2 for data validation
- Structured logging with OpenTelemetry
- MCP tool registration for Claude/LLM integration
- A2A protocol for inter-agent communication
- All agents must respect the current autonomy level
- Audit log every action taken
