"""Analytics dashboard data endpoints.

Story 1.6: 6 GET endpoints for dashboard visualization data.

All endpoints use PL/pgSQL functions via the analytics service for
performance (NFR-001: < 2s response time).
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Query

from app.models.analytics import (
    ComparisonResponse,
    CompetitiveAnalysisResponse,
    OverviewResponse,
    PostRankingResponse,
    SentimentTimelineResponse,
    ThemeDistributionResponse,
    WordCloudResponse,
)
from app.services.analytics import (
    get_comparison,
    get_competitive_analysis,
    get_overview,
    get_post_rankings,
    get_sentiment_timeline,
    get_theme_distribution,
    get_wordcloud,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# AC1: GET /api/v1/analytics/overview
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=OverviewResponse)
async def analytics_overview() -> OverviewResponse:
    """Return overview metrics for all candidates, side by side.

    FR-006: Overview Dashboard -- metrics side by side.
    """
    return get_overview()


# ---------------------------------------------------------------------------
# AC2: GET /api/v1/analytics/sentiment-timeline
# ---------------------------------------------------------------------------

@router.get("/sentiment-timeline", response_model=SentimentTimelineResponse)
async def analytics_sentiment_timeline(
    candidate_id: str | None = Query(
        default=None,
        description="UUID of a specific candidate (omit for all)",
    ),
    start_date: str | None = Query(
        default=None,
        description="ISO date start (default: 30 days ago)",
    ),
    end_date: str | None = Query(
        default=None,
        description="ISO date end (default: today)",
    ),
) -> SentimentTimelineResponse:
    """Return temporal sentiment data points per post.

    FR-007: Temporal Sentiment Chart.
    """
    return get_sentiment_timeline(
        candidate_id=candidate_id,
        start_date=start_date,
        end_date=end_date,
    )


# ---------------------------------------------------------------------------
# AC3: GET /api/v1/analytics/wordcloud
# ---------------------------------------------------------------------------

@router.get("/wordcloud", response_model=WordCloudResponse)
async def analytics_wordcloud(
    candidate_id: str | None = Query(
        default=None,
        description="UUID of a specific candidate (omit for all)",
    ),
) -> WordCloudResponse:
    """Return word frequency data for word cloud rendering.

    FR-008: Word Cloud -- frequencies excluding stop words PT.
    """
    return get_wordcloud(candidate_id=candidate_id)


# ---------------------------------------------------------------------------
# AC4: GET /api/v1/analytics/themes
# ---------------------------------------------------------------------------

@router.get("/themes", response_model=ThemeDistributionResponse)
async def analytics_themes(
    candidate_id: str | None = Query(
        default=None,
        description="UUID of a specific candidate (omit for all)",
    ),
) -> ThemeDistributionResponse:
    """Return theme distribution data.

    FR-009: Recurring Themes -- thematic grouping keyword-based.
    """
    return get_theme_distribution(candidate_id=candidate_id)


# ---------------------------------------------------------------------------
# AC5: GET /api/v1/analytics/posts
# ---------------------------------------------------------------------------

@router.get("/posts", response_model=PostRankingResponse)
async def analytics_posts(
    candidate_id: str | None = Query(
        default=None,
        description="UUID of a specific candidate (omit for all)",
    ),
    sort_by: Literal[
        "comment_count",
        "like_count",
        "positive_ratio",
        "negative_ratio",
        "sentiment_score",
        "posted_at",
    ] = Query(
        default="comment_count",
        description="Metric to sort by",
    ),
    order: Literal["asc", "desc"] = Query(
        default="desc",
        description="Sort order",
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Results per page"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
) -> PostRankingResponse:
    """Return ranked posts with engagement and sentiment metrics.

    FR-010: Post Comparison -- ranked list of posts.
    """
    # Map 'sentiment_score' to the PL/pgSQL column name
    db_sort_by = sort_by
    if sort_by == "sentiment_score":
        db_sort_by = "avg_sentiment"

    return get_post_rankings(
        candidate_id=candidate_id,
        sort_by=db_sort_by,
        order=order,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# AC6: GET /api/v1/analytics/comparison
# ---------------------------------------------------------------------------

@router.get("/comparison", response_model=ComparisonResponse)
async def analytics_comparison() -> ComparisonResponse:
    """Return side-by-side candidate comparison with trend analysis.

    FR-011: Candidate Comparison -- side-by-side with trends.
    """
    return get_comparison()


# ---------------------------------------------------------------------------
# GET /api/v1/analytics/competitive
# ---------------------------------------------------------------------------

@router.get("/competitive", response_model=CompetitiveAnalysisResponse)
async def analytics_competitive(
    our_username: str = Query(
        default="delegadasheila",
        description="Username of our candidate",
    ),
    competitor_username: str = Query(
        default="delegadaione",
        description="Username of the competitor",
    ),
) -> CompetitiveAnalysisResponse:
    """Return competitive analysis between our candidate and a competitor."""
    return get_competitive_analysis(
        our_username=our_username,
        competitor_username=competitor_username,
    )
