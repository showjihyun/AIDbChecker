# Spec: AG-001, DM-001, ADR-006
"""PostgreSQL Remote Adapter — Tier 2 remote metric collection.

Connects from NeuralDB backend to target PostgreSQL via asyncpg (NOT SQLAlchemy).
Uses read-only connection pool (pool_size=2) with statement_timeout=500ms.
Silent failure on collection errors to avoid cascading impact to other instances.
"""

import asyncio
from datetime import datetime, timezone
from uuid import UUID

import asyncpg
import structlog

from app.adapters.base import ActiveSessionSample, BaseAdapter, MetricSample

logger = structlog.get_logger(__name__)

# SQL: Hot metrics from pg_stat_database (1-second interval)
# Spec: FS-KPI-001 — added deadlocks for KPI-10 delta/s calculation
_SQL_HOT_METRICS = """
SELECT
    numbackends,
    xact_commit,
    xact_rollback,
    tup_returned,
    tup_fetched,
    tup_inserted,
    tup_updated,
    tup_deleted,
    blks_hit,
    blks_read,
    deadlocks
FROM pg_stat_database
WHERE datname = current_database();
"""

# Spec: FS-KPI-001 Section 5.1 — Live KPI queries for point-in-time metrics
_SQL_KPI_EXTRAS = """
SELECT
    -- KPI-04: Slow queries (duration > 1s)
    (SELECT count(*)
     FROM pg_stat_activity
     WHERE state = 'active'
       AND clock_timestamp() - query_start > INTERVAL '1 second'
       AND backend_type = 'client backend'
       AND pid <> pg_backend_pid()
    ) AS slow_query_count,

    -- KPI-07: Active sessions
    (SELECT count(*)
     FROM pg_stat_activity
     WHERE state = 'active'
       AND backend_type = 'client backend'
    ) AS active_sessions,

    -- KPI-08: numbackends + max_connections for connection usage
    (SELECT numbackends
     FROM pg_stat_database
     WHERE datname = current_database()
    ) AS numbackends,
    (SELECT setting::int
     FROM pg_settings
     WHERE name = 'max_connections'
    ) AS max_connections,

    -- KPI-09: Lock waits
    (SELECT count(*)
     FROM pg_stat_activity
     WHERE wait_event_type = 'Lock'
    ) AS lock_waits,

    -- KPI-10: Cumulative deadlocks (for live fallback)
    (SELECT deadlocks
     FROM pg_stat_database
     WHERE datname = current_database()
    ) AS deadlocks;
"""

# Separate query for pg_stat_statements (optional extension — may not be installed)
_SQL_AVG_RESPONSE_TIME = """
SELECT round(avg(mean_exec_time)::numeric, 3) AS avg_response_time_ms
FROM pg_stat_statements
WHERE calls > 0;
"""

# SQL: Warm metrics from pg_stat_user_tables (10-second interval)
_SQL_WARM_METRICS = """
SELECT
    schemaname,
    relname AS table_name,
    seq_scan,
    seq_tup_read,
    idx_scan,
    idx_tup_fetch,
    n_tup_ins,
    n_tup_upd,
    n_tup_del,
    n_live_tup,
    n_dead_tup,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC
LIMIT 50;
"""

# SQL: ASH sampling from pg_stat_activity
_SQL_ASH = """
SELECT
    pid,
    query,
    NULL::bigint AS query_hash,  -- queryid is in pg_stat_statements, not pg_stat_activity
    state,
    wait_event_type,
    wait_event,
    backend_type,
    client_addr::text AS client_addr,
    application_name,
    query_start,
    EXTRACT(EPOCH FROM (clock_timestamp() - query_start)) * 1000 AS duration_ms
FROM pg_stat_activity
WHERE backend_type = 'client backend'
  AND pid <> pg_backend_pid()
ORDER BY state, duration_ms DESC NULLS LAST;
"""


class PostgreSQLRemoteAdapter(BaseAdapter):
    """Remote PostgreSQL adapter — queries target DB over TCP.

    Suitable for Phase 1-2 (up to ~30 instances in the same DC).
    For Phase 3+, use PostgreSQLLocalCollector for 1-second guarantees at scale.
    """

    def __init__(self, instance_id: UUID, dsn: str) -> None:
        self._instance_id = instance_id
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> bool:
        """Create asyncpg connection pool (pool_size=2, statement_timeout=500ms)."""
        try:
            self._pool = await asyncpg.create_pool(
                self._dsn,
                min_size=1,
                max_size=2,
                command_timeout=5,
                server_settings={
                    "statement_timeout": "500",
                    "default_transaction_read_only": "on",
                },
            )
            logger.info(
                "adapter.connected",
                instance_id=str(self._instance_id),
            )
            return True
        except (asyncpg.PostgresError, OSError, asyncio.TimeoutError) as exc:
            logger.warning(
                "adapter.connect_failed",
                instance_id=str(self._instance_id),
                error=str(exc),
            )
            return False

    async def disconnect(self) -> None:
        """Close connection pool and release resources."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info(
                "adapter.disconnected",
                instance_id=str(self._instance_id),
            )

    async def test_connection(self) -> tuple[bool, str]:
        """Test connectivity by running SELECT 1."""
        pool: asyncpg.Pool | None = None
        try:
            pool = await asyncpg.create_pool(
                self._dsn,
                min_size=1,
                max_size=1,
                command_timeout=5,
                server_settings={"statement_timeout": "3000"},
            )
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return (True, "OK")
        except (asyncpg.PostgresError, OSError, asyncio.TimeoutError) as exc:
            return (False, str(exc))
        finally:
            if pool is not None:
                await pool.close()

    async def collect_metrics(self, category: str) -> MetricSample | None:
        """Collect metrics by category. Returns None on failure (silent skip)."""
        if self._pool is None:
            logger.warning(
                "adapter.not_connected",
                instance_id=str(self._instance_id),
                category=category,
            )
            return None

        try:
            now = datetime.now(timezone.utc)

            if category == "hot":
                return await self._collect_hot(now)
            elif category == "warm":
                return await self._collect_warm(now)
            elif category == "cold":
                return await self._collect_cold(now)
            else:
                logger.warning(
                    "adapter.unknown_category",
                    instance_id=str(self._instance_id),
                    category=category,
                )
                return None

        except asyncio.TimeoutError:
            logger.warning(
                "adapter.collect_timeout",
                instance_id=str(self._instance_id),
                category=category,
            )
            return None
        except asyncpg.PostgresError as exc:
            logger.warning(
                "adapter.collect_error",
                instance_id=str(self._instance_id),
                category=category,
                error=str(exc),
            )
            return None

    async def _collect_hot(self, now: datetime) -> MetricSample | None:
        """Hot metrics: pg_stat_database counters (1-second interval)."""
        async with self._pool.acquire() as conn:  # type: ignore[union-attr]
            row = await conn.fetchrow(_SQL_HOT_METRICS)

        if row is None:
            return None

        # Spec: FS-KPI-001 — include deadlocks for KPI-10 delta/s calculation
        return MetricSample(
            instance_id=self._instance_id,
            sampled_at=now,
            category="hot",
            metrics={
                "numbackends": row["numbackends"],
                "xact_commit": row["xact_commit"],
                "xact_rollback": row["xact_rollback"],
                "tup_returned": row["tup_returned"],
                "tup_fetched": row["tup_fetched"],
                "tup_inserted": row["tup_inserted"],
                "tup_updated": row["tup_updated"],
                "tup_deleted": row["tup_deleted"],
                "blks_hit": row["blks_hit"],
                "blks_read": row["blks_read"],
                "deadlocks": row["deadlocks"],
            },
        )

    async def _collect_warm(self, now: datetime) -> MetricSample | None:
        """Warm metrics: pg_stat_user_tables top 50 tables (10-second interval)."""
        async with self._pool.acquire() as conn:  # type: ignore[union-attr]
            rows = await conn.fetch(_SQL_WARM_METRICS)

        if not rows:
            return None

        tables = []
        for row in rows:
            tables.append({
                "schema": row["schemaname"],
                "table": row["table_name"],
                "seq_scan": row["seq_scan"],
                "seq_tup_read": row["seq_tup_read"],
                "idx_scan": row["idx_scan"],
                "idx_tup_fetch": row["idx_tup_fetch"],
                "n_tup_ins": row["n_tup_ins"],
                "n_tup_upd": row["n_tup_upd"],
                "n_tup_del": row["n_tup_del"],
                "n_live_tup": row["n_live_tup"],
                "n_dead_tup": row["n_dead_tup"],
                "last_vacuum": row["last_vacuum"].isoformat() if row["last_vacuum"] else None,
                "last_autovacuum": row["last_autovacuum"].isoformat() if row["last_autovacuum"] else None,
                "last_analyze": row["last_analyze"].isoformat() if row["last_analyze"] else None,
                "last_autoanalyze": row["last_autoanalyze"].isoformat() if row["last_autoanalyze"] else None,
            })

        return MetricSample(
            instance_id=self._instance_id,
            sampled_at=now,
            category="warm",
            metrics={"tables": tables},
        )

    async def _collect_cold(self, now: datetime) -> MetricSample | None:
        """Cold metrics: replication lag, vacuum progress, settings (1-minute interval)."""
        async with self._pool.acquire() as conn:  # type: ignore[union-attr]
            # Replication lag
            rep_rows = await conn.fetch(
                "SELECT client_addr::text, state, "
                "EXTRACT(EPOCH FROM replay_lag) AS replay_lag_seconds "
                "FROM pg_stat_replication;"
            )
            # Database size
            db_size = await conn.fetchval(
                "SELECT pg_database_size(current_database());"
            )

        return MetricSample(
            instance_id=self._instance_id,
            sampled_at=now,
            category="cold",
            metrics={
                "replication": [
                    {
                        "client_addr": r["client_addr"],
                        "state": r["state"],
                        "replay_lag_seconds": float(r["replay_lag_seconds"]) if r["replay_lag_seconds"] else None,
                    }
                    for r in rep_rows
                ],
                "database_size_bytes": db_size,
            },
        )

    async def collect_ash(self) -> list[ActiveSessionSample]:
        """Sample active sessions from pg_stat_activity. Returns [] on failure."""
        if self._pool is None:
            logger.warning(
                "adapter.not_connected_ash",
                instance_id=str(self._instance_id),
            )
            return []

        try:
            now = datetime.now(timezone.utc)
            async with self._pool.acquire() as conn:  # type: ignore[union-attr]
                rows = await conn.fetch(_SQL_ASH)

            samples: list[ActiveSessionSample] = []
            for row in rows:
                samples.append(
                    ActiveSessionSample(
                        instance_id=self._instance_id,
                        sampled_at=now,
                        pid=row["pid"],
                        query=row["query"],
                        query_hash=row["query_hash"],
                        state=row["state"] or "unknown",
                        wait_event_type=row["wait_event_type"],
                        wait_event=row["wait_event"],
                        backend_type=row["backend_type"],
                        client_addr=row["client_addr"],
                        application_name=row["application_name"],
                        query_start=row["query_start"],
                        duration_ms=float(row["duration_ms"]) if row["duration_ms"] is not None else None,
                    )
                )
            return samples

        except asyncio.TimeoutError:
            logger.warning(
                "adapter.ash_timeout",
                instance_id=str(self._instance_id),
            )
            return []
        except asyncpg.PostgresError as exc:
            logger.warning(
                "adapter.ash_error",
                instance_id=str(self._instance_id),
                error=str(exc),
            )
            return []

    # Spec: FS-KPI-001 Section 5.1 — Live KPI queries
    async def collect_kpi_extras(self) -> dict | None:
        """Query live KPI data directly from target DB.

        Returns dict with: slow_query_count, active_sessions, numbackends,
        max_connections, lock_waits, avg_response_time_ms, deadlocks.
        Returns None if pool not connected or query fails.

        Note: This uses a read-only connection with statement_timeout=500ms,
        same as all other adapter queries. The query uses subqueries to
        minimize round-trips.
        """
        if self._pool is None:
            logger.warning(
                "adapter.not_connected_kpi",
                instance_id=str(self._instance_id),
            )
            return None

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(_SQL_KPI_EXTRAS)

            if row is None:
                return None

            # pg_stat_statements is optional — query separately to avoid
            # breaking the main KPI query if the extension isn't installed
            avg_rt: float | None = None
            try:
                async with self._pool.acquire() as conn:
                    rt_row = await conn.fetchrow(_SQL_AVG_RESPONSE_TIME)
                    if rt_row and rt_row["avg_response_time_ms"] is not None:
                        avg_rt = float(rt_row["avg_response_time_ms"])
            except (asyncpg.PostgresError, asyncio.TimeoutError):
                pass  # Extension not installed — avg_response_time stays None

            return {
                "slow_query_count": row["slow_query_count"],
                "active_sessions": row["active_sessions"],
                "numbackends": row["numbackends"],
                "max_connections": row["max_connections"],
                "lock_waits": row["lock_waits"],
                "avg_response_time_ms": avg_rt,
                "deadlocks": row["deadlocks"],
            }

        except asyncio.TimeoutError:
            logger.warning(
                "adapter.kpi_timeout",
                instance_id=str(self._instance_id),
            )
            return None
        except asyncpg.PostgresError as exc:
            logger.warning(
                "adapter.kpi_error",
                instance_id=str(self._instance_id),
                error=str(exc),
            )
            return None
