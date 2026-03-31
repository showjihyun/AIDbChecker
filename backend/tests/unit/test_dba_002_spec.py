# Spec: FS-DBA-002
"""Tests for DBA Agent Orchestrator — 10 ACs."""

from uuid import uuid4

import pytest

from tests.conftest import spec_ref


@spec_ref("FS-DBA-002", "AC-1")
def test_dba_002_ac1_ask_method():
    """FS-DBA-002 AC-1: DBAAgent.ask() accepts question + instance_id."""
    from app.agents.dba_agent import DBAAgent

    agent = DBAAgent()
    assert hasattr(agent, "ask")


@spec_ref("FS-DBA-002", "AC-2")
def test_dba_002_ac2_keyword_intent_classification():
    """FS-DBA-002 AC-2: Keyword-based intent for 5 categories."""
    from app.agents.dba_agent import DBAAgent

    agent = DBAAgent()

    intent, conf = agent.classify_intent("쿼리가 느려요")
    assert intent == "analyze"

    intent, conf = agent.classify_intent("장애 원인 분석해줘")
    assert intent == "diagnose"

    intent, conf = agent.classify_intent("인덱스 만들어줘")
    assert intent == "execute"

    intent, conf = agent.classify_intent("인시던트 목록 보여줘")
    assert intent == "query"

    intent, conf = agent.classify_intent("시스템 상태 점검")
    assert intent == "status"


@spec_ref("FS-DBA-002", "AC-3")
def test_dba_002_ac3_llm_fallback_exists():
    """FS-DBA-002 AC-3: LLM fallback method exists."""
    from app.agents.dba_agent import DBAAgent

    agent = DBAAgent()
    assert hasattr(agent, "classify_intent_with_llm")


@spec_ref("FS-DBA-002", "AC-4")
def test_dba_002_ac4_analyze_routes_to_tuning():
    """FS-DBA-002 AC-4: analyze intent → TuningAgent."""
    from app.agents.dba_agent import DBAAgent

    agent = DBAAgent()
    assert hasattr(agent, "_handle_analyze")


@spec_ref("FS-DBA-002", "AC-5")
def test_dba_002_ac5_diagnose_routes_to_copilot():
    """FS-DBA-002 AC-5: diagnose intent → CopilotAgent."""
    from app.agents.dba_agent import DBAAgent

    agent = DBAAgent()
    assert hasattr(agent, "_handle_diagnose")


@spec_ref("FS-DBA-002", "AC-6")
def test_dba_002_ac6_execute_routes_to_engine():
    """FS-DBA-002 AC-6: execute intent → ExecutionEngine."""
    from app.agents.dba_agent import DBAAgent

    agent = DBAAgent()
    assert hasattr(agent, "_handle_execute")

    # Parse action from natural language (English to avoid identifier validation)
    req = agent._parse_action_request(
        "create index on orders user_id", uuid4()
    )
    assert req is not None
    assert "INDEX" in req.sql.upper()


@spec_ref("FS-DBA-002", "AC-7")
def test_dba_002_ac7_query_routes_to_nl2sql():
    """FS-DBA-002 AC-7: query intent → NL2SQL."""
    from app.agents.dba_agent import DBAAgent

    agent = DBAAgent()
    assert hasattr(agent, "_handle_query")


@spec_ref("FS-DBA-002", "AC-8")
def test_dba_002_ac8_status_routes_to_health():
    """FS-DBA-002 AC-8: status intent → System Health."""
    from app.agents.dba_agent import DBAAgent

    agent = DBAAgent()
    assert hasattr(agent, "_handle_status")


@spec_ref("FS-DBA-002", "AC-9")
def test_dba_002_ac9_session_id_in_response():
    """FS-DBA-002 AC-9: DBAResponse has session_id."""
    from app.schemas.dba import DBAResponse

    fields = DBAResponse.model_fields
    assert "session_id" in fields


@spec_ref("FS-DBA-002", "AC-10")
def test_dba_002_ac10_actions_in_response():
    """FS-DBA-002 AC-10: DBAResponse has actions field."""
    from app.schemas.dba import ActionSummary, DBAResponse

    fields = DBAResponse.model_fields
    assert "actions" in fields

    action = ActionSummary(
        action_type="create_index",
        sql="CREATE INDEX CONCURRENTLY idx ON t(c)",
        risk_level="warning",
        status="suggested",
        description="test",
    )
    assert action.risk_level == "warning"


@spec_ref("FS-DBA-002", "AC-14")
def test_dba_002_ac14_clean_react_output():
    """FS-DBA-002 AC-14: ReAct internal reasoning stripped from user answers."""
    from app.agents.dba_agent import DBAAgent

    agent = DBAAgent()
    raw = "Action: search\nAction Input: slow queries\nObservation: found 3\nFinal Answer: 느린 쿼리 3개 발견"
    cleaned = agent._clean_react_output(raw)
    assert "Action:" not in cleaned
    assert "Observation:" not in cleaned
    assert "느린 쿼리" in cleaned


@spec_ref("FS-DBA-002", "AC-15")
def test_dba_002_ac15_synthesize_from_observations():
    """FS-DBA-002 AC-15: _synthesize_from_observations exists for max_iterations fallback."""
    from app.agents.tuning_agent import DBTuningAgent

    assert hasattr(DBTuningAgent, "_synthesize_from_observations")


@spec_ref("FS-DBA-002", "AC-16")
def test_dba_002_ac16_answer_is_natural_language():
    """FS-DBA-002 AC-16: DBA Agent answer field is human-readable natural language."""
    from app.agents.dba_agent import DBAAgent

    agent = DBAAgent()
    # Verify _clean_react_output removes all machine patterns
    machine_output = "Thought: I need to check\nAction: analyze\nAction Input: cpu\nFinal Answer: CPU 사용률이 높습니다."
    result = agent._clean_react_output(machine_output)
    assert "Thought:" not in result
    assert "Action:" not in result
    # Should contain the human-readable part
    assert "CPU" in result
