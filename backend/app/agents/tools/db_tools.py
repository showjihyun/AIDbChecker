# Spec: FS-AI-TUNE-001
"""7 PostgreSQL performance analysis tools for the DB Tuning Agent.

Each tool is a regular async function accepting an asyncpg Pool as the first
argument and returning a formatted string for LLM context.  The pool MUST be
configured with ``default_transaction_read_only = on`` and a reasonable
``statement_timeout`` (5 s for tuning analysis, vs 500 ms for live collection).

These functions are intentionally *not* decorated with ``@tool`` so they can be
wrapped as LangChain StructuredTools with the pool baked in via closure (see
``tuning_agent.py``).
"""

from __future__ import annotations

import re
import textwrap

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Spec: FS-AI-TUNE-001 Section 5 -- read-only validation
# Reuses the same defence-in-depth pattern as NL2SQL (_validate_sql_readonly).
# ---------------------------------------------------------------------------

_WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|"
    r"COPY|VACUUM|REINDEX|CLUSTER|COMMENT|LOCK|DISCARD|REASSIGN|"
    r"DO|EXECUTE|CALL|PERFORM)\b",
    re.IGNORECASE,
)

_DANGEROUS_FUNCTIONS = re.compile(
    r"\b(pg_read_file|pg_read_binary_file|pg_stat_file|lo_get|lo_export|"
    r"dblink|pg_execute_server_program|query_to_xml|xpath)\b",
    re.IGNORECASE,
)


def _validate_sql_readonly(sql: str) -> None:
    """Reject SQL containing write operations or dangerous functions.

    Raises ``ValueError`` on violation.
    """
    if _WRITE_KEYWORDS.search(sql):
        raise ValueError(
            "SQL contains write operations. Only SELECT queries are allowed."
        )
    if _DANGEROUS_FUNCTIONS.search(sql):
        raise ValueError(
            "SQL contains restricted functions. Only standard SELECT queries are allowed."
        )
    stripped = sql.strip().upper()
    if not stripped.startswith("SELECT") and not stripped.startswith("WITH"):
        raise ValueError("Only SELECT or WITH (CTE) queries are allowed.")


# ---------------------------------------------------------------------------
# Tool 1: explain_query
# ---------------------------------------------------------------------------

async def explain_query(pool: asyncpg.Pool, sql: str) -> str:
    """EXPLAIN ANALYZE a SELECT query and return the execution plan.

    Spec: FS-AI-TUNE-001 Section 3.1
    - Validates read-only (SELECT/WITH only).
    - Uses ``SET LOCAL statement_timeout = '5000'``.
    - Returns the formatted EXPLAIN ANALYZE output.
    """
    _validate_sql_readonly(sql)

    # Strip trailing semicolons (asyncpg does not want them)
    sql = sql.rstrip(";").strip()

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("SET LOCAL statement_timeout = '5000'")
                rows = await conn.fetch(f"EXPLAIN ANALYZE {sql}")
        plan_lines = [row[0] for row in rows]
        return "\n".join(plan_lines)
    except asyncpg.PostgresError as exc:
        return f"EXPLAIN failed: {exc}"


# ---------------------------------------------------------------------------
# Tool 2: slow_queries
# ---------------------------------------------------------------------------

_SQL_SLOW_QUERIES = textwrap.dedent("""\
    SELECT
        queryid,
        LEFT(query, 200) AS query_text,
        calls,
        round(mean_exec_time::numeric, 2)  AS mean_time_ms,
        round(total_exec_time::numeric, 2) AS total_time_ms,
        rows
    FROM pg_stat_statements
    WHERE calls > 0
    ORDER BY mean_exec_time DESC
    LIMIT $1
""")


async def slow_queries(pool: asyncpg.Pool, top_n: int = 10) -> str:
    """Return the Top-N slowest queries from ``pg_stat_statements``.

    Spec: FS-AI-TUNE-001 Section 3.2
    Returns a formatted table.  If the extension is not installed the error
    message tells the caller.
    """
    top_n = max(1, min(top_n, 50))

    try:
        async with pool.acquire() as conn:
            await conn.execute("SET LOCAL statement_timeout = '5000'")
            rows = await conn.fetch(_SQL_SLOW_QUERIES, top_n)
    except asyncpg.UndefinedTableError:
        return (
            "pg_stat_statements extension is not installed or not loaded. "
            "Run: CREATE EXTENSION IF NOT EXISTS pg_stat_statements; and "
            "add shared_preload_libraries = 'pg_stat_statements' in postgresql.conf."
        )
    except asyncpg.PostgresError as exc:
        return f"slow_queries failed: {exc}"

    if not rows:
        return "No query statistics available (pg_stat_statements is empty)."

    lines = [
        f"{'#':<4} {'Mean(ms)':<12} {'Total(ms)':<14} {'Calls':<10} {'Rows':<10} Query",
        "-" * 90,
    ]
    for i, r in enumerate(rows, 1):
        lines.append(
            f"{i:<4} {r['mean_time_ms']:<12} {r['total_time_ms']:<14} "
            f"{r['calls']:<10} {r['rows']:<10} {r['query_text']}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 3: index_recommendations
# ---------------------------------------------------------------------------

_SQL_INDEX_SCAN_RATIO = textwrap.dedent("""\
    SELECT
        schemaname,
        relname AS table_name,
        seq_scan,
        idx_scan,
        n_live_tup,
        CASE WHEN (seq_scan + COALESCE(idx_scan, 0)) > 0
             THEN round(seq_scan::numeric / (seq_scan + COALESCE(idx_scan, 0)) * 100, 1)
             ELSE 0 END AS seq_scan_pct
    FROM pg_stat_user_tables
    WHERE n_live_tup > 500
    ORDER BY seq_scan_pct DESC, seq_scan DESC
    LIMIT 20
""")

_SQL_TABLE_INDEXES = textwrap.dedent("""\
    SELECT
        indexname,
        indexdef
    FROM pg_indexes
    WHERE tablename = $1
    ORDER BY indexname
""")

_SQL_TABLE_COLUMNS = textwrap.dedent("""\
    SELECT
        column_name,
        data_type
    FROM information_schema.columns
    WHERE table_name = $1
      AND table_schema = 'public'
    ORDER BY ordinal_position
""")


async def index_recommendations(pool: asyncpg.Pool, table_name: str | None = None) -> str:
    """Analyse seq_scan vs idx_scan ratio and recommend indexes.

    Spec: FS-AI-TUNE-001 Section 3.3
    - Without ``table_name``: show tables with high sequential scan ratio.
    - With ``table_name``: show columns and existing indexes for that table.
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute("SET LOCAL statement_timeout = '5000'")

            if table_name is None:
                rows = await conn.fetch(_SQL_INDEX_SCAN_RATIO)
                if not rows:
                    return "No user tables found or all tables are small (<500 rows)."

                lines = [
                    f"{'Table':<35} {'SeqScans':<12} {'IdxScans':<12} {'Rows':<12} {'Seq%':<8}",
                    "-" * 80,
                ]
                recommendations: list[str] = []
                for r in rows:
                    tbl = f"{r['schemaname']}.{r['table_name']}"
                    lines.append(
                        f"{tbl:<35} {r['seq_scan']:<12} {r['idx_scan'] or 0:<12} "
                        f"{r['n_live_tup']:<12} {r['seq_scan_pct']}%"
                    )
                    if r["seq_scan_pct"] and float(r["seq_scan_pct"]) > 80 and r["n_live_tup"] > 1000:
                        recommendations.append(
                            f"  - {tbl}: {r['seq_scan_pct']}% sequential scans "
                            f"with {r['n_live_tup']} rows. Consider adding an index."
                        )

                if recommendations:
                    lines.append("\nRecommendations:")
                    lines.extend(recommendations)
                return "\n".join(lines)

            # Specific table analysis
            cols = await conn.fetch(_SQL_TABLE_COLUMNS, table_name)
            idxs = await conn.fetch(_SQL_TABLE_INDEXES, table_name)

        if not cols:
            return f"Table '{table_name}' not found in public schema."

        lines = [f"Table: {table_name}", "", "Columns:"]
        for c in cols:
            lines.append(f"  {c['column_name']}: {c['data_type']}")

        lines.append("\nExisting Indexes:")
        if idxs:
            for idx in idxs:
                lines.append(f"  {idx['indexname']}: {idx['indexdef']}")
        else:
            lines.append("  (none)")

        lines.append(
            "\nRecommendation: Review columns used in WHERE/JOIN/ORDER BY "
            "clauses and add indexes for those not yet indexed."
        )
        return "\n".join(lines)

    except asyncpg.PostgresError as exc:
        return f"index_recommendations failed: {exc}"


# ---------------------------------------------------------------------------
# Tool 4: parameter_tuning
# ---------------------------------------------------------------------------

_SQL_PARAMETERS = textwrap.dedent("""\
    SELECT name, setting, unit, context, source
    FROM pg_settings
    WHERE name IN (
        'shared_buffers', 'work_mem', 'effective_cache_size',
        'maintenance_work_mem', 'random_page_cost', 'wal_buffers',
        'max_connections', 'checkpoint_completion_target',
        'effective_io_concurrency', 'max_worker_processes',
        'max_parallel_workers_per_gather'
    )
    ORDER BY name
""")

# Best-practice guidelines (relative to RAM or absolute)
_PARAM_GUIDELINES: dict[str, str] = {
    "shared_buffers": "25% of RAM (e.g. 4GB for 16GB RAM)",
    "work_mem": "RAM / max_connections / 4 (e.g. 16MB for 16GB/200 conns)",
    "effective_cache_size": "50-75% of RAM (e.g. 12GB for 16GB RAM)",
    "maintenance_work_mem": "5-10% of RAM (e.g. 1GB for 16GB RAM)",
    "random_page_cost": "1.1 for SSD, 4.0 for HDD",
    "wal_buffers": "1/32 of shared_buffers or 64MB, whichever is smaller",
    "checkpoint_completion_target": "0.9 recommended",
    "effective_io_concurrency": "200 for SSD, 2 for HDD",
    "max_parallel_workers_per_gather": "2-4 depending on CPU cores",
}


async def parameter_tuning(pool: asyncpg.Pool) -> str:
    """Analyse current PostgreSQL parameters and recommend changes.

    Spec: FS-AI-TUNE-001 Section 3.4
    Compares current values with best-practice guidelines.
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute("SET LOCAL statement_timeout = '5000'")
            rows = await conn.fetch(_SQL_PARAMETERS)
    except asyncpg.PostgresError as exc:
        return f"parameter_tuning failed: {exc}"

    if not rows:
        return "Could not retrieve pg_settings."

    lines = [
        f"{'Parameter':<40} {'Current':<20} {'Unit':<6} {'Context':<14} Guideline",
        "-" * 120,
    ]
    for r in rows:
        guideline = _PARAM_GUIDELINES.get(r["name"], "")
        lines.append(
            f"{r['name']:<40} {r['setting']:<20} {r['unit'] or '':<6} "
            f"{r['context']:<14} {guideline}"
        )

    lines.append(
        "\nNote: Changes to 'postmaster' context require a PostgreSQL restart. "
        "'sighup' context can be reloaded via SELECT pg_reload_conf()."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 5: table_bloat
# ---------------------------------------------------------------------------

_SQL_TABLE_BLOAT = textwrap.dedent("""\
    SELECT
        schemaname,
        relname AS table_name,
        n_live_tup,
        n_dead_tup,
        CASE WHEN n_live_tup + n_dead_tup > 0
             THEN round(n_dead_tup::numeric / (n_live_tup + n_dead_tup) * 100, 1)
             ELSE 0 END AS dead_pct,
        last_vacuum,
        last_autovacuum,
        last_analyze,
        last_autoanalyze
    FROM pg_stat_user_tables
    {where_clause}
    ORDER BY dead_pct DESC, n_dead_tup DESC
    LIMIT 20
""")


async def table_bloat(pool: asyncpg.Pool, table_name: str | None = None) -> str:
    """Analyse dead tuples and bloat for tables.

    Spec: FS-AI-TUNE-001 Section 3.5
    Reports dead-tuple ratio and last vacuum timestamps.
    Recommends VACUUM ANALYZE for bloated tables.
    """
    where_clause = f"WHERE relname = '{table_name}'" if table_name else ""
    # Safe: table_name is used in a WHERE on pg_stat_user_tables (system catalog).
    # We still sanitise to prevent SQL injection via the tool input.
    if table_name and not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table_name):
        return f"Invalid table name: '{table_name}'."

    sql = _SQL_TABLE_BLOAT.format(where_clause=where_clause)

    try:
        async with pool.acquire() as conn:
            await conn.execute("SET LOCAL statement_timeout = '5000'")
            rows = await conn.fetch(sql)
    except asyncpg.PostgresError as exc:
        return f"table_bloat failed: {exc}"

    if not rows:
        return f"No data for table '{table_name}'." if table_name else "No user tables found."

    lines = [
        f"{'Table':<35} {'Live':<12} {'Dead':<12} {'Dead%':<8} {'Last Vacuum':<24} {'Last AutoVac':<24}",
        "-" * 120,
    ]
    recommendations: list[str] = []
    for r in rows:
        tbl = f"{r['schemaname']}.{r['table_name']}"
        lv = str(r["last_vacuum"] or "never")[:19]
        la = str(r["last_autovacuum"] or "never")[:19]
        lines.append(
            f"{tbl:<35} {r['n_live_tup']:<12} {r['n_dead_tup']:<12} "
            f"{r['dead_pct']}%{'':<4} {lv:<24} {la:<24}"
        )
        if r["dead_pct"] and float(r["dead_pct"]) > 10:
            recommendations.append(
                f"  VACUUM ANALYZE {tbl};  -- {r['dead_pct']}% dead tuples"
            )

    if recommendations:
        lines.append("\nRecommended VACUUM commands:")
        lines.extend(recommendations)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 6: lock_analysis
# ---------------------------------------------------------------------------

_SQL_LOCK_ANALYSIS = textwrap.dedent("""\
    SELECT
        blocked.pid AS blocked_pid,
        blocked.query AS blocked_query,
        blocked.wait_event_type,
        blocked.wait_event,
        EXTRACT(EPOCH FROM clock_timestamp() - blocked.query_start)::int AS wait_seconds,
        blocker.pid AS blocker_pid,
        blocker.query AS blocker_query,
        blocker.state AS blocker_state
    FROM pg_stat_activity blocked
    JOIN LATERAL (
        SELECT unnest(pg_blocking_pids(blocked.pid)) AS pid
    ) bp ON true
    JOIN pg_stat_activity blocker ON blocker.pid = bp.pid
    WHERE blocked.wait_event_type = 'Lock'
    ORDER BY wait_seconds DESC
    LIMIT 20
""")


async def lock_analysis(pool: asyncpg.Pool) -> str:
    """Identify current lock waits and blocking sessions.

    Spec: FS-AI-TUNE-001 Section 3.6
    Shows blocked and blocker PIDs with their queries.
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute("SET LOCAL statement_timeout = '5000'")
            rows = await conn.fetch(_SQL_LOCK_ANALYSIS)
    except asyncpg.PostgresError as exc:
        return f"lock_analysis failed: {exc}"

    if not rows:
        return "No lock waits detected. The database has no blocking sessions."

    lines = [
        f"{'Blocked PID':<14} {'Wait(s)':<10} {'Blocker PID':<14} {'Blocker State':<18} Blocked Query",
        "-" * 100,
    ]
    for r in rows:
        lines.append(
            f"{r['blocked_pid']:<14} {r['wait_seconds']:<10} "
            f"{r['blocker_pid']:<14} {r['blocker_state']:<18} "
            f"{(r['blocked_query'] or '')[:60]}"
        )

    lines.append(
        "\nTo terminate a blocking session (HIGH RISK): "
        "SELECT pg_terminate_backend(<blocker_pid>);"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 7: connection_analysis
# ---------------------------------------------------------------------------

_SQL_CONNECTION_ANALYSIS = textwrap.dedent("""\
    SELECT
        state,
        count(*) AS cnt,
        CASE WHEN state = 'idle in transaction'
             THEN max(EXTRACT(EPOCH FROM clock_timestamp() - state_change))::int
             ELSE NULL END AS max_idle_txn_seconds
    FROM pg_stat_activity
    WHERE backend_type = 'client backend'
    GROUP BY state
    ORDER BY cnt DESC
""")

_SQL_MAX_CONNECTIONS = textwrap.dedent("""\
    SELECT
        setting::int AS max_connections
    FROM pg_settings
    WHERE name = 'max_connections'
""")


async def connection_analysis(pool: asyncpg.Pool) -> str:
    """Analyse connection pool efficiency and idle sessions.

    Spec: FS-AI-TUNE-001 Section 3.7
    Groups sessions by state, checks idle-in-transaction duration,
    and reports max_connections usage.
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute("SET LOCAL statement_timeout = '5000'")
            state_rows = await conn.fetch(_SQL_CONNECTION_ANALYSIS)
            max_conn_row = await conn.fetchrow(_SQL_MAX_CONNECTIONS)
    except asyncpg.PostgresError as exc:
        return f"connection_analysis failed: {exc}"

    max_conns = max_conn_row["max_connections"] if max_conn_row else 100
    total = sum(r["cnt"] for r in state_rows)
    usage_pct = round(total / max_conns * 100, 1) if max_conns else 0

    lines = [
        f"Connection Usage: {total}/{max_conns} ({usage_pct}%)",
        "",
        f"{'State':<25} {'Count':<10} {'Max Idle Txn (s)':<20}",
        "-" * 60,
    ]
    idle_txn_count = 0
    for r in state_rows:
        idle_info = str(r["max_idle_txn_seconds"] or "") if r["max_idle_txn_seconds"] else ""
        lines.append(f"{r['state'] or 'NULL':<25} {r['cnt']:<10} {idle_info:<20}")
        if r["state"] == "idle in transaction":
            idle_txn_count = r["cnt"]

    recommendations: list[str] = []
    if usage_pct > 80:
        recommendations.append(
            f"  - Connection usage is {usage_pct}%. "
            "Consider increasing max_connections or using a connection pooler (pgBouncer)."
        )
    if idle_txn_count > 5:
        recommendations.append(
            f"  - {idle_txn_count} sessions are 'idle in transaction'. "
            "These hold locks and waste connections. Set idle_in_transaction_session_timeout."
        )

    if recommendations:
        lines.append("\nRecommendations:")
        lines.extend(recommendations)
    return "\n".join(lines)
