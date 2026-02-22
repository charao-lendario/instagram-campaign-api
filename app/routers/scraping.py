"""Scraping trigger endpoints.

Story 1.2: POST /posts -- triggers post scraping for all active candidates.
Story 1.3: POST /comments -- triggers comment scraping for eligible posts.
Story 1.7: POST /run -- triggers the full pipeline (409 if already running).

Both endpoints return ``202 Accepted`` immediately.  For the MVP the
scraping runs synchronously before the response is sent (acceptable given
Railway has no strict request-timeout limit).
"""

from __future__ import annotations

import logging
import threading
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.db.supabase import get_supabase
from app.models.post import Post
from app.scheduler.lock import get_current_run_id, is_pipeline_running
from app.services.pipeline import run_full_pipeline
from app.services.scraping import (
    scrape_all_comments,
    scrape_posts,
    _create_scraping_run,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_active_candidates() -> list[dict[str, Any]]:
    """Return all candidates with ``is_active = True``."""
    client = get_supabase()
    result = (
        client.table("candidates")
        .select("id, username")
        .eq("is_active", True)
        .execute()
    )
    return result.data or []


def _get_eligible_posts() -> list[Post]:
    """Return all posts in the database (MVP: scrape comments for all).

    For a production system this would filter by staleness threshold, but
    for MVP we simply return all posts from active candidates.
    """
    client = get_supabase()
    result = (
        client.table("posts")
        .select("*")
        .execute()
    )
    posts: list[Post] = []
    for row in result.data or []:
        posts.append(Post(**row))
    return posts


# ---------------------------------------------------------------------------
# Story 1.2: POST /posts
# ---------------------------------------------------------------------------

@router.post("/posts", status_code=202)
async def trigger_post_scraping() -> dict[str, Any]:
    """Trigger post scraping for all active candidates.

    Creates a ``ScrapingRun``, invokes ``scrape_posts`` for each active
    candidate, and returns 202 with the run summary.
    """
    run_id = _create_scraping_run()
    candidates = _get_active_candidates()

    if not candidates:
        raise HTTPException(status_code=404, detail="No active candidates found")

    usernames: list[str] = []
    for candidate in candidates:
        username = candidate["username"]
        usernames.append(username)
        try:
            scrape_posts(username, run_id)
        except Exception as exc:
            # Error already logged and recorded in scraping_runs.errors by
            # scrape_posts; we continue to the next candidate.
            logger.error(
                "trigger_post_scraping_candidate_failed",
                extra={
                    "username": username,
                    "run_id": str(run_id),
                    "error_message": str(exc),
                },
            )

    return {
        "run_id": str(run_id),
        "status": "started",
        "candidates": usernames,
    }


# ---------------------------------------------------------------------------
# Story 1.3: POST /comments
# ---------------------------------------------------------------------------

@router.post("/comments", status_code=202)
async def trigger_comment_scraping() -> dict[str, Any]:
    """Trigger comment scraping for all eligible posts.

    Creates a ``ScrapingRun``, fetches eligible posts, invokes
    ``scrape_all_comments``, and returns 202 with the run summary.
    """
    run_id = _create_scraping_run()
    posts = _get_eligible_posts()

    if not posts:
        raise HTTPException(status_code=404, detail="No posts found for comment scraping")

    total = scrape_all_comments(posts, run_id)

    return {
        "run_id": str(run_id),
        "status": "started",
        "posts_queued": len(posts),
        "comments_scraped": total,
    }


# ---------------------------------------------------------------------------
# Story 1.7: POST /run -- Full pipeline trigger
# ---------------------------------------------------------------------------

@router.post("/run", status_code=202)
async def trigger_full_pipeline() -> dict[str, Any]:
    """Trigger the full pipeline: posts -> comments -> VADER -> LLM -> themes.

    AC4: Returns 202 if pipeline starts, 409 if already running.
    Pipeline runs in a background thread to not block the response.

    FR-014: Manual Scraping Trigger.
    """
    if is_pipeline_running():
        current_run = get_current_run_id()
        raise HTTPException(
            status_code=409,
            detail="Pipeline already in progress",
            headers={"X-Current-Run-Id": str(current_run) if current_run else "unknown"},
        )

    run_id = uuid4()

    def _run_pipeline() -> None:
        run_full_pipeline(trigger="manual")

    thread = threading.Thread(target=_run_pipeline, daemon=True)
    thread.start()

    return {
        "run_id": str(run_id),
        "status": "started",
        "message": "Full pipeline initiated",
    }
