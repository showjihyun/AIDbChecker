# Spec: FR-AI-002, FS-AI-RAG-001
"""Lightweight RAG API — incident similarity search and embedding status.

POST /api/v1/rag/search — search similar past incidents via pgvector
GET  /api/v1/rag/status — embedding statistics and health

MVP scope: incident history embeddings only.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, require_role
from app.config import settings
from app.schemas.rag import (
    RAGSearchRequest,
    RAGSearchResponse,
    RAGStatusResponse,
)
from app.services import rag as rag_service

logger = structlog.get_logger(__name__)

router = APIRouter()


# Spec: FS-AI-RAG-001 Section 2.1 — similarity search endpoint
@router.post(
    "/rag/search",
    response_model=RAGSearchResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="Search similar past incidents",
    description="Uses pgvector cosine similarity to find past incidents "
    "similar to the query text. Results are cached in Valkey for 5 minutes.",
)
async def search_similar_incidents(
    body: RAGSearchRequest,
    session: AsyncSession = Depends(get_session),
) -> RAGSearchResponse:
    """Search for similar past incidents using pgvector embeddings."""
    try:
        results, search_time_ms = await rag_service.search_similar(
            session=session,
            query_text=body.query,
            instance_id=body.instance_id,
            top_k=body.top_k,
            min_similarity=body.min_similarity,
        )
    except RuntimeError as exc:
        logger.error("rag.search_api_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"RAG search failed: {exc}. Check embedding service availability.",
        )

    return RAGSearchResponse(
        results=results,
        search_time_ms=search_time_ms,
        embedding_model=settings.EMBEDDING_MODEL,
    )


# Spec: FS-AI-RAG-001 Section 2.1 — embedding status endpoint
@router.get(
    "/rag/status",
    response_model=RAGStatusResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator", "viewer"))],
    summary="Get RAG embedding status",
    description="Returns statistics about the RAG embedding index: "
    "total documents, model info, last embedding time.",
)
async def get_rag_status(
    session: AsyncSession = Depends(get_session),
) -> RAGStatusResponse:
    """Get embedding statistics for the RAG index."""
    try:
        status_data = await rag_service.get_embedding_status(session)
    except Exception as exc:
        logger.error("rag.status_api_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve RAG status: {exc}.",
        )

    return RAGStatusResponse(**status_data)
