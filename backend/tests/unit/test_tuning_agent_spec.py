# Spec: FS-AI-TUNE-001
"""Tests for the DB Performance Tuning Agent.

Covers all 8 Acceptance Criteria from FS-AI-TUNE-001:
  AC-1: POST /api/v1/tuning/analyze returns analysis
  AC-2: 7 tools all work individually
  AC-3: Agent auto-selects appropriate tools
  AC-4: Recommended actions contain executable SQL
  AC-5: All tool queries are read-only
  AC-6: max_iterations exceeded returns partial result
  AC-7: Uses LLMProviderManager
  AC-8: GET /api/v1/tuning/history returns history
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import _create_access_token, pwd_context
from app.models.db_instance import DBInstance
from app.models.user import User
from tests.conftest import spec_ref


# ---------------------------------------------------------------------------
# Helpers for API tests
# ---------------------------------------------------------------------------

def _auth_header(user_id: str) -> dict[str, str]:
    token = _create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


async def _create_user(session: AsyncSession, *, role: str = "db_admin") -> User:
    user = User(
        id=uuid4(),
        email=f"tune-test-{uuid4().hex[:8]}@neuraldb.io",
        name="Tuning Test User",
        hashed_password=pwd_context.hash("TestPass123!"),
        role=role,
        auth_provider="local",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# AC-2: Individual tool tests (pure-unit, mock asyncpg pool)
# ---------------------------------------------------------------------------

def _make_mock_pool(rows=None, fetchrow=None, side_effect=None):
    """Create a mock asyncpg Pool that returns given rows for conn.fetch()."""
    conn = AsyncMock()
    conn.execute = AsyncMock()

    if side_effect:
        conn.fetch = AsyncMock(side_effect=side_effect)
        conn.fetchrow = AsyncMock(side_effect=side_effect)
    else:
        conn.fetch = AsyncMock(return_value=rows or [])
        conn.fetchrow = AsyncMock(return_value=fetchrow)
    conn.fetchval = AsyncMock(return_value=None)

    # Support `async with conn.transaction():`
    txn = AsyncMock()
    txn.__aenter__ = AsyncMock(return_value=txn)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)

    pool = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=cm)

    return pool, conn


@spec_ref("FS-AI-TUNE-001", "AC-2")
@pytest.mark.asyncio
async def test_explain_query_returns_plan():
    """explain_query returns EXPLAIN ANALYZE output for a valid SELECT."""
    from app.agents.tools.db_tools import explain_query

    plan_rows = [("Seq Scan on users  (cost=0.00..1.00 rows=1 width=32)",),
                 ("Planning Time: 0.05 ms",),
                 ("Execution Time: 0.10 ms",)]
    pool, conn = _make_mock_pool()
    conn.fetch = AsyncMock(return_value=plan_rows)

    result = await explain_query(pool, "SELECT * FROM users")
    assert "Seq Scan" in result
    assert "Execution Time" in result


@spec_ref("FS-AI-TUNE-001", "AC-2")
@pytest.mark.asyncio
async def test_slow_queries_formats_table():
    """slow_queries returns a formatted table of slow queries."""
    from app.agents.tools.db_tools import slow_queries

    rows = [
        {"queryid": 123, "query_text": "SELECT * FROM big_table",
         "calls": 100, "mean_time_ms": 500.0, "total_time_ms": 50000.0, "rows": 10000},
    ]
    pool, _ = _make_mock_pool(rows=rows)

    result = await slow_queries(pool, top_n=5)
    assert "big_table" in result
    assert "500" in result


@spec_ref("FS-AI-TUNE-001", "AC-2")
@pytest.mark.asyncio
async def test_slow_queries_extension_not_installed():
    """slow_queries returns helpful message if pg_stat_statements is missing."""
    import asyncpg
    from app.agents.tools.db_tools import slow_queries

    pool, _ = _make_mock_pool(side_effect=asyncpg.UndefinedTableError("pg_stat_statements"))

    result = await slow_queries(pool)
    assert "pg_stat_statements" in result
    assert "not installed" in result


@spec_ref("FS-AI-TUNE-001", "AC-2")
@pytest.mark.asyncio
async def test_index_recommendations_all_tables():
    """index_recommendations returns scan ratio for all tables."""
    from app.agents.tools.db_tools import index_recommendations

    rows = [
        {"schemaname": "public", "table_name": "orders", "seq_scan": 9000,
         "idx_scan": 100, "n_live_tup": 50000, "seq_scan_pct": 98.9},
    ]
    pool, _ = _make_mock_pool(rows=rows)

    result = await index_recommendations(pool)
    assert "orders" in result
    assert "98.9%" in result


@spec_ref("FS-AI-TUNE-001", "AC-2")
@pytest.mark.asyncio
async def test_parameter_tuning_returns_settings():
    """parameter_tuning returns current values and guidelines."""
    from app.agents.tools.db_tools import parameter_tuning

    rows = [
        {"name": "shared_buffers", "setting": "128MB", "unit": "8kB",
         "context": "postmaster", "source": "configuration file"},
        {"name": "work_mem", "setting": "4MB", "unit": "kB",
         "context": "user", "source": "default"},
    ]
    pool, _ = _make_mock_pool(rows=rows)

    result = await parameter_tuning(pool)
    assert "shared_buffers" in result
    assert "work_mem" in result
    assert "Guideline" in result


@spec_ref("FS-AI-TUNE-001", "AC-2")
@pytest.mark.asyncio
async def test_table_bloat_shows_dead_tuples():
    """table_bloat reports dead tuple ratio and recommends VACUUM."""
    from app.agents.tools.db_tools import table_bloat

    rows = [
        {"schemaname": "public", "table_name": "events", "n_live_tup": 10000,
         "n_dead_tup": 5000, "dead_pct": 33.3, "last_vacuum": None,
         "last_autovacuum": None, "last_analyze": None, "last_autoanalyze": None},
    ]
    pool, _ = _make_mock_pool(rows=rows)

    result = await table_bloat(pool)
    assert "events" in result
    assert "33.3%" in result
    assert "VACUUM" in result


@spec_ref("FS-AI-TUNE-001", "AC-2")
@pytest.mark.asyncio
async def test_lock_analysis_no_locks():
    """lock_analysis returns clean message when no locks."""
    from app.agents.tools.db_tools import lock_analysis

    pool, _ = _make_mock_pool(rows=[])

    result = await lock_analysis(pool)
    assert "No lock waits" in result


@spec_ref("FS-AI-TUNE-001", "AC-2")
@pytest.mark.asyncio
async def test_connection_analysis_returns_usage():
    """connection_analysis reports connection usage percentage."""
    from app.agents.tools.db_tools import connection_analysis

    state_rows = [
        {"state": "active", "cnt": 5, "max_idle_txn_seconds": None},
        {"state": "idle", "cnt": 15, "max_idle_txn_seconds": None},
        {"state": "idle in transaction", "cnt": 3, "max_idle_txn_seconds": 120},
    ]
    max_row = {"max_connections": 100}
    pool, conn = _make_mock_pool(rows=state_rows, fetchrow=max_row)

    result = await connection_analysis(pool)
    assert "23/100" in result
    assert "23.0%" in result


# ---------------------------------------------------------------------------
# AC-5: Read-only enforcement
# ---------------------------------------------------------------------------

@spec_ref("FS-AI-TUNE-001", "AC-5")
@pytest.mark.asyncio
async def test_explain_query_rejects_write_sql():
    """explain_query refuses to run non-SELECT queries."""
    from app.agents.tools.db_tools import explain_query, _validate_sql_readonly

    pool, _ = _make_mock_pool()

    # explain_query raises ValueError for write SQL
    with pytest.raises(ValueError, match="write operations"):
        await explain_query(pool, "DELETE FROM users")

    # Direct validation also rejects DDL
    with pytest.raises(ValueError, match="write operations"):
        _validate_sql_readonly("DROP TABLE users")


@spec_ref("FS-AI-TUNE-001", "AC-5")
@pytest.mark.asyncio
async def test_validate_rejects_dangerous_functions():
    """_validate_sql_readonly blocks pg_read_file and similar."""
    from app.agents.tools.db_tools import _validate_sql_readonly

    with pytest.raises(ValueError, match="restricted functions"):
        _validate_sql_readonly("SELECT pg_read_file('/etc/passwd')")


@spec_ref("FS-AI-TUNE-001", "AC-5")
@pytest.mark.asyncio
async def test_validate_rejects_non_select():
    """_validate_sql_readonly blocks non-SELECT statements."""
    from app.agents.tools.db_tools import _validate_sql_readonly

    with pytest.raises(ValueError, match="Only SELECT"):
        _validate_sql_readonly("COPY users TO '/tmp/out'")


# ---------------------------------------------------------------------------
# AC-3, AC-4, AC-6: Agent behavior tests (mock LLM)
# ---------------------------------------------------------------------------

def _make_mock_llm(responses: list[str]):
    """Create a mock LLM that returns canned responses in sequence."""
    llm = AsyncMock()
    llm.model_name = "test-model"
    side = [MagicMock(content=r) for r in responses]
    llm.ainvoke = AsyncMock(side_effect=side)
    return llm


@spec_ref("FS-AI-TUNE-001", "AC-3")
@pytest.mark.asyncio
async def test_agent_selects_tools_based_on_question():
    """Agent calls appropriate tools based on the question content."""
    from app.agents.tuning_agent import DBTuningAgent

    pool, conn = _make_mock_pool(rows=[])
    conn.fetchrow = AsyncMock(return_value={"max_connections": 100})

    llm = _make_mock_llm([
        # First call: agent wants to use connection_analysis
        "Thought: Let me check connections.\nAction: connection_analysis\nAction Input: {}",
        # Second call: final answer
        'Final Answer: {"analysis": "Connections look fine.", "actions": []}',
    ])

    agent = DBTuningAgent(llm=llm, pool=pool)
    result = await agent.analyze("Why are connections piling up?", instance_id=uuid4())

    assert "connection_analysis" in result.tools_used
    assert result.model_used == "test-model"


@spec_ref("FS-AI-TUNE-001", "AC-4")
@pytest.mark.asyncio
async def test_agent_returns_actions_with_sql():
    """Agent returns structured actions including SQL recommendations."""
    from app.agents.tuning_agent import DBTuningAgent

    pool, _ = _make_mock_pool(rows=[])

    llm = _make_mock_llm([
        'Final Answer: {"analysis": "Missing index on orders.customer_id", '
        '"actions": [{"action_type": "CREATE_INDEX", '
        '"description": "Add index for customer_id", '
        '"sql": "CREATE INDEX CONCURRENTLY idx_orders_cust ON orders(customer_id);", '
        '"risk_level": "low", "estimated_impact": "50% faster lookups"}]}',
    ])

    agent = DBTuningAgent(llm=llm, pool=pool)
    result = await agent.analyze("Why is orders table slow?", instance_id=uuid4())

    assert len(result.actions) == 1
    assert result.actions[0].action_type == "CREATE_INDEX"
    assert "CREATE INDEX" in result.actions[0].sql
    assert result.actions[0].risk_level == "low"


@spec_ref("FS-AI-TUNE-001", "AC-6")
@pytest.mark.asyncio
async def test_agent_max_iterations_returns_partial():
    """Agent returns partial result when max_iterations is exceeded."""
    from app.agents.tuning_agent import DBTuningAgent

    pool, _ = _make_mock_pool(rows=[])

    # LLM never gives Final Answer — just keeps asking for tools
    responses = [
        "Thought: Need more data.\nAction: slow_queries\nAction Input: 5",
    ] * 3  # 3 iterations, set max to 2

    llm = _make_mock_llm(responses)

    agent = DBTuningAgent(llm=llm, pool=pool)
    result = await agent.analyze("Analyze everything", instance_id=uuid4(), max_iterations=2)

    assert result.iterations == 2
    # Should still have some analysis (even if partial)
    assert result.analysis is not None


# ---------------------------------------------------------------------------
# AC-7: Uses LLMProviderManager
# ---------------------------------------------------------------------------

@spec_ref("FS-AI-TUNE-001", "AC-7")
@pytest.mark.asyncio
async def test_api_uses_llm_provider_manager():
    """Verify that the tuning API router imports and uses get_llm_manager."""
    # Static check: the module must reference get_llm_manager
    import inspect
    from app.api.v1 import tuning
    source = inspect.getsource(tuning)
    assert "get_llm_manager" in source


# ---------------------------------------------------------------------------
# AC-1, AC-8: API endpoint tests (require client fixture)
# ---------------------------------------------------------------------------

@spec_ref("FS-AI-TUNE-001", "AC-8")
@pytest.mark.asyncio
async def test_tuning_history_empty(client, async_session):
    """GET /api/v1/tuning/history returns empty list initially."""
    from app.api.v1.tuning import _history
    _history.clear()  # ensure clean state

    user = await _create_user(async_session, role="db_admin")
    headers = _auth_header(str(user.id))

    resp = await client.get("/api/v1/tuning/history", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


@spec_ref("FS-AI-TUNE-001", "AC-1")
@pytest.mark.asyncio
async def test_tuning_analyze_instance_not_found(client, async_session):
    """POST /api/v1/tuning/analyze returns 404 for unknown instance."""
    user = await _create_user(async_session, role="db_admin")
    headers = _auth_header(str(user.id))

    resp = await client.post(
        "/api/v1/tuning/analyze",
        json={
            "instance_id": str(uuid4()),
            "question": "Why is the database slow?",
        },
        headers=headers,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------

@spec_ref("FS-AI-TUNE-001", "AC-4")
@pytest.mark.asyncio
async def test_tuning_action_schema_validation():
    """TuningAction schema validates action_type and risk_level."""
    from app.schemas.tuning import TuningAction

    action = TuningAction(
        action_type="CREATE_INDEX",
        description="Add index",
        sql="CREATE INDEX idx_test ON t(c);",
        risk_level="low",
        estimated_impact="Faster queries",
    )
    assert action.action_type == "CREATE_INDEX"
    assert action.risk_level == "low"

    # Invalid action_type should fail
    with pytest.raises(Exception):
        TuningAction(
            action_type="INVALID_TYPE",
            description="Bad",
            risk_level="low",
        )


@spec_ref("FS-AI-TUNE-001", "AC-1")
@pytest.mark.asyncio
async def test_tuning_request_schema_validation():
    """TuningRequest validates question length and max_iterations."""
    from app.schemas.tuning import TuningRequest

    req = TuningRequest(
        instance_id=uuid4(),
        question="Why is the database slow?",
        max_iterations=5,
    )
    assert req.max_iterations == 5

    # Too short question
    with pytest.raises(Exception):
        TuningRequest(instance_id=uuid4(), question="ab")

    # max_iterations > 10
    with pytest.raises(Exception):
        TuningRequest(instance_id=uuid4(), question="test question", max_iterations=11)
