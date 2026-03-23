---
name: gen-mcp-tool
description: Generate MCP (Model Context Protocol) server tools, resources, and prompts for the NeuralDB monitoring system. Creates MCP tools that allow external AI assistants (Claude, Copilot) to query metrics, analyze queries, run diagnostics, and manage playbooks.
argument-hint: "[tool-name] [type: tool|resource|prompt]"
allowed-tools: Read, Write, Glob, Grep, Edit
---

# Generate MCP Tool

## Arguments
- Tool name: $0
- MCP type: $1 (default: tool)

## Reference
- Read `ai-db-monitor-architecture-spec-v3.md` for MCP Server spec

## Output Files
```
backend/app/mcp/
├── server.py                    # MCP server setup
├── tools/{tool_name}.py         # Tool implementation
├── resources/{resource_name}.py # Resource provider
└── prompts/{prompt_name}.py     # Prompt template
```

## MCP Server Setup (Python)
```python
from mcp.server import Server
from mcp.server.stdio import stdio_server

app = Server("neuraldb-mcp")

@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="query_metrics",
            description="Query database performance metrics",
            inputSchema={...}
        ),
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "query_metrics":
        return await query_metrics(**arguments)
```

## MCP Tools to Implement
| Tool | Description | Input |
|------|-------------|-------|
| query_metrics | Query real-time DB metrics | instance_id, metric_type, time_range |
| get_active_sessions | Get current active sessions (ASH) | instance_id, min_duration |
| analyze_query | Analyze SQL query execution plan | instance_id, sql_query |
| run_diagnosis | Trigger AI diagnosis on an incident | incident_id |
| list_incidents | List active incidents | severity, status, limit |
| get_topology | Get full-stack topology map | cluster_id |
| execute_playbook | Run a remediation playbook | playbook_id, instance_id, dry_run |
| nl2sql | Convert natural language to SQL | question, instance_id |

## MCP Resources
| Resource | URI | Description |
|----------|-----|-------------|
| instances | neuraldb://instances | List monitored DB instances |
| metrics/{id} | neuraldb://metrics/{id} | Instance metrics snapshot |
| topology | neuraldb://topology | Current topology graph |
| playbooks | neuraldb://playbooks | Available playbooks |

## Rules
- All tools return JSON-serializable results
- Include `description` for LLM understanding
- `inputSchema` follows JSON Schema spec
- Read-only tools by default (remediation requires `dry_run` flag)
- Rate limiting on expensive operations
- Auth via MCP auth token
- Log all tool invocations to audit log
