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
    CompetitiveAnalysisResponse,
    CompetitiveMetrics,
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
    """Tokenize texts into bigrams, filter stop words, count frequencies.

    Returns bigrams (2-word expressions) for richer context instead of
    single words. Captures what people are actually saying.
    """
    bigrams: list[str] = []
    unigrams: list[str] = []

    for text in texts:
        normalized = _normalize_for_wordcloud(text)
        tokens = [
            t for t in normalized.split()
            if t not in STOP_WORDS_PT and len(t) > 2
        ]
        # Collect bigrams
        for i in range(len(tokens) - 1):
            bigrams.append(f"{tokens[i]} {tokens[i + 1]}")
        # Collect unigrams as fallback
        unigrams.extend(tokens)

    # Combine: prioritize bigrams, fill with unigrams
    bi_counter = Counter(bigrams)
    uni_counter = Counter(unigrams)

    entries: list[WordEntry] = []
    # Top bigrams (with minimum 2 occurrences)
    for phrase, count in bi_counter.most_common(top_n):
        if count >= 2:
            entries.append(WordEntry(word=phrase, count=count))

    # Fill remaining with unigrams
    remaining = top_n - len(entries)
    if remaining > 0:
        # Exclude words already covered by bigrams
        bigram_words = set()
        for e in entries:
            bigram_words.update(e.word.split())
        for word, count in uni_counter.most_common(top_n):
            if word not in bigram_words and count >= 2:
                entries.append(WordEntry(word=word, count=count))
                if len(entries) >= top_n:
                    break

    return entries[:top_n]


# ---------------------------------------------------------------------------
# AC4: GET /analytics/themes
# ---------------------------------------------------------------------------

def get_theme_distribution(
    candidate_id: str | None = None,
) -> ThemeDistributionResponse:
    """Get theme distribution with per-candidate breakdown.

    Queries themes table directly with joins, aggregating counts in Python
    to avoid PL/pgSQL round() and ambiguity issues.
    """
    client = get_supabase()

    # Get all active candidates
    candidates_result = (
        client.table("candidates")
        .select("id, username")
        .eq("is_active", True)
        .execute()
    )
    candidates = candidates_result.data or []

    # Fetch raw theme data with candidate info
    query = (
        client.table("themes")
        .select("theme, comment_id, comments!inner(post_id, posts!inner(candidate_id))")
    )
    raw_result = query.execute()
    raw_rows = raw_result.data or []

    # Aggregate in Python
    from collections import defaultdict

    theme_totals: dict[str, int] = defaultdict(int)
    theme_by_candidate: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for row in raw_rows:
        theme_name = row["theme"]
        cid = row["comments"]["posts"]["candidate_id"]

        if candidate_id and cid != candidate_id:
            continue

        theme_totals[theme_name] += 1
        theme_by_candidate[theme_name][cid] += 1

    total_themed = sum(theme_totals.values()) or 1
    cand_lookup = {c["id"]: c["username"] for c in candidates}

    themes: list[ThemeDistribution] = []
    for theme_name, count in sorted(theme_totals.items(), key=lambda x: -x[1]):
        by_candidate: list[CandidateThemeCount] = []
        for cid, ccount in theme_by_candidate[theme_name].items():
            if cid in cand_lookup:
                by_candidate.append(
                    CandidateThemeCount(
                        candidate_id=UUID(cid),
                        username=cand_lookup[cid],
                        count=ccount,
                    )
                )

        themes.append(
            ThemeDistribution(
                theme=theme_name,
                count=count,
                percentage=round((count / total_themed) * 100, 2),
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

    Uses get_candidate_overview per candidate for core metrics and
    calculates trend from recent vs previous posts in Python.
    """
    client = get_supabase()

    # Get active candidates
    cand_result = (
        client.table("candidates")
        .select("id, username, display_name")
        .eq("is_active", True)
        .order("username")
        .execute()
    )

    candidates: list[CandidateComparison] = []
    for cand in cand_result.data or []:
        cid = cand["id"]

        # Reuse get_candidate_overview RPC (which works)
        overview = client.rpc(
            "get_candidate_overview", {"p_candidate_id": cid}
        ).execute()
        ov = overview.data[0] if overview.data else {}

        # Get top 3 themes for this candidate
        theme_resp = get_theme_distribution(candidate_id=cid)
        top_themes = [
            ThemeCount(theme=t.theme, count=t.count)
            for t in theme_resp.themes[:3]
        ]

        # Calculate trend: recent 5 posts vs previous 5 posts
        posts_result = (
            client.table("posts")
            .select("id, posted_at")
            .eq("candidate_id", cid)
            .order("posted_at", desc=True)
            .limit(10)
            .execute()
        )
        post_ids = [p["id"] for p in (posts_result.data or [])]
        recent_ids = post_ids[:5]
        previous_ids = post_ids[5:10]

        recent_avg = 0.0
        previous_avg = 0.0

        if recent_ids:
            sent_result = (
                client.table("sentiment_scores")
                .select("vader_compound, comments!inner(post_id)")
                .in_("comments.post_id", recent_ids)
                .execute()
            )
            scores = [float(r["vader_compound"]) for r in (sent_result.data or []) if r.get("vader_compound") is not None]
            recent_avg = sum(scores) / len(scores) if scores else 0.0

        if previous_ids:
            sent_result2 = (
                client.table("sentiment_scores")
                .select("vader_compound, comments!inner(post_id)")
                .in_("comments.post_id", previous_ids)
                .execute()
            )
            scores2 = [float(r["vader_compound"]) for r in (sent_result2.data or []) if r.get("vader_compound") is not None]
            previous_avg = sum(scores2) / len(scores2) if scores2 else 0.0

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
                username=cand["username"],
                display_name=cand.get("display_name"),
                total_posts=int(ov.get("total_posts", 0)),
                total_comments=int(ov.get("total_comments", 0)),
                average_sentiment_score=float(ov.get("avg_sentiment", 0.0)),
                total_engagement=int(ov.get("total_engagement", 0)),
                sentiment_distribution=SentimentDistribution(
                    positive=int(ov.get("positive_count", 0)),
                    negative=int(ov.get("negative_count", 0)),
                    neutral=int(ov.get("neutral_count", 0)),
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


# ---------------------------------------------------------------------------
# Competitive Analysis
# ---------------------------------------------------------------------------

def _build_candidate_metrics(
    cid: str,
    username: str,
    display_name: str | None,
) -> CompetitiveMetrics:
    """Build metrics for a single candidate."""
    client = get_supabase()

    overview = client.rpc(
        "get_candidate_overview", {"p_candidate_id": cid}
    ).execute()
    ov = overview.data[0] if overview.data else {}

    total_posts = int(ov.get("total_posts", 0))
    total_comments = int(ov.get("total_comments", 0))
    total_engagement = int(ov.get("total_engagement", 0))

    theme_resp = get_theme_distribution(candidate_id=cid)
    top_themes = [
        ThemeCount(theme=t.theme, count=t.count)
        for t in theme_resp.themes[:5]
        if t.theme != "outros"
    ]

    return CompetitiveMetrics(
        username=username,
        display_name=display_name,
        total_posts=total_posts,
        total_comments=total_comments,
        average_sentiment_score=float(ov.get("avg_sentiment", 0.0)),
        total_engagement=total_engagement,
        avg_likes_per_post=round(total_engagement / max(total_posts, 1), 1),
        avg_comments_per_post=round(total_comments / max(total_posts, 1), 1),
        sentiment_distribution=SentimentDistribution(
            positive=int(ov.get("positive_count", 0)),
            negative=int(ov.get("negative_count", 0)),
            neutral=int(ov.get("neutral_count", 0)),
        ),
        top_themes=top_themes,
    )


def get_competitive_analysis(
    our_username: str,
    competitor_username: str,
) -> CompetitiveAnalysisResponse:
    """Compare engagement and sentiment between our candidate and a competitor."""
    client = get_supabase()

    # Resolve candidate IDs
    our_result = (
        client.table("candidates")
        .select("id, username, display_name")
        .eq("username", our_username)
        .execute()
    )
    comp_result = (
        client.table("candidates")
        .select("id, username, display_name")
        .eq("username", competitor_username)
        .execute()
    )

    our_data = our_result.data[0] if our_result.data else None
    comp_data = comp_result.data[0] if comp_result.data else None

    our_metrics = None
    comp_metrics = None

    if our_data:
        our_metrics = _build_candidate_metrics(
            our_data["id"], our_data["username"], our_data.get("display_name")
        )
    if comp_data:
        comp_metrics = _build_candidate_metrics(
            comp_data["id"], comp_data["username"], comp_data.get("display_name")
        )

    engagement_adv = 0.0
    sentiment_adv = 0.0
    if our_metrics and comp_metrics:
        if comp_metrics.avg_likes_per_post > 0:
            engagement_adv = round(
                ((our_metrics.avg_likes_per_post - comp_metrics.avg_likes_per_post)
                 / comp_metrics.avg_likes_per_post) * 100, 1
            )
        sentiment_adv = round(
            our_metrics.average_sentiment_score - comp_metrics.average_sentiment_score, 4
        )

    return CompetitiveAnalysisResponse(
        our_candidate=our_metrics,
        competitor=comp_metrics,
        engagement_advantage=engagement_adv,
        sentiment_advantage=sentiment_adv,
    )
