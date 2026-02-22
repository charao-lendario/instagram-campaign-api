"""Pydantic models for the ``comments`` table.

Covers all columns from SCHEMA.md Section 3.4.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CommentCreate(BaseModel):
    """Payload for inserting a new comment."""
    post_id: UUID
    scraping_run_id: UUID | None = None
    instagram_id: str
    text: str
    author_username: str | None = None
    like_count: int = 0
    reply_count: int = 0
    commented_at: datetime | None = None
    raw_data: dict[str, Any] | None = None


class CommentUpsert(BaseModel):
    """Payload for upserting a comment (conflict on instagram_id)."""
    post_id: UUID
    scraping_run_id: UUID | None = None
    instagram_id: str
    text: str
    author_username: str | None = None
    like_count: int = 0
    reply_count: int = 0
    commented_at: datetime | None = None
    raw_data: dict[str, Any] | None = None


class Comment(BaseModel):
    """Full comment record returned from the database."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_id: UUID
    scraping_run_id: UUID | None = None
    instagram_id: str
    text: str
    author_username: str | None = None
    like_count: int = 0
    reply_count: int = 0
    commented_at: datetime | None = None
    scraped_at: datetime
    raw_data: dict[str, Any] | None = None
    created_at: datetime
