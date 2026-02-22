"""Apify-based Instagram scraping service.

Implements post and comment collection via Apify actors with idempotent
upserts into Supabase.  Each public function creates or updates a
``scraping_runs`` record for observability.

Story 1.2: ``scrape_posts``
Story 1.3: ``scrape_comments``, ``scrape_all_comments``
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from apify_client import ApifyClient

from app.core.config import settings
from app.db.supabase import get_supabase
from app.models.comment import Comment, CommentUpsert
from app.models.enums import MediaType
from app.models.post import Post, PostUpsert

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Apify client helper
# ---------------------------------------------------------------------------

def _get_apify_client() -> ApifyClient:
    """Return a configured Apify client."""
    return ApifyClient(settings.APIFY_TOKEN)


# ---------------------------------------------------------------------------
# Candidate resolution
# ---------------------------------------------------------------------------

def _resolve_candidate_id(username: str) -> UUID:
    """Resolve a ``candidate_id`` from ``candidates`` by *username*.

    Raises ``ValueError`` if the username is not found.
    """
    client = get_supabase()
    result = (
        client.table("candidates")
        .select("id")
        .eq("username", username)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise ValueError(f"Candidate not found for username: {username}")
    return UUID(result.data[0]["id"])


# ---------------------------------------------------------------------------
# Apify -> Pydantic mappers
# ---------------------------------------------------------------------------

_MEDIA_TYPE_MAP: dict[str, MediaType] = {
    "Image": MediaType.image,
    "Video": MediaType.video,
    "Carousel": MediaType.carousel,
    "Sidecar": MediaType.carousel,
    "image": MediaType.image,
    "video": MediaType.video,
    "carousel": MediaType.carousel,
    "sidecar": MediaType.carousel,
}


def _map_apify_post(
    item: dict[str, Any],
    candidate_id: UUID,
    run_id: UUID,
) -> PostUpsert:
    """Map a single Apify post-scraper result to a ``PostUpsert``."""
    raw_type = item.get("type", "")
    media_type = _MEDIA_TYPE_MAP.get(str(raw_type), MediaType.unknown)

    posted_at_raw = item.get("timestamp")
    posted_at: datetime | None = None
    if posted_at_raw:
        if isinstance(posted_at_raw, str):
            try:
                posted_at = datetime.fromisoformat(posted_at_raw.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                posted_at = None
        elif isinstance(posted_at_raw, (int, float)):
            posted_at = datetime.fromtimestamp(posted_at_raw, tz=timezone.utc)

    return PostUpsert(
        candidate_id=candidate_id,
        scraping_run_id=run_id,
        instagram_id=str(item.get("id", "")),
        url=item.get("url") or item.get("postUrl") or "",
        shortcode=item.get("shortCode"),
        caption=item.get("caption"),
        like_count=int(item.get("likesCount", 0)),
        comment_count=int(item.get("commentsCount", 0)),
        media_type=media_type,
        is_sponsored=bool(item.get("isSponsored", False)),
        video_view_count=item.get("videoViewCount"),
        posted_at=posted_at,
        raw_data=item,
    )


def _map_apify_comment(
    item: dict[str, Any],
    post_id: UUID,
    run_id: UUID,
) -> CommentUpsert:
    """Map a single Apify comment-scraper result to a ``CommentUpsert``."""
    commented_at_raw = item.get("timestamp")
    commented_at: datetime | None = None
    if commented_at_raw:
        if isinstance(commented_at_raw, str):
            try:
                commented_at = datetime.fromisoformat(
                    commented_at_raw.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                commented_at = None
        elif isinstance(commented_at_raw, (int, float)):
            commented_at = datetime.fromtimestamp(commented_at_raw, tz=timezone.utc)

    # reply_count: Apify may return a count or an array of replies
    replies_raw = item.get("replies", 0)
    if isinstance(replies_raw, list):
        reply_count = len(replies_raw)
    else:
        reply_count = int(replies_raw or 0)

    return CommentUpsert(
        post_id=post_id,
        scraping_run_id=run_id,
        instagram_id=str(item.get("id", "")),
        text=item.get("text", ""),
        author_username=item.get("ownerUsername"),
        like_count=int(item.get("likesCount", 0)),
        reply_count=reply_count,
        commented_at=commented_at,
        raw_data=item,
    )


# ---------------------------------------------------------------------------
# ScrapingRun helpers
# ---------------------------------------------------------------------------

def _create_scraping_run() -> UUID:
    """Insert a new ``scraping_runs`` row with status *running* and return its id."""
    client = get_supabase()
    result = (
        client.table("scraping_runs")
        .insert({"status": "running"})
        .execute()
    )
    return UUID(result.data[0]["id"])


def _update_run_posts_scraped(run_id: UUID, count: int) -> None:
    """Increment ``posts_scraped`` on the given run."""
    client = get_supabase()
    # Fetch current value to increment
    current = (
        client.table("scraping_runs")
        .select("posts_scraped")
        .eq("id", str(run_id))
        .limit(1)
        .execute()
    )
    current_count = current.data[0]["posts_scraped"] if current.data else 0
    client.table("scraping_runs").update(
        {"posts_scraped": current_count + count}
    ).eq("id", str(run_id)).execute()


def _update_run_comments_scraped(run_id: UUID, count: int) -> None:
    """Increment ``comments_scraped`` on the given run."""
    client = get_supabase()
    current = (
        client.table("scraping_runs")
        .select("comments_scraped")
        .eq("id", str(run_id))
        .limit(1)
        .execute()
    )
    current_count = current.data[0]["comments_scraped"] if current.data else 0
    client.table("scraping_runs").update(
        {"comments_scraped": current_count + count}
    ).eq("id", str(run_id)).execute()


def _append_run_error(run_id: UUID, error_entry: dict[str, Any]) -> None:
    """Append an error entry to ``scraping_runs.errors`` JSONB array."""
    client = get_supabase()
    current = (
        client.table("scraping_runs")
        .select("errors")
        .eq("id", str(run_id))
        .limit(1)
        .execute()
    )
    existing_errors: list[dict[str, Any]] = []
    if current.data and current.data[0].get("errors"):
        existing_errors = current.data[0]["errors"]
    existing_errors.append(error_entry)
    client.table("scraping_runs").update(
        {"errors": existing_errors}
    ).eq("id", str(run_id)).execute()


# ---------------------------------------------------------------------------
# Story 1.2: Post scraping
# ---------------------------------------------------------------------------

def scrape_posts(candidate_username: str, run_id: UUID) -> list[Post]:
    """Scrape the latest posts for *candidate_username* using Apify.

    1. Resolve ``candidate_id`` from the database.
    2. Invoke the ``instagram-post-scraper`` actor.
    3. Map results to ``PostUpsert`` and upsert into Supabase.
    4. Update ``scraping_runs.posts_scraped``.

    Returns the list of upserted ``Post`` records.

    Raises on Apify errors after logging and recording the failure in
    ``scraping_runs.errors``.
    """
    logger.info(
        "scrape_posts_started",
        extra={
            "candidate_username": candidate_username,
            "actor_id": settings.APIFY_POST_ACTOR_ID,
            "run_id": str(run_id),
        },
    )

    try:
        candidate_id = _resolve_candidate_id(candidate_username)
    except ValueError:
        error_entry = {
            "candidate": candidate_username,
            "phase": "post_scraping",
            "message": f"Candidate not found: {candidate_username}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _append_run_error(run_id, error_entry)
        raise

    try:
        apify = _get_apify_client()
        run_result = apify.actor(settings.APIFY_POST_ACTOR_ID).call(
            run_input={
                "username": [candidate_username],
                "resultsLimit": 10,
            }
        )
        items: list[dict[str, Any]] = list(
            apify.dataset(run_result["defaultDatasetId"]).iterate_items()
        )
    except Exception as exc:
        error_msg = f"Apify actor failed: {exc}"
        logger.error(
            "scrape_posts_apify_failed",
            extra={
                "candidate_username": candidate_username,
                "actor_id": settings.APIFY_POST_ACTOR_ID,
                "error_message": str(exc),
            },
        )
        error_entry = {
            "candidate": candidate_username,
            "phase": "post_scraping",
            "message": error_msg,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _append_run_error(run_id, error_entry)
        raise RuntimeError(error_msg) from exc

    # Map and upsert
    supabase = get_supabase()
    upserted_posts: list[Post] = []

    for item in items:
        post_upsert = _map_apify_post(item, candidate_id, run_id)
        result = (
            supabase.table("posts")
            .upsert(
                post_upsert.model_dump(mode="json"),
                on_conflict="instagram_id",
            )
            .execute()
        )
        if result.data:
            upserted_posts.append(Post(**result.data[0]))

    # Update run stats
    _update_run_posts_scraped(run_id, len(upserted_posts))

    logger.info(
        "scrape_posts_completed",
        extra={
            "candidate_username": candidate_username,
            "posts_count": len(upserted_posts),
            "run_id": str(run_id),
        },
    )

    return upserted_posts


# ---------------------------------------------------------------------------
# Story 1.3: Comment scraping
# ---------------------------------------------------------------------------

def scrape_comments(post_url: str, post_id: UUID, run_id: UUID) -> list[Comment]:
    """Scrape comments for a single post via Apify comment-scraper.

    Returns the list of upserted ``Comment`` records.  On Apify failure the
    error is logged and recorded in ``scraping_runs.errors``, and the
    function returns an empty list (partial-failure resilience per AC5).
    """
    logger.info(
        "scrape_comments_started",
        extra={
            "post_url": post_url,
            "post_id": str(post_id),
            "actor_id": settings.APIFY_COMMENT_ACTOR_ID,
            "run_id": str(run_id),
        },
    )

    try:
        apify = _get_apify_client()
        run_result = apify.actor(settings.APIFY_COMMENT_ACTOR_ID).call(
            run_input={
                "directUrls": [post_url],
                "resultsLimit": 500,
            }
        )
        items: list[dict[str, Any]] = list(
            apify.dataset(run_result["defaultDatasetId"]).iterate_items()
        )
    except Exception as exc:
        error_msg = f"Apify actor failed for post {post_url}: {exc}"
        logger.error(
            "scrape_comments_apify_failed",
            extra={
                "post_url": post_url,
                "post_id": str(post_id),
                "actor_id": settings.APIFY_COMMENT_ACTOR_ID,
                "error_message": str(exc),
            },
        )
        error_entry = {
            "candidate": "",
            "phase": "comment_scraping",
            "message": error_msg,
            "post_url": post_url,
            "post_id": str(post_id),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _append_run_error(run_id, error_entry)
        return []

    # Map and upsert
    supabase = get_supabase()
    upserted_comments: list[Comment] = []

    for item in items:
        comment_upsert = _map_apify_comment(item, post_id, run_id)
        result = (
            supabase.table("comments")
            .upsert(
                comment_upsert.model_dump(mode="json"),
                on_conflict="instagram_id",
            )
            .execute()
        )
        if result.data:
            upserted_comments.append(Comment(**result.data[0]))

    logger.info(
        "scrape_comments_completed",
        extra={
            "post_url": post_url,
            "post_id": str(post_id),
            "comments_count": len(upserted_comments),
            "run_id": str(run_id),
        },
    )

    return upserted_comments


def scrape_all_comments(posts: list[Post], run_id: UUID) -> int:
    """Scrape comments for every post in *posts*, tolerating partial failures.

    For each post, ``scrape_comments`` is invoked sequentially.  If a single
    post fails the error is logged and the loop continues (AC4).

    Returns the total number of comments collected successfully.
    ``scraping_runs.comments_scraped`` is updated with the total.
    """
    total_scraped = 0

    for idx, post in enumerate(posts, start=1):
        logger.info(
            "scrape_all_comments_progress",
            extra={
                "progress": f"{idx}/{len(posts)}",
                "post_id": str(post.id),
                "run_id": str(run_id),
            },
        )
        try:
            comments = scrape_comments(post.url, post.id, run_id)
            total_scraped += len(comments)
        except Exception as exc:
            # scrape_comments already handles its own error logging and
            # appending to scraping_runs.errors, but we guard against any
            # unexpected propagation here.
            logger.error(
                "scrape_all_comments_unexpected_error",
                extra={
                    "post_id": str(post.id),
                    "error_message": str(exc),
                },
            )

    # Update run total
    _update_run_comments_scraped(run_id, total_scraped)

    logger.info(
        "scrape_all_comments_completed",
        extra={
            "total_comments": total_scraped,
            "posts_processed": len(posts),
            "run_id": str(run_id),
        },
    )

    return total_scraped
