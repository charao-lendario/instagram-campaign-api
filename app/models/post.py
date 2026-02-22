"""Pydantic models for the ``posts`` table.

Covers all columns from SCHEMA.md Section 3.3.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import MediaType


class PostCreate(BaseModel):
    """Payload for inserting a new post."""
    candidate_id: UUID
    scraping_run_id: UUID | None = None
    instagram_id: str
    url: str
    shortcode: str | None = None
    caption: str | None = None
    like_count: int = 0
    comment_count: int = 0
    media_type: MediaType = MediaType.unknown
    is_sponsored: bool = False
    video_view_count: int | None = None
    posted_at: datetime | None = None
    raw_data: dict[str, Any] | None = None


class PostUpsert(BaseModel):
    """Payload for upserting a post (conflict on instagram_id)."""
    candidate_id: UUID
    scraping_run_id: UUID | None = None
    instagram_id: str
    url: str
    shortcode: str | None = None
    caption: str | None = None
    like_count: int = 0
    comment_count: int = 0
    media_type: MediaType = MediaType.unknown
    is_sponsored: bool = False
    video_view_count: int | None = None
    posted_at: datetime | None = None
    raw_data: dict[str, Any] | None = None


class Post(BaseModel):
    """Full post record returned from the database."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID
    scraping_run_id: UUID | None = None
    instagram_id: str
    url: str
    shortcode: str | None = None
    caption: str | None = None
    like_count: int = 0
    comment_count: int = 0
    media_type: MediaType = MediaType.unknown
    is_sponsored: bool = False
    video_view_count: int | None = None
    posted_at: datetime | None = None
    scraped_at: datetime
    raw_data: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
