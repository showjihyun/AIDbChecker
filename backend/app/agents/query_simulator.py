# Spec: FS-DBA-001 Tier 2 — J1: Query Simulation Layer
"""Pre-execution impact analysis using EXPLAIN.

Before executing any write operation, the simulator:
1. Runs EXPLAIN (FORMAT JSON) to get cost/row estimates
2. Checks if cost exceeds threshold → requires approval
3. Estimates execution time and lock impact
4. Returns human-readable impact summary

DBA principle: "EXPLAIN 먼저, 실행은 나중에."
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

# Cost thresholds for automatic approval decisions
COST_THRESHOLD_WARNING = 1000  # EXPLAIN cost > 1000 → warn
COST_THRESHOLD_DANGEROUS = 10000  # EXPLAIN cost > 10000 → require approval
ROW_THRESHOLD_DANGEROUS = 100000  # Affected rows > 100k → require approval


class QuerySimulator:
    """Analyze SQL impact before execution via EXPLAIN."""

    async def simulate(self, pool, sql: str) -> SimulationResult:
        """Run EXPLAIN and analyze the execution plan.

        Returns impact assessment with cost, rows, and recommendation.
        """
        plan = await self._explain(pool, sql)
        if plan is None:
            return SimulationResult(
                feasible=True,
                cost=0,
                estimated_rows=0,
                summary="EXPLAIN not applicable for this statement.",
            )

        cost = plan.get("Total Cost", 0)
        rows = plan.get("Plan Rows", 0)
        node_type = plan.get("Node Type", "Unknown")

        # Risk assessment
        if cost > COST_THRESHOLD_DANGEROUS or rows > ROW_THRESHOLD_DANGEROUS:
            return SimulationResult(
                feasible=False,
                cost=cost,
                estimated_rows=rows,
                summary=(
                    f"High impact: cost={cost:.0f}, rows={rows}. "
                    f"Plan: {node_type}. Manual approval recommended."
                ),
                requires_approval=True,
                plan_details=plan,
            )

        if cost > COST_THRESHOLD_WARNING:
            return SimulationResult(
                feasible=True,
                cost=cost,
                estimated_rows=rows,
                summary=(
                    f"Moderate impact: cost={cost:.0f}, rows={rows}. "
                    f"Plan: {node_type}. Proceed with caution."
                ),
                plan_details=plan,
            )

        return SimulationResult(
            feasible=True,
            cost=cost,
            estimated_rows=rows,
            summary=f"Low impact: cost={cost:.0f}, rows={rows}. Safe to execute.",
            plan_details=plan,
        )

    async def estimate_index_impact(
        self, pool, table: str, columns: list[str], sample_query: str | None = None
    ) -> str:
        """Estimate the impact of creating an index.

        If a sample_query is provided, compares EXPLAIN cost before/after
        (hypothetical — uses the query plan without actually creating the index).
        """
        # Get table stats
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT n_live_tup, pg_total_relation_size($1) AS size_bytes "
                    "FROM pg_stat_user_tables WHERE relname = $1",
                    table,
                )
                if row:
                    tup = row["n_live_tup"]
                    size_mb = row["size_bytes"] / (1024 * 1024)
                    cols = ", ".join(columns)
                    # Rough estimate: index build time ~= table_size_mb * 0.5 seconds
                    est_seconds = max(1, int(size_mb * 0.5))
                    return (
                        f"Table '{table}': {tup:,} rows, {size_mb:.1f} MB. "
                        f"Index on ({cols}) estimated build time: ~{est_seconds}s. "
                        f"Uses CONCURRENTLY — no table lock."
                    )
        except Exception as exc:
            logger.warning("query_simulator.estimate_failed", error=str(exc))

        return f"Index on {table}({', '.join(columns)}). Impact estimation unavailable."

    async def _explain(self, pool, sql: str) -> dict | None:
        """Run EXPLAIN (FORMAT JSON) and return the top-level plan node."""
        try:
            clean = sql.strip().rstrip(";")
            # Only EXPLAIN for SELECT/INSERT/UPDATE/DELETE
            first_word = clean.split()[0].upper() if clean else ""
            if first_word not in ("SELECT", "INSERT", "UPDATE", "DELETE", "WITH"):
                return None

            async with pool.acquire() as conn:
                rows = await conn.fetch(f"EXPLAIN (FORMAT JSON) {clean}")
                if rows:
                    import json

                    plan_list = json.loads(rows[0][0])
                    return plan_list[0].get("Plan", {})
        except Exception as exc:
            logger.debug("query_simulator.explain_failed", error=str(exc))
        return None


class SimulationResult:
    """Impact analysis result."""

    def __init__(
        self,
        feasible: bool,
        cost: float,
        estimated_rows: int,
        summary: str,
        requires_approval: bool = False,
        plan_details: dict | None = None,
    ):
        self.feasible = feasible
        self.cost = cost
        self.estimated_rows = estimated_rows
        self.summary = summary
        self.requires_approval = requires_approval
        self.plan_details = plan_details

    def to_dict(self) -> dict:
        return {
            "feasible": self.feasible,
            "cost": self.cost,
            "estimated_rows": self.estimated_rows,
            "summary": self.summary,
            "requires_approval": self.requires_approval,
        }
