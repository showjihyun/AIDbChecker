# Spec: FR-AI-005, FS-AI-005
"""Pydantic v2 schemas for AIGC Report generation API."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class ReportType(StrEnum):
    """Available report types."""

    HEALTH = "health"
    PERFORMANCE = "performance"
    INCIDENT = "incident"


class ReportFormat(StrEnum):
    """Report output formats."""

    HTML = "html"
    JSON = "json"


class SectionSeverity(StrEnum):
    """Section health severity."""

    GOOD = "good"
    WARNING = "warning"
    CRITICAL = "critical"


class RecommendationPriority(StrEnum):
    """Recommendation priority."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Request ---


class ReportGenerateRequest(BaseModel):
    """Request to generate an AIGC report.

    Spec: FS-AI-005 Section 2.1
    """

    instance_id: UUID | None = Field(
        None, description="Target instance. None = all instances summary."
    )
    period: str = Field(
        "7d",
        description="Period shorthand: 1d, 7d, 30d, or 'custom'",
        pattern=r"^(1d|7d|30d|custom)$",
    )
    period_start: datetime | None = Field(None, description="Custom period start (UTC)")
    period_end: datetime | None = Field(None, description="Custom period end (UTC)")
    report_type: ReportType = ReportType.HEALTH
    format: ReportFormat = ReportFormat.HTML
    language: str = Field("ko", pattern=r"^(ko|en)$")
    custom_prompt: str | None = Field(None, max_length=500, description="Additional analysis focus")


# --- Response ---


class ReportSection(BaseModel):
    """A single report section with optional chart data."""

    title: str
    content: str = Field(..., description="Markdown body")
    severity: SectionSeverity | None = None
    metrics: dict | None = Field(None, description="Key metric values for this section")
    chart_data: dict | None = Field(None, description="ECharts-compatible chart data")


class Recommendation(BaseModel):
    """AI-generated recommendation with actionable command."""

    priority: RecommendationPriority
    title: str
    description: str
    action: str | None = Field(None, description="Executable SQL or config command")
    confidence: float = Field(..., ge=0.0, le=1.0)


class ReportGenerateResponse(BaseModel):
    """Full AIGC report response.

    Spec: FS-AI-005 Section 2.1
    """

    report_id: UUID
    instance_id: UUID | None
    report_type: ReportType
    period: str

    # Report body
    title: str
    executive_summary: str
    sections: list[ReportSection]
    recommendations: list[Recommendation]

    # Metadata
    status: str = Field(..., description="completed | failed")
    format: ReportFormat
    generated_at: datetime
    generation_time_ms: int
    ai_model: str
    tokens_used: int
    confidence: float = Field(..., ge=0.0, le=1.0)


class ReportListItem(BaseModel):
    """Summary item for report list endpoint."""

    report_id: UUID
    instance_id: UUID | None
    report_type: ReportType
    period: str
    title: str
    status: str
    confidence: float
    generated_at: datetime
    generation_time_ms: int
