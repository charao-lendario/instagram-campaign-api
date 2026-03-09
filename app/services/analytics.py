"""Analytics service with pure SQL queries via asyncpg."""

from app.core.logging import logger
from app.db.pool import get_pool
from app.services.themes import extract_words_for_wordcloud


async def get_overview() -> dict:
    """Get overview analytics for all candidates."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        candidates = await conn.fetch(
            """SELECT
                 c.id as candidate_id,
                 c.username,
                 c.display_name,
                 COUNT(DISTINCT p.id) as total_posts,
                 COUNT(DISTINCT cm.id) as total_comments,
                 COALESCE(AVG(s.vader_compound), 0) as avg_sentiment,
                 COUNT(*) FILTER (WHERE s.final_label = 'positive') as positive,
                 COUNT(*) FILTER (WHERE s.final_label = 'negative') as negative,
                 COUNT(*) FILTER (WHERE s.final_label = 'neutral') as neutral,
                 COALESCE(SUM(p.like_count), 0) + COALESCE(COUNT(DISTINCT cm.id), 0) as total_engagement
               FROM candidates c
               LEFT JOIN posts p ON p.candidate_id = c.id
               LEFT JOIN comments cm ON cm.post_id = p.id
               LEFT JOIN sentiment_scores s ON s.comment_id = cm.id
               WHERE c.is_active = TRUE
               GROUP BY c.id, c.username, c.display_name
               ORDER BY c.username"""
        )

        # Last scrape info
        last_scrape = await conn.fetchrow(
            """SELECT id, started_at, completed_at, status, posts_scraped, comments_scraped
               FROM scraping_runs ORDER BY started_at DESC LIMIT 1"""
        )

        total_analyzed = await conn.fetchval(
            "SELECT COUNT(*) FROM sentiment_scores"
        )

    candidate_list = []
    for c in candidates:
        # Deduplicate engagement: use distinct post likes
        candidate_list.append({
            "candidate_id": str(c["candidate_id"]),
            "username": c["username"],
            "display_name": c["display_name"],
            "total_posts": c["total_posts"],
            "total_comments": c["total_comments"],
            "average_sentiment_score": round(float(c["avg_sentiment"]), 4),
            "sentiment_distribution": {
                "positive": c["positive"],
                "negative": c["negative"],
                "neutral": c["neutral"],
            },
            "total_engagement": int(c["total_engagement"]),
        })

    return {
        "candidates": candidate_list,
        "last_scrape": {
            "id": str(last_scrape["id"]),
            "started_at": last_scrape["started_at"].isoformat() if last_scrape["started_at"] else None,
            "completed_at": last_scrape["completed_at"].isoformat() if last_scrape["completed_at"] else None,
            "status": last_scrape["status"],
            "posts_scraped": last_scrape["posts_scraped"],
            "comments_scraped": last_scrape["comments_scraped"],
        } if last_scrape else None,
        "total_comments_analyzed": total_analyzed or 0,
    }


async def get_sentiment_timeline(
    candidate_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Get sentiment timeline grouped by post."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        query = """
            SELECT
              p.candidate_id,
              c.username as candidate_username,
              p.id as post_id,
              p.url as post_url,
              p.caption as post_caption,
              p.posted_at,
              COALESCE(AVG(s.vader_compound), 0) as avg_sentiment,
              COUNT(s.id) as comment_count
            FROM posts p
            JOIN candidates c ON c.id = p.candidate_id
            JOIN comments cm ON cm.post_id = p.id
            JOIN sentiment_scores s ON s.comment_id = cm.id
            WHERE 1=1
        """
        params: list = []
        idx = 1

        if candidate_id:
            query += f" AND p.candidate_id = ${idx}::uuid"
            params.append(candidate_id)
            idx += 1

        if start_date:
            query += f" AND p.posted_at >= ${idx}::timestamptz"
            params.append(start_date)
            idx += 1

        if end_date:
            query += f" AND p.posted_at <= ${idx}::timestamptz"
            params.append(end_date)
            idx += 1

        query += """
            GROUP BY p.id, p.candidate_id, c.username, p.url, p.caption, p.posted_at
            ORDER BY p.posted_at ASC NULLS LAST
        """

        rows = await conn.fetch(query, *params)

    return {
        "data_points": [
            {
                "candidate_id": str(r["candidate_id"]),
                "candidate_username": r["candidate_username"],
                "post_id": str(r["post_id"]),
                "post_url": r["post_url"],
                "post_caption": r["post_caption"],
                "posted_at": r["posted_at"].isoformat() if r["posted_at"] else "",
                "average_sentiment_score": round(float(r["avg_sentiment"]), 4),
                "comment_count": r["comment_count"],
            }
            for r in rows
        ]
    }


async def get_wordcloud(candidate_id: str | None = None) -> dict:
    """Get word frequencies for wordcloud."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if candidate_id:
            rows = await conn.fetch(
                """SELECT cm.text FROM comments cm
                   JOIN posts p ON p.id = cm.post_id
                   WHERE p.candidate_id = $1::uuid AND cm.text IS NOT NULL""",
                candidate_id,
            )
        else:
            rows = await conn.fetch(
                "SELECT text FROM comments WHERE text IS NOT NULL"
            )

    texts = [r["text"] for r in rows]
    words = extract_words_for_wordcloud(texts)

    return {
        "words": words,
        "total_unique_words": len(words),
    }


async def get_themes(candidate_id: str | None = None) -> dict:
    """Get theme distribution with per-candidate breakdown."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if candidate_id:
            rows = await conn.fetch(
                """SELECT t.theme, COUNT(*) as cnt,
                          c.id as cand_id, c.username
                   FROM themes t
                   JOIN comments cm ON cm.id = t.comment_id
                   JOIN posts p ON p.id = cm.post_id
                   JOIN candidates c ON c.id = p.candidate_id
                   WHERE p.candidate_id = $1::uuid
                   GROUP BY t.theme, c.id, c.username
                   ORDER BY cnt DESC""",
                candidate_id,
            )
        else:
            rows = await conn.fetch(
                """SELECT t.theme, COUNT(*) as cnt,
                          c.id as cand_id, c.username
                   FROM themes t
                   JOIN comments cm ON cm.id = t.comment_id
                   JOIN posts p ON p.id = cm.post_id
                   JOIN candidates c ON c.id = p.candidate_id
                   GROUP BY t.theme, c.id, c.username
                   ORDER BY cnt DESC"""
            )

    # Aggregate
    theme_totals: dict[str, int] = {}
    theme_by_cand: dict[str, dict[str, dict]] = {}

    for r in rows:
        theme = r["theme"]
        cnt = r["cnt"]
        cand_id = str(r["cand_id"])
        username = r["username"]

        theme_totals[theme] = theme_totals.get(theme, 0) + cnt
        if theme not in theme_by_cand:
            theme_by_cand[theme] = {}
        theme_by_cand[theme][cand_id] = {"candidate_id": cand_id, "username": username, "count": cnt}

    grand_total = sum(theme_totals.values()) or 1

    themes_list = []
    for theme, count in sorted(theme_totals.items(), key=lambda x: x[1], reverse=True):
        themes_list.append({
            "theme": theme,
            "count": count,
            "percentage": round(count / grand_total * 100, 2),
            "by_candidate": list(theme_by_cand.get(theme, {}).values()),
        })

    return {"themes": themes_list}


async def get_posts(
    candidate_id: str | None = None,
    sort_by: str = "posted_at",
    order: str = "desc",
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Get posts with sentiment ratios."""
    pool = await get_pool()

    allowed_sort = {"posted_at", "like_count", "comment_count", "average_sentiment_score"}
    if sort_by not in allowed_sort:
        sort_by = "posted_at"
    order_dir = "ASC" if order.lower() == "asc" else "DESC"

    # Map sort field to actual column
    sort_col = sort_by
    if sort_by == "average_sentiment_score":
        sort_col = "avg_sentiment"

    async with pool.acquire() as conn:
        base_where = "WHERE 1=1"
        params: list = []
        idx = 1

        if candidate_id:
            base_where += f" AND p.candidate_id = ${idx}::uuid"
            params.append(candidate_id)
            idx += 1

        # Count total
        total = await conn.fetchval(
            f"""SELECT COUNT(*) FROM posts p {base_where}""",
            *params,
        )

        # Main query
        query = f"""
            SELECT
              p.id as post_id,
              c.username as candidate_username,
              p.url,
              p.caption,
              p.posted_at,
              p.like_count,
              p.comment_count,
              COALESCE(AVG(s.vader_compound), 0) as avg_sentiment,
              COUNT(*) FILTER (WHERE s.final_label = 'positive') as pos_count,
              COUNT(*) FILTER (WHERE s.final_label = 'negative') as neg_count,
              COUNT(s.id) as scored_count
            FROM posts p
            JOIN candidates c ON c.id = p.candidate_id
            LEFT JOIN comments cm ON cm.post_id = p.id
            LEFT JOIN sentiment_scores s ON s.comment_id = cm.id
            {base_where}
            GROUP BY p.id, c.username, p.url, p.caption, p.posted_at, p.like_count, p.comment_count
            ORDER BY {sort_col} {order_dir} NULLS LAST
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        params.extend([limit, offset])

        rows = await conn.fetch(query, *params)

    posts_list = []
    for r in rows:
        scored = r["scored_count"] or 1
        posts_list.append({
            "post_id": str(r["post_id"]),
            "candidate_username": r["candidate_username"],
            "url": r["url"],
            "caption": r["caption"],
            "posted_at": r["posted_at"].isoformat() if r["posted_at"] else None,
            "like_count": r["like_count"],
            "comment_count": r["comment_count"],
            "positive_ratio": round(r["pos_count"] / scored, 4) if scored else 0.0,
            "negative_ratio": round(r["neg_count"] / scored, 4) if scored else 0.0,
            "average_sentiment_score": round(float(r["avg_sentiment"]), 4),
        })

    return {
        "posts": posts_list,
        "total": total or 0,
        "limit": limit,
        "offset": offset,
    }


async def get_comparison() -> dict:
    """Get comparison data for all candidates with trends and top themes."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        candidates = await conn.fetch(
            """SELECT
                 c.id, c.username, c.display_name,
                 COUNT(DISTINCT p.id) as total_posts,
                 COUNT(DISTINCT cm.id) as total_comments,
                 COALESCE(AVG(s.vader_compound), 0) as avg_sentiment,
                 COALESCE(SUM(p.like_count), 0) + COUNT(DISTINCT cm.id) as total_engagement,
                 COUNT(*) FILTER (WHERE s.final_label = 'positive') as positive,
                 COUNT(*) FILTER (WHERE s.final_label = 'negative') as negative,
                 COUNT(*) FILTER (WHERE s.final_label = 'neutral') as neutral
               FROM candidates c
               LEFT JOIN posts p ON p.candidate_id = c.id
               LEFT JOIN comments cm ON cm.post_id = p.id
               LEFT JOIN sentiment_scores s ON s.comment_id = cm.id
               WHERE c.is_active = TRUE
               GROUP BY c.id, c.username, c.display_name"""
        )

        result = []
        for c in candidates:
            cand_id = c["id"]

            # Top themes
            themes = await conn.fetch(
                """SELECT t.theme, COUNT(*) as cnt
                   FROM themes t
                   JOIN comments cm ON cm.id = t.comment_id
                   JOIN posts p ON p.id = cm.post_id
                   WHERE p.candidate_id = $1
                   GROUP BY t.theme
                   ORDER BY cnt DESC
                   LIMIT 5""",
                cand_id,
            )

            # Trend: average sentiment per week
            trend = await conn.fetch(
                """SELECT
                     date_trunc('week', p.posted_at) as week,
                     AVG(s.vader_compound) as avg_sentiment,
                     COUNT(s.id) as comment_count
                   FROM posts p
                   JOIN comments cm ON cm.post_id = p.id
                   JOIN sentiment_scores s ON s.comment_id = cm.id
                   WHERE p.candidate_id = $1 AND p.posted_at IS NOT NULL
                   GROUP BY week
                   ORDER BY week ASC""",
                cand_id,
            )

            result.append({
                "candidate_id": str(cand_id),
                "username": c["username"],
                "display_name": c["display_name"],
                "total_posts": c["total_posts"],
                "total_comments": c["total_comments"],
                "average_sentiment_score": round(float(c["avg_sentiment"]), 4),
                "total_engagement": int(c["total_engagement"]),
                "sentiment_distribution": {
                    "positive": c["positive"],
                    "negative": c["negative"],
                    "neutral": c["neutral"],
                },
                "top_themes": [
                    {"theme": t["theme"], "count": t["cnt"]}
                    for t in themes
                ],
                "trend": [
                    {
                        "week": t["week"].isoformat() if t["week"] else None,
                        "average_sentiment": round(float(t["avg_sentiment"]), 4),
                        "comment_count": t["comment_count"],
                    }
                    for t in trend
                ],
            })

    return {"candidates": result}


async def get_competitive(our_username: str, competitor_username: str) -> dict:
    """Compare two candidates head-to-head."""
    pool = await get_pool()

    async def _get_candidate_stats(username: str) -> dict | None:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT
                     c.id, c.username, c.display_name,
                     COUNT(DISTINCT p.id) as total_posts,
                     COUNT(DISTINCT cm.id) as total_comments,
                     COALESCE(AVG(s.vader_compound), 0) as avg_sentiment,
                     COALESCE(SUM(p.like_count), 0) + COUNT(DISTINCT cm.id) as total_engagement,
                     COUNT(*) FILTER (WHERE s.final_label = 'positive') as positive,
                     COUNT(*) FILTER (WHERE s.final_label = 'negative') as negative,
                     COUNT(*) FILTER (WHERE s.final_label = 'neutral') as neutral
                   FROM candidates c
                   LEFT JOIN posts p ON p.candidate_id = c.id
                   LEFT JOIN comments cm ON cm.post_id = p.id
                   LEFT JOIN sentiment_scores s ON s.comment_id = cm.id
                   WHERE c.username = $1
                   GROUP BY c.id, c.username, c.display_name""",
                username,
            )

        if not row:
            return None

        return {
            "candidate_id": str(row["id"]),
            "username": row["username"],
            "display_name": row["display_name"],
            "total_posts": row["total_posts"],
            "total_comments": row["total_comments"],
            "average_sentiment_score": round(float(row["avg_sentiment"]), 4),
            "total_engagement": int(row["total_engagement"]),
            "sentiment_distribution": {
                "positive": row["positive"],
                "negative": row["negative"],
                "neutral": row["neutral"],
            },
        }

    our = await _get_candidate_stats(our_username)
    comp = await _get_candidate_stats(competitor_username)

    our_engagement = our["total_engagement"] if our else 0
    comp_engagement = comp["total_engagement"] if comp else 0
    our_sentiment = our["average_sentiment_score"] if our else 0.0
    comp_sentiment = comp["average_sentiment_score"] if comp else 0.0

    return {
        "our_candidate": our,
        "competitor": comp,
        "engagement_advantage": round(our_engagement - comp_engagement, 2),
        "sentiment_advantage": round(our_sentiment - comp_sentiment, 4),
    }
