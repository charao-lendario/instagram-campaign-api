"""Pydantic models for the ``sentiment_scores`` table and analysis results.

Covers all columns from SCHEMA.md Section 3.5.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SentimentLabel


class SentimentScoreCreate(BaseModel):
    """Payload for inserting a sentiment score."""
    comment_id: UUID
    vader_compound: float = Field(..., ge=-1.0, le=1.0)
    vader_positive: float | None = Field(default=None, ge=0.0, le=1.0)
    vader_negative: float | None = Field(default=None, ge=0.0, le=1.0)
    vader_neutral: float | None = Field(default=None, ge=0.0, le=1.0)
    vader_label: SentimentLabel
    llm_label: SentimentLabel | None = None
    llm_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    llm_model: str | None = None
    final_label: SentimentLabel


class SentimentScore(BaseModel):
    """Full sentiment_scores record returned from the database."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    comment_id: UUID
    vader_compound: float
    vader_positive: float | None = None
    vader_negative: float | None = None
    vader_neutral: float | None = None
    vader_label: SentimentLabel
    llm_label: SentimentLabel | None = None
    llm_confidence: float | None = None
    llm_model: str | None = None
    final_label: SentimentLabel
    analyzed_at: datetime
    created_at: datetime
    updated_at: datetime


class SentimentResult(BaseModel):
    """Lightweight result returned after VADER analysis."""
    comment_id: UUID
    vader_compound: float
    vader_label: SentimentLabel
    final_label: SentimentLabel


class LLMSentimentResult(BaseModel):
    """Result from LLM reclassification."""
    comment_id: UUID
    llm_label: SentimentLabel
    llm_confidence: float = Field(..., ge=0.0, le=1.0)
    llm_model: str
    final_label: SentimentLabel
