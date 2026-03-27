# Spec: FS-DBA-001 E3
"""SQL Risk Classifier + Policy Engine.

4-level risk classification: SAFE → WARNING → DANGEROUS → CRITICAL.
Combined with Autonomy Level + Confidence to determine execution policy.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel


class RiskLevel(StrEnum):
    """Spec: FS-DBA-001 §4.1 — 4-stage risk classification."""

    SAFE = "safe"
    WARNING = "warning"
    DANGEROUS = "dangerous"
    CRITICAL = "critical"


class PolicyDecision(BaseModel):
    """Spec: FS-DBA-001 §4.2 — execution policy decision."""

    action: str  # "execute" | "approve_required" | "blocked"
    reason: str
    risk_level: RiskLevel


# SQL classification patterns
_CRITICAL_PATTERNS = re.compile(
    r"\b(DROP\s+(TABLE|DATABASE|SCHEMA|INDEX(?!\s+CONCURRENTLY))|TRUNCATE|"
    r"DELETE\s+FROM\s+\w+\s*$|DELETE\s+FROM\s+\w+\s*;)\b",
    re.IGNORECASE,
)
_DANGEROUS_PATTERNS = re.compile(
    r"\b(VACUUM\s+FULL|pg_terminate_backend|pg_cancel_backend|"
    r"ALTER\s+SYSTEM|UPDATE\s+|DELETE\s+FROM\s+\w+\s+WHERE)\b",
    re.IGNORECASE,
)
_WARNING_PATTERNS = re.compile(
    r"\b(CREATE\s+INDEX|REINDEX|VACUUM(?!\s+FULL)|ANALYZE\s+\w+|"
    r"ALTER\s+TABLE|CLUSTER)\b",
    re.IGNORECASE,
)

# Action type overrides (more reliable than SQL parsing)
_ACTION_RISK_MAP: dict[str, RiskLevel] = {
    "analyze_table": RiskLevel.SAFE,
    "create_index": RiskLevel.WARNING,
    "reindex": RiskLevel.WARNING,
    "vacuum": RiskLevel.WARNING,
    "vacuum_full": RiskLevel.DANGEROUS,
    "kill_session": RiskLevel.DANGEROUS,
    "alter_parameter": RiskLevel.DANGEROUS,
    "custom_sql": RiskLevel.DANGEROUS,  # conservative default
}

# Policy matrix: (risk_level, autonomy_level) → action
# Spec: FS-DBA-001 §4.3
_POLICY_MATRIX: dict[tuple[RiskLevel, int], str] = {
    # SAFE: always execute
    (RiskLevel.SAFE, 0): "execute",
    (RiskLevel.SAFE, 1): "execute",
    (RiskLevel.SAFE, 2): "execute",
    (RiskLevel.SAFE, 3): "execute",
    (RiskLevel.SAFE, 4): "execute",
    # WARNING: L0 block, L1 recommend, L2+ execute
    (RiskLevel.WARNING, 0): "blocked",
    (RiskLevel.WARNING, 1): "approve_required",
    (RiskLevel.WARNING, 2): "execute",
    (RiskLevel.WARNING, 3): "execute",
    (RiskLevel.WARNING, 4): "execute",
    # DANGEROUS: L0-L1 block/recommend, L2 approve, L3+ execute
    (RiskLevel.DANGEROUS, 0): "blocked",
    (RiskLevel.DANGEROUS, 1): "approve_required",
    (RiskLevel.DANGEROUS, 2): "approve_required",
    (RiskLevel.DANGEROUS, 3): "execute",
    (RiskLevel.DANGEROUS, 4): "execute",
    # CRITICAL: always block except L4 (approve)
    (RiskLevel.CRITICAL, 0): "blocked",
    (RiskLevel.CRITICAL, 1): "blocked",
    (RiskLevel.CRITICAL, 2): "blocked",
    (RiskLevel.CRITICAL, 3): "blocked",
    (RiskLevel.CRITICAL, 4): "approve_required",
}


class SafetyGuard:
    """Spec: FS-DBA-001 E3 — SQL Risk Classifier + Policy Engine."""

    def classify_risk(self, sql: str, action_type: str = "custom_sql") -> RiskLevel:
        """Classify SQL risk level.

        Priority: action_type override (except custom_sql) > SQL pattern matching.
        """
        # 1. Action type override (skip for custom_sql — use SQL patterns)
        if action_type != "custom_sql" and action_type in _ACTION_RISK_MAP:
            return _ACTION_RISK_MAP[action_type]

        # 2. SQL pattern matching (check CRITICAL first, then DANGEROUS, WARNING)
        if _CRITICAL_PATTERNS.search(sql):
            return RiskLevel.CRITICAL
        if _DANGEROUS_PATTERNS.search(sql):
            return RiskLevel.DANGEROUS
        if _WARNING_PATTERNS.search(sql):
            return RiskLevel.WARNING
        return RiskLevel.SAFE

    def check_policy(
        self,
        risk: RiskLevel,
        autonomy_level: int,
        confidence: float = 1.0,
    ) -> PolicyDecision:
        """Determine execution policy from risk + autonomy + confidence.

        Spec: FS-DBA-001 §4.3 — Policy Matrix.
        AC-12: Confidence < 0.5 blocks DANGEROUS+.
        """
        # Confidence gate: low confidence blocks dangerous actions
        if confidence < 0.5 and risk in (RiskLevel.DANGEROUS, RiskLevel.CRITICAL):
            return PolicyDecision(
                action="blocked",
                reason=f"Confidence {confidence:.2f} < 0.5 — DANGEROUS action blocked.",
                risk_level=risk,
            )

        # Clamp autonomy to 0-4
        level = max(0, min(4, autonomy_level))
        action = _POLICY_MATRIX.get((risk, level), "blocked")

        reasons = {
            "execute": f"Risk={risk.value}, Autonomy=L{level} — auto-execute allowed.",
            "approve_required": f"Risk={risk.value}, Autonomy=L{level} — human approval required.",
            "blocked": f"Risk={risk.value}, Autonomy=L{level} — action blocked.",
        }

        return PolicyDecision(
            action=action,
            reason=reasons.get(action, "Unknown policy."),
            risk_level=risk,
        )
