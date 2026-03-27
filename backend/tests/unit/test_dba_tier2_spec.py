# Spec: FS-DBA-001 Tier 2 (J1/J2/J3)
"""Tests for DBA Agent Tier 2 — Query Simulation, Action Memory, LLM Retry."""

import asyncio
from uuid import uuid4

import pytest

from tests.conftest import spec_ref


# ---------------------------------------------------------------------------
# J1: Query Simulator
# ---------------------------------------------------------------------------

@spec_ref("FS-DBA-001", "AC-2")
def test_tier2_query_simulator_exists():
    """J1: QuerySimulator with simulate() and estimate_index_impact()."""
    from app.agents.query_simulator import QuerySimulator, SimulationResult

    sim = QuerySimulator()
    assert hasattr(sim, "simulate")
    assert hasattr(sim, "estimate_index_impact")

    # SimulationResult fields
    r = SimulationResult(
        feasible=True, cost=50, estimated_rows=100,
        summary="Low impact", requires_approval=False,
    )
    assert r.to_dict()["feasible"] is True
    assert r.cost == 50


@spec_ref("FS-DBA-001", "AC-2")
def test_tier2_cost_thresholds():
    """J1: Cost thresholds are defined."""
    from app.agents.query_simulator import (
        COST_THRESHOLD_DANGEROUS,
        COST_THRESHOLD_WARNING,
        ROW_THRESHOLD_DANGEROUS,
    )

    assert COST_THRESHOLD_WARNING < COST_THRESHOLD_DANGEROUS
    assert ROW_THRESHOLD_DANGEROUS > 0


# ---------------------------------------------------------------------------
# J2: Action Memory
# ---------------------------------------------------------------------------

@spec_ref("FS-DBA-001", "AC-3")
def test_tier2_action_memory_exists():
    """J2: ActionMemory with get_context() and get_similar_actions()."""
    from app.agents.action_memory import ActionMemory

    mem = ActionMemory()
    assert hasattr(mem, "get_context")
    assert hasattr(mem, "get_similar_actions")


@spec_ref("FS-DBA-001", "AC-3")
def test_tier2_action_memory_max_history():
    """J2: MAX_HISTORY limits context size."""
    from app.agents.action_memory import MAX_HISTORY

    assert MAX_HISTORY > 0
    assert MAX_HISTORY <= 10  # reasonable limit


# ---------------------------------------------------------------------------
# J3: LLM Retry + Fallback
# ---------------------------------------------------------------------------

@spec_ref("FS-DBA-001", "AC-4")
def test_tier2_retry_success_first_try():
    """J3: retry_llm_call succeeds on first attempt."""
    from app.agents.llm_retry import retry_llm_call

    async def _ok():
        return "success"

    result = asyncio.get_event_loop().run_until_complete(
        retry_llm_call(_ok)
    )
    assert result == "success"


@spec_ref("FS-DBA-001", "AC-4")
def test_tier2_retry_recovers_on_second():
    """J3: retry_llm_call recovers after 1 failure."""
    from app.agents.llm_retry import retry_llm_call

    call_count = 0

    async def _fail_once():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("LLM timeout")
        return "recovered"

    result = asyncio.get_event_loop().run_until_complete(
        retry_llm_call(_fail_once, max_retries=2, backoff_base=0.01)
    )
    assert result == "recovered"
    assert call_count == 2


@spec_ref("FS-DBA-001", "AC-4")
def test_tier2_retry_fallback():
    """J3: retry_llm_call uses fallback when primary exhausted."""
    from app.agents.llm_retry import retry_llm_call

    async def _always_fail():
        raise RuntimeError("primary down")

    async def _fallback():
        return "fallback_result"

    result = asyncio.get_event_loop().run_until_complete(
        retry_llm_call(
            _always_fail,
            max_retries=1,
            backoff_base=0.01,
            fallback_func=_fallback,
        )
    )
    assert result == "fallback_result"


@spec_ref("FS-DBA-001", "AC-4")
def test_tier2_retry_safe_mode():
    """J3: retry_llm_call returns safe_mode_response when all fails."""
    from app.agents.llm_retry import retry_llm_call

    async def _always_fail():
        raise RuntimeError("everything down")

    async def _fallback_fail():
        raise RuntimeError("fallback also down")

    result = asyncio.get_event_loop().run_until_complete(
        retry_llm_call(
            _always_fail,
            max_retries=0,
            backoff_base=0.01,
            fallback_func=_fallback_fail,
            safe_mode_response="SAFE_MODE: check manually",
        )
    )
    assert result == "SAFE_MODE: check manually"


@spec_ref("FS-DBA-001", "AC-4")
def test_tier2_retry_config_presets():
    """J3: LLMRetryConfig has presets for each agent type."""
    from app.agents.llm_retry import LLMRetryConfig

    tuning = LLMRetryConfig.for_tuning()
    assert tuning.max_retries >= 2

    copilot = LLMRetryConfig.for_copilot()
    assert copilot.max_retries >= 3

    nl2sql = LLMRetryConfig.for_nl2sql()
    assert nl2sql.max_retries >= 1
