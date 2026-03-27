# Spec: FS-DBA-001 E1
"""DBA Agent Execution Engine — safe SQL execution with pre/post checks.

All write operations go through this engine. Never execute SQL directly.
Pipeline: classify → gate → pre-check → execute → post-check → audit.
"""

from __future__ import annotations

import time
from uuid import UUID, uuid4

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.safety_guard import SafetyGuard
from app.agents.tools.ops_tools import ActionRequest, ActionResult

logger = structlog.get_logger(__name__)

_guard = SafetyGuard()


class ExecutionEngine:
    """Spec: FS-DBA-001 E1 — safe execution engine for DBA Agent.

    Core principle: LLM never touches DB directly.
    All writes go through classify → gate → pre_check → execute → post_check → audit.
    """

    async def execute(
        self,
        request: ActionRequest,
        session: AsyncSession,
        pool,
        autonomy_level: int = 0,
    ) -> ActionResult:
        """Full execution pipeline.

        Args:
            request: ActionRequest from ops_tools.
            session: System DB session (for audit logging).
            pool: asyncpg pool to target DB.
            autonomy_level: Instance autonomy level.

        Returns:
            ActionResult with execution status and before/after state.
        """
        action_id = uuid4()

        # Step 1: Classify risk
        risk = _guard.classify_risk(request.sql, request.action_type)
        request.risk_level = risk.value

        # Step 2: Policy gate
        policy = _guard.check_policy(risk, autonomy_level, request.confidence)

        if policy.action == "blocked":
            logger.warning(
                "execution_engine.blocked",
                action_type=request.action_type,
                reason=policy.reason,
            )
            result = ActionResult(
                action_id=action_id,
                status="blocked",
                error=policy.reason,
            )
            await self._save_action(session, action_id, request, result)
            return result

        if policy.action == "approve_required":
            logger.info(
                "execution_engine.approval_required",
                action_type=request.action_type,
                reason=policy.reason,
            )
            request.requires_approval = True
            result = ActionResult(
                action_id=action_id,
                status="pending",
            )
            await self._save_action(session, action_id, request, result)
            return result

        # Step 3: Pre-check (EXPLAIN cost)
        before_state = await self._pre_check(pool, request.sql)

        # Step 4: Execute with timeout
        start = time.monotonic()
        try:
            rows_affected = await self._execute_with_timeout(pool, request.sql)
            elapsed_ms = int((time.monotonic() - start) * 1000)
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "execution_engine.failed",
                action_type=request.action_type,
                error=str(exc),
                elapsed_ms=elapsed_ms,
            )
            result = ActionResult(
                action_id=action_id,
                status="failed",
                execution_time_ms=elapsed_ms,
                before_state=before_state,
                error=str(exc),
            )
            await self._save_action(session, action_id, request, result)
            await self._audit_log(session, request, result)
            return result

        # Step 5: Post-check
        after_state = await self._post_check(pool, request.action_type)

        result = ActionResult(
            action_id=action_id,
            status="executed",
            execution_time_ms=elapsed_ms,
            rows_affected=rows_affected,
            before_state=before_state,
            after_state=after_state,
        )

        # Step 6: Audit log
        await self._save_action(session, action_id, request, result)
        await self._audit_log(session, request, result)

        logger.info(
            "execution_engine.success",
            action_type=request.action_type,
            elapsed_ms=elapsed_ms,
            rows_affected=rows_affected,
        )
        return result

    async def execute_approved(
        self,
        action_id: UUID,
        session: AsyncSession,
        pool,
        approved_by: UUID,
    ) -> ActionResult:
        """Execute a previously pending action after human approval.

        Spec: FS-DBA-001 AC-14.
        """
        # Load pending action from DB
        row = await session.execute(
            text("SELECT * FROM agent_actions WHERE id = :id AND status = 'pending'"),
            {"id": action_id},
        )
        action = row.mappings().first()
        if not action:
            return ActionResult(
                action_id=action_id,
                status="failed",
                error="Action not found or not in pending status.",
            )

        sql = action["sql_command"]
        before_state = await self._pre_check(pool, sql)

        start = time.monotonic()
        try:
            rows_affected = await self._execute_with_timeout(pool, sql)
            elapsed_ms = int((time.monotonic() - start) * 1000)
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            await session.execute(
                text(
                    "UPDATE agent_actions SET status='failed', "
                    "error=:err, executed_at=NOW() WHERE id=:id"
                ),
                {"id": action_id, "err": str(exc)},
            )
            await session.commit()
            return ActionResult(action_id=action_id, status="failed", error=str(exc))

        after_state = await self._post_check(pool, action["action_type"])

        await session.execute(
            text("""
                UPDATE agent_actions SET
                    status='executed', approved_by=:by, approved_at=NOW(), executed_at=NOW(),
                    execution_time_ms=:ms, rows_affected=:rows,
                    before_state=CAST(:before AS jsonb), after_state=CAST(:after AS jsonb)
                WHERE id=:id
            """),
            {
                "id": action_id,
                "by": approved_by,
                "ms": elapsed_ms,
                "rows": rows_affected,
                "before": _to_json(before_state),
                "after": _to_json(after_state),
            },
        )
        await session.commit()

        return ActionResult(
            action_id=action_id,
            status="executed",
            execution_time_ms=elapsed_ms,
            rows_affected=rows_affected,
            before_state=before_state,
            after_state=after_state,
        )

    async def _pre_check(self, pool, sql: str) -> dict:
        """Spec: FS-DBA-001 AC-2 — EXPLAIN cost estimate before execution.

        Finding 5: Reject multi-statement SQL before EXPLAIN.
        Uses EXPLAIN (not ANALYZE) to avoid actual execution.
        """
        try:
            explain_sql = sql.strip().rstrip(";")
            # Security: reject multi-statement
            if ";" in explain_sql:
                return {}
            if explain_sql.upper().startswith(("SELECT", "INSERT", "UPDATE", "DELETE")):
                async with pool.acquire() as conn:
                    # Wrap in read-only transaction for safety
                    async with conn.transaction(readonly=True):
                        rows = await conn.fetch(f"EXPLAIN (FORMAT JSON) {explain_sql}")
                    if rows:
                        import json

                        plan = json.loads(rows[0][0])
                        return {
                            "plan_cost": plan[0].get("Plan", {}).get("Total Cost"),
                            "plan_rows": plan[0].get("Plan", {}).get("Plan Rows"),
                        }
        except Exception:
            pass
        return {}

    async def _execute_with_timeout(self, pool, sql: str, timeout_sec: int = 30) -> int:
        """Execute SQL with statement_timeout in explicit transaction.

        Finding 7: SET LOCAL requires transaction context.
        Finding 1: Reject multi-statement SQL.
        """
        # Security: reject semicolons (multi-statement)
        if ";" in sql.strip().rstrip(";"):
            raise ValueError("Multi-statement SQL rejected for safety.")

        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    f"SET LOCAL statement_timeout = '{int(timeout_sec) * 1000}'"
                )
                result = await conn.execute(sql)
                if isinstance(result, str):
                    return 0
                return 0

    async def _post_check(self, pool, action_type: str) -> dict:
        """Spec: FS-DBA-001 AC-3 — verify execution result."""
        try:
            if action_type == "create_index":
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT indexname, indexdef FROM pg_indexes ORDER BY indexname DESC LIMIT 1"
                    )
                    if rows:
                        return {"last_index": rows[0]["indexname"]}
            elif action_type in ("vacuum", "vacuum_full"):
                async with pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT last_vacuum, last_autovacuum FROM pg_stat_user_tables LIMIT 1"
                    )
                    if rows:
                        return {"last_vacuum": str(rows[0]["last_vacuum"])}
        except Exception:
            pass
        return {}

    async def _save_action(
        self, session: AsyncSession, action_id: UUID, request: ActionRequest, result: ActionResult
    ) -> None:
        """Save action to agent_actions table."""
        import json

        try:
            await session.execute(
                text("""
                    INSERT INTO agent_actions
                        (id, instance_id, action_type, sql_command, description, risk_level,
                         status, requested_by, confidence, estimated_impact,
                         execution_time_ms, rows_affected, before_state, after_state, error)
                    VALUES
                        (:id, :iid, :atype, :sql, :desc, :risk,
                         :status, :by, :conf, :impact,
                         :ms, :rows, CAST(:before AS jsonb), CAST(:after AS jsonb), :err)
                """),
                {
                    "id": action_id,
                    "iid": request.instance_id,
                    "atype": request.action_type,
                    "sql": request.sql,
                    "desc": request.description,
                    "risk": request.risk_level,
                    "status": result.status,
                    "by": request.requested_by,
                    "conf": request.confidence,
                    "impact": request.estimated_impact,
                    "ms": result.execution_time_ms,
                    "rows": result.rows_affected,
                    "before": json.dumps(result.before_state) if result.before_state else None,
                    "after": json.dumps(result.after_state) if result.after_state else None,
                    "err": result.error,
                },
            )
            await session.flush()
        except Exception as exc:
            # Finding 6: For DANGEROUS+, audit failure must be flagged
            if request.risk_level in ("dangerous", "critical"):
                logger.critical(
                    "execution_engine.AUDIT_FAILED_DANGEROUS",
                    action_type=request.action_type,
                    sql=request.sql[:100],
                    error=str(exc),
                )
            else:
                logger.error("execution_engine.save_failed", error=str(exc))

    async def _audit_log(
        self,
        session: AsyncSession,
        request: ActionRequest,
        result: ActionResult,
    ) -> None:
        """Spec: FS-DBA-001 AC-4 — AI Decision Log."""
        try:
            from app.utils.ai_logger import build_ai_details, create_ai_decision_log

            details = build_ai_details(
                ai_model="dba-agent",
                inference_time_ms=result.execution_time_ms or 0,
                decision=result.status,
                confidence=request.confidence,
                input_summary={"action_type": request.action_type, "sql": request.sql[:200]},
                output_summary={"rows_affected": result.rows_affected, "error": result.error},
            )
            details["risk_level"] = request.risk_level
            details["approval_status"] = result.status
            await create_ai_decision_log(
                session,
                resource_type="dba_agent_action",
                resource_id=str(request.instance_id),
                details=details,
            )
        except Exception as exc:
            logger.error("execution_engine.audit_failed", error=str(exc))


def _to_json(data: dict | None) -> str | None:
    if data is None:
        return None
    import json

    return json.dumps(data, default=str)
