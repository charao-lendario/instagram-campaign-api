"""Analytics endpoints for the frontend dashboard."""

from fastapi import APIRouter, Query

from app.services.analytics import (
    get_comparison,
    get_competitive,
    get_overview,
    get_posts,
    get_sentiment_timeline,
    get_themes,
    get_wordcloud,
)
from app.services.suggestions import generate_suggestions

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/overview")
async def overview():
    """Get overview analytics for all candidates."""
    return await get_overview()


@router.get("/sentiment-timeline")
async def sentiment_timeline(
    candidate_id: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
):
    """Get sentiment timeline data grouped by post."""
    return await get_sentiment_timeline(candidate_id, start_date, end_date)


@router.get("/wordcloud")
async def wordcloud(candidate_id: str | None = Query(None)):
    """Get word frequencies for wordcloud visualization."""
    return await get_wordcloud(candidate_id)


@router.get("/themes")
async def themes(candidate_id: str | None = Query(None)):
    """Get theme distribution."""
    return await get_themes(candidate_id)


@router.get("/posts")
async def posts(
    candidate_id: str | None = Query(None),
    sort_by: str = Query("posted_at"),
    order: str = Query("desc"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Get posts with sentiment data."""
    return await get_posts(candidate_id, sort_by, order, limit, offset)


@router.get("/comparison")
async def comparison():
    """Get comparison data for all candidates."""
    return await get_comparison()


@router.get("/competitive")
async def competitive(
    our_username: str = Query(...),
    competitor_username: str = Query(...),
):
    """Compare two candidates head-to-head."""
    return await get_competitive(our_username, competitor_username)


@router.post("/suggestions")
async def suggestions():
    """Generate strategic suggestions using LLM."""
    return await generate_suggestions()
