"""Pydantic models for the ``themes`` table.

Covers all columns from SCHEMA.md Section 3.6.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AnalysisMethod, ThemeCategory


class ThemeCreate(BaseModel):
    """Payload for inserting a theme classification."""
    comment_id: UUID
    theme: ThemeCategory
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    method: AnalysisMethod


class Theme(BaseModel):
    """Full theme record returned from the database."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    comment_id: UUID
    theme: ThemeCategory
    confidence: float
    method: AnalysisMethod
    created_at: datetime
