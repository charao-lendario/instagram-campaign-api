"""Response models for analytics / dashboard endpoints.

These are API-layer response schemas, not direct table mappings.
Defined per architecture.md Section 3.2.4 endpoint contracts.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# --- Overview ---

class SentimentDistribution(BaseModel):
    """Counts of positive / negative / neutral comments."""
    positive: int = 0
    negative: int = 0
    neutral: int = 0


class OverviewMetrics(BaseModel):
    """Per-candidate overview metrics."""
    candidate_id: UUID
    username: str
    display_name: str | None = None
    total_posts: int = 0
    total_comments: int = 0
    average_sentiment_score: float = 0.0
    sentiment_distribution: SentimentDistribution = SentimentDistribution()
    total_engagement: int = 0


class OverviewResponse(BaseModel):
    """Full response for GET /api/v1/analytics/overview."""
    candidates: list[OverviewMetrics] = []
    last_scrape: datetime | None = None
    total_comments_analyzed: int = 0


# --- Sentiment Timeline ---

class SentimentTimelinePoint(BaseModel):
    """A single data point on the sentiment timeline."""
    candidate_id: UUID
    candidate_username: str
    post_id: UUID
    post_url: str
    post_caption: str | None = None
    posted_at: datetime | None = None
    average_sentiment_score: float = 0.0
    comment_count: int = 0


class SentimentTimelineResponse(BaseModel):
    """Full response for GET /api/v1/analytics/sentiment-timeline."""
    data_points: list[SentimentTimelinePoint] = []


# --- Word Cloud ---

class WordEntry(BaseModel):
    """A single word with its frequency count."""
    word: str
    count: int


class WordCloudResponse(BaseModel):
    """Full response for GET /api/v1/analytics/wordcloud."""
    words: list[WordEntry] = []
    total_unique_words: int = 0


# --- Theme Distribution ---

class CandidateThemeCount(BaseModel):
    """Per-candidate count within a theme."""
    candidate_id: UUID
    username: str
    count: int


class ThemeDistribution(BaseModel):
    """Counts for a single theme across all candidates."""
    theme: str
    count: int = 0
    percentage: float = 0.0
    by_candidate: list[CandidateThemeCount] = []


class ThemeDistributionResponse(BaseModel):
    """Full response for GET /api/v1/analytics/themes."""
    themes: list[ThemeDistribution] = []


# --- Post Rankings ---

class PostRanking(BaseModel):
    """A ranked post with engagement and sentiment metrics."""
    post_id: UUID
    candidate_username: str
    url: str
    caption: str | None = None
    posted_at: datetime | None = None
    like_count: int = 0
    comment_count: int = 0
    positive_ratio: float = 0.0
    negative_ratio: float = 0.0
    average_sentiment_score: float = 0.0


class PostRankingResponse(BaseModel):
    """Full response for GET /api/v1/analytics/posts."""
    posts: list[PostRanking] = []
    total: int = 0
    limit: int = 20
    offset: int = 0


# --- Candidate Comparison ---

class ThemeCount(BaseModel):
    """Theme name and count pair."""
    theme: str
    count: int


class SentimentTrend(BaseModel):
    """Trend analysis data for a candidate."""
    direction: str  # "improving" | "declining" | "stable"
    recent_avg: float = 0.0
    previous_avg: float = 0.0
    delta: float = 0.0


class CandidateComparison(BaseModel):
    """Full comparison metrics for a single candidate."""
    candidate_id: UUID
    username: str
    display_name: str | None = None
    total_posts: int = 0
    total_comments: int = 0
    average_sentiment_score: float = 0.0
    total_engagement: int = 0
    sentiment_distribution: SentimentDistribution = SentimentDistribution()
    top_themes: list[ThemeCount] = []
    trend: SentimentTrend = SentimentTrend(direction="stable")


class ComparisonResponse(BaseModel):
    """Full response for GET /api/v1/analytics/comparison."""
    candidates: list[CandidateComparison] = []
