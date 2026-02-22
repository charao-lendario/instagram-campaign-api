"""Strategic suggestions endpoint.

Story 1.7 AC6: POST /api/v1/analytics/suggestions generates
AI-powered strategic suggestions based on current analytics data.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.suggestion import SuggestionsResponse
from app.services.suggestions import generate_strategic_suggestions

logger = logging.getLogger(__name__)

router = APIRouter()


class SuggestionsRequest(BaseModel):
    """Optional request body for suggestions endpoint."""
    candidate_id: str | None = None


@router.post("/suggestions", response_model=SuggestionsResponse)
async def create_suggestions(
    body: SuggestionsRequest | None = None,
) -> SuggestionsResponse:
    """Generate AI-powered strategic suggestions.

    FR-012: Strategic Suggestions -- 3-5 suggestions with supporting data.

    Accepts an optional body with candidate_id to focus on a specific
    candidate. When omitted, generates suggestions for both candidates.
    """
    candidate_id = body.candidate_id if body else None

    try:
        result = await generate_strategic_suggestions(candidate_id=candidate_id)
    except RuntimeError as exc:
        logger.error(
            "create_suggestions_failed",
            extra={
                "candidate_id": candidate_id,
                "error_message": str(exc),
            },
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate suggestions: {exc}",
        ) from exc

    return result
