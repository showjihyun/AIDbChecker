# Spec: FS-AI-TRACE-001
"""Spec-Driven tests for ReAct Trace.

AC Coverage:
  AC-1: AI 응답에 trace 필드 포함
  AC-2: trace.steps에 최소 3단계 포함
  AC-5: total_duration_ms 추적
"""

import time

import pytest

from tests.conftest import spec_ref

from app.utils.react_trace import ReActTrace


@spec_ref("FS-AI-TRACE-001", "AC-1")
def test_trace_001_ac1_to_dict_has_required_fields():
    """AC-1: trace.to_dict()에 agent, steps, total_duration_ms, status 포함."""
    trace = ReActTrace("mtl_rca")
    trace.thought("Analyzing metrics")
    trace.result("Done")

    d = trace.to_dict()
    assert d["agent"] == "mtl_rca"
    assert isinstance(d["steps"], list)
    assert "total_duration_ms" in d
    assert d["status"] == "completed"


@spec_ref("FS-AI-TRACE-001", "AC-2")
def test_trace_001_ac2_minimum_3_steps():
    """AC-2: thought → action → result 최소 3단계."""
    trace = ReActTrace("copilot")
    trace.thought("Checking CPU metrics")
    trace.action("Running RAG search")
    trace.observation("3 similar incidents found")
    trace.result("Root cause identified")

    d = trace.to_dict()
    assert len(d["steps"]) >= 3

    types = [s["step_type"] for s in d["steps"]]
    assert "thought" in types
    assert "action" in types
    assert "result" in types


@spec_ref("FS-AI-TRACE-001", "AC-2")
def test_trace_001_ac2_step_types():
    """AC-2: 5개 step_type 모두 사용 가능."""
    trace = ReActTrace("test")
    trace.thought("t")
    trace.action("a")
    trace.observation("o")
    trace.result("r")
    trace.error("e")  # result 후에도 추가 가능

    types = {s.step_type for s in trace.steps}
    assert types == {"thought", "action", "observation", "result", "error"}


@spec_ref("FS-AI-TRACE-001", "AC-5")
def test_trace_001_ac5_duration_tracking():
    """AC-5: total_duration_ms가 0 이상."""
    trace = ReActTrace("nl2sql")
    trace.thought("Parsing question")
    trace.action("Generating SQL")
    trace.result("SQL generated")

    assert trace.total_duration_ms >= 0


@spec_ref("FS-AI-TRACE-001", "AC-5")
def test_trace_001_ac5_timestamp_ms_increasing():
    """AC-5: 각 step의 timestamp_ms가 단조 증가."""
    trace = ReActTrace("report")
    trace.thought("Start")
    trace.action("Fetching data")
    trace.observation("Data fetched")
    trace.result("Report done")

    timestamps = [s.timestamp_ms for s in trace.steps]
    for i in range(1, len(timestamps)):
        assert timestamps[i] >= timestamps[i - 1]


@spec_ref("FS-AI-TRACE-001", "AC-1")
def test_trace_001_ac1_status_transitions():
    """AC-1: status 전이 — running → completed/failed."""
    trace = ReActTrace("test")
    assert trace.status == "running"

    trace.result("Done")
    assert trace.status == "completed"

    trace2 = ReActTrace("test2")
    trace2.error("Failed")
    assert trace2.status == "failed"


@spec_ref("FS-AI-TRACE-001", "AC-1")
def test_trace_001_ac1_metadata_support():
    """AC-1: step에 metadata dict 첨부 가능."""
    trace = ReActTrace("mtl_rca")
    trace.action("RAG search", top_k=3, similarity=0.89)

    step = trace.steps[0]
    assert step.metadata is not None
    assert step.metadata["top_k"] == 3
    assert step.metadata["similarity"] == 0.89
