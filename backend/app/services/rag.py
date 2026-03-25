# Spec: FR-AI-002, FS-AI-RAG-001
"""Lightweight RAG service — incident history embeddings and similarity search.

MVP scope: incident history embeddings only (source_type='incident').
Uses sentence-transformers (all-MiniLM-L6-v2) for 384-dim embeddings
and pgvector cosine similarity for search. Valkey caching with 5-min TTL.

Phase 2: extends to documents, playbooks, manuals.
"""

import hashlib
import json
import time
from datetime import datetime
from uuid import UUID, uuid4

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.incident import Incident
from app.models.rag_document import RAGDocument
from app.schemas.rag import RAGSearchResult

logger = structlog.get_logger(__name__)

# Module-level embedding model cache (lazy-loaded)
_embedding_model = None


def _get_embedding_model():
    """Lazy-load the sentence-transformers embedding model.

    Spec: FR-AI-002 — all-MiniLM-L6-v2, 384 dimensions, CPU for MVP.
    """
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer(
            settings.EMBEDDING_MODEL,
            device="cpu",
        )
        logger.info(
            "rag.embedding_model_loaded",
            model=settings.EMBEDDING_MODEL,
            dimensions=settings.EMBEDDING_DIMENSIONS,
        )
    return _embedding_model


def _build_incident_content(incident: Incident) -> str:
    """Build embedding text from an incident's context.

    Spec: FS-AI-RAG-001 Section 3.1 — incident context composition.
    """
    parts = [
        f"Severity: {incident.severity}",
        f"Source: {incident.source}",
        f"Title: {incident.title}",
    ]
    if incident.description:
        parts.append(f"Description: {incident.description}")
    if incident.metric_type:
        parts.append(f"Metric: {incident.metric_type}")
    if incident.metric_value is not None:
        parts.append(f"Metric Value: {incident.metric_value}")
    if incident.baseline_value is not None:
        parts.append(f"Baseline Value: {incident.baseline_value}")

    # Include resolution info from metadata if available
    meta = incident.metadata_ or {}
    if meta.get("resolution"):
        parts.append(f"Resolution: {meta['resolution']}")

    return "\n".join(parts)


def _compute_embedding(text_content: str) -> list[float]:
    """Generate embedding vector for the given text.

    Returns a list of floats (384 dimensions for MiniLM).
    """
    model = _get_embedding_model()
    embedding = model.encode(text_content, normalize_embeddings=True)
    return embedding.tolist()


async def embed_incident(
    session: AsyncSession, incident: Incident
) -> RAGDocument:
    """Create or update a RAG embedding for an incident.

    Spec: FS-AI-RAG-001 Section 3.1 — embedding triggers:
    - Incident creation: immediate embedding
    - Incident resolution: re-embed with resolution info
    - Incident deletion: cascade deletes RAG document

    Args:
        session: Async DB session.
        incident: The incident to embed.

    Returns:
        The created/updated RAGDocument.
    """
    content = _build_incident_content(incident)

    try:
        embedding = _compute_embedding(content)
    except Exception as exc:
        logger.error(
            "rag.embedding_failed",
            incident_id=str(incident.id),
            error=str(exc),
        )
        raise RuntimeError(
            f"Embedding generation failed: {exc}. "
            "Check that sentence-transformers is installed and model is available."
        ) from exc

    # Build metadata for the RAG document
    metadata = {
        "instance_id": str(incident.instance_id) if incident.instance_id else None,
        "severity": incident.severity,
        "source": incident.source,
        "metric_type": incident.metric_type,
    }
    meta = incident.metadata_ or {}
    if meta.get("resolution"):
        metadata["resolution"] = meta["resolution"]

    # UPSERT: check if document already exists for this incident
    stmt = select(RAGDocument).where(
        RAGDocument.source_type == "incident",
        RAGDocument.source_id == incident.id,
    )
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.content = content
        existing.embedding = embedding
        existing.metadata_ = metadata
        doc = existing
        logger.info("rag.embedding_updated", incident_id=str(incident.id))
    else:
        doc = RAGDocument(
            id=uuid4(),
            source_type="incident",
            source_id=incident.id,
            content=content,
            metadata_=metadata,
            embedding=embedding,
        )
        session.add(doc)
        logger.info("rag.embedding_created", incident_id=str(incident.id))

    await session.flush()
    return doc


async def search_similar(
    session: AsyncSession,
    query_text: str,
    *,
    instance_id: UUID | None = None,
    top_k: int = 3,
    min_similarity: float = 0.7,
) -> tuple[list[RAGSearchResult], int]:
    """Search for similar incidents using pgvector cosine similarity.

    Spec: FS-AI-RAG-001 Section 3.2 — pgvector cosine similarity search.

    Args:
        session: Async DB session.
        query_text: Search query text.
        instance_id: Optional filter to specific instance.
        top_k: Number of results to return.
        min_similarity: Minimum cosine similarity threshold.

    Returns:
        Tuple of (search_results, search_time_ms).
    """
    start = time.monotonic()

    # First check Valkey cache
    cache_key = _build_cache_key(query_text, instance_id, top_k)
    cached = await _get_from_cache(cache_key)
    if cached is not None:
        elapsed = int((time.monotonic() - start) * 1000)
        logger.info("rag.cache_hit", cache_key=cache_key[:40], time_ms=elapsed)
        return cached, elapsed

    # Generate query embedding
    try:
        query_embedding = _compute_embedding(query_text)
    except Exception as exc:
        logger.error("rag.search_embedding_failed", error=str(exc))
        return [], int((time.monotonic() - start) * 1000)

    # Spec: FS-AI-RAG-001 Section 3.2 — pgvector cosine distance search
    # 1 - (embedding <=> query) gives cosine similarity
    embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    sql = """
        SELECT
            rd.source_id AS incident_id,
            1 - (rd.embedding <=> :query_vec::vector) AS similarity,
            i.description AS summary,
            i.title AS title,
            rd.metadata->>'resolution' AS resolution,
            rd.created_at
        FROM rag_documents rd
        JOIN incidents i ON i.id = rd.source_id
        WHERE rd.source_type = 'incident'
          AND 1 - (rd.embedding <=> :query_vec::vector) >= :min_sim
    """
    params: dict = {
        "query_vec": embedding_str,
        "min_sim": min_similarity,
        "top_k": top_k,
    }

    if instance_id is not None:
        sql += " AND (rd.metadata->>'instance_id')::uuid = :instance_id"
        params["instance_id"] = str(instance_id)

    sql += """
        ORDER BY rd.embedding <=> :query_vec::vector
        LIMIT :top_k
    """

    try:
        result = await session.execute(text(sql), params)
        rows = result.fetchall()
    except Exception as exc:
        logger.error("rag.search_query_failed", error=str(exc))
        elapsed = int((time.monotonic() - start) * 1000)
        return [], elapsed

    results = []
    for row in rows:
        results.append(RAGSearchResult(
            incident_id=row.incident_id,
            similarity=round(float(row.similarity), 4),
            summary=row.title + (f": {row.summary}" if row.summary else ""),
            root_cause=None,  # Populated from RCA results in Phase 2
            resolution=row.resolution,
            created_at=row.created_at,
        ))

    elapsed = int((time.monotonic() - start) * 1000)

    # Cache results in Valkey
    await _set_to_cache(cache_key, results)

    logger.info(
        "rag.search_complete",
        results_count=len(results),
        time_ms=elapsed,
        top_similarity=results[0].similarity if results else 0.0,
    )
    return results, elapsed


def format_for_prompt(results: list[RAGSearchResult]) -> str:
    """Format RAG search results for insertion into an LLM prompt.

    Spec: FS-AI-RAG-001 Section 3.3 — format_rag_for_mtl.
    """
    if not results:
        return "No similar past incidents found."

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(
            f"--- Similar Incident #{i} (similarity: {r.similarity:.2f}) ---"
        )
        lines.append(f"Summary: {r.summary}")
        if r.root_cause:
            lines.append(f"Root Cause: {r.root_cause}")
        if r.resolution:
            lines.append(f"Resolution: {r.resolution}")
        lines.append("")

    return "\n".join(lines)


async def get_embedding_status(session: AsyncSession) -> dict:
    """Get RAG embedding statistics.

    Spec: FS-AI-RAG-001 Section 2.1 — /api/v1/rag/status response.
    """
    # Total documents
    total_stmt = select(func.count()).select_from(RAGDocument)
    total = (await session.execute(total_stmt)).scalar_one()

    # Total incidents embedded
    incident_stmt = select(func.count()).select_from(RAGDocument).where(
        RAGDocument.source_type == "incident"
    )
    incident_count = (await session.execute(incident_stmt)).scalar_one()

    # Last embedding time
    last_stmt = (
        select(RAGDocument.created_at)
        .order_by(RAGDocument.created_at.desc())
        .limit(1)
    )
    last_result = await session.execute(last_stmt)
    last_row = last_result.scalar_one_or_none()

    return {
        "total_documents": total,
        "total_incidents_embedded": incident_count,
        "last_embedding_at": last_row,
        "embedding_model": settings.EMBEDDING_MODEL,
        "vector_dimensions": settings.EMBEDDING_DIMENSIONS,
    }


# --- Valkey Cache Helpers ---
# Spec: FS-AI-RAG-001 Section 3.4 — Valkey caching (5 min TTL)

_RAG_CACHE_TTL = 300  # 5 minutes
_RAG_CACHE_PREFIX = "rag:search:"


def _build_cache_key(query: str, instance_id: UUID | None, top_k: int) -> str:
    """Build a deterministic cache key from search parameters."""
    raw = f"{query}:{instance_id}:{top_k}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:32]
    return f"{_RAG_CACHE_PREFIX}{digest}"


async def _get_from_cache(key: str) -> list[RAGSearchResult] | None:
    """Attempt to retrieve cached search results from Valkey."""
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.VALKEY_URL)
        try:
            data = await client.get(key)
            if data is None:
                return None
            items = json.loads(data)
            return [RAGSearchResult(**item) for item in items]
        finally:
            await client.aclose()
    except Exception as exc:
        # Cache miss is non-critical — log and continue
        logger.debug("rag.cache_get_failed", key=key[:40], error=str(exc))
        return None


async def _set_to_cache(key: str, results: list[RAGSearchResult]) -> None:
    """Store search results in Valkey with TTL."""
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(settings.VALKEY_URL)
        try:
            data = json.dumps(
                [r.model_dump(mode="json") for r in results]
            )
            await client.setex(key, _RAG_CACHE_TTL, data)
        finally:
            await client.aclose()
    except Exception as exc:
        # Cache write failure is non-critical
        logger.debug("rag.cache_set_failed", key=key[:40], error=str(exc))
