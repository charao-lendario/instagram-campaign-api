"""Analytics aggregation service for dashboard endpoints.

Story 1.6: Calls PL/pgSQL functions via supabase.rpc() and processes
results into Pydantic response models. Word cloud tokenization is done
in Python (stop words, frequency counting).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from app.core.constants import STOP_WORDS_PT
from app.db.supabase import get_supabase
from app.models.analytics import (
    CandidateComparison,
    CandidateThemeCount,
    ComparisonResponse,
    OverviewMetrics,
    OverviewResponse,
    PostRanking,
    PostRankingResponse,
    SentimentDistribution,
    SentimentTimelinePoint,
    SentimentTimelineResponse,
    SentimentTrend,
    ThemeCount,
    ThemeDistribution,
    ThemeDistributionResponse,
    WordCloudResponse,
    WordEntry,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AC1: GET /analytics/overview
# ---------------------------------------------------------------------------

def get_overview() -> OverviewResponse:
    """Aggregate overview metrics for all active candidates.

    Uses PL/pgSQL ``get_candidate_overview(candidate_id)`` per candidate
    and ``get_last_successful_scrape()`` for the last scrape timestamp.
    """
    client = get_supabase()

    # Get all active candidates
    candidates_result = (
        client.table("candidates")
        .select("id, username, display_name")
        .eq("is_active", True)
        .execute()
    )
    candidates_data = candidates_result.data or []

    metrics_list: list[OverviewMetrics] = []
    total_comments = 0

    for candidate in candidates_data:
        cid = candidate["id"]
        rpc_result = client.rpc(
            "get_candidate_overview",
            {"p_candidate_id": cid},
        ).execute()

        rows = rpc_result.data or []
        if rows:
            row = rows[0]
            om = OverviewMetrics(
                candidate_id=UUID(row["candidate_id"]),
                username=row["username"],
                display_name=row.get("display_name"),
                total_posts=int(row.get("total_posts", 0)),
                total_comments=int(row.get("total_comments", 0)),
                average_sentiment_score=float(row.get("avg_sentiment", 0.0)),
                sentiment_distribution=SentimentDistribution(
                    positive=int(row.get("positive_count", 0)),
                    negative=int(row.get("negative_count", 0)),
                    neutral=int(row.get("neutral_count", 0)),
                ),
                total_engagement=int(row.get("total_engagement", 0)),
            )
            metrics_list.append(om)
            total_comments += om.total_comments
        else:
            # Candidate has no data yet -- return zeros
            metrics_list.append(
                OverviewMetrics(
                    candidate_id=UUID(cid),
                    username=candidate["username"],
                    display_name=candidate.get("display_name"),
                )
            )

    # Last successful scrape timestamp
    last_scrape_result = client.rpc("get_last_successful_scrape", {}).execute()
    last_scrape: datetime | None = None
    if last_scrape_result.data is not None:
        raw = last_scrape_result.data
        if isinstance(raw, str) and raw:
            last_scrape = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        elif isinstance(raw, list) and raw:
            # Some supabase-py versions return as list
            val = raw[0] if isinstance(raw[0], str) else None
            if val:
                last_scrape = datetime.fromisoformat(val.replace("Z", "+00:00"))

    return OverviewResponse(
        candidates=metrics_list,
        last_scrape=last_scrape,
        total_comments_analyzed=total_comments,
    )


# ---------------------------------------------------------------------------
# AC2: GET /analytics/sentiment-timeline
# ---------------------------------------------------------------------------

def get_sentiment_timeline(
    candidate_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> SentimentTimelineResponse:
    """Get sentiment timeline data points aggregated per post.

    When candidate_id is omitted, returns data for all candidates.
    When dates are omitted, defaults to last 30 days.
    """
    client = get_supabase()

    # Parse date defaults
    if not start_date:
        start_dt = datetime.now(timezone.utc) - timedelta(days=30)
        start_date = start_dt.isoformat()
    if not end_date:
        end_dt = datetime.now(timezone.utc)
        end_date = end_dt.isoformat()

    data_points: list[SentimentTimelinePoint] = []

    if candidate_id:
        # Single candidate
        points = _fetch_timeline_for_candidate(
            client, candidate_id, start_date, end_date
        )
        data_points.extend(points)
    else:
        # All active candidates
        candidates_result = (
            client.table("candidates")
            .select("id, username")
            .eq("is_active", True)
            .execute()
        )
        for candidate in candidates_result.data or []:
            points = _fetch_timeline_for_candidate(
                client, candidate["id"], start_date, end_date
            )
            data_points.extend(points)

    return SentimentTimelineResponse(data_points=data_points)


def _fetch_timeline_for_candidate(
    client: Any,
    candidate_id: str,
    start_date: str,
    end_date: str,
) -> list[SentimentTimelinePoint]:
    """Fetch timeline points for a single candidate via RPC."""
    # Get candidate username for the response
    cand_result = (
        client.table("candidates")
        .select("username")
        .eq("id", candidate_id)
        .limit(1)
        .execute()
    )
    username = ""
    if cand_result.data:
        username = cand_result.data[0]["username"]

    rpc_result = client.rpc(
        "get_sentiment_timeline",
        {
            "p_candidate_id": candidate_id,
            "p_start_date": start_date,
            "p_end_date": end_date,
        },
    ).execute()

    points: list[SentimentTimelinePoint] = []
    for row in rpc_result.data or []:
        points.append(
            SentimentTimelinePoint(
                candidate_id=UUID(candidate_id),
                candidate_username=username,
                post_id=UUID(row["post_id"]),
                post_url=row.get("post_url", ""),
                post_caption=row.get("post_caption"),
                posted_at=row.get("posted_at"),
                average_sentiment_score=float(row.get("avg_sentiment", 0.0)),
                comment_count=int(row.get("comment_count", 0)),
            )
        )
    return points


# ---------------------------------------------------------------------------
# AC3: GET /analytics/wordcloud
# ---------------------------------------------------------------------------

def get_wordcloud(
    candidate_id: str | None = None,
    limit: int = 200,
) -> WordCloudResponse:
    """Get word frequency data for word cloud rendering.

    Fetches raw comment texts via PL/pgSQL, tokenizes in Python,
    filters stop words, and returns top N words by frequency.
    """
    client = get_supabase()

    params: dict[str, Any] = {"p_limit": 10000}
    if candidate_id:
        params["p_candidate_id"] = candidate_id

    rpc_result = client.rpc(
        "get_comments_text_for_wordcloud",
        params,
    ).execute()

    texts = [row["comment_text"] for row in (rpc_result.data or []) if row.get("comment_text")]

    word_entries = _get_word_frequencies(texts, top_n=limit)

    return WordCloudResponse(
        words=word_entries,
        total_unique_words=len(word_entries),
    )


def _normalize_for_wordcloud(text: str) -> str:
    """Normalize text for word cloud: lowercase, strip accents, remove punctuation."""
    lowered = text.lower()
    nfkd = unicodedata.normalize("NFKD", lowered)
    stripped = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    # Remove punctuation and numbers
    cleaned = re.sub(r"[^a-z\s]", "", stripped)
    return cleaned


def _get_word_frequencies(
    texts: list[str],
    top_n: int = 200,
) -> list[WordEntry]:
    """Tokenize texts, filter stop words, count frequencies.

    Per story 1.6 technical notes: split, lowercase, filter stop words
    PT, count frequencies, return top N.
    """
    words: list[str] = []
    for text in texts:
        normalized = _normalize_for_wordcloud(text)
        tokens = normalized.split()
        words.extend(
            t for t in tokens
            if t not in STOP_WORDS_PT and len(t) > 2
        )

    counter = Counter(words)
    return [
        WordEntry(word=w, count=c)
        for w, c in counter.most_common(top_n)
    ]


# ---------------------------------------------------------------------------
# AC4: GET /analytics/themes
# ---------------------------------------------------------------------------

def get_theme_distribution(
    candidate_id: str | None = None,
) -> ThemeDistributionResponse:
    """Get theme distribution with per-candidate breakdown.

    Uses PL/pgSQL get_theme_distribution for aggregate counts, then
    builds per-candidate breakdown with additional queries.
    """
    client = get_supabase()

    params: dict[str, Any] = {}
    if candidate_id:
        params["p_candidate_id"] = candidate_id

    rpc_result = client.rpc("get_theme_distribution", params).execute()
    rows = rpc_result.data or []

    # Get all active candidates for by_candidate breakdown
    candidates_result = (
        client.table("candidates")
        .select("id, username")
        .eq("is_active", True)
        .execute()
    )
    candidates = candidates_result.data or []

    themes: list[ThemeDistribution] = []
    for row in rows:
        theme_name = row["theme"]
        total_count = int(row.get("comment_count", 0))
        percentage = float(row.get("percentage", 0.0))

        # Build per-candidate counts for this theme
        by_candidate: list[CandidateThemeCount] = []

        if not candidate_id:
            # Get per-candidate breakdown
            for cand in candidates:
                cand_params = {"p_candidate_id": cand["id"]}
                cand_rpc = client.rpc(
                    "get_theme_distribution",
                    cand_params,
                ).execute()
                cand_rows = cand_rpc.data or []
                cand_count = 0
                for cr in cand_rows:
                    if cr["theme"] == theme_name:
                        cand_count = int(cr.get("comment_count", 0))
                        break
                if cand_count > 0:
                    by_candidate.append(
                        CandidateThemeCount(
                            candidate_id=UUID(cand["id"]),
                            username=cand["username"],
                            count=cand_count,
                        )
                    )
        else:
            # Single candidate -- the count IS the candidate count
            for cand in candidates:
                if cand["id"] == candidate_id:
                    by_candidate.append(
                        CandidateThemeCount(
                            candidate_id=UUID(cand["id"]),
                            username=cand["username"],
                            count=total_count,
                        )
                    )
                    break

        themes.append(
            ThemeDistribution(
                theme=theme_name,
                count=total_count,
                percentage=percentage,
                by_candidate=by_candidate,
            )
        )

    return ThemeDistributionResponse(themes=themes)


# ---------------------------------------------------------------------------
# AC5: GET /analytics/posts
# ---------------------------------------------------------------------------

def get_post_rankings(
    candidate_id: str | None = None,
    sort_by: str = "comment_count",
    order: str = "desc",
    limit: int = 20,
    offset: int = 0,
) -> PostRankingResponse:
    """Get ranked posts with engagement and sentiment metrics.

    Uses PL/pgSQL get_post_rankings for the heavy lifting.
    """
    client = get_supabase()

    params: dict[str, Any] = {
        "p_sort_by": sort_by,
        "p_sort_order": order,
        "p_limit": limit,
        "p_offset": offset,
    }
    if candidate_id:
        params["p_candidate_id"] = candidate_id

    rpc_result = client.rpc("get_post_rankings", params).execute()
    rows = rpc_result.data or []

    posts: list[PostRanking] = []
    for row in rows:
        posts.append(
            PostRanking(
                post_id=UUID(row["post_id"]),
                candidate_username=row.get("candidate_username", ""),
                url=row.get("url", ""),
                caption=row.get("caption_preview"),
                posted_at=row.get("posted_at"),
                like_count=int(row.get("like_count", 0)),
                comment_count=int(row.get("comment_count", 0)),
                positive_ratio=float(row.get("positive_ratio", 0.0)),
                negative_ratio=float(row.get("negative_ratio", 0.0)),
                average_sentiment_score=float(row.get("avg_sentiment", 0.0)),
            )
        )

    # Get total count for pagination
    total = len(posts)
    if len(posts) == limit:
        # There might be more -- get total from a count query
        if candidate_id:
            count_result = (
                client.table("posts")
                .select("id", count="exact")
                .eq("candidate_id", candidate_id)
                .execute()
            )
        else:
            count_result = (
                client.table("posts")
                .select("id", count="exact")
                .execute()
            )
        total = count_result.count if count_result.count is not None else len(posts)

    return PostRankingResponse(
        posts=posts,
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# AC6: GET /analytics/comparison
# ---------------------------------------------------------------------------

def get_comparison() -> ComparisonResponse:
    """Get side-by-side candidate comparison with trend analysis.

    Uses PL/pgSQL get_candidate_comparison for core metrics and trend data.
    Adds top_themes from get_theme_distribution per candidate.
    """
    client = get_supabase()

    rpc_result = client.rpc("get_candidate_comparison", {}).execute()
    rows = rpc_result.data or []

    candidates: list[CandidateComparison] = []
    for row in rows:
        cid = row["candidate_id"]

        # Get top 3 themes for this candidate
        theme_result = client.rpc(
            "get_theme_distribution",
            {"p_candidate_id": cid},
        ).execute()
        theme_rows = theme_result.data or []
        top_themes = [
            ThemeCount(
                theme=tr["theme"],
                count=int(tr.get("comment_count", 0)),
            )
            for tr in theme_rows[:3]
        ]

        # Calculate trend direction
        recent_avg = float(row.get("recent_avg_sentiment", 0.0))
        previous_avg = float(row.get("previous_avg_sentiment", 0.0))
        delta = round(recent_avg - previous_avg, 4)

        if delta > 0.02:
            direction = "improving"
        elif delta < -0.02:
            direction = "declining"
        else:
            direction = "stable"

        candidates.append(
            CandidateComparison(
                candidate_id=UUID(cid),
                username=row["username"],
                display_name=row.get("display_name"),
                total_posts=int(row.get("total_posts", 0)),
                total_comments=int(row.get("total_comments", 0)),
                average_sentiment_score=float(row.get("avg_sentiment", 0.0)),
                total_engagement=int(row.get("total_engagement", 0)),
                sentiment_distribution=SentimentDistribution(
                    positive=int(row.get("positive_count", 0)),
                    negative=int(row.get("negative_count", 0)),
                    neutral=int(row.get("neutral_count", 0)),
                ),
                top_themes=top_themes,
                trend=SentimentTrend(
                    direction=direction,
                    recent_avg=recent_avg,
                    previous_avg=previous_avg,
                    delta=delta,
                ),
            )
        )

    return ComparisonResponse(candidates=candidates)
