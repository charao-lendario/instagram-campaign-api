"""Unit tests for Instagram scraping service and endpoints.

Story 1.2: Post scraping tests (AC1-AC7)
Story 1.3: Comment scraping tests (AC1-AC7)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CANDIDATE_ID = uuid4()
RUN_ID = uuid4()
POST_ID = uuid4()


def _make_apify_post(idx: int = 1) -> dict[str, Any]:
    """Return a realistic Apify post-scraper item."""
    return {
        "id": f"apify-post-{idx}",
        "url": f"https://www.instagram.com/p/shortcode{idx}/",
        "postUrl": f"https://www.instagram.com/p/shortcode{idx}/",
        "shortCode": f"shortcode{idx}",
        "caption": f"Post caption number {idx}",
        "likesCount": 100 + idx,
        "commentsCount": 20 + idx,
        "type": "Image",
        "isSponsored": False,
        "videoViewCount": None,
        "timestamp": "2026-02-20T12:00:00Z",
        "ownerUsername": "charlles.evangelista",
    }


def _make_apify_comment(idx: int = 1) -> dict[str, Any]:
    """Return a realistic Apify comment-scraper item."""
    return {
        "id": f"apify-comment-{idx}",
        "text": f"Great post! Comment {idx}",
        "ownerUsername": f"user{idx}",
        "timestamp": "2026-02-20T13:00:00Z",
        "likesCount": idx,
        "replies": [],
    }


def _mock_supabase_chain(mock_client: MagicMock) -> MagicMock:
    """Setup a chained mock for supabase.table(...).method(...).execute().

    Returns the mock_client for further assertions.
    """
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    # Allow chaining of any method
    for method_name in ("select", "insert", "upsert", "update", "eq", "limit"):
        getattr(mock_table, method_name).return_value = mock_table

    mock_table.execute.return_value = MagicMock(data=[])
    return mock_client


# ---------------------------------------------------------------------------
# Story 1.2 -- Post Scraping Tests
# ---------------------------------------------------------------------------

class TestMapApifyPost:
    """AC2: Field mapping from Apify response to PostUpsert."""

    def test_maps_all_fields_correctly(self) -> None:
        """Given an Apify item, all fields are correctly mapped."""
        from app.services.scraping import _map_apify_post
        from app.models.enums import MediaType

        item = _make_apify_post(1)
        result = _map_apify_post(item, CANDIDATE_ID, RUN_ID)

        assert result.instagram_id == "apify-post-1"
        assert result.url == "https://www.instagram.com/p/shortcode1/"
        assert result.shortcode == "shortcode1"
        assert result.caption == "Post caption number 1"
        assert result.like_count == 101
        assert result.comment_count == 21
        assert result.media_type == MediaType.image
        assert result.is_sponsored is False
        assert result.video_view_count is None
        assert result.posted_at is not None
        assert result.raw_data == item
        assert result.candidate_id == CANDIDATE_ID
        assert result.scraping_run_id == RUN_ID

    def test_maps_media_type_video(self) -> None:
        """Given type='Video', media_type is set to video."""
        from app.services.scraping import _map_apify_post
        from app.models.enums import MediaType

        item = _make_apify_post(1)
        item["type"] = "Video"
        item["videoViewCount"] = 5000
        result = _map_apify_post(item, CANDIDATE_ID, RUN_ID)

        assert result.media_type == MediaType.video
        assert result.video_view_count == 5000

    def test_maps_media_type_carousel(self) -> None:
        """Given type='Sidecar', media_type is set to carousel."""
        from app.services.scraping import _map_apify_post
        from app.models.enums import MediaType

        item = _make_apify_post(1)
        item["type"] = "Sidecar"
        result = _map_apify_post(item, CANDIDATE_ID, RUN_ID)

        assert result.media_type == MediaType.carousel

    def test_maps_unknown_media_type(self) -> None:
        """Given an unknown type string, media_type falls back to unknown."""
        from app.services.scraping import _map_apify_post
        from app.models.enums import MediaType

        item = _make_apify_post(1)
        item["type"] = "IGTV"
        result = _map_apify_post(item, CANDIDATE_ID, RUN_ID)

        assert result.media_type == MediaType.unknown

    def test_handles_missing_optional_fields(self) -> None:
        """Given minimal Apify response, optional fields default correctly."""
        from app.services.scraping import _map_apify_post

        item = {"id": "minimal-post", "url": "https://instagram.com/p/x/"}
        result = _map_apify_post(item, CANDIDATE_ID, RUN_ID)

        assert result.instagram_id == "minimal-post"
        assert result.caption is None
        assert result.like_count == 0
        assert result.comment_count == 0
        assert result.is_sponsored is False

    def test_maps_unix_timestamp(self) -> None:
        """Given a unix timestamp, posted_at is correctly converted."""
        from app.services.scraping import _map_apify_post

        item = _make_apify_post(1)
        item["timestamp"] = 1740000000  # unix timestamp
        result = _map_apify_post(item, CANDIDATE_ID, RUN_ID)

        assert result.posted_at is not None
        assert isinstance(result.posted_at, datetime)


def _make_table_dispatch(**table_mocks: MagicMock) -> MagicMock:
    """Return a Supabase mock whose ``.table(name)`` dispatches to per-table mocks.

    Example::

        sb = _make_table_dispatch(
            candidates=mock_candidates_table,
            posts=mock_posts_table,
            scraping_runs=mock_runs_table,
        )

    Any table not listed returns a generic ``MagicMock``.
    """
    sb = MagicMock()

    def _table_side_effect(name: str) -> MagicMock:
        return table_mocks.get(name, MagicMock())

    sb.table.side_effect = _table_side_effect
    return sb


def _chainable_table_mock() -> MagicMock:
    """Return a mock that supports fluent chaining (select/eq/limit/update/upsert/execute)."""
    m = MagicMock()
    for method in ("select", "insert", "upsert", "update", "eq", "limit"):
        getattr(m, method).return_value = m
    return m


class TestScrapePostsService:
    """AC1, AC3, AC4, AC5: scrape_posts() integration tests (mocked Apify)."""

    @patch("app.services.scraping._get_apify_client")
    @patch("app.services.scraping.get_supabase")
    def test_scrape_posts_success(
        self, mock_get_supabase: MagicMock, mock_get_apify: MagicMock
    ) -> None:
        """AC1: Successful scraping returns mapped posts."""
        from app.services.scraping import scrape_posts

        # Per-table mocks
        mock_candidates = _chainable_table_mock()
        mock_candidates.execute.return_value = MagicMock(
            data=[{"id": str(CANDIDATE_ID)}]
        )

        mock_posts = _chainable_table_mock()
        post_data = {
            "id": str(uuid4()),
            "candidate_id": str(CANDIDATE_ID),
            "scraping_run_id": str(RUN_ID),
            "instagram_id": "apify-post-1",
            "url": "https://www.instagram.com/p/shortcode1/",
            "shortcode": "shortcode1",
            "caption": "Post caption",
            "like_count": 101,
            "comment_count": 21,
            "media_type": "image",
            "is_sponsored": False,
            "video_view_count": None,
            "posted_at": "2026-02-20T12:00:00+00:00",
            "scraped_at": "2026-02-21T10:00:00+00:00",
            "raw_data": {},
            "created_at": "2026-02-21T10:00:00+00:00",
            "updated_at": "2026-02-21T10:00:00+00:00",
        }
        mock_posts.execute.return_value = MagicMock(data=[post_data])

        mock_runs = _chainable_table_mock()
        mock_runs.execute.return_value = MagicMock(
            data=[{"posts_scraped": 0}]
        )

        mock_sb = _make_table_dispatch(
            candidates=mock_candidates,
            posts=mock_posts,
            scraping_runs=mock_runs,
        )
        mock_get_supabase.return_value = mock_sb

        # Apify mock
        mock_apify_client = MagicMock()
        mock_get_apify.return_value = mock_apify_client
        mock_actor = MagicMock()
        mock_apify_client.actor.return_value = mock_actor
        mock_actor.call.return_value = {"defaultDatasetId": "ds-123"}
        mock_dataset = MagicMock()
        mock_apify_client.dataset.return_value = mock_dataset
        mock_dataset.iterate_items.return_value = [_make_apify_post(1)]

        result = scrape_posts("charlles.evangelista", RUN_ID)

        assert len(result) == 1
        assert result[0].instagram_id == "apify-post-1"

        # Verify actor was called with correct input
        mock_actor.call.assert_called_once_with(
            run_input={
                "usernames": ["charlles.evangelista"],
                "resultsLimit": 10,
            }
        )

    @patch("app.services.scraping._get_apify_client")
    @patch("app.services.scraping.get_supabase")
    def test_scrape_posts_upsert_deduplication(
        self, mock_get_supabase: MagicMock, mock_get_apify: MagicMock
    ) -> None:
        """AC3: Second scraping updates existing posts (upsert on instagram_id)."""
        from app.services.scraping import scrape_posts

        mock_candidates = _chainable_table_mock()
        mock_candidates.execute.return_value = MagicMock(
            data=[{"id": str(CANDIDATE_ID)}]
        )

        mock_posts = _chainable_table_mock()
        post_data = {
            "id": str(uuid4()),
            "candidate_id": str(CANDIDATE_ID),
            "scraping_run_id": str(RUN_ID),
            "instagram_id": "apify-post-1",
            "url": "https://www.instagram.com/p/shortcode1/",
            "shortcode": "shortcode1",
            "caption": "Post caption",
            "like_count": 200,
            "comment_count": 50,
            "media_type": "image",
            "is_sponsored": False,
            "video_view_count": None,
            "posted_at": "2026-02-20T12:00:00+00:00",
            "scraped_at": "2026-02-21T12:00:00+00:00",
            "raw_data": {},
            "created_at": "2026-02-21T10:00:00+00:00",
            "updated_at": "2026-02-21T12:00:00+00:00",
        }
        mock_posts.execute.return_value = MagicMock(data=[post_data])

        mock_runs = _chainable_table_mock()
        mock_runs.execute.return_value = MagicMock(
            data=[{"posts_scraped": 0}]
        )

        mock_sb = _make_table_dispatch(
            candidates=mock_candidates,
            posts=mock_posts,
            scraping_runs=mock_runs,
        )
        mock_get_supabase.return_value = mock_sb

        # Apify mock
        mock_apify_client = MagicMock()
        mock_get_apify.return_value = mock_apify_client
        mock_actor = MagicMock()
        mock_apify_client.actor.return_value = mock_actor
        mock_actor.call.return_value = {"defaultDatasetId": "ds-123"}
        mock_dataset = MagicMock()
        mock_apify_client.dataset.return_value = mock_dataset
        mock_dataset.iterate_items.return_value = [_make_apify_post(1)]

        result = scrape_posts("charlles.evangelista", RUN_ID)

        # Verify upsert was called with on_conflict
        mock_posts.upsert.assert_called_once()
        call_kwargs = mock_posts.upsert.call_args
        assert call_kwargs.kwargs.get("on_conflict") == "instagram_id"

    @patch("app.services.scraping._get_apify_client")
    @patch("app.services.scraping.get_supabase")
    def test_scrape_posts_apify_failure(
        self, mock_get_supabase: MagicMock, mock_get_apify: MagicMock
    ) -> None:
        """AC5: Apify failure logs error and raises RuntimeError."""
        from app.services.scraping import scrape_posts

        mock_candidates = _chainable_table_mock()
        mock_candidates.execute.return_value = MagicMock(
            data=[{"id": str(CANDIDATE_ID)}]
        )

        mock_runs = _chainable_table_mock()
        mock_runs.execute.return_value = MagicMock(
            data=[{"errors": None}]
        )

        mock_sb = _make_table_dispatch(
            candidates=mock_candidates,
            scraping_runs=mock_runs,
        )
        mock_get_supabase.return_value = mock_sb

        # Apify mock that raises
        mock_apify_client = MagicMock()
        mock_get_apify.return_value = mock_apify_client
        mock_actor = MagicMock()
        mock_apify_client.actor.return_value = mock_actor
        mock_actor.call.side_effect = RuntimeError("Apify actor timeout after 60s")

        with pytest.raises(RuntimeError, match="Apify actor failed"):
            scrape_posts("charlles.evangelista", RUN_ID)

    @patch("app.services.scraping._get_apify_client")
    @patch("app.services.scraping.get_supabase")
    def test_scrape_posts_10_items(
        self, mock_get_supabase: MagicMock, mock_get_apify: MagicMock
    ) -> None:
        """AC1: Scraping returns up to 10 posts mapped correctly."""
        from app.services.scraping import scrape_posts

        mock_candidates = _chainable_table_mock()
        mock_candidates.execute.return_value = MagicMock(
            data=[{"id": str(CANDIDATE_ID)}]
        )

        mock_posts = _chainable_table_mock()
        upserted_posts = []
        for i in range(10):
            upserted_posts.append({
                "id": str(uuid4()),
                "candidate_id": str(CANDIDATE_ID),
                "scraping_run_id": str(RUN_ID),
                "instagram_id": f"apify-post-{i}",
                "url": f"https://www.instagram.com/p/sc{i}/",
                "shortcode": f"sc{i}",
                "caption": f"Caption {i}",
                "like_count": 100 + i,
                "comment_count": 20 + i,
                "media_type": "image",
                "is_sponsored": False,
                "video_view_count": None,
                "posted_at": "2026-02-20T12:00:00+00:00",
                "scraped_at": "2026-02-21T10:00:00+00:00",
                "raw_data": {},
                "created_at": "2026-02-21T10:00:00+00:00",
                "updated_at": "2026-02-21T10:00:00+00:00",
            })
        mock_posts.execute.side_effect = [
            MagicMock(data=[p]) for p in upserted_posts
        ]

        mock_runs = _chainable_table_mock()
        mock_runs.execute.return_value = MagicMock(
            data=[{"posts_scraped": 0}]
        )

        mock_sb = _make_table_dispatch(
            candidates=mock_candidates,
            posts=mock_posts,
            scraping_runs=mock_runs,
        )
        mock_get_supabase.return_value = mock_sb

        # Apify returns 10 items
        mock_apify_client = MagicMock()
        mock_get_apify.return_value = mock_apify_client
        mock_actor = MagicMock()
        mock_apify_client.actor.return_value = mock_actor
        mock_actor.call.return_value = {"defaultDatasetId": "ds-123"}
        mock_dataset = MagicMock()
        mock_apify_client.dataset.return_value = mock_dataset
        mock_dataset.iterate_items.return_value = [
            _make_apify_post(i) for i in range(10)
        ]

        result = scrape_posts("charlles.evangelista", RUN_ID)

        assert len(result) == 10


# ---------------------------------------------------------------------------
# Story 1.2 -- Endpoint Tests
# ---------------------------------------------------------------------------

class TestPostScrapingEndpoint:
    """AC6: POST /api/v1/scraping/posts endpoint."""

    @patch("app.routers.scraping.scrape_posts")
    @patch("app.routers.scraping._get_active_candidates")
    @patch("app.routers.scraping._create_scraping_run")
    def test_trigger_returns_202(
        self,
        mock_create_run: MagicMock,
        mock_get_candidates: MagicMock,
        mock_scrape: MagicMock,
    ) -> None:
        """Given active candidates, POST /scraping/posts returns 202."""
        from app.main import app

        mock_create_run.return_value = RUN_ID
        mock_get_candidates.return_value = [
            {"id": str(uuid4()), "username": "charlles.evangelista"},
            {"id": str(uuid4()), "username": "delegadasheila"},
        ]
        mock_scrape.return_value = []

        with TestClient(app) as client:
            response = client.post("/api/v1/scraping/posts")

        assert response.status_code == 202
        body = response.json()
        assert body["run_id"] == str(RUN_ID)
        assert body["status"] == "started"
        assert "charlles.evangelista" in body["candidates"]
        assert "delegadasheila" in body["candidates"]

    @patch("app.routers.scraping._get_active_candidates")
    @patch("app.routers.scraping._create_scraping_run")
    def test_trigger_no_candidates_404(
        self,
        mock_create_run: MagicMock,
        mock_get_candidates: MagicMock,
    ) -> None:
        """Given no active candidates, POST /scraping/posts returns 404."""
        from app.main import app

        mock_create_run.return_value = RUN_ID
        mock_get_candidates.return_value = []

        with TestClient(app) as client:
            response = client.post("/api/v1/scraping/posts")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Story 1.3 -- Comment Mapping Tests
# ---------------------------------------------------------------------------

class TestMapApifyComment:
    """AC2 (1.3): Field mapping from Apify comment response to CommentUpsert."""

    def test_maps_all_fields_correctly(self) -> None:
        """Given an Apify comment item, all fields are correctly mapped."""
        from app.services.scraping import _map_apify_comment

        item = _make_apify_comment(1)
        result = _map_apify_comment(item, POST_ID, RUN_ID)

        assert result.instagram_id == "apify-comment-1"
        assert result.text == "Great post! Comment 1"
        assert result.author_username == "user1"
        assert result.like_count == 1
        assert result.reply_count == 0  # empty list
        assert result.commented_at is not None
        assert result.raw_data == item
        assert result.post_id == POST_ID
        assert result.scraping_run_id == RUN_ID

    def test_reply_count_from_list(self) -> None:
        """Given replies as a list, reply_count is len(replies)."""
        from app.services.scraping import _map_apify_comment

        item = _make_apify_comment(1)
        item["replies"] = [{"id": "r1"}, {"id": "r2"}, {"id": "r3"}]
        result = _map_apify_comment(item, POST_ID, RUN_ID)

        assert result.reply_count == 3

    def test_reply_count_from_int(self) -> None:
        """Given replies as an integer, reply_count uses it directly."""
        from app.services.scraping import _map_apify_comment

        item = _make_apify_comment(1)
        item["replies"] = 5
        result = _map_apify_comment(item, POST_ID, RUN_ID)

        assert result.reply_count == 5

    def test_handles_missing_optional_fields(self) -> None:
        """Given minimal comment data, optional fields default correctly."""
        from app.services.scraping import _map_apify_comment

        item = {"id": "min-comment", "text": "Nice"}
        result = _map_apify_comment(item, POST_ID, RUN_ID)

        assert result.instagram_id == "min-comment"
        assert result.text == "Nice"
        assert result.author_username is None
        assert result.like_count == 0
        assert result.reply_count == 0
        assert result.commented_at is None


# ---------------------------------------------------------------------------
# Story 1.3 -- Comment Scraping Service Tests
# ---------------------------------------------------------------------------

class TestScrapeCommentsService:
    """AC1, AC3, AC5 (1.3): scrape_comments tests (mocked Apify)."""

    @patch("app.services.scraping._get_apify_client")
    @patch("app.services.scraping.get_supabase")
    def test_scrape_comments_success(
        self, mock_get_supabase: MagicMock, mock_get_apify: MagicMock
    ) -> None:
        """AC1: Successful comment scraping returns mapped comments."""
        from app.services.scraping import scrape_comments

        mock_sb = MagicMock()
        mock_get_supabase.return_value = mock_sb
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table

        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.limit.return_value = mock_table

        # 50 comments returned
        comment_items = [_make_apify_comment(i) for i in range(50)]

        # Apify mock
        mock_apify_client = MagicMock()
        mock_get_apify.return_value = mock_apify_client
        mock_actor = MagicMock()
        mock_apify_client.actor.return_value = mock_actor
        mock_actor.call.return_value = {"defaultDatasetId": "ds-456"}
        mock_dataset = MagicMock()
        mock_apify_client.dataset.return_value = mock_dataset
        mock_dataset.iterate_items.return_value = comment_items

        # Upsert returns comment data
        comment_data = []
        for i in range(50):
            comment_data.append({
                "id": str(uuid4()),
                "post_id": str(POST_ID),
                "scraping_run_id": str(RUN_ID),
                "instagram_id": f"apify-comment-{i}",
                "text": f"Great post! Comment {i}",
                "author_username": f"user{i}",
                "like_count": i,
                "reply_count": 0,
                "commented_at": "2026-02-20T13:00:00+00:00",
                "scraped_at": "2026-02-21T10:00:00+00:00",
                "raw_data": {},
                "created_at": "2026-02-21T10:00:00+00:00",
            })

        mock_upsert = MagicMock()
        mock_table.upsert.return_value = mock_upsert
        mock_upsert.execute.side_effect = [
            MagicMock(data=[c]) for c in comment_data
        ]

        result = scrape_comments(
            "https://www.instagram.com/p/abc123/",
            POST_ID,
            RUN_ID,
        )

        assert len(result) == 50

        # Verify actor was called with correct input
        mock_actor.call.assert_called_once_with(
            run_input={
                "directUrls": ["https://www.instagram.com/p/abc123/"],
                "resultsLimit": 500,
            }
        )

    @patch("app.services.scraping._get_apify_client")
    @patch("app.services.scraping.get_supabase")
    def test_scrape_comments_upsert_deduplication(
        self, mock_get_supabase: MagicMock, mock_get_apify: MagicMock
    ) -> None:
        """AC3: Second scraping updates existing comments (upsert)."""
        from app.services.scraping import scrape_comments

        mock_sb = MagicMock()
        mock_get_supabase.return_value = mock_sb
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.limit.return_value = mock_table

        mock_apify_client = MagicMock()
        mock_get_apify.return_value = mock_apify_client
        mock_actor = MagicMock()
        mock_apify_client.actor.return_value = mock_actor
        mock_actor.call.return_value = {"defaultDatasetId": "ds-456"}
        mock_dataset = MagicMock()
        mock_apify_client.dataset.return_value = mock_dataset
        mock_dataset.iterate_items.return_value = [_make_apify_comment(1)]

        comment_data = {
            "id": str(uuid4()),
            "post_id": str(POST_ID),
            "scraping_run_id": str(RUN_ID),
            "instagram_id": "apify-comment-1",
            "text": "Great post! Comment 1",
            "author_username": "user1",
            "like_count": 10,  # Updated
            "reply_count": 0,
            "commented_at": "2026-02-20T13:00:00+00:00",
            "scraped_at": "2026-02-21T12:00:00+00:00",
            "raw_data": {},
            "created_at": "2026-02-21T10:00:00+00:00",
        }
        mock_upsert = MagicMock()
        mock_table.upsert.return_value = mock_upsert
        mock_upsert.execute.return_value = MagicMock(data=[comment_data])

        result = scrape_comments(
            "https://www.instagram.com/p/abc123/",
            POST_ID,
            RUN_ID,
        )

        assert len(result) == 1
        # Verify upsert was called with on_conflict
        mock_table.upsert.assert_called_once()
        call_kwargs = mock_table.upsert.call_args
        assert call_kwargs.kwargs.get("on_conflict") == "instagram_id" or \
               (len(call_kwargs.args) > 1 or call_kwargs[1].get("on_conflict") == "instagram_id")

    @patch("app.services.scraping._get_apify_client")
    @patch("app.services.scraping.get_supabase")
    def test_scrape_comments_apify_failure_returns_empty(
        self, mock_get_supabase: MagicMock, mock_get_apify: MagicMock
    ) -> None:
        """AC5: Apify failure returns empty list (partial-failure resilience)."""
        from app.services.scraping import scrape_comments

        mock_sb = MagicMock()
        mock_get_supabase.return_value = mock_sb
        mock_table = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[{"errors": None}])
        mock_table.update.return_value = mock_table

        mock_apify_client = MagicMock()
        mock_get_apify.return_value = mock_apify_client
        mock_actor = MagicMock()
        mock_apify_client.actor.return_value = mock_actor
        mock_actor.call.side_effect = RuntimeError("Apify actor timeout")

        result = scrape_comments(
            "https://www.instagram.com/p/abc123/",
            POST_ID,
            RUN_ID,
        )

        assert result == []


# ---------------------------------------------------------------------------
# Story 1.3 -- scrape_all_comments Tests
# ---------------------------------------------------------------------------

class TestScrapeAllComments:
    """AC4 (1.3): scrape_all_comments partial failure and total count."""

    @patch("app.services.scraping.scrape_comments")
    @patch("app.services.scraping._update_run_comments_scraped")
    def test_scrape_all_comments_success(
        self,
        mock_update_run: MagicMock,
        mock_scrape_comments: MagicMock,
    ) -> None:
        """Given 3 posts, all succeed, total is sum of comments."""
        from app.services.scraping import scrape_all_comments
        from app.models.post import Post

        posts = []
        for i in range(3):
            posts.append(Post(
                id=uuid4(),
                candidate_id=CANDIDATE_ID,
                instagram_id=f"post-{i}",
                url=f"https://www.instagram.com/p/code{i}/",
                like_count=100,
                comment_count=20,
                media_type="image",
                is_sponsored=False,
                scraped_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))

        # Each scrape_comments returns a list of 10 mock Comment objects
        mock_comments = [MagicMock() for _ in range(10)]
        mock_scrape_comments.return_value = mock_comments

        total = scrape_all_comments(posts, RUN_ID)

        assert total == 30
        assert mock_scrape_comments.call_count == 3
        mock_update_run.assert_called_once_with(RUN_ID, 30)

    @patch("app.services.scraping.scrape_comments")
    @patch("app.services.scraping._update_run_comments_scraped")
    def test_scrape_all_comments_partial_failure(
        self,
        mock_update_run: MagicMock,
        mock_scrape_comments: MagicMock,
    ) -> None:
        """AC4: 1 of 3 posts fails, the other 2 succeed, total reflects success only."""
        from app.services.scraping import scrape_all_comments
        from app.models.post import Post

        posts = []
        for i in range(3):
            posts.append(Post(
                id=uuid4(),
                candidate_id=CANDIDATE_ID,
                instagram_id=f"post-{i}",
                url=f"https://www.instagram.com/p/code{i}/",
                like_count=100,
                comment_count=20,
                media_type="image",
                is_sponsored=False,
                scraped_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ))

        # First post: 10 comments, second: exception, third: 5 comments
        mock_comments_10 = [MagicMock() for _ in range(10)]
        mock_comments_5 = [MagicMock() for _ in range(5)]
        mock_scrape_comments.side_effect = [
            mock_comments_10,
            Exception("Apify timeout"),
            mock_comments_5,
        ]

        total = scrape_all_comments(posts, RUN_ID)

        assert total == 15  # 10 + 0 + 5
        assert mock_scrape_comments.call_count == 3
        mock_update_run.assert_called_once_with(RUN_ID, 15)


# ---------------------------------------------------------------------------
# Story 1.3 -- Endpoint Tests
# ---------------------------------------------------------------------------

class TestCommentScrapingEndpoint:
    """AC6 (1.3): POST /api/v1/scraping/comments endpoint."""

    @patch("app.routers.scraping.scrape_all_comments")
    @patch("app.routers.scraping._get_eligible_posts")
    @patch("app.routers.scraping._create_scraping_run")
    def test_trigger_returns_202(
        self,
        mock_create_run: MagicMock,
        mock_get_posts: MagicMock,
        mock_scrape_all: MagicMock,
    ) -> None:
        """Given eligible posts, POST /scraping/comments returns 202."""
        from app.main import app
        from app.models.post import Post

        mock_create_run.return_value = RUN_ID
        mock_get_posts.return_value = [
            Post(
                id=uuid4(),
                candidate_id=CANDIDATE_ID,
                instagram_id="p-1",
                url="https://instagram.com/p/abc/",
                like_count=0,
                comment_count=0,
                media_type="image",
                is_sponsored=False,
                scraped_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
        ]
        mock_scrape_all.return_value = 25

        with TestClient(app) as client:
            response = client.post("/api/v1/scraping/comments")

        assert response.status_code == 202
        body = response.json()
        assert body["run_id"] == str(RUN_ID)
        assert body["status"] == "started"
        assert body["posts_queued"] == 1
        assert body["comments_scraped"] == 25

    @patch("app.routers.scraping._get_eligible_posts")
    @patch("app.routers.scraping._create_scraping_run")
    def test_trigger_no_posts_404(
        self,
        mock_create_run: MagicMock,
        mock_get_posts: MagicMock,
    ) -> None:
        """Given no eligible posts, POST /scraping/comments returns 404."""
        from app.main import app

        mock_create_run.return_value = RUN_ID
        mock_get_posts.return_value = []

        with TestClient(app) as client:
            response = client.post("/api/v1/scraping/comments")

        assert response.status_code == 404
