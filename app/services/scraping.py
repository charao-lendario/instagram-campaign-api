"""Scraping service using Apify to fetch Instagram posts and comments."""

import asyncio
import json
import time
from datetime import datetime, timezone
from uuid import UUID

from apify_client import ApifyClient

from app.core.config import settings
from app.core.logging import logger
from app.db.pool import get_pool

# Thread-safe lock for pipeline
_pipeline_lock = asyncio.Lock()


async def is_pipeline_running() -> bool:
    """Check if a scraping pipeline is currently running."""
    return _pipeline_lock.locked()


async def get_last_scrape_info() -> dict | None:
    """Get info about the last scraping run."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, started_at, completed_at, status, posts_scraped, comments_scraped "
            "FROM scraping_runs ORDER BY started_at DESC LIMIT 1"
        )
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "started_at": row["started_at"].isoformat() if row["started_at"] else None,
            "completed_at": row["completed_at"].isoformat() if row["completed_at"] else None,
            "status": row["status"],
            "posts_scraped": row["posts_scraped"],
            "comments_scraped": row["comments_scraped"],
        }


async def run_full_pipeline() -> UUID:
    """Run the full scraping + analysis pipeline. Returns the scraping run ID."""
    if _pipeline_lock.locked():
        raise RuntimeError("Pipeline already running")

    async with _pipeline_lock:
        pool = await get_pool()
        start_time = time.time()

        # Create scraping run
        async with pool.acquire() as conn:
            run_row = await conn.fetchrow(
                "INSERT INTO scraping_runs (status) VALUES ('running') RETURNING id"
            )
            run_id: UUID = run_row["id"]

        logger.info(f"Pipeline started: run_id={run_id}")

        total_posts = 0
        total_comments = 0
        errors: list[str] = []

        try:
            # Get active candidates
            async with pool.acquire() as conn:
                candidates = await conn.fetch(
                    "SELECT id, username FROM candidates WHERE is_active = TRUE"
                )

            if not candidates:
                logger.warning("No active candidates found")

            for candidate in candidates:
                cand_id = candidate["id"]
                username = candidate["username"]
                logger.info(f"Scraping posts for @{username}")

                try:
                    posts_count, comments_count = await _scrape_candidate(
                        pool, run_id, cand_id, username
                    )
                    total_posts += posts_count
                    total_comments += comments_count
                except Exception as e:
                    error_msg = f"Error scraping @{username}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)

            # Run sentiment analysis
            from app.services.sentiment import analyze_unanalyzed_comments
            analyzed = await analyze_unanalyzed_comments()
            logger.info(f"Sentiment analysis: {analyzed} comments analyzed")

            # Run theme classification
            from app.services.themes import classify_unclassified_comments
            themed = await classify_unclassified_comments()
            logger.info(f"Theme classification: {themed} comments classified")

            duration = round(time.time() - start_time, 2)
            status = "partial" if errors else "success"

            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE scraping_runs
                       SET status = $1, completed_at = NOW(),
                           posts_scraped = $2, comments_scraped = $3,
                           duration_seconds = $4, errors = $5::jsonb
                       WHERE id = $6""",
                    status, total_posts, total_comments,
                    duration, json.dumps(errors) if errors else None, run_id,
                )

            logger.info(
                f"Pipeline complete: {total_posts} posts, "
                f"{total_comments} comments in {duration}s"
            )

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE scraping_runs
                       SET status = 'failed', completed_at = NOW(),
                           errors = $1::jsonb
                       WHERE id = $2""",
                    json.dumps([str(e)]), run_id,
                )
            raise

        return run_id


async def _scrape_candidate(
    pool, run_id: UUID, candidate_id: UUID, username: str
) -> tuple[int, int]:
    """Scrape posts and comments for a single candidate. Returns (posts, comments) count."""
    if not settings.APIFY_TOKEN:
        logger.warning("APIFY_TOKEN not set, skipping scraping")
        return 0, 0

    client = ApifyClient(settings.APIFY_TOKEN)

    # Run Instagram Post Scraper
    run_input = {
        "username": [username],
        "resultsLimit": 30,
    }

    logger.info(f"Starting Apify actor for @{username}")
    actor_run = client.actor("apify/instagram-post-scraper").call(
        run_input=run_input, timeout_secs=300
    )

    items = list(
        client.dataset(actor_run["defaultDatasetId"]).iterate_items()
    )
    logger.info(f"Got {len(items)} items from Apify for @{username}")

    posts_count = 0
    comments_count = 0

    async with pool.acquire() as conn:
        for item in items:
            instagram_id = item.get("id", item.get("shortCode", ""))
            if not instagram_id:
                continue

            shortcode = item.get("shortCode", "")
            url = item.get("url", f"https://www.instagram.com/p/{shortcode}/")
            caption = item.get("caption", "")
            like_count = item.get("likesCount", 0) or 0
            comment_count_val = item.get("commentsCount", 0) or 0

            # Determine media type
            item_type = item.get("type", "unknown")
            if item_type == "Video":
                mt = "video"
            elif item_type == "Sidecar":
                mt = "carousel"
            elif item_type == "Image":
                mt = "image"
            else:
                mt = "unknown"

            posted_at = item.get("timestamp")
            if posted_at and isinstance(posted_at, str):
                try:
                    posted_at = datetime.fromisoformat(
                        posted_at.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    posted_at = None

            video_views = item.get("videoViewCount")
            is_sponsored = item.get("isSponsored", False) or False

            # Upsert post
            post_row = await conn.fetchrow(
                """INSERT INTO posts
                   (candidate_id, scraping_run_id, instagram_id, url, shortcode,
                    caption, like_count, comment_count, media_type, is_sponsored,
                    video_view_count, posted_at, raw_data)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::media_type, $10, $11, $12, $13::jsonb)
                   ON CONFLICT (instagram_id) DO UPDATE SET
                    like_count = EXCLUDED.like_count,
                    comment_count = EXCLUDED.comment_count,
                    updated_at = NOW()
                   RETURNING id""",
                candidate_id, run_id, str(instagram_id), url, shortcode,
                caption, like_count, comment_count_val, mt, is_sponsored,
                video_views, posted_at, json.dumps(item),
            )
            post_id = post_row["id"]
            posts_count += 1

            # Process comments from the item
            item_comments = item.get("latestComments", []) or []
            for comment in item_comments:
                comment_ig_id = comment.get("id", "")
                if not comment_ig_id:
                    continue

                comment_text = comment.get("text", "")
                if not comment_text:
                    continue

                author = comment.get("ownerUsername", comment.get("owner", {}).get("username"))
                c_like_count = comment.get("likesCount", 0) or 0
                c_reply_count = comment.get("repliesCount", 0) or 0
                commented_at = comment.get("timestamp")
                if commented_at and isinstance(commented_at, str):
                    try:
                        commented_at = datetime.fromisoformat(
                            commented_at.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        commented_at = None

                try:
                    await conn.execute(
                        """INSERT INTO comments
                           (post_id, scraping_run_id, instagram_id, text,
                            author_username, like_count, reply_count, commented_at, raw_data)
                           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb)
                           ON CONFLICT (instagram_id) DO NOTHING""",
                        post_id, run_id, str(comment_ig_id), comment_text,
                        author, c_like_count, c_reply_count, commented_at,
                        json.dumps(comment),
                    )
                    comments_count += 1
                except Exception as e:
                    logger.debug(f"Comment insert error (likely duplicate): {e}")

    return posts_count, comments_count
