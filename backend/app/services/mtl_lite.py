# Spec: FR-AI-010, FR-AI-011, FR-AI-014, FS-AI-010
"""MTL Lite RCA service — LLM Few-shot Multi-Task Learning for MVP.

Single LLM prompt that performs 4 tasks simultaneously:
  Head 1: Anomaly type classification
  Head 2: Root cause identification
  Head 3: Severity scoring
  Head 4: Action recommendation

Phase 1 (MVP): LLM Few-shot prompting (GPT-4o / Mistral:7b)
Phase 2: Transformer Encoder fine-tuning (PyTorch)
"""

import json
import time
from datetime import datetime, timedelta, timezone
from statistics import mean
from uuid import UUID, uuid4

import structlog

from app.config import settings
from app.schemas.mtl import (
    ActionRisk,
    AnomalyType,
    MTLPredictResponse,
    RootCauseDetail,
    SeverityLevel,
    SuggestedAction,
)
from app.schemas.rag import RAGSearchResult

logger = structlog.get_logger(__name__)

# Spec: FS-AI-010 Section 3.1 — MTL system prompt
_MTL_SYSTEM_PROMPT = """You are NeuralDB's Multi-Task RCA engine.
Given a database incident context, you MUST respond with a JSON object
containing ALL of the following fields simultaneously.

IMPORTANT:
- Be specific about root causes (name exact queries, tables, indexes)
- Confidence scores must reflect actual certainty (don't inflate)
- Reasoning chain must show step-by-step logic
- Suggested actions must be executable SQL or config changes
"""

# Spec: FS-AI-010 Section 3.1 — MTL user prompt template
_MTL_USER_PROMPT = """## Incident Context

### Current Metrics (last 5 minutes)
{metrics_snapshot}

### Active Sessions (ASH)
{ash_summary}

### Similar Past Incidents (RAG, Top-3)
{rag_results}

---

Respond ONLY with valid JSON:
{{
  "anomaly_type": "<one of: query_performance_degradation, resource_exhaustion, lock_contention, replication_lag, connection_saturation, vacuum_bloat, schema_regression, security_anomaly, unknown>",
  "anomaly_confidence": <0.0-1.0>,
  "root_cause": "<specific root cause in natural language>",
  "root_cause_detail": {{
    "component": "<query|table|index|parameter|connection|replication>",
    "identifier": "<specific query hash / table name / param name>",
    "evidence": "<key metric or log entry>"
  }},
  "root_cause_confidence": <0.0-1.0>,
  "severity": "<CRITICAL|WARNING|NOTICE|INFO>",
  "severity_score": <0.0-1.0>,
  "suggested_actions": [
    {{
      "action": "<executable SQL or config command>",
      "description": "<what this does and why>",
      "confidence": <0.0-1.0>,
      "risk": "<LOW|MEDIUM|HIGH|CRITICAL>"
    }}
  ],
  "confidence": <0.0-1.0>,
  "reasoning_chain": [
    "Step 1: <observation>",
    "Step 2: <hypothesis>",
    "Step 3: <evidence>",
    "Step 4: <conclusion>"
  ]
}}"""

# Spec: FS-AI-010 Section 3.6 — fallback when LLM fails
_MTL_FALLBACK = {
    "anomaly_type": "unknown",
    "anomaly_confidence": 0.0,
    "root_cause": "AI analysis failed. Manual investigation required.",
    "root_cause_detail": None,
    "root_cause_confidence": 0.0,
    "severity": "NOTICE",
    "severity_score": 0.5,
    "suggested_actions": [],
    "confidence": 0.0,
    "reasoning_chain": [
        "AI analysis was unable to complete. Please review manually."
    ],
}


def _get_llm():
    """Create LangChain LLM based on AI_MODE config.

    Spec: FS-AI-010 Section 3.5 — LLM model selection.
    """
    if settings.AI_MODE == "online":
        from langchain_openai import ChatOpenAI

        if not settings.OPENAI_API_KEY:
            raise RuntimeError(
                "AI_MODE is 'online' but OPENAI_API_KEY is not set. "
                "Set the key or switch AI_MODE to 'offline'."
            )
        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.1,
            max_tokens=1500,
            request_timeout=30,
        )
    else:
        from langchain_community.llms import Ollama

        return Ollama(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.OLLAMA_MODEL,
            temperature=0.1,
            num_predict=1500,
        )


def _parse_llm_response(raw: str) -> dict:
    """Parse and validate the LLM JSON response.

    Strips markdown fences and attempts JSON parsing.
    Returns the parsed dict or raises ValueError.
    """
    cleaned = raw.strip()
    # Remove markdown code fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    return json.loads(cleaned)


def _compute_overall_confidence(prediction: dict) -> float:
    """Compute weighted average confidence across 4 heads.

    Spec: FS-AI-010 Section 3.3 — confidence score calculation.
    Weights: anomaly=0.25, root_cause=0.35, severity=0.15, action=0.25
    """
    weights = {
        "anomaly_confidence": 0.25,
        "root_cause_confidence": 0.35,
        "severity_accuracy": 0.15,
        "action_confidence": 0.25,
    }

    actions = prediction.get("suggested_actions", [])
    action_conf = (
        mean([a.get("confidence", 0) for a in actions]) if actions else 0.0
    )

    overall = (
        weights["anomaly_confidence"]
        * prediction.get("anomaly_confidence", 0)
        + weights["root_cause_confidence"]
        * prediction.get("root_cause_confidence", 0)
        + weights["severity_accuracy"]
        * prediction.get("severity_score", 0)
        + weights["action_confidence"] * action_conf
    )
    return round(min(max(overall, 0.0), 1.0), 3)


def _build_evidence_links(
    instance_id: UUID, incident_id: UUID, detected_at: datetime
) -> list[str]:
    """Build API links to evidence data.

    Spec: FS-AI-010 Section 3.4 — evidence link generation.
    """
    base = f"/api/v1/instances/{instance_id}"
    t_from = (detected_at - timedelta(minutes=5)).isoformat()
    t_to = (detected_at + timedelta(minutes=5)).isoformat()
    time_range = f"from={t_from}&to={t_to}"

    return [
        f"{base}/metrics?{time_range}",
        f"{base}/ash?{time_range}",
        f"{base}/ash/wait-breakdown?{time_range}",
        f"/api/v1/incidents/{incident_id}",
    ]


def _safe_anomaly_type(raw: str) -> AnomalyType:
    """Safely convert a string to AnomalyType enum, defaulting to UNKNOWN."""
    try:
        return AnomalyType(raw)
    except ValueError:
        return AnomalyType.UNKNOWN


def _safe_severity(raw: str) -> SeverityLevel:
    """Safely convert a string to SeverityLevel enum, defaulting to NOTICE."""
    try:
        return SeverityLevel(raw.upper())
    except (ValueError, AttributeError):
        return SeverityLevel.NOTICE


def _safe_risk(raw: str) -> ActionRisk:
    """Safely convert a string to ActionRisk enum, defaulting to LOW."""
    try:
        return ActionRisk(raw.upper())
    except (ValueError, AttributeError):
        return ActionRisk.LOW


async def predict(
    incident_id: UUID,
    instance_id: UUID,
    metrics_snapshot: str,
    ash_summary: str,
    rag_results: str,
    detected_at: datetime | None = None,
) -> MTLPredictResponse:
    """Run MTL Lite 4-Head prediction using LLM Few-shot prompting.

    Spec: FS-AI-010 — single prompt, 4 simultaneous task outputs.

    Args:
        incident_id: UUID of the incident being analyzed.
        instance_id: UUID of the DB instance.
        metrics_snapshot: Formatted metrics context string.
        ash_summary: Formatted ASH session context string.
        rag_results: Formatted RAG search results string.
        detected_at: Incident detection time (for evidence links).

    Returns:
        MTLPredictResponse with all 4 head results + confidence + reasoning.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    prediction_id = uuid4()
    now = datetime.now(timezone.utc)
    detected = detected_at or now
    start = time.monotonic()
    tokens_used = None

    # Build the prompt
    user_prompt = _MTL_USER_PROMPT.format(
        metrics_snapshot=metrics_snapshot or "No metrics available.",
        ash_summary=ash_summary or "No active sessions data.",
        rag_results=rag_results or "No similar past incidents found.",
    )

    llm = _get_llm()
    parsed = None

    # Spec: FS-AI-010 Section 4.2 — max 2 retries on invalid JSON
    max_retries = 2
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = await llm.ainvoke([
                SystemMessage(content=_MTL_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ])
            raw = (
                response.content
                if hasattr(response, "content")
                else str(response)
            )

            # Extract token usage if available
            if hasattr(response, "response_metadata"):
                usage = response.response_metadata.get("token_usage", {})
                tokens_used = usage.get("total_tokens")

            parsed = _parse_llm_response(raw)
            break  # Success — exit retry loop

        except json.JSONDecodeError as exc:
            last_error = exc
            logger.warning(
                "mtl.json_parse_retry",
                attempt=attempt,
                error=str(exc),
            )
        except Exception as exc:
            last_error = exc
            logger.error(
                "mtl.llm_call_failed",
                attempt=attempt,
                error=str(exc),
            )
            break  # Non-JSON errors — don't retry

    elapsed_ms = int((time.monotonic() - start) * 1000)

    # Spec: FS-AI-010 Section 3.6 — fallback on failure
    if parsed is None:
        logger.error(
            "mtl.prediction_failed_fallback",
            incident_id=str(incident_id),
            last_error=str(last_error),
        )
        parsed = dict(_MTL_FALLBACK)

    # Build evidence links
    evidence_links = _build_evidence_links(instance_id, incident_id, detected)

    # Compute overall confidence
    overall_confidence = _compute_overall_confidence(parsed)

    # Parse suggested actions
    raw_actions = parsed.get("suggested_actions", [])
    suggested_actions = []
    for a in raw_actions[:3]:  # Max 3 actions
        if isinstance(a, dict):
            suggested_actions.append(SuggestedAction(
                action=a.get("action", "Review manually"),
                description=a.get("description", ""),
                confidence=min(max(float(a.get("confidence", 0)), 0.0), 1.0),
                risk=_safe_risk(a.get("risk", "LOW")),
            ))

    # Parse root cause detail
    raw_detail = parsed.get("root_cause_detail")
    root_cause_detail = None
    if isinstance(raw_detail, dict):
        try:
            root_cause_detail = RootCauseDetail(
                component=raw_detail.get("component", "unknown"),
                identifier=raw_detail.get("identifier", "unknown"),
                evidence=raw_detail.get("evidence", ""),
            )
        except Exception:
            root_cause_detail = None

    model_name = (
        settings.OPENAI_MODEL
        if settings.AI_MODE == "online"
        else settings.OLLAMA_MODEL
    )

    result = MTLPredictResponse(
        prediction_id=prediction_id,
        incident_id=incident_id,
        timestamp=now,
        # Head 1
        anomaly_type=_safe_anomaly_type(
            parsed.get("anomaly_type", "unknown")
        ),
        anomaly_confidence=min(
            max(float(parsed.get("anomaly_confidence", 0)), 0.0), 1.0
        ),
        # Head 2
        root_cause=parsed.get(
            "root_cause", "AI analysis incomplete. Manual review needed."
        ),
        root_cause_detail=root_cause_detail,
        root_cause_confidence=min(
            max(float(parsed.get("root_cause_confidence", 0)), 0.0), 1.0
        ),
        # Head 3
        severity=_safe_severity(parsed.get("severity", "NOTICE")),
        severity_score=min(
            max(float(parsed.get("severity_score", 0.5)), 0.0), 1.0
        ),
        # Head 4
        suggested_actions=suggested_actions,
        # Explainable AI
        confidence=overall_confidence,
        reasoning_chain=parsed.get("reasoning_chain", []),
        evidence_links=evidence_links,
        # Meta
        model_version="mtl-lite-v1",
        inference_time_ms=elapsed_ms,
        tokens_used=tokens_used,
    )

    logger.info(
        "mtl.prediction_complete",
        prediction_id=str(prediction_id),
        incident_id=str(incident_id),
        anomaly_type=result.anomaly_type.value,
        confidence=result.confidence,
        inference_time_ms=elapsed_ms,
        model=model_name,
    )

    return result
