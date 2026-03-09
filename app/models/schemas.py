"""Pydantic schemas for API request/response models."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# --- Health ---
class HealthResponse(BaseModel):
    status: str
    database: str
    scheduler: str
    last_scrape: dict | None = None


# --- Scraping ---
class ScrapingRunResponse(BaseModel):
    id: UUID
    status: str
    started_at: datetime
    message: str


# --- Sentiment ---
class SentimentAnalysisResponse(BaseModel):
    analyzed: int
    message: str


class SentimentDistribution(BaseModel):
    positive: int = 0
    negative: int = 0
    neutral: int = 0


class SentimentSummary(BaseModel):
    total_comments: int
    distribution: SentimentDistribution
    average_compound: float
    candidate_id: str | None = None
    candidate_username: str | None = None


class LLMFallbackResponse(BaseModel):
    reclassified: int
    message: str


class ContextualSentimentResponse(BaseModel):
    post_id: str
    caption: str | None = None
    total_comments: int
    sentiment_distribution: SentimentDistribution
    average_sentiment: float
    comments: list[dict]


# --- Analytics: Overview ---
class CandidateOverview(BaseModel):
    candidate_id: str
    username: str
    display_name: str | None = None
    total_posts: int = 0
    total_comments: int = 0
    average_sentiment_score: float = 0.0
    sentiment_distribution: SentimentDistribution = SentimentDistribution()
    total_engagement: int = 0


class OverviewResponse(BaseModel):
    candidates: list[CandidateOverview]
    last_scrape: dict | None = None
    total_comments_analyzed: int = 0


# --- Analytics: Timeline ---
class TimelineDataPoint(BaseModel):
    candidate_id: str
    candidate_username: str
    post_id: str
    post_url: str
    post_caption: str | None = None
    posted_at: str
    average_sentiment_score: float
    comment_count: int


class TimelineResponse(BaseModel):
    data_points: list[TimelineDataPoint]


# --- Analytics: Wordcloud ---
class WordCount(BaseModel):
    word: str
    count: int


class WordcloudResponse(BaseModel):
    words: list[WordCount]
    total_unique_words: int


# --- Analytics: Themes ---
class ThemeCandidateBreakdown(BaseModel):
    candidate_id: str
    username: str
    count: int


class ThemeItem(BaseModel):
    theme: str
    count: int
    percentage: float
    by_candidate: list[ThemeCandidateBreakdown]


class ThemesResponse(BaseModel):
    themes: list[ThemeItem]


# --- Analytics: Posts ---
class PostItem(BaseModel):
    post_id: str
    candidate_username: str
    url: str
    caption: str | None = None
    posted_at: str | None = None
    like_count: int = 0
    comment_count: int = 0
    positive_ratio: float = 0.0
    negative_ratio: float = 0.0
    average_sentiment_score: float = 0.0


class PostsResponse(BaseModel):
    posts: list[PostItem]
    total: int
    limit: int
    offset: int


# --- Analytics: Comparison ---
class CandidateComparison(BaseModel):
    candidate_id: str
    username: str
    display_name: str | None = None
    total_posts: int = 0
    total_comments: int = 0
    average_sentiment_score: float = 0.0
    total_engagement: int = 0
    sentiment_distribution: SentimentDistribution = SentimentDistribution()
    top_themes: list[dict] = []
    trend: list[dict] = []


class ComparisonResponse(BaseModel):
    candidates: list[CandidateComparison]


# --- Analytics: Competitive ---
class CompetitiveCandidate(BaseModel):
    candidate_id: str
    username: str
    display_name: str | None = None
    total_posts: int = 0
    total_comments: int = 0
    average_sentiment_score: float = 0.0
    total_engagement: int = 0
    sentiment_distribution: SentimentDistribution = SentimentDistribution()


class CompetitiveResponse(BaseModel):
    our_candidate: CompetitiveCandidate | None = None
    competitor: CompetitiveCandidate | None = None
    engagement_advantage: float = 0.0
    sentiment_advantage: float = 0.0


# --- Suggestions ---
class SuggestionItem(BaseModel):
    title: str
    description: str
    supporting_data: str | None = None
    priority: str = "medium"
    categoria: str | None = None
    acoes_concretas: list[str] | None = None
    exemplo_post: str | None = None
    roteiro_video: str | None = None
    publico_alvo: str | None = None
    para_quem: str | None = None
    impacto_esperado: str | None = None


class SuggestionsResponse(BaseModel):
    suggestions: list[SuggestionItem]
    resumo_executivo: str | None = None
    generated_at: str | None = None
    data_snapshot: dict | None = None
