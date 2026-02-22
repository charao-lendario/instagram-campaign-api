"""Pydantic models for the ``candidates`` table.

Covers all columns from SCHEMA.md Section 3.1.
``profile_url`` and ``updated_at`` are managed by the database (GENERATED /
trigger) and are therefore optional / read-only in create models.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CandidateCreate(BaseModel):
    """Payload for creating a candidate (insert)."""
    username: str
    display_name: str | None = None
    is_active: bool = True


class Candidate(BaseModel):
    """Full candidate record returned from the database."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    display_name: str | None = None
    profile_url: str | None = None  # GENERATED STORED -- read-only
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
