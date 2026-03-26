# Spec: FR-AI-002, FS-AI-RAG-001
"""Unit tests for RAG service — prompt formatting and graceful fallback.

Tests the format_for_prompt pure function and search_similar with mocked pgvector.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.schemas.rag import RAGSearchResult
from app.services.rag import format_for_prompt, search_similar
from tests.conftest import spec_ref


class TestFormatForPrompt:
    """Tests for format_for_prompt — pure function, no mocks needed."""

    @spec_ref("FS-AI-RAG-001", "AC-5")
    def test_format_for_prompt_empty(self) -> None:
        """Empty results list returns the 'no similar' sentinel string."""
        # Spec: FS-AI-RAG-001 Section 3.3
        result = format_for_prompt([])
        assert result == "No similar past incidents found."

    @spec_ref("FS-AI-RAG-001", "AC-5")
    def test_format_for_prompt_with_results(self) -> None:
        """Non-empty results are formatted with similarity, summary, and optional fields."""
        # Spec: FS-AI-RAG-001 Section 3.3
        results = [
            RAGSearchResult(
                incident_id=uuid4(),
                similarity=0.92,
                summary="High CPU due to missing index on orders table",
                root_cause="Sequential scan on orders.created_at",
                resolution="CREATE INDEX CONCURRENTLY idx_orders_created ON orders(created_at)",
                created_at=datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc),
            ),
            RAGSearchResult(
                incident_id=uuid4(),
                similarity=0.85,
                summary="Connection saturation during peak hours",
                root_cause=None,
                resolution=None,
                created_at=datetime(2026, 3, 18, 8, 0, 0, tzinfo=timezone.utc),
            ),
        ]

        output = format_for_prompt(results)

        # Check structure
        assert "Similar Incident #1" in output
        assert "similarity: 0.92" in output
        assert "High CPU due to missing index" in output
        assert "Root Cause: Sequential scan" in output
        assert "Resolution: CREATE INDEX CONCURRENTLY" in output

        assert "Similar Incident #2" in output
        assert "similarity: 0.85" in output
        assert "Connection saturation" in output
        # No root_cause or resolution for second result
        assert "Root Cause:" not in output.split("Similar Incident #2")[1] or \
               output.count("Root Cause:") == 1

    @spec_ref("FS-AI-RAG-001", "AC-5")
    def test_format_for_prompt_single_result_no_optional_fields(self) -> None:
        """Single result with no root_cause/resolution still formats correctly."""
        results = [
            RAGSearchResult(
                incident_id=uuid4(),
                similarity=0.75,
                summary="Replication lag spike",
                root_cause=None,
                resolution=None,
                created_at=datetime(2026, 3, 15, 6, 0, 0, tzinfo=timezone.utc),
            ),
        ]

        output = format_for_prompt(results)

        assert "Similar Incident #1" in output
        assert "similarity: 0.75" in output
        assert "Summary: Replication lag spike" in output
        assert "Root Cause:" not in output
        assert "Resolution:" not in output


class TestSearchSimilarFallback:
    """Tests for search_similar with mocked embedding and DB."""

    @spec_ref("FS-AI-RAG-001", "AC-2")
    @pytest.mark.asyncio
    async def test_search_similar_no_pgvector(self) -> None:
        """When pgvector query fails (e.g., extension not installed),
        returns empty list gracefully without raising.
        """
        # Spec: FS-AI-RAG-001 — graceful fallback on search failure
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=Exception("relation 'rag_documents' does not exist")
        )

        with patch(
            "app.services.rag._compute_embedding",
            return_value=[0.1] * 384,
        ), patch(
            "app.services.rag._get_from_cache",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "app.services.rag._set_to_cache",
            new_callable=AsyncMock,
        ):
            results, elapsed_ms = await search_similar(
                mock_session,
                "high cpu usage on production database",
                top_k=3,
                min_similarity=0.7,
            )

        assert results == []
        assert isinstance(elapsed_ms, int)
        assert elapsed_ms >= 0
