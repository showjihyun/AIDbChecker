# Spec: FS-AI-TUNE-001
"""DB Performance Tuning Agent — LangChain ReAct agent with 7 PostgreSQL tools.

The agent uses a Thought-Action-Observation loop to autonomously analyse
database performance and recommend tuning actions.  All DB access is strictly
read-only; the agent *recommends* SQL but never executes write statements.
"""

from __future__ import annotations

import json
import time
from uuid import UUID

import asyncpg
import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool

from app.agents.tools.db_tools import (
    connection_analysis,
    explain_query,
    index_recommendations,
    lock_analysis,
    parameter_tuning,
    slow_queries,
    table_bloat,
)
from app.schemas.tuning import TuningAction, TuningResponse

logger = structlog.get_logger(__name__)

# Spec: FS-AI-TUNE-001 Section 2 -- ReAct system prompt
_SYSTEM_PROMPT = """\
You are a PostgreSQL performance tuning expert.  You have access to 7 diagnostic
tools that query a live PostgreSQL database (read-only).  Use them to analyse
the user's question and provide concrete recommendations.

WORKFLOW:
1. Understand the user's question.
2. Call the most relevant tools to gather evidence.
3. Synthesise findings into a clear analysis.
4. Recommend specific actions with executable SQL where applicable.

RULES:
- You ONLY analyse and recommend.  You NEVER execute ALTER, CREATE, DROP, etc.
- Each recommended action must include: action_type, description, sql (if any),
  risk_level (low/medium/high), and estimated_impact.
- action_type is one of: CREATE_INDEX, VACUUM, ALTER_SYSTEM, KILL_SESSION,
  REWRITE_QUERY, OTHER.
- Format your FINAL answer as JSON with keys: "analysis" (string) and
  "actions" (list of objects with the fields above).
- If a tool returns an error, mention it in your analysis and move on.
- Keep your analysis concise but thorough.
"""


class DBTuningAgent:
    """ReAct-style agent that wraps 7 DB diagnostic tools.

    Spec: FS-AI-TUNE-001 Section 2
    """

    def __init__(self, llm, pool: asyncpg.Pool) -> None:  # noqa: ANN001
        self.llm = llm
        self.pool = pool
        self._tools: list[StructuredTool] = []
        self._build_tools()

    # ------------------------------------------------------------------
    # Tool construction
    # ------------------------------------------------------------------

    def _build_tools(self) -> None:
        """Wrap each DB tool function as a LangChain StructuredTool.

        The asyncpg pool is baked into each tool via ``functools.partial``
        so the LLM only sees the user-facing parameters.
        """
        pool = self.pool

        # Helper: create an async wrapper that binds pool as first arg
        async def _explain(sql: str) -> str:
            return await explain_query(pool, sql)

        async def _slow(top_n: int = 10) -> str:
            return await slow_queries(pool, top_n)

        async def _index(table_name: str = "") -> str:
            return await index_recommendations(pool, table_name or None)

        async def _params() -> str:
            return await parameter_tuning(pool)

        async def _bloat(table_name: str = "") -> str:
            return await table_bloat(pool, table_name or None)

        async def _locks() -> str:
            return await lock_analysis(pool)

        async def _conns() -> str:
            return await connection_analysis(pool)

        self._tools = [
            StructuredTool.from_function(
                coroutine=_explain,
                name="explain_query",
                description=(
                    "Run EXPLAIN ANALYZE on a SELECT query and return the "
                    "execution plan.  Input: a valid SELECT SQL string."
                ),
            ),
            StructuredTool.from_function(
                coroutine=_slow,
                name="slow_queries",
                description=(
                    "Return the Top-N slowest queries from pg_stat_statements. "
                    "Input: top_n (int, default 10)."
                ),
            ),
            StructuredTool.from_function(
                coroutine=_index,
                name="index_recommendations",
                description=(
                    "Analyse seq_scan vs idx_scan ratio and recommend indexes. "
                    "Input: table_name (optional, empty string for all tables)."
                ),
            ),
            StructuredTool.from_function(
                coroutine=_params,
                name="parameter_tuning",
                description=(
                    "Analyse PostgreSQL configuration parameters and recommend "
                    "optimal values.  No input required."
                ),
            ),
            StructuredTool.from_function(
                coroutine=_bloat,
                name="table_bloat",
                description=(
                    "Analyse dead tuples and table bloat.  Recommends VACUUM. "
                    "Input: table_name (optional, empty string for all tables)."
                ),
            ),
            StructuredTool.from_function(
                coroutine=_locks,
                name="lock_analysis",
                description=("Show current lock waits and blocking sessions.  No input required."),
            ),
            StructuredTool.from_function(
                coroutine=_conns,
                name="connection_analysis",
                description=(
                    "Analyse connection pool efficiency, idle sessions, and "
                    "max_connections usage.  No input required."
                ),
            ),
        ]

    # ------------------------------------------------------------------
    # Main analysis entry-point
    # ------------------------------------------------------------------

    async def analyze(
        self,
        question: str,
        instance_id: UUID,
        max_iterations: int = 5,
    ) -> TuningResponse:
        """Run the ReAct agent loop and return structured tuning results.

        Spec: FS-AI-TUNE-001 Section 4.1
        """
        max_iterations = max(1, min(max_iterations, 10))
        start = time.monotonic()
        tools_used: list[str] = []

        # Build tool name -> callable mapping
        tool_map = {t.name: t for t in self._tools}
        tool_descriptions = "\n".join(f"- {t.name}: {t.description}" for t in self._tools)

        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Available tools:\n{tool_descriptions}\n\n"
                    f"To use a tool, respond with EXACTLY this format:\n"
                    f"Action: <tool_name>\n"
                    f"Action Input: <input as JSON or plain string>\n\n"
                    f"When you have enough information, respond with:\n"
                    f"Final Answer: <your JSON response>\n\n"
                    f"Question: {question}"
                )
            ),
        ]

        iteration = 0
        final_text = ""

        for iteration in range(1, max_iterations + 1):
            try:
                response = await self.llm.ainvoke(messages)
            except Exception as exc:
                logger.error("tuning_agent.llm_error", error=str(exc), iteration=iteration)
                final_text = f"LLM call failed at iteration {iteration}: {exc}"
                break

            content = response.content if hasattr(response, "content") else str(response)
            messages.append(AIMessage(content=content))

            # Check for Final Answer
            if "Final Answer:" in content:
                final_text = content.split("Final Answer:", 1)[1].strip()
                break

            # Parse Action / Action Input
            action_name, action_input = self._parse_action(content)
            if action_name and action_name in tool_map:
                tools_used.append(action_name)
                try:
                    tool = tool_map[action_name]
                    result = await tool.ainvoke(action_input)
                except Exception as exc:
                    result = f"Tool error: {exc}"
                    logger.warning(
                        "tuning_agent.tool_error",
                        tool=action_name,
                        error=str(exc),
                    )

                messages.append(HumanMessage(content=f"Observation: {result}"))
            elif action_name:
                messages.append(
                    HumanMessage(
                        content=f"Observation: Unknown tool '{action_name}'. Available: {list(tool_map.keys())}"
                    )
                )
            else:
                # LLM did not follow format -- nudge it
                messages.append(
                    HumanMessage(
                        content=(
                            "Observation: Please use the format 'Action: <tool_name>' "
                            "and 'Action Input: <input>' or 'Final Answer: <JSON>'."
                        )
                    )
                )
        else:
            # max_iterations exceeded without Final Answer
            final_text = content if "content" in dir() else "Max iterations exceeded."

        duration_ms = int((time.monotonic() - start) * 1000)

        # Parse the final text into structured response
        analysis, actions = self._parse_final_answer(final_text)

        # Determine model name
        model_name = "unknown"
        if hasattr(self.llm, "model_name"):
            model_name = self.llm.model_name
        elif hasattr(self.llm, "model"):
            model_name = str(self.llm.model)

        return TuningResponse(
            instance_id=instance_id,
            question=question,
            analysis=analysis,
            actions=actions,
            tools_used=list(dict.fromkeys(tools_used)),  # dedupe preserving order
            iterations=iteration,
            model_used=model_name,
            duration_ms=duration_ms,
        )

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_action(text: str) -> tuple[str | None, str]:
        """Extract Action and Action Input from LLM output."""
        action_name = None
        action_input = ""

        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("Action:") and "Action Input" not in stripped:
                action_name = stripped.split("Action:", 1)[1].strip()
            elif stripped.startswith("Action Input:"):
                action_input = stripped.split("Action Input:", 1)[1].strip()

        # Try to parse action_input as JSON for tools that expect kwargs
        if action_input:
            try:
                parsed = json.loads(action_input)
                if isinstance(parsed, dict):
                    return action_name, parsed
                # Single value — return as string
                return action_name, str(parsed)
            except (json.JSONDecodeError, TypeError):
                return action_name, action_input

        return action_name, action_input

    @staticmethod
    def _parse_final_answer(text: str) -> tuple[str, list[TuningAction]]:
        """Parse the agent's final answer into analysis text and actions list.

        Attempts JSON parsing first; falls back to treating the whole text as
        analysis with no structured actions.
        """
        # Try to extract JSON from the text
        json_str = text.strip()
        # Strip markdown code fences if present
        if "```" in json_str:
            lines = json_str.split("\n")
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            json_str = "\n".join(lines).strip()

        try:
            data = json.loads(json_str)
            analysis = data.get("analysis", text)
            raw_actions = data.get("actions", [])
            actions = []
            for a in raw_actions:
                actions.append(
                    TuningAction(
                        action_type=a.get("action_type", "OTHER"),
                        description=a.get("description", ""),
                        sql=a.get("sql"),
                        risk_level=a.get("risk_level", "medium"),
                        estimated_impact=a.get("estimated_impact", ""),
                    )
                )
            return analysis, actions
        except (json.JSONDecodeError, TypeError, AttributeError):
            # Fallback: return raw text as analysis, no structured actions
            return text, []
