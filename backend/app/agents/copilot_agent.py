# Spec: FS-AI-012
"""DB Copilot Agent — Tree-of-Thought diagnosis for PostgreSQL.

Explores multiple diagnostic branches in parallel (via a single LLM call),
scores each branch, and selects the best path for deeper analysis.
Reuses existing DB diagnostic tools from the tuning agent.

Spec: FS-AI-012 Section 2
"""

from __future__ import annotations

import json
import time
from uuid import UUID, uuid4

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from app.schemas.copilot import BranchScore, CopilotDiagnoseResponse

logger = structlog.get_logger(__name__)

# Spec: FS-AI-012 Section 2.2 — 8 branch types
BRANCH_TYPES = [
    "QueryPerformance",
    "ResourceBottleneck",
    "LockContention",
    "Replication",
    "VacuumBloat",
    "Connection",
    "SchemaRegression",
    "Security",
]

# Spec: FS-AI-012 Section 2 — system prompt for ToT evaluation
_TOT_SYSTEM_PROMPT = """\
You are a PostgreSQL diagnostic expert using Tree-of-Thought reasoning.
Given an incident context, you must evaluate multiple diagnostic branches
and score each one.

For each branch, provide:
- relevance_score (0.0-1.0): how relevant this branch is to the current issue
- evidence_strength (0.0-1.0): strength of supporting evidence
- action_confidence (0.0-1.0): confidence in the recommended actions
- risk_penalty (0.0-0.5): risk of the proposed actions
- anomaly_type: specific anomaly classification
- root_cause: identified root cause
- severity_score (0.0-1.0): severity of the issue
- suggested_actions: list of concrete action descriptions
- reasoning: step-by-step reasoning for this branch

Respond as JSON with key "branches" containing a list of branch objects,
each with keys: branch_name, relevance_score, evidence_strength,
action_confidence, risk_penalty, anomaly_type, root_cause, severity_score,
suggested_actions (list of strings), reasoning (list of strings).

LANGUAGE:
- root_cause, suggested_actions, reasoning MUST be in Korean (한국어).
- branch_name and anomaly_type remain in English (machine-readable).
- Use DBA terminology: 풀스캔, 인덱스 누락, 커넥션 포화, 데드락, WAL 지연 등.
"""


class DBCopilotAgent:
    """Tree-of-Thought diagnostic agent.

    Spec: FS-AI-012 Section 2
    """

    def __init__(self, llm) -> None:  # noqa: ANN001
        self.llm = llm

    async def diagnose(
        self,
        instance_id: UUID,
        incident_id: UUID | None = None,
        max_branches: int = 4,
        autonomy_level: int = 0,
        auto_execute: bool = False,
    ) -> CopilotDiagnoseResponse:
        """Run Tree-of-Thought diagnosis.

        Spec: FS-AI-012 Section 2.1
        """
        max_branches = max(2, min(max_branches, 8))
        start = time.monotonic()

        # Select which branches to explore (up to max_branches)
        branches_to_explore = BRANCH_TYPES[:max_branches]

        # Build context prompt
        context = self._build_context(instance_id, incident_id, branches_to_explore)

        # Single LLM call to evaluate all branches
        branch_results = await self._evaluate_branches(context, branches_to_explore)

        # Score each branch per Spec Section 2.3
        scored_branches: list[BranchScore] = []
        branch_details: list[dict] = []
        for br in branch_results:
            score = BranchScore(
                branch_name=br["branch_name"],
                relevance_score=br.get("relevance_score", 0.0),
                evidence_strength=br.get("evidence_strength", 0.0),
                action_confidence=br.get("action_confidence", 0.0),
                risk_penalty=br.get("risk_penalty", 0.0),
            )
            scored_branches.append(score)
            branch_details.append(
                {
                    "branch_name": score.branch_name,
                    "relevance_score": score.relevance_score,
                    "evidence_strength": score.evidence_strength,
                    "action_confidence": score.action_confidence,
                    "risk_penalty": score.risk_penalty,
                    "final_score": score.final_score,
                }
            )

        # Select best branch (highest final_score)
        if scored_branches:
            best = max(scored_branches, key=lambda b: b.final_score)
            best_name = best.branch_name
            best_detail = next(
                (br for br in branch_results if br["branch_name"] == best_name),
                {},
            )
        else:
            best_name = "Unknown"
            best_detail = {}

        # Extract diagnosis from best branch
        confidence = best.final_score if scored_branches else 0.0
        anomaly_type = best_detail.get("anomaly_type", "unknown")
        root_cause = best_detail.get("root_cause", "Unable to determine")
        severity_score = best_detail.get("severity_score", 0.5)
        suggested_actions = best_detail.get("suggested_actions", [])
        reasoning_chain = best_detail.get("reasoning", [])

        # Spec: FS-AI-012 AC-4 — block if confidence < 0.5
        # Spec: FS-AI-012 AC-3 — autonomy level gate
        execution_status = self._determine_execution_status(
            confidence=confidence,
            autonomy_level=autonomy_level,
            auto_execute=auto_execute,
        )

        # Spec: FS-AI-012 AC-7, AC-8 — Playbook 하이브리드 연동 (ADR-008)
        recommended_playbook = None
        try:
            from app.services.playbook_executor import match_playbook

            recommended_playbook = match_playbook(anomaly_type)
        except Exception:
            pass

        # AC-8: Playbook 없는 신규 패턴
        if recommended_playbook is None and execution_status == "recommended":
            execution_status = "copilot_recommended"

        duration_ms = int((time.monotonic() - start) * 1000)

        return CopilotDiagnoseResponse(
            session_id=uuid4(),
            instance_id=instance_id,
            branches_explored=len(scored_branches),
            selected_branch=best_name,
            branch_scores=branch_details,
            anomaly_type=anomaly_type,
            root_cause=root_cause,
            severity_score=severity_score,
            suggested_actions=suggested_actions,
            confidence=confidence,
            reasoning_chain=reasoning_chain,
            total_inference_time_ms=duration_ms,
            total_tokens_used=0,
            autonomy_level_applied=autonomy_level,
            execution_status=execution_status,
            recommended_playbook=recommended_playbook,
        )

    def _build_context(
        self,
        instance_id: UUID,
        incident_id: UUID | None,
        branches: list[str],
    ) -> str:
        """Build the LLM prompt context."""
        branch_list = ", ".join(branches)
        parts = [
            f"Instance ID: {instance_id}",
            f"Incident ID: {incident_id or 'manual trigger'}",
            f"Branches to evaluate: {branch_list}",
            "",
            "Evaluate each branch and provide scores.",
        ]
        return "\n".join(parts)

    async def _evaluate_branches(
        self,
        context: str,
        branches: list[str],
    ) -> list[dict]:
        """Call LLM to evaluate all branches in a single prompt.

        Spec: FS-AI-012 Section 2 — MVP uses single prompt, not multi-path.
        """
        messages = [
            SystemMessage(content=_TOT_SYSTEM_PROMPT),
            HumanMessage(content=context),
        ]

        try:
            response = await self.llm.ainvoke(messages)
            content = response.content if hasattr(response, "content") else str(response)
            return self._parse_branch_response(content, branches)
        except Exception as exc:
            logger.error("copilot_agent.llm_error", error=str(exc))
            # Return minimal scores for all branches on LLM failure
            return [
                {
                    "branch_name": b,
                    "relevance_score": 0.1,
                    "evidence_strength": 0.1,
                    "action_confidence": 0.1,
                    "risk_penalty": 0.0,
                    "anomaly_type": "unknown",
                    "root_cause": f"LLM unavailable: {exc}",
                    "severity_score": 0.5,
                    "suggested_actions": [],
                    "reasoning": [f"LLM call failed: {exc}"],
                }
                for b in branches
            ]

    @staticmethod
    def _parse_branch_response(content: str, branches: list[str]) -> list[dict]:
        """Parse LLM JSON response into branch result dicts."""
        # Strip markdown fences
        text = content.strip()
        if "```" in text:
            lines = text.split("\n")
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
            raw_branches = data.get("branches", [])
            if isinstance(raw_branches, list) and len(raw_branches) >= 2:
                return raw_branches
        except (json.JSONDecodeError, TypeError, AttributeError):
            logger.warning("copilot_agent.parse_failed", content=content[:200])

        # Fallback: generate default entries for requested branches
        return [
            {
                "branch_name": b,
                "relevance_score": 0.2,
                "evidence_strength": 0.2,
                "action_confidence": 0.2,
                "risk_penalty": 0.0,
                "anomaly_type": "unknown",
                "root_cause": "Parse error — fallback scores",
                "severity_score": 0.5,
                "suggested_actions": [],
                "reasoning": ["LLM response could not be parsed"],
            }
            for b in branches
        ]

    @staticmethod
    def _determine_execution_status(
        confidence: float,
        autonomy_level: int,
        auto_execute: bool,
    ) -> str:
        """Determine execution status based on confidence and autonomy.

        Spec: FS-AI-012 AC-3, AC-4
        """
        # AC-4: block if confidence too low
        if confidence < 0.5:
            return "blocked"

        if not auto_execute:
            return "recommended"

        # AC-3: autonomy level gate
        if autonomy_level >= 3:
            return "executed"
        elif autonomy_level >= 2:
            return "awaiting_approval"
        else:
            return "recommended"
