"""Full pipeline orchestration service.

Story 1.7 AC2: Executes the complete data pipeline in sequence:
1. Scrape posts for each active candidate
2. Scrape comments for all collected posts
3. VADER sentiment analysis for new comments
4. LLM fallback for ambiguous comments
5. Theme classification for unthemed comments

AC8: Structured logging for all phases.
AC9: ScrapingRun status tracking (success/partial/failed).
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.db.supabase import get_supabase
from app.models.post import Post
from app.scheduler.lock import acquire_pipeline_lock, release_pipeline_lock
from app.services.scraping import (
    _create_scraping_run,
    scrape_all_comments,
    scrape_posts,
)
from app.services.sentiment import (
    analyze_comments_batch,
    reclassify_ambiguous_comments,
)
from app.services.themes import classify_all_unthemed_comments

logger = logging.getLogger(__name__)


def _get_active_candidates() -> list[dict[str, Any]]:
    """Return all active candidates from the database."""
    client = get_supabase()
    result = (
        client.table("candidates")
        .select("id, username")
        .eq("is_active", True)
        .execute()
    )
    return result.data or []


def _get_unanalyzed_comments() -> list[dict[str, Any]]:
    """Fetch comments without sentiment scores."""
    client = get_supabase()

    analyzed_result = (
        client.table("sentiment_scores")
        .select("comment_id")
        .execute()
    )
    analyzed_ids: set[str] = {
        row["comment_id"] for row in (analyzed_result.data or [])
    }

    comments_result = (
        client.table("comments")
        .select("id, text")
        .execute()
    )
    all_comments: list[dict[str, Any]] = comments_result.data or []

    return [c for c in all_comments if c["id"] not in analyzed_ids]


def _update_run_status(
    run_id: UUID,
    status: str,
    duration_seconds: float | None = None,
) -> None:
    """Update the scraping_runs record with final status."""
    client = get_supabase()
    update_data: dict[str, Any] = {
        "status": status,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    if duration_seconds is not None:
        update_data["duration_seconds"] = round(duration_seconds, 2)
    client.table("scraping_runs").update(update_data).eq(
        "id", str(run_id)
    ).execute()


def run_full_pipeline(trigger: str = "scheduler") -> dict[str, Any]:
    """Execute the full scraping + analysis + themes pipeline.

    AC2: Sequential execution of all 5 phases.
    AC3: Lock acquisition / release with finally block.
    AC8: Structured logging per phase.
    AC9: ScrapingRun status tracking.

    Parameters
    ----------
    trigger:
        Either "scheduler" or "manual" -- logged for observability.

    Returns
    -------
    Dict with run summary or skip message.
    """
    run_id = _create_scraping_run()

    # AC3: Acquire lock
    if not acquire_pipeline_lock(run_id):
        logger.warning(
            "Pipeline already running, skipping scheduled trigger",
            extra={
                "run_id": str(run_id),
                "trigger": trigger,
            },
        )
        # Mark the run as skipped
        _update_run_status(run_id, "failed", 0.0)
        return {"status": "skipped", "reason": "pipeline_already_running"}

    start_time = time.time()
    has_errors = False
    total_posts_scraped = 0
    total_comments_scraped = 0

    logger.info(
        "pipeline_start",
        extra={
            "event": "pipeline_start",
            "run_id": str(run_id),
            "trigger": trigger,
        },
    )

    try:
        # ---- PHASE 1: Scrape posts ----
        phase_start = time.time()
        candidates = _get_active_candidates()
        all_posts: list[Post] = []

        for candidate in candidates:
            username = candidate["username"]
            try:
                posts = scrape_posts(username, run_id)
                all_posts.extend(posts)
                total_posts_scraped += len(posts)
            except Exception as exc:
                has_errors = True
                logger.error(
                    "pipeline_error",
                    extra={
                        "event": "pipeline_error",
                        "run_id": str(run_id),
                        "phase": "post_scraping",
                        "error": str(exc),
                        "candidate": username,
                    },
                )

        logger.info(
            "phase_complete",
            extra={
                "event": "phase_complete",
                "phase": "post_scraping",
                "count": total_posts_scraped,
                "duration_ms": int((time.time() - phase_start) * 1000),
            },
        )

        # ---- PHASE 2: Scrape comments ----
        phase_start = time.time()
        if all_posts:
            total_comments_scraped = scrape_all_comments(all_posts, run_id)

        logger.info(
            "phase_complete",
            extra={
                "event": "phase_complete",
                "phase": "comment_scraping",
                "count": total_comments_scraped,
                "duration_ms": int((time.time() - phase_start) * 1000),
            },
        )

        # ---- PHASE 3: VADER sentiment analysis ----
        phase_start = time.time()
        unanalyzed = _get_unanalyzed_comments()
        vader_results = analyze_comments_batch(unanalyzed)
        vader_count = len(vader_results)

        logger.info(
            "phase_complete",
            extra={
                "event": "phase_complete",
                "phase": "vader",
                "count": vader_count,
                "duration_ms": int((time.time() - phase_start) * 1000),
            },
        )

        # ---- PHASE 4: LLM fallback ----
        phase_start = time.time()
        try:
            llm_result = asyncio.run(reclassify_ambiguous_comments())
            llm_count = llm_result.get("reclassified_count", 0)
        except RuntimeError:
            # If already in an async event loop (e.g., called from test),
            # create a new loop in a thread-safe way
            loop = asyncio.new_event_loop()
            try:
                llm_result = loop.run_until_complete(
                    reclassify_ambiguous_comments()
                )
                llm_count = llm_result.get("reclassified_count", 0)
            finally:
                loop.close()

        logger.info(
            "phase_complete",
            extra={
                "event": "phase_complete",
                "phase": "llm",
                "count": llm_count,
                "duration_ms": int((time.time() - phase_start) * 1000),
            },
        )

        # ---- PHASE 5: Theme classification ----
        phase_start = time.time()
        themes_count = classify_all_unthemed_comments()

        logger.info(
            "phase_complete",
            extra={
                "event": "phase_complete",
                "phase": "themes",
                "count": themes_count,
                "duration_ms": int((time.time() - phase_start) * 1000),
            },
        )

        # ---- Complete ----
        duration = time.time() - start_time
        status = "partial" if has_errors else "success"
        _update_run_status(run_id, status, duration)

        logger.info(
            "pipeline_complete",
            extra={
                "event": "pipeline_complete",
                "run_id": str(run_id),
                "posts_scraped": total_posts_scraped,
                "comments_scraped": total_comments_scraped,
                "duration_seconds": round(duration, 2),
                "status": status,
            },
        )

        return {
            "run_id": str(run_id),
            "status": status,
            "posts_scraped": total_posts_scraped,
            "comments_scraped": total_comments_scraped,
            "vader_analyzed": vader_count,
            "llm_reclassified": llm_count,
            "themes_classified": themes_count,
            "duration_seconds": round(duration, 2),
        }

    except Exception as exc:
        duration = time.time() - start_time
        _update_run_status(run_id, "failed", duration)

        logger.error(
            "pipeline_error",
            extra={
                "event": "pipeline_error",
                "run_id": str(run_id),
                "phase": "unknown",
                "error": str(exc),
            },
        )

        return {
            "run_id": str(run_id),
            "status": "failed",
            "error": str(exc),
            "duration_seconds": round(duration, 2),
        }

    finally:
        # AC3c: Lock is ALWAYS released
        release_pipeline_lock()
