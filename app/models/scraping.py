"""Pydantic models for the ``scraping_runs`` table.

Covers all columns from SCHEMA.md Section 3.2.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import ScrapingStatus


class ScrapingRunCreate(BaseModel):
    """Payload for creating a new scraping run."""
    status: ScrapingStatus = ScrapingStatus.running
    metadata: dict[str, Any] | None = None


class ScrapingRunUpdate(BaseModel):
    """Payload for updating an existing scraping run."""
    completed_at: datetime | None = None
    status: ScrapingStatus | None = None
    posts_scraped: int | None = None
    comments_scraped: int | None = None
    duration_seconds: float | None = None
    errors: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None


class ScrapingRun(BaseModel):
    """Full scraping_runs record returned from the database."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    started_at: datetime
    completed_at: datetime | None = None
    status: ScrapingStatus
    posts_scraped: int = 0
    comments_scraped: int = 0
    duration_seconds: float | None = None
    errors: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime
