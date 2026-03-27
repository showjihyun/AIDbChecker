# Spec: FR-AI-010, FR-AI-011, FR-AI-014, FS-AI-010
"""MTL Lite RCA API — Multi-Task Learning 4-Head prediction.

POST /api/v1/mtl/predict — run MTL Lite diagnosis on an incident
  Gathers metrics context, ASH summary, RAG results, then invokes the LLM
  for simultaneous anomaly classification, root cause, severity, and actions.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_role
from app.models.incident import Incident
from app.schemas.mtl import MTLPredictRequest, MTLPredictResponse
from app.services import mtl_lite
from app.services import rag as rag_service

logger = structlog.get_logger(__name__)

router = APIRouter()


# Spec: FS-AI-010 Section 2.1 — MTL prediction endpoint
@router.post(
    "/mtl/predict",
    response_model=MTLPredictResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="Run MTL Lite 4-Head RCA prediction",
    description="Performs simultaneous anomaly classification, root cause "
    "identification, severity assessment, and action recommendation "
    "using LLM few-shot prompting.",
)
async def mtl_predict(
    body: MTLPredictRequest,
    session: AsyncSession = Depends(get_session),
) -> MTLPredictResponse:
    """Run MTL Lite prediction for the given incident.

    Gathers context from metrics, ASH, and RAG, then invokes the LLM
    to produce 4-head predictions with confidence scores and reasoning.
    """
    # Step 1: Verify incident exists
    stmt = select(Incident).where(Incident.id == body.incident_id)
    result = await session.execute(stmt)
    incident = result.scalar_one_or_none()

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {body.incident_id} not found. Verify the incident ID is correct.",
        )

    # Step 2: Build metrics snapshot context
    metrics_snapshot = _build_metrics_context(incident)

    # Step 3: Build ASH summary context
    ash_summary = _build_ash_context(incident)

    # Step 4: Search similar incidents via RAG
    rag_text = "No similar past incidents found."
    try:
        search_query = f"{incident.title} {incident.description or ''}"
        rag_results, _ = await rag_service.search_similar(
            session=session,
            query_text=search_query,
            instance_id=incident.instance_id,
            top_k=3,
            min_similarity=0.5,  # Lower threshold for MTL context
        )
        if rag_results:
            rag_text = rag_service.format_for_prompt(rag_results)
    except Exception as exc:
        logger.warning(
            "mtl.rag_search_failed",
            incident_id=str(body.incident_id),
            error=str(exc),
        )
        # Non-critical — continue without RAG context

    # Step 5: Run MTL Lite prediction
    try:
        prediction = await mtl_lite.predict(
            incident_id=body.incident_id,
            instance_id=body.instance_id,
            metrics_snapshot=metrics_snapshot,
            ash_summary=ash_summary,
            rag_results=rag_text,
            detected_at=incident.detected_at,
        )
    except RuntimeError as exc:
        logger.error(
            "mtl.prediction_api_error",
            incident_id=str(body.incident_id),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"MTL prediction failed: {exc}. Check AI_MODE setting and LLM availability.",
        )

    return prediction


def _build_metrics_context(incident: Incident) -> str:
    """Build a metrics snapshot string from incident data.

    Spec: FS-AI-010 Section 3.2 — {metrics_snapshot} format.
    In MVP, we extract what's available from the incident itself.
    Full metrics integration comes when MetricService is available.
    """
    lines = ["=== Incident Metrics ==="]

    if incident.metric_type:
        lines.append(f"Metric Type: {incident.metric_type}")
    if incident.metric_value is not None:
        lines.append(f"Current Value: {incident.metric_value}")
    if incident.baseline_value is not None:
        lines.append(f"Baseline Value: {incident.baseline_value}")

    lines.append(f"Severity: {incident.severity}")
    lines.append(f"Source: {incident.source}")

    meta = incident.metadata_ or {}
    for key in ("cpu_usage", "memory_usage", "active_connections", "tps"):
        if key in meta:
            lines.append(f"{key}: {meta[key]}")

    if len(lines) == 1:
        lines.append("No detailed metrics available for this incident.")

    return "\n".join(lines)


def _build_ash_context(incident: Incident) -> str:
    """Build an ASH summary string from incident metadata.

    Spec: FS-AI-010 Section 3.2 — {ash_summary} format.
    In MVP, ASH data may be embedded in incident metadata.
    Full ASH integration comes with the ASH service.
    """
    meta = incident.metadata_ or {}
    ash_data = meta.get("ash_summary")
    if ash_data:
        return str(ash_data)

    top_queries = meta.get("top_queries")
    if top_queries:
        return f"=== Top Queries ===\n{top_queries}"

    return "No active session data available for this incident."
