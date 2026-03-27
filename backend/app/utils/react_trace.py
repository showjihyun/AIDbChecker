# Spec: FS-AI-TRACE-001
"""ReAct Trace — step-by-step reasoning trace collector for AI agents.

Usage:
    trace = ReActTrace("mtl_rca")
    trace.thought("CPU 92% detected, baseline deviation")
    trace.action("RAG similar incident search")
    trace.observation("3 similar incidents found (similarity: 0.89)")
    trace.thought("All past cases point to missing index")
    trace.result("anomaly_type=query_performance, confidence=0.87")
    return trace.to_dict()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class TraceStep:
    """A single step in the ReAct trace."""

    step_type: str  # thought | action | observation | result | error
    content: str
    timestamp_ms: int
    metadata: dict | None = None


@dataclass
class ReActTrace:
    """Collects ReAct-style reasoning steps during AI execution.

    Spec: FS-AI-TRACE-001 Section 2.
    """

    agent: str
    steps: list[TraceStep] = field(default_factory=list)
    _start_time: float = field(default_factory=time.monotonic, repr=False)
    status: str = "running"

    def _elapsed(self) -> int:
        return int((time.monotonic() - self._start_time) * 1000)

    def thought(self, content: str, **meta: object) -> None:
        """Record a reasoning step."""
        self.steps.append(TraceStep(
            step_type="thought",
            content=content,
            timestamp_ms=self._elapsed(),
            metadata=dict(meta) if meta else None,
        ))

    def action(self, content: str, **meta: object) -> None:
        """Record an action being taken."""
        self.steps.append(TraceStep(
            step_type="action",
            content=content,
            timestamp_ms=self._elapsed(),
            metadata=dict(meta) if meta else None,
        ))

    def observation(self, content: str, **meta: object) -> None:
        """Record an observation from an action result."""
        self.steps.append(TraceStep(
            step_type="observation",
            content=content,
            timestamp_ms=self._elapsed(),
            metadata=dict(meta) if meta else None,
        ))

    def result(self, content: str, **meta: object) -> None:
        """Record the final result."""
        self.status = "completed"
        self.steps.append(TraceStep(
            step_type="result",
            content=content,
            timestamp_ms=self._elapsed(),
            metadata=dict(meta) if meta else None,
        ))

    def error(self, content: str, **meta: object) -> None:
        """Record an error."""
        self.status = "failed"
        self.steps.append(TraceStep(
            step_type="error",
            content=content,
            timestamp_ms=self._elapsed(),
            metadata=dict(meta) if meta else None,
        ))

    @property
    def total_duration_ms(self) -> int:
        return self._elapsed()

    def to_dict(self) -> dict:
        """Serialize to API response format."""
        return {
            "agent": self.agent,
            "steps": [
                {
                    "step_type": s.step_type,
                    "content": s.content,
                    "timestamp_ms": s.timestamp_ms,
                    "metadata": s.metadata,
                }
                for s in self.steps
            ],
            "total_duration_ms": self.total_duration_ms,
            "status": self.status,
        }
