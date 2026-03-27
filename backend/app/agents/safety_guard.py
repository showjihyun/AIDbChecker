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


_RISK_ORDER = {RiskLevel.SAFE: 0, RiskLevel.WARNING: 1, RiskLevel.DANGEROUS: 2, RiskLevel.CRITICAL: 3}


def _risk_order(level: RiskLevel) -> int:
    return _RISK_ORDER.get(level, 0)


class SafetyGuard:
    """Spec: FS-DBA-001 E3 — SQL Risk Classifier + Policy Engine."""

    def classify_risk(self, sql: str, action_type: str = "custom_sql") -> RiskLevel:
        """Classify SQL risk level.

        Security: ALWAYS check SQL patterns regardless of action_type.
        Action type sets a risk floor, but SQL content can only raise it.
        Finding 2: action_type override must not skip SQL inspection.
        """
        # Finding 2 fix: Always check for CRITICAL patterns first
        # (semicolons, DROP, TRUNCATE — regardless of action_type)
        if self._contains_multi_statement(sql):
            return RiskLevel.CRITICAL
        if _CRITICAL_PATTERNS.search(sql):
            return RiskLevel.CRITICAL

        # Known action_type with explicit risk mapping → use it
        # (unless SQL pattern is MORE dangerous)
        if action_type in _ACTION_RISK_MAP and action_type != "custom_sql":
            mapped = _ACTION_RISK_MAP[action_type]
            # SQL can raise risk above the mapped level, but not lower it
            sql_risk = RiskLevel.SAFE
            if _DANGEROUS_PATTERNS.search(sql):
                sql_risk = RiskLevel.DANGEROUS
            elif _WARNING_PATTERNS.search(sql):
                sql_risk = RiskLevel.WARNING
            return max(mapped, sql_risk, key=_risk_order)

        # custom_sql or unknown: rely entirely on SQL patterns
        if _DANGEROUS_PATTERNS.search(sql):
            return RiskLevel.DANGEROUS
        if _WARNING_PATTERNS.search(sql):
            return RiskLevel.WARNING
        return RiskLevel.SAFE

    @staticmethod
    def _contains_multi_statement(sql: str) -> bool:
        """Finding 1+2: Reject any SQL with semicolons or comment injection."""
        # Strip trailing whitespace/semicolons for single-statement check
        clean = sql.strip().rstrip(";").strip()
        if ";" in clean:
            return True
        # Block comment injection attempts
        if "--" in clean or "/*" in clean:
            return True
        return False

    @staticmethod
    def validate_identifier(name: str) -> str:
        """Finding 1: Validate SQL identifiers (table/column/index names).

        Raises ValueError if the name contains anything other than
        alphanumerics, underscores, and dots (for schema.table).
        """
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*$", name):
            raise ValueError(
                f"Invalid SQL identifier: '{name}'. "
                "Only alphanumeric, underscores, and dots allowed."
            )
        if len(name) > 128:
            raise ValueError(f"Identifier too long: {len(name)} chars (max 128).")
        return name

    def check_policy(
        self,
        risk: RiskLevel,
        autonomy_level: int,
        confidence: float = 1.0,
        user_role: str = "operator",
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

        # Finding 3: Role-based risk ceiling
        _ROLE_MAX_RISK = {
            "operator": RiskLevel.WARNING,
            "db_admin": RiskLevel.DANGEROUS,
            "super_admin": RiskLevel.CRITICAL,
            "viewer": RiskLevel.SAFE,
            "api_user": RiskLevel.WARNING,
        }
        max_risk = _ROLE_MAX_RISK.get(user_role, RiskLevel.WARNING)
        if _risk_order(risk) > _risk_order(max_risk):
            return PolicyDecision(
                action="blocked",
                reason=f"Role '{user_role}' cannot execute {risk.value} actions (max: {max_risk.value}).",
                risk_level=risk,
            )
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
