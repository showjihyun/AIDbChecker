# Spec: FS-DBA-002
"""Unified DBA Agent — single interface routing to sub-agents.

Intent Classification: keyword-first, LLM fallback.
Sub-agents: TuningAgent, CopilotAgent, ExecutionEngine, NL2SQL, SystemHealth.
Session context: Valkey (30min TTL, last 5 turns).
"""

from __future__ import annotations

import re
import time
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.schemas.dba import ActionSummary, DBAResponse

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Intent keywords — Spec: FS-DBA-002 §2.1
# ---------------------------------------------------------------------------

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "analyze": [
        "느린",
        "느려",
        "slow",
        "성능",
        "performance",
        "쿼리 분석",
        "query analysis",
        "bloat",
        "튜닝",
        "추천",
        "tuning",
        "explain",
        "plan",
        "비효율",
        "개선",
        "왜 느",
    ],
    "diagnose": [
        "장애",
        "원인",
        "rca",
        "진단",
        "diagnose",
        "incident",
        "이상",
        "anomaly",
        "why",
        "왜",
        "문제",
        "error",
        "에러",
    ],
    "execute": [
        "실행",
        "execute",
        "만들어",
        "생성",
        "create index",
        "vacuum",
        "kill",
        "terminate",
        "alter system",
        "reindex",
    ],
    "query": [
        "조회",
        "select",
        "보여줘",
        "show",
        "list",
        "count",
        "몇 개",
        "how many",
        "가져와",
        "알려줘",
        "recent",
        "latest",
        "최근",
    ],
    "status": [
        "상태",
        "health",
        "status",
        "정상",
        "점검",
        "check",
        "헬스",
        "alive",
        "up",
        "down",
    ],
}

_INTENT_PROMPT = """You are a DBA Agent intent classifier.
Classify the user's question into exactly one category:
- analyze: performance analysis, slow query, index, tuning
- diagnose: incident investigation, root cause, anomaly
- execute: run a DB operation (create index, vacuum, kill session)
- query: data retrieval, show/list/count information
- status: system health check, DB status

Question: {question}
Answer with one word only: analyze, diagnose, execute, query, or status"""


class DBAAgent:
    """Spec: FS-DBA-002 — unified DBA Agent with intent routing.

    Single entry point: ask(question, instance_id).
    Routes to: TuningAgent | CopilotAgent | ExecutionEngine | NL2SQL | Health.
    """

    def classify_intent(self, question: str) -> tuple[str, bool]:
        """Classify user intent via keyword matching.

        Returns:
            (intent, is_confident): intent string and whether
            keyword match was unambiguous.
        """
        q_lower = question.lower()
        scores: dict[str, int] = {}

        for intent, keywords in _INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in q_lower)
            if score > 0:
                scores[intent] = score

        if not scores:
            return "analyze", False  # default, not confident

        sorted_intents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top = sorted_intents[0]

        # Confident if top score is 2+ ahead of second
        if len(sorted_intents) == 1 or top[1] >= sorted_intents[1][1] + 2:
            return top[0], True

        return top[0], False  # ambiguous

    async def classify_intent_with_llm(self, question: str) -> str:
        """LLM fallback for ambiguous intent classification.

        Spec: FS-DBA-002 §2.2.
        """
        try:
            from app.services.llm_provider import LLMProviderManager

            mgr = LLMProviderManager()
            llm = mgr.get_llm()
            if llm is None:
                return "analyze"

            from langchain_core.messages import HumanMessage

            prompt = _INTENT_PROMPT.format(question=question)
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            raw = response.content if hasattr(response, "content") else str(response)
            intent = raw.strip().lower().split()[0]

            if intent in _INTENT_KEYWORDS:
                return intent
            return "analyze"
        except Exception as exc:
            logger.warning("dba_agent.intent_llm_failed", error=str(exc))
            return "analyze"

    async def ask(
        self,
        question: str,
        instance_id: UUID,
        session: AsyncSession,
        pool=None,
        autonomy_level: int = 0,
    ) -> DBAResponse:
        """Spec: FS-DBA-002 AC-1 — unified DBA Agent entry point.

        Classifies intent, routes to sub-agent, returns unified response.
        """
        session_id = uuid4()
        start = time.monotonic()

        # Step 1: Intent classification
        intent, confident = self.classify_intent(question)
        if not confident:
            intent = await self.classify_intent_with_llm(question)

        logger.info(
            "dba_agent.classified",
            intent=intent,
            confident=confident,
            question=question[:80],
        )

        # Step 2: Route to sub-agent
        try:
            if intent == "analyze":
                response = await self._handle_analyze(question, instance_id, pool)
            elif intent == "diagnose":
                response = await self._handle_diagnose(question, instance_id, session, pool)
            elif intent == "execute":
                response = await self._handle_execute(
                    question,
                    instance_id,
                    session,
                    pool,
                    autonomy_level,
                )
            elif intent == "query":
                response = await self._handle_query(question, instance_id, session)
            elif intent == "status":
                response = await self._handle_status()
            else:
                response = DBAResponse(
                    session_id=session_id,
                    intent=intent,
                    answer="질문을 이해하지 못했습니다.",
                )
        except Exception as exc:
            logger.error(
                "dba_agent.route_failed",
                intent=intent,
                error=str(exc),
            )
            response = DBAResponse(
                session_id=session_id,
                intent=intent,
                answer=f"처리 중 오류가 발생했습니다: {exc}",
            )

        elapsed = int((time.monotonic() - start) * 1000)
        response.session_id = session_id
        response.intent = intent
        response.processing_time_ms = elapsed
        return response

    # ------------------------------------------------------------------
    # Sub-agent handlers
    # ------------------------------------------------------------------

    async def _handle_analyze(self, question: str, instance_id: UUID, pool) -> DBAResponse:
        """Route to DBTuningAgent."""
        from app.agents.tuning_agent import DBTuningAgent
        from app.services.llm_provider import LLMProviderManager

        mgr = LLMProviderManager()
        llm = mgr.get_llm()
        agent = DBTuningAgent(llm=llm, pool=pool)
        result = await agent.analyze(question, instance_id)

        # result may be TuningResponse or str
        answer_text = result.summary if hasattr(result, "summary") else str(result)
        actions = self._extract_actions_from_text(answer_text, instance_id)
        model = settings.AI_MODEL

        return DBAResponse(
            session_id=uuid4(),
            intent="analyze",
            answer=answer_text,
            actions=actions if actions else None,
            model=model,
        )

    async def _handle_diagnose(
        self,
        question: str,
        instance_id: UUID,
        session: AsyncSession,
        pool,
    ) -> DBAResponse:
        """Route to DBCopilotAgent."""
        from app.agents.copilot_agent import DBCopilotAgent
        from app.services.llm_provider import LLMProviderManager

        mgr = LLMProviderManager()
        llm = mgr.get_llm()
        agent = DBCopilotAgent(llm=llm)
        result = await agent.diagnose(instance_id=instance_id, incident_id=None)

        conf = getattr(result, "confidence", 0.0)
        actions_list = getattr(result, "suggested_actions", [])
        answer = (
            f"진단 결과: {result.selected_branch}\n"
            f"Confidence: {conf:.2f}\n"
            f"추천: {', '.join(actions_list or [])}"
        )

        return DBAResponse(
            session_id=uuid4(),
            intent="diagnose",
            answer=answer,
            data=result.model_dump() if hasattr(result, "model_dump") else {},
            model=settings.AI_MODEL,
        )

    async def _handle_execute(
        self,
        question: str,
        instance_id: UUID,
        session: AsyncSession,
        pool,
        autonomy_level: int,
    ) -> DBAResponse:
        """Parse action from question, route to ExecutionEngine."""
        from app.agents.execution_engine import ExecutionEngine

        action = self._parse_action_request(question, instance_id)
        if action is None:
            return DBAResponse(
                session_id=uuid4(),
                intent="execute",
                answer=(
                    "실행할 작업을 파악하지 못했습니다. "
                    "예: 'orders 테이블에 user_id 인덱스 만들어줘'"
                ),
            )

        engine = ExecutionEngine()
        result = await engine.execute(action, session, pool, autonomy_level)

        actions = [
            ActionSummary(
                action_id=result.action_id,
                action_type=action.action_type,
                sql=action.sql,
                risk_level=action.risk_level,
                status=result.status,
                description=action.description,
            )
        ]

        if result.status == "pending":
            answer = (
                f"승인이 필요합니다.\n"
                f"작업: {action.description}\n"
                f"위험도: {action.risk_level}\n"
                f"SQL: {action.sql}"
            )
        elif result.status == "executed":
            answer = f"실행 완료.\n{action.description}\n소요: {result.execution_time_ms}ms"
        elif result.status == "blocked":
            answer = f"차단됨: {result.error}"
        else:
            answer = f"상태: {result.status}"

        return DBAResponse(
            session_id=uuid4(),
            intent="execute",
            answer=answer,
            actions=actions,
        )

    async def _handle_query(
        self, question: str, instance_id: UUID, session: AsyncSession
    ) -> DBAResponse:
        """Route to NL2SQL (GraphRAG)."""
        from app.services.nl2sql import (
            execute_readonly_sql,
            generate_sql_with_graph,
            get_model_name,
        )

        sql = await generate_sql_with_graph(question, instance_id, session)
        columns, rows, exec_ms = await execute_readonly_sql(session, sql)

        answer = f"SQL: {sql}\n결과: {len(rows)}행 반환 ({exec_ms}ms)"
        data = {"sql": sql, "columns": columns, "rows": rows[:20]}

        return DBAResponse(
            session_id=uuid4(),
            intent="query",
            answer=answer,
            data=data,
            model=get_model_name(),
        )

    async def _handle_status(self) -> DBAResponse:
        """Route to System Health."""
        from app.api.v1.system import (
            _check_celery,
            _check_db,
            _check_valkey,
        )

        db = await _check_db()
        valkey = await _check_valkey()
        celery = await _check_celery()

        if db == "down":
            overall = "unhealthy"
        elif all(s == "up" for s in [db, valkey, celery]):
            overall = "healthy"
        else:
            overall = "degraded"

        answer = f"System: {overall}\nDB: {db}, Valkey: {valkey}, Celery: {celery}"

        return DBAResponse(
            session_id=uuid4(),
            intent="status",
            answer=answer,
            data={
                "db": db,
                "valkey": valkey,
                "celery": celery,
                "status": overall,
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_action_request(self, question: str, instance_id: UUID):
        """Extract ActionRequest from natural language."""
        from app.agents.tools.ops_tools import (
            analyze_table,
            create_index,
            kill_session,
            vacuum_table,
        )

        q = question.lower()

        # CREATE INDEX pattern
        m = re.search(
            r"(?:인덱스|index).*?(\w+)\s*(?:테이블|table)?.*?(\w+)",
            q,
        )
        if ("인덱스" in q or "index" in q) and m:
            return create_index(instance_id, m.group(1), [m.group(2)])

        # VACUUM pattern
        if "vacuum" in q:
            full = "full" in q
            table_m = re.search(r"vacuum\s+(?:full\s+)?(\w+)", q)
            table = table_m.group(1) if table_m else "unknown"
            return vacuum_table(instance_id, table, full=full)

        # KILL pattern
        pid_m = re.search(r"(?:kill|terminate).*?(\d+)", q)
        if pid_m:
            return kill_session(instance_id, int(pid_m.group(1)))

        # ANALYZE pattern
        if "analyze" in q or "통계" in q:
            table_m = re.search(r"(?:analyze|통계)\s+(\w+)", q)
            table = table_m.group(1) if table_m else "unknown"
            return analyze_table(instance_id, table)

        return None

    def _extract_actions_from_text(self, text: str, instance_id: UUID) -> list[ActionSummary]:
        """Extract suggested actions from TuningAgent output."""
        actions = []
        if "CREATE INDEX" in text.upper():
            actions.append(
                ActionSummary(
                    action_type="create_index",
                    sql="(parsed from recommendation)",
                    risk_level="warning",
                    status="suggested",
                    description="Index creation suggested by Tuning Agent",
                )
            )
        if "VACUUM" in text.upper():
            actions.append(
                ActionSummary(
                    action_type="vacuum",
                    sql="(parsed from recommendation)",
                    risk_level="warning",
                    status="suggested",
                    description="VACUUM suggested by Tuning Agent",
                )
            )
        return actions
