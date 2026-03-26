# Spec: FS-AI-NL2SQL-001
"""NL2GraphRAG service -- Schema Knowledge Graph builder and retriever.

Phase 2: Converts target DB information_schema into a Knowledge Graph
stored in the system DB (graph_nodes + graph_edges). Uses pgvector
cosine similarity for retrieval and 1-hop expansion for subgraph extraction.

Key design decisions:
  - SchemaGraphBuilder queries TARGET DB via adapter pool (not system DB)
  - GraphRAGRetriever queries SYSTEM DB (where graph is stored)
  - Embeddings via sentence-transformers (all-MiniLM-L6-v2, 384-dim)
  - Same embedding model as rag.py for consistency
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import json

import structlog
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.graph_edge import GraphEdge
from app.models.graph_node import GraphNode

logger = structlog.get_logger(__name__)

# Module-level embedding model cache (shared with rag.py pattern)
_embedding_model = None


def _get_embedding_model():
    """Lazy-load the sentence-transformers embedding model.

    Spec: FS-AI-NL2SQL-001 -- same model as FS-AI-RAG-001 (all-MiniLM-L6-v2, 384 dim).
    """
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer(
            settings.EMBEDDING_MODEL,
            device="cpu",
        )
        logger.info(
            "graph_rag.embedding_model_loaded",
            model=settings.EMBEDDING_MODEL,
            dimensions=settings.EMBEDDING_DIMENSIONS,
        )
    return _embedding_model


def _compute_embedding(text_content: str) -> str:
    """Generate embedding vector for the given text.

    Spec: FS-AI-NL2SQL-001 -- 384-dim via all-MiniLM-L6-v2.
    Returns pgvector-compatible string "[0.1,0.2,...]" for use in raw SQL
    with ::vector cast (avoids asyncpg type registration issues).
    """
    model = _get_embedding_model()
    embedding = model.encode(text_content, normalize_embeddings=True)
    return "[" + ",".join(str(float(x)) for x in embedding) + "]"


# ---------------------------------------------------------------------------
# SubgraphContext -- the result of GraphRAG retrieval
# ---------------------------------------------------------------------------

@dataclass
class SubgraphContext:
    """Extracted subgraph context for LLM prompt construction.

    Spec: FS-AI-NL2SQL-001 Section 4.2 -- Subgraph to LLM Context.
    """

    tables: list[str] = field(default_factory=list)
    columns: dict[str, list[str]] = field(default_factory=dict)  # table -> [col1, col2]
    join_paths: list[tuple[str, str, str]] = field(default_factory=list)  # (tbl1.col, tbl2.col, edge_type)
    metrics: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Convert subgraph to LLM prompt schema text.

        Spec: FS-AI-NL2SQL-001 Section 4.2 -- only relevant subgraph,
        not the full schema, reducing token usage.
        """
        lines = ["DATABASE SCHEMA (relevant tables from Knowledge Graph):"]
        lines.append("")

        for table in self.tables:
            cols = self.columns.get(table, [])
            col_str = ", ".join(cols) if cols else "..."
            lines.append(f"-- {table}")
            lines.append(f"{table}({col_str})")
            lines.append("")

        if self.join_paths:
            lines.append("-- Join paths (Foreign Keys):")
            for src, tgt, etype in self.join_paths:
                lines.append(f"  {src} -> {tgt} ({etype})")
            lines.append("")

        if self.metrics:
            lines.append(f"-- Business metrics: {', '.join(self.metrics)}")
        if self.concepts:
            lines.append(f"-- Business concepts: {', '.join(self.concepts)}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# SchemaGraphBuilder -- information_schema -> Knowledge Graph
# ---------------------------------------------------------------------------

class SchemaGraphBuilder:
    """Builds a Schema Knowledge Graph from a target DB's information_schema.

    Spec: FS-AI-NL2SQL-001 Section 3.4
    Queries TARGET DB via adapter pool, stores results in SYSTEM DB.
    """

    async def build_graph(
        self,
        session: AsyncSession,
        instance_id: UUID,
        adapter_pool,
    ) -> tuple[int, int]:
        """Build Knowledge Graph from target DB information_schema.

        Spec: FS-AI-NL2SQL-001 Section 3.4 -- Schema -> Graph auto generation.

        1. Query information_schema.tables -> Table nodes
        2. Query information_schema.columns -> Column nodes + HAS_COLUMN edges
        3. Query pg_constraint (FK) -> FOREIGN_KEY edges
        4. Generate embeddings for each node (sentence-transformers)
        5. Store in graph_nodes/graph_edges tables

        Args:
            session: System DB async session (for storing graph).
            instance_id: Target DB instance UUID.
            adapter_pool: asyncpg connection pool to the target DB.

        Returns:
            Tuple of (nodes_created, edges_created).
        """
        # Spec: FS-AI-NL2SQL-001 -- clear existing graph for this instance before rebuild
        await session.execute(
            delete(GraphNode).where(GraphNode.instance_id == instance_id)
        )
        await session.flush()

        node_count = 0
        edge_count = 0

        # Track node IDs for edge creation
        table_nodes: dict[str, UUID] = {}  # "schema.table" -> node_id
        column_nodes: dict[str, UUID] = {}  # "schema.table.column" -> node_id

        # --- Step 1: Table nodes ---
        async with adapter_pool.acquire() as conn:
            tables = await conn.fetch(
                """
                SELECT table_schema, table_name, obj_description(
                    (quote_ident(table_schema) || '.' || quote_ident(table_name))::regclass
                ) AS table_comment
                FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                  AND table_type = 'BASE TABLE'
                ORDER BY table_schema, table_name
                """
            )

        for row in tables:
            schema = row["table_schema"]
            tname = row["table_name"]
            comment = row["table_comment"] or ""
            full_name = f"{schema}.{tname}" if schema != "public" else tname

            desc_text = f"Table: {full_name}"
            if comment:
                desc_text += f" -- {comment}"

            embedding_str = _compute_embedding(desc_text)
            node_id = uuid4()

            # Use raw SQL with ::vector cast to avoid asyncpg type registration
            await session.execute(
                text("""
                    INSERT INTO graph_nodes (id, node_type, name, description, metadata, embedding, instance_id)
                    VALUES (:id, :node_type, :name, :description, CAST(:metadata AS jsonb), CAST(:embedding AS vector), :instance_id)
                """),
                {
                    "id": node_id,
                    "node_type": "table",
                    "name": full_name,
                    "description": comment or None,
                    "metadata": json.dumps({"schema": schema, "table": tname}),
                    "embedding": embedding_str,
                    "instance_id": instance_id,
                },
            )
            table_nodes[f"{schema}.{tname}"] = node_id
            node_count += 1

        await session.flush()

        # --- Step 2: Column nodes + HAS_COLUMN edges ---
        async with adapter_pool.acquire() as conn:
            columns = await conn.fetch(
                """
                SELECT table_schema, table_name, column_name, data_type,
                       is_nullable, column_default,
                       col_description(
                           (quote_ident(table_schema) || '.' || quote_ident(table_name))::regclass,
                           ordinal_position
                       ) AS col_comment
                FROM information_schema.columns
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                ORDER BY table_schema, table_name, ordinal_position
                """
            )

        for row in columns:
            schema = row["table_schema"]
            tname = row["table_name"]
            cname = row["column_name"]
            dtype = row["data_type"]
            comment = row["col_comment"] or ""

            full_table = f"{schema}.{tname}" if schema != "public" else tname
            full_col = f"{full_table}.{cname}"

            desc_text = f"Column: {full_col} ({dtype})"
            if comment:
                desc_text += f" -- {comment}"

            embedding_str = _compute_embedding(desc_text)
            col_id = uuid4()

            await session.execute(
                text("""
                    INSERT INTO graph_nodes (id, node_type, name, description, metadata, embedding, instance_id)
                    VALUES (:id, :node_type, :name, :description, CAST(:metadata AS jsonb), CAST(:embedding AS vector), :instance_id)
                """),
                {
                    "id": col_id,
                    "node_type": "column",
                    "name": full_col,
                    "description": comment or None,
                    "metadata": json.dumps({
                        "schema": schema,
                        "table": tname,
                        "column": cname,
                        "data_type": dtype,
                        "is_nullable": row["is_nullable"],
                    }),
                    "embedding": embedding_str,
                    "instance_id": instance_id,
                },
            )
            column_nodes[f"{schema}.{tname}.{cname}"] = col_id
            node_count += 1

            # HAS_COLUMN edge: table -> column
            table_key = f"{schema}.{tname}"
            if table_key in table_nodes:
                edge = GraphEdge(
                    id=uuid4(),
                    source_id=table_nodes[table_key],
                    target_id=col_id,
                    edge_type="has_column",
                    metadata_extra={"data_type": dtype},
                )
                session.add(edge)
                edge_count += 1

        await session.flush()

        # --- Step 3: FOREIGN_KEY edges ---
        async with adapter_pool.acquire() as conn:
            fk_rows = await conn.fetch(
                """
                SELECT
                    con.conname AS constraint_name,
                    src_ns.nspname AS src_schema,
                    src_cl.relname AS src_table,
                    src_att.attname AS src_column,
                    tgt_ns.nspname AS tgt_schema,
                    tgt_cl.relname AS tgt_table,
                    tgt_att.attname AS tgt_column
                FROM pg_constraint con
                JOIN pg_class src_cl ON con.conrelid = src_cl.oid
                JOIN pg_namespace src_ns ON src_cl.relnamespace = src_ns.oid
                JOIN pg_class tgt_cl ON con.confrelid = tgt_cl.oid
                JOIN pg_namespace tgt_ns ON tgt_cl.relnamespace = tgt_ns.oid
                CROSS JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS sk(attnum, ord)
                CROSS JOIN LATERAL unnest(con.confkey) WITH ORDINALITY AS tk(attnum, ord)
                JOIN pg_attribute src_att ON src_att.attrelid = src_cl.oid
                    AND src_att.attnum = sk.attnum
                JOIN pg_attribute tgt_att ON tgt_att.attrelid = tgt_cl.oid
                    AND tgt_att.attnum = tk.attnum
                WHERE con.contype = 'f'
                  AND sk.ord = tk.ord
                  AND src_ns.nspname NOT IN ('pg_catalog', 'information_schema')
                ORDER BY con.conname
                """
            )

        for row in fk_rows:
            src_key = f"{row['src_schema']}.{row['src_table']}.{row['src_column']}"
            tgt_key = f"{row['tgt_schema']}.{row['tgt_table']}.{row['tgt_column']}"

            src_id = column_nodes.get(src_key)
            tgt_id = column_nodes.get(tgt_key)

            if src_id and tgt_id:
                edge = GraphEdge(
                    id=uuid4(),
                    source_id=src_id,
                    target_id=tgt_id,
                    edge_type="foreign_key",
                    metadata_extra={
                        "constraint_name": row["constraint_name"],
                        "src_column": src_key,
                        "tgt_column": tgt_key,
                    },
                )
                session.add(edge)
                edge_count += 1

        await session.flush()

        logger.info(
            "graph_rag.build_complete",
            instance_id=str(instance_id),
            nodes=node_count,
            edges=edge_count,
        )
        return node_count, edge_count

    async def add_business_metric(
        self,
        session: AsyncSession,
        instance_id: UUID,
        name: str,
        description: str,
        source_columns: list[str],
    ) -> tuple[UUID, int]:
        """Add a business metric node + METRIC_SOURCE edges.

        Spec: FS-AI-NL2SQL-001 Section 3.4 -- manual business metric registration.

        Args:
            session: System DB async session.
            instance_id: Target DB instance.
            name: Metric name (e.g. 'avg_query_time').
            description: Metric description.
            source_columns: Source columns in 'table.column' format.

        Returns:
            Tuple of (node_id, edges_created).
        """
        desc_text = f"Metric: {name} -- {description}"
        embedding_str = _compute_embedding(desc_text)
        node_id = uuid4()

        await session.execute(
            text("""
                INSERT INTO graph_nodes (id, node_type, name, description, metadata, embedding, instance_id)
                VALUES (:id, :node_type, :name, :description, CAST(:metadata AS jsonb), CAST(:embedding AS vector), :instance_id)
            """),
            {
                "id": node_id,
                "node_type": "metric",
                "name": name,
                "description": description,
                "metadata": json.dumps({"source_columns": source_columns}),
                "embedding": embedding_str,
                "instance_id": instance_id,
            },
        )
        await session.flush()

        # Create a lightweight ORM reference for edge creation
        class _NodeRef:
            id = node_id
        metric_node = _NodeRef()

        edges_created = 0
        for col_ref in source_columns:
            # Find the column node by name
            stmt = select(GraphNode).where(
                GraphNode.instance_id == instance_id,
                GraphNode.node_type == "column",
                GraphNode.name == col_ref,
            )
            result = await session.execute(stmt)
            col_node = result.scalar_one_or_none()
            if col_node:
                edge = GraphEdge(
                    id=uuid4(),
                    source_id=metric_node.id,
                    target_id=col_node.id,
                    edge_type="metric_source",
                    metadata_extra={},
                )
                session.add(edge)
                edges_created += 1
            else:
                logger.warning(
                    "graph_rag.metric_source_not_found",
                    metric=name,
                    column=col_ref,
                )

        await session.flush()
        logger.info(
            "graph_rag.metric_added",
            name=name,
            edges=edges_created,
        )
        return metric_node.id, edges_created

    async def add_business_concept(
        self,
        session: AsyncSession,
        instance_id: UUID,
        name: str,
        description: str,
        related_metrics: list[str],
    ) -> tuple[UUID, int]:
        """Add a business concept node + CONCEPT_MAP edges.

        Spec: FS-AI-NL2SQL-001 Section 3.4 -- manual business concept registration.

        Args:
            session: System DB async session.
            instance_id: Target DB instance.
            name: Concept name (e.g. 'slow_query').
            description: Concept description.
            related_metrics: Related metric names.

        Returns:
            Tuple of (node_id, edges_created).
        """
        desc_text = f"Concept: {name} -- {description}"
        embedding_str = _compute_embedding(desc_text)
        node_id = uuid4()

        await session.execute(
            text("""
                INSERT INTO graph_nodes (id, node_type, name, description, metadata, embedding, instance_id)
                VALUES (:id, :node_type, :name, :description, CAST(:metadata AS jsonb), CAST(:embedding AS vector), :instance_id)
            """),
            {
                "id": node_id,
                "node_type": "concept",
                "name": name,
                "description": description,
                "metadata": json.dumps({"related_metrics": related_metrics}),
                "embedding": embedding_str,
                "instance_id": instance_id,
            },
        )
        await session.flush()

        edges_created = 0
        for metric_name in related_metrics:
            stmt = select(GraphNode).where(
                GraphNode.instance_id == instance_id,
                GraphNode.node_type == "metric",
                GraphNode.name == metric_name,
            )
            result = await session.execute(stmt)
            metric_node = result.scalar_one_or_none()
            if metric_node:
                edge = GraphEdge(
                    id=uuid4(),
                    source_id=node_id,
                    target_id=metric_node.id,
                    edge_type="concept_map",
                    metadata_extra={},
                )
                session.add(edge)
                edges_created += 1
            else:
                logger.warning(
                    "graph_rag.concept_metric_not_found",
                    concept=name,
                    metric=metric_name,
                )

        await session.flush()
        logger.info(
            "graph_rag.concept_added",
            name=name,
            edges=edges_created,
        )
        return node_id, edges_created


# ---------------------------------------------------------------------------
# GraphRAGRetriever -- question -> subgraph extraction
# ---------------------------------------------------------------------------

class GraphRAGRetriever:
    """Retrieves a relevant subgraph for a natural language question.

    Spec: FS-AI-NL2SQL-001 Section 4.1
    Queries SYSTEM DB where graph_nodes/graph_edges are stored.
    """

    async def retrieve(
        self,
        session: AsyncSession,
        question: str,
        instance_id: UUID,
        top_k: int = 10,
    ) -> SubgraphContext:
        """Extract relevant schema subgraph for a question.

        Spec: FS-AI-NL2SQL-001 Section 4.1
        1. Embed question (sentence-transformers)
        2. pgvector cosine search -> top_k graph_nodes
        3. Expand 1-hop neighbors (edges)
        4. Build SubgraphContext with tables, columns, join_paths

        Args:
            session: System DB async session.
            question: User's natural language question.
            instance_id: Target DB instance.
            top_k: Number of nearest nodes to retrieve.

        Returns:
            SubgraphContext with relevant tables, columns, joins, etc.
        """
        # Step 1: Embed the question
        try:
            query_embedding = _compute_embedding(question)
        except Exception as exc:
            logger.error("graph_rag.retrieve_embedding_failed", error=str(exc))
            return SubgraphContext()

        # Convert numpy array to pgvector string format for raw SQL
        embedding_str = "[" + ",".join(str(float(v)) for v in query_embedding) + "]"

        # Step 2: pgvector cosine similarity search for top_k nodes
        sql = text("""
            SELECT
                id, node_type, name, metadata AS metadata_extra,
                1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
            FROM graph_nodes
            WHERE instance_id = :instance_id
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:query_vec AS vector)
            LIMIT :top_k
        """)

        try:
            result = await session.execute(sql, {
                "query_vec": embedding_str,
                "instance_id": instance_id,
                "top_k": top_k,
            })
            seed_rows = result.fetchall()
        except Exception as exc:
            logger.error("graph_rag.retrieve_search_failed", error=str(exc))
            return SubgraphContext()

        if not seed_rows:
            return SubgraphContext()

        seed_ids = [row.id for row in seed_rows]

        # Step 3: 1-hop expansion -- find all edges from/to seed nodes
        edge_sql = text("""
            SELECT
                ge.source_id, ge.target_id, ge.edge_type,
                ge.metadata AS edge_metadata
            FROM graph_edges ge
            WHERE ge.source_id = ANY(:node_ids)
               OR ge.target_id = ANY(:node_ids)
        """)

        try:
            edge_result = await session.execute(edge_sql, {"node_ids": seed_ids})
            edge_rows = edge_result.fetchall()
        except Exception as exc:
            logger.error("graph_rag.retrieve_edges_failed", error=str(exc))
            edge_rows = []

        # Collect all neighbor node IDs from edges
        neighbor_ids = set()
        for erow in edge_rows:
            neighbor_ids.add(erow.source_id)
            neighbor_ids.add(erow.target_id)

        # Remove already-known seed IDs
        extra_ids = neighbor_ids - set(seed_ids)

        # Fetch neighbor node details
        neighbor_nodes = {}
        if extra_ids:
            neighbor_sql = text("""
                SELECT id, node_type, name, metadata AS metadata_extra
                FROM graph_nodes
                WHERE id = ANY(:ids)
            """)
            try:
                nb_result = await session.execute(neighbor_sql, {"ids": list(extra_ids)})
                for nb in nb_result.fetchall():
                    neighbor_nodes[nb.id] = nb
            except Exception as exc:
                logger.error("graph_rag.retrieve_neighbors_failed", error=str(exc))

        # Build a unified node map
        all_nodes: dict[UUID, dict] = {}
        for row in seed_rows:
            all_nodes[row.id] = {
                "node_type": row.node_type,
                "name": row.name,
                "metadata_extra": row.metadata_extra or {},
            }
        for nid, nb in neighbor_nodes.items():
            all_nodes[nid] = {
                "node_type": nb.node_type,
                "name": nb.name,
                "metadata_extra": nb.metadata_extra or {},
            }

        # Step 4: Build SubgraphContext
        ctx = SubgraphContext()

        for nid, info in all_nodes.items():
            ntype = info["node_type"]
            name = info["name"]
            meta = info["metadata_extra"]

            if ntype == "table":
                if name not in ctx.tables:
                    ctx.tables.append(name)

            elif ntype == "column":
                table_name = meta.get("table", "")
                schema_name = meta.get("schema", "public")
                full_table = f"{schema_name}.{table_name}" if schema_name != "public" else table_name
                col_name = meta.get("column", name.split(".")[-1] if "." in name else name)
                dtype = meta.get("data_type", "")
                col_display = f"{col_name} {dtype}".strip()

                if full_table not in ctx.tables:
                    ctx.tables.append(full_table)
                ctx.columns.setdefault(full_table, [])
                if col_display not in ctx.columns[full_table]:
                    ctx.columns[full_table].append(col_display)

            elif ntype == "metric":
                if name not in ctx.metrics:
                    ctx.metrics.append(name)

            elif ntype == "concept":
                if name not in ctx.concepts:
                    ctx.concepts.append(name)

        # Extract join paths from FOREIGN_KEY edges
        for erow in edge_rows:
            if erow.edge_type == "foreign_key":
                emeta = erow.edge_metadata or {}
                src_col = emeta.get("src_column", "")
                tgt_col = emeta.get("tgt_column", "")
                if src_col and tgt_col:
                    path = (src_col, tgt_col, "foreign_key")
                    if path not in ctx.join_paths:
                        ctx.join_paths.append(path)

        logger.info(
            "graph_rag.retrieve_complete",
            tables=len(ctx.tables),
            columns=sum(len(v) for v in ctx.columns.values()),
            joins=len(ctx.join_paths),
        )
        return ctx


async def has_graph_for_instance(session: AsyncSession, instance_id: UUID) -> bool:
    """Check if a Knowledge Graph exists for the given instance.

    Spec: FS-AI-NL2SQL-001 -- fallback logic: if no graph, use hardcoded schema.
    """
    stmt = select(func.count()).select_from(GraphNode).where(
        GraphNode.instance_id == instance_id,
        GraphNode.node_type == "table",
    )
    result = await session.execute(stmt)
    count = result.scalar_one()
    return count > 0
