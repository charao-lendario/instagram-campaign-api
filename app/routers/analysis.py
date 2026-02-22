"""Analysis trigger endpoints.

Story 1.4: POST /sentiment -- triggers VADER batch analysis.
           GET /sentiment/summary -- returns aggregate counts per candidate.
Story 1.5: POST /sentiment/llm-fallback -- triggers LLM reclassification.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.services.sentiment import (
    analyze_post_contextual_sentiment,
    get_sentiment_summary,
    reclassify_ambiguous_comments,
    run_vader_analysis,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Story 1.4: VADER Sentiment Analysis
# ---------------------------------------------------------------------------


@router.post("/sentiment", status_code=200)
async def trigger_sentiment_analysis() -> dict[str, Any]:
    """Trigger VADER sentiment analysis for all unanalyzed comments.

    AC5 (1.4): Identifies comments without sentiment_scores, runs
    analyze_comments_batch, returns analyzed_count and skipped_count.
    """
    try:
        result = run_vader_analysis()
    except Exception as exc:
        logger.error(
            "trigger_sentiment_analysis_failed",
            extra={"error_message": str(exc)},
        )
        raise HTTPException(
            status_code=500,
            detail=f"Sentiment analysis failed: {exc}",
        ) from exc

    return {
        "analyzed_count": result["analyzed_count"],
        "skipped_count": result["skipped_count"],
        "message": "Sentiment analysis complete",
    }


@router.get("/sentiment/summary", status_code=200)
async def sentiment_summary(
    candidate_id: str = Query(..., description="UUID of the candidate to aggregate"),
) -> dict[str, Any]:
    """Return aggregate sentiment counts for a candidate.

    AC6 (1.4): JOIN path sentiment_scores -> comments -> posts -> candidates.
    Returns counts by label and average compound score.
    """
    try:
        result = get_sentiment_summary(candidate_id)
    except Exception as exc:
        logger.error(
            "sentiment_summary_failed",
            extra={
                "candidate_id": candidate_id,
                "error_message": str(exc),
            },
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sentiment summary: {exc}",
        ) from exc

    return result


# ---------------------------------------------------------------------------
# Story 1.5: LLM Fallback
# ---------------------------------------------------------------------------


@router.post("/sentiment/llm-fallback", status_code=200)
async def trigger_llm_fallback() -> dict[str, Any]:
    """Trigger LLM reclassification for ambiguous comments.

    AC6 (1.5): Invokes reclassify_ambiguous_comments() and returns
    reclassified_count, api_calls_made, confidence_upgrades,
    retained_vader_label.
    """
    try:
        result = await reclassify_ambiguous_comments()
    except Exception as exc:
        logger.error(
            "trigger_llm_fallback_failed",
            extra={"error_message": str(exc)},
        )
        raise HTTPException(
            status_code=500,
            detail=f"LLM fallback failed: {exc}",
        ) from exc

    return result


# ---------------------------------------------------------------------------
# Contextual Sentiment Analysis (post-level)
# ---------------------------------------------------------------------------


@router.post("/sentiment/contextual/{post_id}", status_code=200)
async def trigger_contextual_sentiment(post_id: str) -> dict[str, Any]:
    """Analyze comments of a specific post with contextual awareness.

    Considers the post caption to distinguish topic negativity
    (supporting the candidate) from candidate negativity (attacking).
    """
    try:
        result = await analyze_post_contextual_sentiment(post_id)
    except Exception as exc:
        logger.error(
            "contextual_sentiment_failed",
            extra={
                "post_id": post_id,
                "error_message": str(exc),
            },
        )
        raise HTTPException(
            status_code=500,
            detail=f"Contextual sentiment analysis failed: {exc}",
        ) from exc

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result
