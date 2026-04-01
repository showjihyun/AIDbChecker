# Spec: FS-DBA-005
"""Claude Native Tool Use Agent — replaces ReAct text parsing with SDK tool_use.

Uses Anthropic AsyncAnthropic client directly for structured tool calling.
Falls back to LangChain ReAct if Anthropic is unavailable.
"""

from __future__ import annotations

import time
from uuid import UUID

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# Spec: FS-DBA-005 §2.1 — System prompt (Korean DBA expert)
_SYSTEM_PROMPT = """\
당신은 PostgreSQL 성능 분석 전문 DBA입니다.

사용자의 질문에 대해 제공된 도구를 사용하여 실제 DB 데이터를 수집하고,
구체적이고 실용적인 분석 결과를 제공합니다.

규칙:
- 반드시 한국어로 답변하세요.
- 분석은 [현황] → [원인 분석] → [권장 조치] 구조로 작성하세요.
- 추천 액션에는 실행 가능한 SQL을 포함하세요.
- 수치 데이터(ms, %, 건수)를 적극 활용하세요.
- 도구 실행 결과가 없으면 "데이터 없음"으로 명시하세요.
- DBA 용어를 사용하세요: 풀스캔, 인덱스, 버퍼히트율, 데드튜플, 블로킹 등.
"""

# Spec: FS-DBA-005 §2.2 — Tool definitions for Anthropic API
TOOL_DEFINITIONS = [
    {
        "name": "slow_queries",
        "description": "pg_stat_statements에서 실행 시간이 긴 Top-N 쿼리를 조회합니다. 느린 쿼리, 성능 분석 시 사용.",
        "input_schema": {
            "type": "object",
            "properties": {
                "top_n": {
                    "type": "integer",
                    "description": "조회할 상위 쿼리 수 (기본: 10)",
                    "default": 10,
                }
            },
        },
    },
    {
        "name": "explain_query",
        "description": "SELECT 쿼리의 실행 계획(EXPLAIN ANALYZE)을 확인합니다. 풀스캔, 인덱스 사용 여부 분석 시 사용.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "분석할 SELECT SQL 쿼리",
                }
            },
            "required": ["sql"],
        },
    },
    {
        "name": "index_recommendations",
        "description": "테이블의 순차스캔/인덱스스캔 비율을 분석하고 인덱스 추천. 테이블명 없으면 전체 분석.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "분석할 테이블명 (빈 문자열이면 전체 테이블)",
                    "default": "",
                }
            },
        },
    },
    {
        "name": "parameter_tuning",
        "description": "PostgreSQL 설정 파라미터(shared_buffers, work_mem 등)를 분석하고 최적값 추천.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "table_bloat",
        "description": "테이블의 데드 튜플, 블로트 비율을 분석하고 VACUUM 추천. 테이블명 없으면 전체 분석.",
        "input_schema": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "분석할 테이블명 (빈 문자열이면 전체)",
                    "default": "",
                }
            },
        },
    },
    {
        "name": "lock_analysis",
        "description": "현재 Lock 대기 및 블로킹 세션을 분석합니다. 데드락, 장시간 대기 확인 시 사용.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "connection_analysis",
        "description": "커넥션 풀 효율, idle 세션, max_connections 사용률을 분석합니다.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


class NativeToolAgent:
    """Anthropic Native Tool Use Agent for PostgreSQL DBA analysis.

    Spec: FS-DBA-005
    """

    def __init__(self, pool=None):
        self.pool = pool
        self._tools_used: list[str] = []

    async def analyze(
        self,
        question: str,
        instance_id: UUID,
        max_iterations: int = 8,
    ) -> dict:
        """Run analysis using Claude native tool_use.

        Returns dict with: analysis, actions, tools_used, model, duration_ms
        """
        start = time.monotonic()

        # AC-6: Fallback if Anthropic not available
        if not settings.ANTHROPIC_API_KEY:
            return await self._fallback_react(question, instance_id, max_iterations)

        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            return await self._fallback_react(question, instance_id, max_iterations)

        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        model = settings.AI_MODEL if "claude" in settings.AI_MODEL else "claude-sonnet-4-6"

        messages: list[dict] = [
            {"role": "user", "content": question},
        ]

        self._tools_used = []
        iterations = 0

        try:
            # AC-1/3: Native tool_use loop
            response = await client.messages.create(
                model=model,
                max_tokens=4096,  # AC-4: expanded from 1500
                system=_SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            while response.stop_reason == "tool_use" and iterations < max_iterations:
                iterations += 1

                # Process all tool_use blocks
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        self._tools_used.append(block.name)
                        result = await self._invoke_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                # Append assistant response + tool results
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

                # Next LLM call
                response = await client.messages.create(
                    model=model,
                    max_tokens=4096,
                    system=_SYSTEM_PROMPT,
                    tools=TOOL_DEFINITIONS,
                    messages=messages,
                )

            # AC-5: Extract final text answer
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text

            duration_ms = int((time.monotonic() - start) * 1000)

            return {
                "analysis": final_text,
                "actions": [],  # Claude will recommend in text, parse if needed
                "tools_used": list(set(self._tools_used)),
                "iterations": iterations + 1,
                "model": model,
                "duration_ms": duration_ms,
            }

        except Exception as exc:
            logger.warning("native_tool_agent.failed", error=str(exc))
            # AC-6: Fallback to ReAct
            return await self._fallback_react(question, instance_id, max_iterations)

    async def _invoke_tool(self, name: str, input_data: dict) -> str:
        """Execute a DB diagnostic tool and return string result."""
        from app.agents.tools.db_tools import (
            connection_analysis,
            explain_query,
            index_recommendations,
            lock_analysis,
            parameter_tuning,
            slow_queries,
            table_bloat,
        )

        tool_map = {
            "slow_queries": lambda: slow_queries(self.pool, input_data.get("top_n", 10)),
            "explain_query": lambda: explain_query(self.pool, input_data.get("sql", "")),
            "index_recommendations": lambda: index_recommendations(
                self.pool, input_data.get("table_name") or None
            ),
            "parameter_tuning": lambda: parameter_tuning(self.pool),
            "table_bloat": lambda: table_bloat(
                self.pool, input_data.get("table_name") or None
            ),
            "lock_analysis": lambda: lock_analysis(self.pool),
            "connection_analysis": lambda: connection_analysis(self.pool),
        }

        handler = tool_map.get(name)
        if not handler:
            return f"Unknown tool: {name}"

        try:
            result = await handler()
            return str(result)[:3000]  # Limit tool output
        except Exception as exc:
            return f"도구 실행 오류 ({name}): {exc}"

    async def _fallback_react(
        self, question: str, instance_id: UUID, max_iterations: int
    ) -> dict:
        """AC-6: Fallback to existing LangChain ReAct agent."""
        from app.agents.tuning_agent import DBTuningAgent
        from app.services.llm_provider import LLMProviderManager

        start = time.monotonic()
        mgr = LLMProviderManager()
        llm = mgr.get_llm()
        agent = DBTuningAgent(llm=llm, pool=self.pool)
        result = await agent.analyze(question, instance_id, max_iterations)

        duration_ms = int((time.monotonic() - start) * 1000)

        analysis = getattr(result, "analysis", str(result))
        actions = getattr(result, "actions", [])

        return {
            "analysis": analysis,
            "actions": [a.model_dump() if hasattr(a, "model_dump") else a for a in actions],
            "tools_used": getattr(result, "tools_used", []),
            "iterations": getattr(result, "iterations", 0),
            "model": getattr(result, "model_used", settings.AI_MODEL),
            "duration_ms": duration_ms,
        }
