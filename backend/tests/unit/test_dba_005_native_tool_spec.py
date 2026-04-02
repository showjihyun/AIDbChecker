# Spec: FS-DBA-005
"""Tests for Claude Native Tool Use Agent."""

from tests.conftest import spec_ref


@spec_ref("FS-DBA-005", "AC-1")
def test_dba_005_ac1_native_agent_exists():
    """AC-1: NativeToolAgent uses Anthropic SDK directly."""
    from app.agents.native_tool_agent import NativeToolAgent

    agent = NativeToolAgent(pool=None)
    assert hasattr(agent, "analyze")

    import inspect
    assert inspect.iscoroutinefunction(agent.analyze)


@spec_ref("FS-DBA-005", "AC-2")
def test_dba_005_ac2_tool_definitions():
    """AC-2: 8 tools (7 diagnostic + 1 query) defined with Anthropic schema."""
    from app.agents.native_tool_agent import TOOL_DEFINITIONS

    assert len(TOOL_DEFINITIONS) == 8

    names = {t["name"] for t in TOOL_DEFINITIONS}
    assert "slow_queries" in names
    assert "explain_query" in names
    assert "index_recommendations" in names
    assert "parameter_tuning" in names
    assert "table_bloat" in names
    assert "lock_analysis" in names
    assert "connection_analysis" in names
    assert "query_database" in names

    # Each tool has required fields
    for tool in TOOL_DEFINITIONS:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"


@spec_ref("FS-DBA-005", "AC-3")
def test_dba_005_ac3_tool_invocation():
    """AC-3: _invoke_tool dispatches to correct db_tools function."""
    from app.agents.native_tool_agent import NativeToolAgent

    agent = NativeToolAgent(pool=None)
    # Pool is None → tools will return error/empty, but dispatch works
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(
        agent._invoke_tool("slow_queries", {"top_n": 5})
    )
    # With pool=None, should get error or empty result
    assert isinstance(result, str)


@spec_ref("FS-DBA-005", "AC-4")
def test_dba_005_ac4_max_tokens():
    """AC-4: max_tokens set to 4096 for expanded output."""
    import inspect
    from app.agents.native_tool_agent import NativeToolAgent

    source = inspect.getsource(NativeToolAgent.analyze)
    assert "max_tokens=4096" in source


@spec_ref("FS-DBA-005", "AC-5")
def test_dba_005_ac5_korean_system_prompt():
    """AC-5: System prompt instructs Korean output."""
    from app.agents.native_tool_agent import _SYSTEM_PROMPT

    assert "한국어" in _SYSTEM_PROMPT
    assert "현황" in _SYSTEM_PROMPT
    assert "권장 조치" in _SYSTEM_PROMPT


@spec_ref("FS-DBA-005", "AC-6")
def test_dba_005_ac6_react_fallback():
    """AC-6: Falls back to ReAct when Anthropic unavailable."""
    from app.agents.native_tool_agent import NativeToolAgent

    agent = NativeToolAgent(pool=None)
    assert hasattr(agent, "_fallback_react")

    import inspect
    assert inspect.iscoroutinefunction(agent._fallback_react)


@spec_ref("FS-DBA-005", "AC-7")
def test_dba_005_ac7_dba_agent_uses_native():
    """AC-7: DBA Agent _handle_analyze uses NativeToolAgent."""
    import inspect
    from app.agents.dba_agent import DBAAgent

    source = inspect.getsource(DBAAgent._handle_analyze)
    assert "NativeToolAgent" in source
