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
            Tool(
                name="dba_ask",
                description=(
                    "Unified DBA Agent — ask anything about your database. "
                    "Routes to: analyze (performance), diagnose (RCA), "
                    "execute (create index, vacuum, kill session), "
                    "query (NL2SQL), status (health check). "
                    "Supports SafetyGuard 4-level risk + Autonomy Policy."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "Natural language DBA question",
                        },
                        "instance_id": {
                            "type": "string",
                            "description": "Target DB instance UUID",
                        },
                    },
                    "required": ["question", "instance_id"],
                },
            ),
            Tool(
                name="dba_execute",
                description=(
                    "Execute a DBA operation with SafetyGuard protection. "
                    "Operations: create_index, vacuum, kill_session, "
                    "alter_parameter, reindex, analyze_table. "
                    "Risk levels: SAFE/WARNING/DANGEROUS/CRITICAL."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "action_type": {
                            "type": "string",
                            "enum": [
                                "create_index", "vacuum", "vacuum_full",
                                "kill_session", "alter_parameter",
                                "reindex", "analyze_table",
                            ],
                            "description": "Type of DBA operation",
                        },
                        "instance_id": {
                            "type": "string",
                            "description": "Target DB instance UUID",
                        },
                        "params": {
                            "type": "object",
                            "description": "Operation parameters (table, columns, pid, etc.)",
                        },
                    },
                    "required": ["action_type", "instance_id"],
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
            elif name == "dba_ask":
                result = await _tool_dba_ask(arguments)
            elif name == "dba_execute":
                result = await _tool_dba_execute(arguments)
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


# ---------------------------------------------------------------------------
# DBA Agent MCP tools
# ---------------------------------------------------------------------------


async def _tool_dba_ask(args: dict) -> dict:
    """MCP tool: Unified DBA Agent — routes to analyze/diagnose/execute/query/status.

    Enables external AI tools (Claude Code, OpenAI, Gemini) to use DBA Agent
    via MCP protocol. Same SafetyGuard + Autonomy as the REST API.
    """
    from uuid import UUID

    import asyncpg

    from app.agents.dba_agent import DBAAgent
    from app.db.session import AsyncSessionLocal
    from app.models.db_instance import DBInstance
    from app.utils.dsn import build_target_dsn
    from sqlalchemy import select

    question = args.get("question", "")
    instance_id = args.get("instance_id", "")

    if not question or not instance_id:
        return {"error": "question and instance_id are required."}

    try:
        iid = UUID(instance_id)
    except ValueError:
        return {"error": f"Invalid instance_id: {instance_id}"}

    pool = None
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(DBInstance).where(
                DBInstance.id == iid,
                DBInstance.deleted_at.is_(None),
            )
            result = await session.execute(stmt)
            instance = result.scalar_one_or_none()
            if not instance:
                return {"error": f"Instance {instance_id} not found."}

            # Build target DB pool
            try:
                dsn = build_target_dsn(instance)
                pool = await asyncpg.create_pool(
                    dsn, min_size=1, max_size=2,
                    command_timeout=10,
                )
            except Exception as exc:
                logger.warning("mcp.dba_pool_failed", error=str(exc))

            agent = DBAAgent()
            response = await agent.ask(
                question=question,
                instance_id=iid,
                session=session,
                pool=pool,
                autonomy_level=instance.autonomy_level,
                user_role="db_admin",  # MCP users get db_admin level
            )

            return {
                "intent": response.intent,
                "answer": response.answer,
                "data": response.data,
                "actions": (
                    [a.model_dump() for a in response.actions]
                    if response.actions
                    else None
                ),
                "model": response.model,
                "processing_time_ms": response.processing_time_ms,
            }
    except Exception as exc:
        logger.error("mcp.dba_ask_error", error=str(exc))
        return {"error": str(exc)}
    finally:
        if pool:
            await pool.close()


async def _tool_dba_execute(args: dict) -> dict:
    """MCP tool: Execute a specific DBA operation with SafetyGuard.

    External AI tools can request create_index, vacuum, kill_session, etc.
    All operations go through SafetyGuard 4-level risk + Autonomy Policy.
    """
    from uuid import UUID

    import asyncpg

    from app.agents.execution_engine import ExecutionEngine
    from app.agents.tools import ops_tools
    from app.db.session import AsyncSessionLocal
    from app.models.db_instance import DBInstance
    from app.utils.dsn import build_target_dsn
    from sqlalchemy import select

    action_type = args.get("action_type", "")
    instance_id = args.get("instance_id", "")
    params = args.get("params", {})

    if not action_type or not instance_id:
        return {"error": "action_type and instance_id are required."}

    try:
        iid = UUID(instance_id)
    except ValueError:
        return {"error": f"Invalid instance_id: {instance_id}"}

    # Build ActionRequest from params
    action_builders = {
        "create_index": lambda: ops_tools.create_index(
            iid,
            params.get("table", "unknown"),
            params.get("columns", ["id"]),
        ),
        "vacuum": lambda: ops_tools.vacuum_table(iid, params.get("table", "unknown")),
        "vacuum_full": lambda: ops_tools.vacuum_table(
            iid, params.get("table", "unknown"), full=True,
        ),
        "kill_session": lambda: ops_tools.kill_session(
            iid, int(params.get("pid", 0)),
            reason=params.get("reason", "MCP-initiated"),
        ),
        "alter_parameter": lambda: ops_tools.alter_parameter(
            iid, params.get("param", ""), params.get("value", ""),
        ),
        "reindex": lambda: ops_tools.reindex(iid, params.get("index_name", "")),
        "analyze_table": lambda: ops_tools.analyze_table(iid, params.get("table", "unknown")),
    }

    builder = action_builders.get(action_type)
    if not builder:
        return {"error": f"Unknown action_type: {action_type}. Allowed: {list(action_builders.keys())}"}

    try:
        action_request = builder()
    except ValueError as ve:
        return {"error": f"Invalid params: {ve}"}

    pool = None
    try:
        async with AsyncSessionLocal() as session:
            stmt = select(DBInstance).where(
                DBInstance.id == iid, DBInstance.deleted_at.is_(None),
            )
            result = await session.execute(stmt)
            instance = result.scalar_one_or_none()
            if not instance:
                return {"error": f"Instance {instance_id} not found."}

            try:
                dsn = build_target_dsn(instance)
                pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)
            except Exception as exc:
                return {"error": f"Cannot connect to target DB: {exc}"}

            engine = ExecutionEngine()
            result = await engine.execute(
                action_request, session, pool,
                autonomy_level=instance.autonomy_level,
                user_role="db_admin",
            )
            await session.commit()

            return {
                "action_id": str(result.action_id),
                "status": result.status,
                "action_type": action_request.action_type,
                "sql": action_request.sql,
                "risk_level": action_request.risk_level,
                "execution_time_ms": result.execution_time_ms,
                "rows_affected": result.rows_affected,
                "error": result.error,
            }
    except Exception as exc:
        logger.error("mcp.dba_execute_error", error=str(exc))
        return {"error": str(exc)}
    finally:
        if pool:
            await pool.close()
