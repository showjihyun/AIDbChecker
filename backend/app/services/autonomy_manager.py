# Spec: FR-AUTO-005, FS-AUTO-002 AC-11
"""Dynamic Autonomy Downgrade — auto-reduce autonomy level on playbook failure.

Rules:
- Single failure: autonomy_level -= 1 (minimum 0)
- 3 consecutive failures: force to L0
- Reset failure counter on success

Phase 3 implementation. Tracks failure counts in-memory.
"""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

import structlog

logger = structlog.get_logger(__name__)

# instance_id → consecutive failure count
_failure_counts: dict[UUID, int] = defaultdict(int)

MAX_CONSECUTIVE_FAILURES = 3


def record_success(instance_id: UUID) -> None:
    """Reset failure counter on successful execution.

    Spec: FR-AUTO-005 — success resets the downgrade counter.
    """
    if instance_id in _failure_counts:
        prev = _failure_counts[instance_id]
        _failure_counts[instance_id] = 0
        if prev > 0:
            logger.info(
                "autonomy.failure_counter_reset",
                instance_id=str(instance_id),
                previous_failures=prev,
            )


def record_failure(instance_id: UUID, current_level: int) -> int:
    """Record a failure and return the new autonomy level.

    Spec: FR-AUTO-005, FS-AUTO-002 AC-11
    - Single failure: level -= 1
    - 3 consecutive failures: force to 0

    Returns the new recommended autonomy level.
    """
    _failure_counts[instance_id] += 1
    count = _failure_counts[instance_id]

    if count >= MAX_CONSECUTIVE_FAILURES:
        new_level = 0
        logger.warning(
            "autonomy.forced_to_l0",
            instance_id=str(instance_id),
            consecutive_failures=count,
        )
    else:
        new_level = max(current_level - 1, 0)
        logger.info(
            "autonomy.downgraded",
            instance_id=str(instance_id),
            old_level=current_level,
            new_level=new_level,
            consecutive_failures=count,
        )

    return new_level


def get_failure_count(instance_id: UUID) -> int:
    """Get current consecutive failure count."""
    return _failure_counts.get(instance_id, 0)


def clear() -> None:
    """Clear all counters (for testing)."""
    _failure_counts.clear()
