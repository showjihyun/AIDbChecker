# Spec: FS-AI-NL2SQL-001
"""Graph API — Schema Knowledge Graph management for NL2GraphRAG Phase 2.

POST /api/v1/graph/build    — build graph from target DB information_schema
GET  /api/v1/graph/nodes    — list graph nodes (with optional filters)
POST /api/v1/graph/metric   — add a business metric node
POST /api/v1/graph/concept  — add a business concept node
"""

import time
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_session, require_role
from app.models.graph_node import GraphNode
from app.models.user import User
from app.schemas.graph import (
    GraphBuildRequest,
    GraphBuildResponse,
    GraphConceptRequest,
    GraphConceptResponse,
    GraphMetricRequest,
    GraphMetricResponse,
    GraphNodeListResponse,
    GraphNodeResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post(
    "/graph/build",
    response_model=GraphBuildResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin"))],
    summary="Build Schema Knowledge Graph from target DB",
    description="Extracts information_schema from the target DB and builds "
    "a Knowledge Graph with table/column nodes and FK edges. "
    "Existing graph for the instance is replaced.",
)
async def build_graph(
    body: GraphBuildRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GraphBuildResponse:
    """Build a Schema Knowledge Graph for a target DB instance.

    Spec: FS-AI-NL2SQL-001 Section 3.4
    """
    from app.models.db_instance import DBInstance
    from app.services.graph_rag import SchemaGraphBuilder

    start = time.monotonic()

    # Verify instance exists
    stmt = select(DBInstance).where(
        DBInstance.id == body.instance_id,
        DBInstance.deleted_at.is_(None),
    )
    result = await session.execute(stmt)
    instance = result.scalar_one_or_none()
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DB instance {body.instance_id} not found.",
        )

    # Build target DB connection pool via asyncpg
    import asyncpg

    dsn = (
        f"postgresql://{instance.connection_config.get('username', 'postgres')}"
        f":{instance.connection_config.get('password', '')}"
        f"@{instance.host}:{instance.port}/{instance.database_name}"
    )

    try:
        pool = await asyncpg.create_pool(
            dsn,
            min_size=1,
            max_size=2,
            command_timeout=10,
            server_settings={"statement_timeout": "5000"},
        )
    except Exception as exc:
        logger.error(
            "graph.build_connection_failed",
            instance_id=str(body.instance_id),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cannot connect to target DB: {exc}. "
            "Verify the instance connection settings.",
        )

    try:
        builder = SchemaGraphBuilder()
        nodes_created, edges_created = await builder.build_graph(
            session=session,
            instance_id=body.instance_id,
            adapter_pool=pool,
        )
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.error(
            "graph.build_failed",
            instance_id=str(body.instance_id),
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph build failed: {exc}",
        )
    finally:
        await pool.close()

    elapsed_ms = int((time.monotonic() - start) * 1000)

    return GraphBuildResponse(
        instance_id=body.instance_id,
        nodes_created=nodes_created,
        edges_created=edges_created,
        build_time_ms=elapsed_ms,
    )


@router.get(
    "/graph/nodes",
    response_model=GraphNodeListResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin", "operator"))],
    summary="List graph nodes",
    description="List Knowledge Graph nodes with optional filters by instance, type, name.",
)
async def list_graph_nodes(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    instance_id: UUID | None = Query(None, description="Filter by instance"),
    node_type: str | None = Query(None, description="Filter by node type (table/column/metric/concept)"),
    name_contains: str | None = Query(None, description="Filter by name substring"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> GraphNodeListResponse:
    """List graph nodes with optional filtering.

    Spec: FS-AI-NL2SQL-001 Section 7.2
    """
    stmt = select(GraphNode)
    count_stmt = select(func.count()).select_from(GraphNode)

    if instance_id is not None:
        stmt = stmt.where(GraphNode.instance_id == instance_id)
        count_stmt = count_stmt.where(GraphNode.instance_id == instance_id)
    if node_type is not None:
        stmt = stmt.where(GraphNode.node_type == node_type)
        count_stmt = count_stmt.where(GraphNode.node_type == node_type)
    if name_contains is not None:
        stmt = stmt.where(GraphNode.name.ilike(f"%{name_contains}%"))
        count_stmt = count_stmt.where(GraphNode.name.ilike(f"%{name_contains}%"))

    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(GraphNode.node_type, GraphNode.name)
    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    nodes = result.scalars().all()

    return GraphNodeListResponse(
        nodes=[
            GraphNodeResponse(
                id=n.id,
                node_type=n.node_type,
                name=n.name,
                description=n.description,
                metadata=n.metadata_extra or {},
                instance_id=n.instance_id,
                created_at=n.created_at,
            )
            for n in nodes
        ],
        total=total,
    )


@router.post(
    "/graph/metric",
    response_model=GraphMetricResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin"))],
    summary="Add a business metric node",
    description="Register a business metric and link it to source columns in the Knowledge Graph.",
)
async def add_business_metric(
    body: GraphMetricRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GraphMetricResponse:
    """Add a business metric node + METRIC_SOURCE edges.

    Spec: FS-AI-NL2SQL-001 Section 3.4
    """
    from app.services.graph_rag import SchemaGraphBuilder

    builder = SchemaGraphBuilder()
    try:
        node_id, edges_created = await builder.add_business_metric(
            session=session,
            instance_id=body.instance_id,
            name=body.name,
            description=body.description,
            source_columns=body.source_columns,
        )
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.error("graph.metric_add_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add metric: {exc}",
        )

    return GraphMetricResponse(
        node_id=node_id,
        name=body.name,
        edges_created=edges_created,
    )


@router.post(
    "/graph/concept",
    response_model=GraphConceptResponse,
    dependencies=[Depends(require_role("super_admin", "db_admin"))],
    summary="Add a business concept node",
    description="Register a business concept and link it to related metrics in the Knowledge Graph.",
)
async def add_business_concept(
    body: GraphConceptRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GraphConceptResponse:
    """Add a business concept node + CONCEPT_MAP edges.

    Spec: FS-AI-NL2SQL-001 Section 3.4
    """
    from app.services.graph_rag import SchemaGraphBuilder

    builder = SchemaGraphBuilder()
    try:
        node_id, edges_created = await builder.add_business_concept(
            session=session,
            instance_id=body.instance_id,
            name=body.name,
            description=body.description,
            related_metrics=body.related_metrics,
        )
        await session.commit()
    except Exception as exc:
        await session.rollback()
        logger.error("graph.concept_add_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add concept: {exc}",
        )

    return GraphConceptResponse(
        node_id=node_id,
        name=body.name,
        edges_created=edges_created,
    )
