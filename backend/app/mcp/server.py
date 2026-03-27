# Spec: PROTO-MCP-001, FR-ALERT-004
"""NeuralDB MCP Server — exposes DB monitoring data to external AI tools.

Provides:
- Resources: instances, incidents, metrics, playbooks
- Tools: query_metrics, list_incidents, nl2sql, analyze_query, run_diagnosis

Transport: stdio (CLI tools like Claude Code) or HTTP (web tools).
Auth: API Key via X-NeuralDB-Token header.

Usage:
  uv run python -m app.mcp.server --transport stdio
  uv run python -m app.mcp.server --transport http --port 3100
"""

from __future__ import annotations

import json

import structlog

logger = structlog.get_logger(__name__)

# MCP SDK import — graceful fallback if not installed
try:
    from mcp.server import Server
    from mcp.types import Resource, TextContent, Tool

    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False
    logger.warning("mcp.sdk_not_installed", hint="Install with: uv add mcp")


def create_mcp_server() -> Server | None:
    """Create and configure the NeuralDB MCP server.

    Spec: PROTO-MCP-001 Section 2.

    Returns None if MCP SDK is not installed.
    """
    if not _MCP_AVAILABLE:
        return None

    app = Server("neuraldb")

    # -----------------------------------------------------------------
    # Resources (Spec: PROTO-MCP-001 Section 3)
    # -----------------------------------------------------------------

    @app.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                uri="neuraldb://instances",
                name="DB Instances",
                description="All monitored database instances with current health status",
                mimeType="application/json",
            ),
            Resource(
                uri="neuraldb://incidents",
                name="Active Incidents",
                description="Currently open incidents across all instances",
                mimeType="application/json",
            ),
            Resource(
                uri="neuraldb://playbooks",
                name="Playbooks",
                description="Available playbooks (built-in + custom) with YAML definitions",
                mimeType="application/json",
            ),
        ]

    @app.read_resource()
    async def read_resource(uri: str) -> str:
        if uri == "neuraldb://instances":
            return await _read_instances()
        elif uri == "neuraldb://incidents":
            return await _read_incidents()
        elif uri == "neuraldb://playbooks":
            return _read_playbooks()
        else:
            return json.dumps({"error": f"Unknown resource: {uri}"})

    # -----------------------------------------------------------------
    # Tools (Spec: PROTO-MCP-001 Section 4)
    # -----------------------------------------------------------------

    @app.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="query_metrics",
                description="Query database performance metrics for a specific instance and time range",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "instance_id": {"type": "string", "description": "UUID of the DB instance"},
                        "from": {"type": "string", "format": "date-time"},
                        "to": {"type": "string", "format": "date-time"},
                    },
                    "required": ["instance_id", "from", "to"],
                },
            ),
            Tool(
                name="list_incidents",
                description="List incidents filtered by severity and status",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "warning", "notice", "info"],
                        },
                        "status": {"type": "string", "enum": ["open", "acknowledged", "resolved"]},
                        "limit": {"type": "integer", "default": 20},
                    },
                },
            ),
            Tool(
                name="nl2sql",
                description="Convert natural language question to SQL and execute read-only",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "Natural language question"},
                        "instance_id": {"type": "string", "description": "Target DB instance UUID"},
                    },
                    "required": ["question", "instance_id"],
                },
            ),
            Tool(
                name="run_diagnosis",
                description="Run AI RCA diagnosis on an incident",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "incident_id": {"type": "string", "description": "Incident UUID"},
                    },
                    "required": ["incident_id"],
                },
            ),
            Tool(
                name="get_schema_changes",
                description="Get DDL schema change history for an instance",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "instance_id": {"type": "string", "description": "DB instance UUID"},
                        "limit": {"type": "integer", "default": 10},
                    },
                    "required": ["instance_id"],
                },
            ),
        ]

    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        logger.info("mcp.tool_called", tool=name, args=list(arguments.keys()))

        try:
            if name == "query_metrics":
                result = await _tool_query_metrics(arguments)
            elif name == "list_incidents":
                result = await _tool_list_incidents(arguments)
            elif name == "nl2sql":
                result = await _tool_nl2sql(arguments)
            elif name == "run_diagnosis":
                result = {"status": "not_implemented", "hint": "Use /api/v1/copilot/diagnose"}
            elif name == "get_schema_changes":
                result = await _tool_schema_changes(arguments)
            else:
                result = {"error": f"Unknown tool: {name}"}
        except Exception as exc:
            logger.error("mcp.tool_error", tool=name, error=str(exc))
            result = {"error": str(exc)}

        return [TextContent(type="text", text=json.dumps(result, default=str))]

    return app


# ---------------------------------------------------------------------------
# Resource handlers
# ---------------------------------------------------------------------------


async def _read_instances() -> str:
    """Read all instances via internal API."""
    try:
        from sqlalchemy import select

        from app.db.session import AsyncSessionLocal
        from app.models.db_instance import DBInstance

        async with AsyncSessionLocal() as session:
            stmt = select(DBInstance).where(
                DBInstance.is_active.is_(True),
                DBInstance.deleted_at.is_(None),
            )
            result = await session.execute(stmt)
            instances = result.scalars().all()
            return json.dumps(
                [
                    {
                        "id": str(i.id),
                        "name": i.name,
                        "db_type": i.db_type,
                        "host": i.host,
                        "environment": i.environment,
                        "autonomy_level": i.autonomy_level,
                    }
                    for i in instances
                ]
            )
    except Exception as exc:
        return json.dumps({"error": str(exc)})


async def _read_incidents() -> str:
    """Read active incidents."""
    try:
        from sqlalchemy import select

        from app.db.session import AsyncSessionLocal
        from app.models.incident import Incident

        async with AsyncSessionLocal() as session:
            stmt = (
                select(Incident)
                .where(Incident.status.in_(["open", "acknowledged", "in_progress"]))
                .order_by(Incident.detected_at.desc())
                .limit(50)
            )
            result = await session.execute(stmt)
            incidents = result.scalars().all()
            return json.dumps(
                [
                    {
                        "id": str(i.id),
                        "title": i.title,
                        "severity": i.severity,
                        "status": i.status,
                        "detected_at": str(i.detected_at),
                    }
                    for i in incidents
                ]
            )
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _read_playbooks() -> str:
    """Read all playbooks."""
    try:
        from app.services.playbook_executor import list_playbooks

        summaries = list_playbooks()
        return json.dumps(
            [
                {
                    "name": s.name,
                    "description": s.description,
                    "risk_level": s.risk_level.value,
                    "min_autonomy_level": s.min_autonomy_level,
                    "tags": s.tags,
                }
                for s in summaries
            ]
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------


async def _tool_query_metrics(args: dict) -> dict:
    """Query metrics for a time range."""
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.metric import MetricSample

    instance_id = args["instance_id"]
    async with AsyncSessionLocal() as session:
        stmt = (
            select(MetricSample.sampled_at, MetricSample.metrics)
            .where(MetricSample.instance_id == instance_id)
            .order_by(MetricSample.sampled_at.desc())
            .limit(100)
        )
        result = await session.execute(stmt)
        rows = result.all()
        return {
            "instance_id": instance_id,
            "count": len(rows),
            "samples": [{"sampled_at": str(r.sampled_at), "metrics": r.metrics} for r in rows[:20]],
        }


async def _tool_list_incidents(args: dict) -> dict:
    """List incidents with filters."""
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.incident import Incident

    limit = args.get("limit", 20)
    async with AsyncSessionLocal() as session:
        stmt = select(Incident).order_by(Incident.detected_at.desc()).limit(limit)
        if args.get("severity"):
            stmt = stmt.where(Incident.severity == args["severity"])
        if args.get("status"):
            stmt = stmt.where(Incident.status == args["status"])

        result = await session.execute(stmt)
        incidents = result.scalars().all()
        return {
            "count": len(incidents),
            "incidents": [
                {"id": str(i.id), "title": i.title, "severity": i.severity, "status": i.status}
                for i in incidents
            ],
        }


async def _tool_nl2sql(args: dict) -> dict:
    """Run NL2SQL query."""
    from app.db.session import AsyncSessionLocal
    from app.services import nl2sql as nl2sql_service

    question = args["question"]
    instance_id = args["instance_id"]

    async with AsyncSessionLocal() as session:
        sql = await nl2sql_service.generate_sql(question, instance_id)
        columns, rows, elapsed = await nl2sql_service.execute_readonly_sql(session, sql)
        return {
            "sql": sql,
            "columns": columns,
            "rows": rows[:50],
            "execution_time_ms": elapsed,
        }


async def _tool_schema_changes(args: dict) -> dict:
    """Get schema changes."""
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.schema_change import SchemaChange

    instance_id = args["instance_id"]
    limit = args.get("limit", 10)

    async with AsyncSessionLocal() as session:
        stmt = (
            select(SchemaChange)
            .where(SchemaChange.instance_id == instance_id)
            .order_by(SchemaChange.detected_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        changes = result.scalars().all()
        return {
            "count": len(changes),
            "changes": [
                {
                    "change_type": c.change_type,
                    "object_type": c.object_type,
                    "object_name": c.object_name,
                    "detected_at": str(c.detected_at),
                }
                for c in changes
            ],
        }
