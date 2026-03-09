"""Sentiment analysis endpoints."""

from fastapi import APIRouter, HTTPException, Query

from app.services.sentiment import (
    analyze_contextual_sentiment,
    analyze_unanalyzed_comments,
    get_sentiment_summary,
    run_llm_fallback,
)

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


@router.post("/sentiment")
async def run_sentiment_analysis():
    """Run VADER sentiment analysis on unanalyzed comments."""
    count = await analyze_unanalyzed_comments()
    return {"analyzed": count, "message": f"Analyzed {count} comments with VADER"}


@router.get("/sentiment/summary")
async def sentiment_summary(candidate_id: str | None = Query(None)):
    """Get sentiment summary, optionally filtered by candidate."""
    return await get_sentiment_summary(candidate_id)


@router.post("/sentiment/llm-fallback")
async def llm_fallback():
    """Reclassify ambiguous comments using LLM."""
    count = await run_llm_fallback()
    return {"reclassified": count, "message": f"Reclassified {count} comments with LLM"}


@router.post("/sentiment/contextual/{post_id}")
async def contextual_sentiment(post_id: str):
    """Get contextual sentiment analysis for a specific post."""
    try:
        return await analyze_contextual_sentiment(post_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
