# Spec: FS-DBA-001 Tier 2 — J2: Action History Memory
"""Remember past agent actions and their outcomes for context-aware decisions.

DBA principle: "지난번에 이 테이블 VACUUM 했더니 2시간 걸렸다" = 경험.
Agent도 동일한 경험을 쌓아서 다음 판단에 활용.

Storage: agent_actions table (PostgreSQL).
Context: last N actions for the same instance → LLM prompt에 삽입.
"""

from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

MAX_HISTORY = 5  # 최근 5개 action만 컨텍스트에 포함


class ActionMemory:
    """Retrieve and format past agent actions for LLM context."""

    async def get_context(
        self, session: AsyncSession, instance_id: UUID, limit: int = MAX_HISTORY
    ) -> str:
        """Fetch recent actions for an instance and format as LLM context.

        Returns a text block suitable for inserting into a prompt:
        "Past DBA actions on this instance: ..."
        """
        actions = await self._fetch_recent(session, instance_id, limit)
        if not actions:
            return "No previous DBA agent actions on this instance."

        lines = [f"Past {len(actions)} DBA agent actions on this instance:"]
        for a in actions:
            status_icon = {
                "executed": "OK",
                "failed": "FAIL",
                "blocked": "BLOCKED",
                "rejected": "REJECTED",
            }.get(a["status"], a["status"])

            line = f"  [{status_icon}] {a['action_type']}: {a['description'][:80]}"
            if a["execution_time_ms"]:
                line += f" ({a['execution_time_ms']}ms)"
            if a["error"]:
                line += f" — error: {a['error'][:50]}"
            lines.append(line)

        return "\n".join(lines)

    async def get_similar_actions(
        self, session: AsyncSession, instance_id: UUID, action_type: str
    ) -> list[dict]:
        """Find past actions of the same type on this instance.

        Useful for: "지난번에 이 테이블 인덱스 만들었을 때 얼마나 걸렸지?"
        """
        try:
            result = await session.execute(
                text("""
                    SELECT action_type, description, status,
                           execution_time_ms, error,
                           created_at
                    FROM agent_actions
                    WHERE instance_id = :iid AND action_type = :atype
                    ORDER BY created_at DESC
                    LIMIT 3
                """),
                {"iid": instance_id, "atype": action_type},
            )
            return [dict(r._mapping) for r in result.fetchall()]
        except Exception as exc:
            logger.debug("action_memory.similar_failed", error=str(exc))
            return []

    async def _fetch_recent(
        self, session: AsyncSession, instance_id: UUID, limit: int
    ) -> list[dict]:
        """Fetch the most recent actions from agent_actions table."""
        try:
            result = await session.execute(
                text("""
                    SELECT action_type, description, status,
                           execution_time_ms, error, risk_level,
                           created_at
                    FROM agent_actions
                    WHERE instance_id = :iid
                    ORDER BY created_at DESC
                    LIMIT :lim
                """),
                {"iid": instance_id, "lim": limit},
            )
            return [dict(r._mapping) for r in result.fetchall()]
        except Exception as exc:
            logger.debug("action_memory.fetch_failed", error=str(exc))
            return []
