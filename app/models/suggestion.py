"""Pydantic models for strategic suggestions (``strategic_insights`` table).

Covers both the database record and the API response contract per
architecture.md Section 3.2.5.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StrategicSuggestion(BaseModel):
    """A single strategic suggestion."""
    title: str
    description: str
    supporting_data: str | None = None
    priority: str = "medium"  # "high" | "medium" | "low"


class SuggestionsResponse(BaseModel):
    """Full response for POST /api/v1/analytics/suggestions."""
    suggestions: list[StrategicSuggestion] = []
    generated_at: datetime | None = None
    data_snapshot: dict[str, Any] | None = None


# --- Database record models ---

class StrategicInsightCreate(BaseModel):
    """Payload for inserting a strategic insight."""
    scraping_run_id: UUID | None = None
    candidate_id: UUID | None = None
    title: str
    description: str
    supporting_data: str | None = None
    priority: str = "medium"
    llm_model: str | None = None
    input_summary: dict[str, Any] | None = None


class StrategicInsight(BaseModel):
    """Full strategic_insights record returned from the database."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    scraping_run_id: UUID | None = None
    candidate_id: UUID | None = None
    title: str
    description: str
    supporting_data: str | None = None
    priority: str
    llm_model: str | None = None
    input_summary: dict[str, Any] | None = None
    created_at: datetime
