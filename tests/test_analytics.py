"""Unit tests for analytics service and endpoints.

Story 1.6 AC1-AC10: Tests for all analytics endpoints and the
underlying service functions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CANDIDATE_1_ID = str(uuid4())
CANDIDATE_2_ID = str(uuid4())
POST_ID = str(uuid4())


def _chainable_table_mock() -> MagicMock:
    """Return a mock that supports fluent chaining."""
    m = MagicMock()
    for method in (
        "select", "insert", "upsert", "update", "eq", "limit",
        "in_", "gt", "lt", "is_", "order",
    ):
        getattr(m, method).return_value = m
    m.count = None
    return m


def _mock_supabase_for_analytics() -> MagicMock:
    """Create a Supabase mock with rpc and table support."""
    mock_sb = MagicMock()

    # Default table mock
    default_table = _chainable_table_mock()
    default_table.execute.return_value = MagicMock(data=[], count=None)
    mock_sb.table.return_value = default_table

    return mock_sb


# ---------------------------------------------------------------------------
# AC1: GET /analytics/overview -- Endpoint Tests
# ---------------------------------------------------------------------------


class TestOverviewEndpoint:
    """AC1: Overview returns correct structure."""

    @patch("app.services.analytics.get_supabase")
    def test_overview_returns_200_with_candidates(
        self, mock_get_supabase: MagicMock
    ) -> None:
        """AC1: Returns 200 with candidates array and metadata."""
        mock_sb = _mock_supabase_for_analytics()

        # Candidates query
        cand_table = _chainable_table_mock()
        cand_table.execute.return_value = MagicMock(
            data=[
                {"id": CANDIDATE_1_ID, "username": "charlles.evangelista", "display_name": "Charlles"},
                {"id": CANDIDATE_2_ID, "username": "delegadasheila", "display_name": "Sheila"},
            ]
        )

        def table_dispatch(name: str) -> MagicMock:
            if name == "candidates":
                return cand_table
            return _chainable_table_mock()

        mock_sb.table.side_effect = table_dispatch

        # RPC mocks
        overview_data_1 = MagicMock(data=[{
            "candidate_id": CANDIDATE_1_ID,
            "username": "charlles.evangelista",
            "display_name": "Charlles",
            "total_posts": 10,
            "total_comments": 487,
            "total_engagement": 3542,
            "avg_sentiment": 0.15,
            "positive_count": 210,
            "negative_count": 127,
            "neutral_count": 150,
        }])
        overview_data_2 = MagicMock(data=[{
            "candidate_id": CANDIDATE_2_ID,
            "username": "delegadasheila",
            "display_name": "Sheila",
            "total_posts": 10,
            "total_comments": 523,
            "total_engagement": 4120,
            "avg_sentiment": -0.03,
            "positive_count": 180,
            "negative_count": 198,
            "neutral_count": 145,
        }])
        last_scrape = MagicMock(data=None)

        rpc_calls: list[tuple[str, dict]] = []

        def rpc_side_effect(func_name: str, params: dict) -> MagicMock:
            rpc_calls.append((func_name, params))
            result = MagicMock()
            if func_name == "get_candidate_overview":
                if params.get("p_candidate_id") == CANDIDATE_1_ID:
                    result.execute.return_value = overview_data_1
                else:
                    result.execute.return_value = overview_data_2
            elif func_name == "get_last_successful_scrape":
                result.execute.return_value = last_scrape
            else:
                result.execute.return_value = MagicMock(data=[])
            return result

        mock_sb.rpc.side_effect = rpc_side_effect
        mock_get_supabase.return_value = mock_sb

        from app.services.analytics import get_overview

        result = get_overview()

        assert len(result.candidates) == 2
        assert result.candidates[0].username == "charlles.evangelista"
        assert result.candidates[0].total_posts == 10
        assert result.candidates[0].total_comments == 487
        assert result.candidates[0].sentiment_distribution.positive == 210
        assert result.total_comments_analyzed == 487 + 523

    @patch("app.routers.analytics.get_overview")
    def test_overview_endpoint_returns_200(
        self, mock_get_overview: MagicMock
    ) -> None:
        """AC1: HTTP endpoint returns 200."""
        from app.models.analytics import OverviewResponse
        from app.main import app

        mock_get_overview.return_value = OverviewResponse(
            candidates=[], last_scrape=None, total_comments_analyzed=0
        )

        with TestClient(app) as client:
            response = client.get("/api/v1/analytics/overview")

        assert response.status_code == 200
        body = response.json()
        assert "candidates" in body
        assert "total_comments_analyzed" in body


# ---------------------------------------------------------------------------
# AC2: Sentiment Timeline Endpoint
# ---------------------------------------------------------------------------


class TestSentimentTimelineEndpoint:
    """AC2: Sentiment timeline returns correct structure."""

    @patch("app.routers.analytics.get_sentiment_timeline")
    def test_timeline_returns_200(
        self, mock_get_timeline: MagicMock
    ) -> None:
        """AC2: Returns 200 with data_points array."""
        from app.models.analytics import SentimentTimelineResponse
        from app.main import app

        mock_get_timeline.return_value = SentimentTimelineResponse(data_points=[])

        with TestClient(app) as client:
            response = client.get("/api/v1/analytics/sentiment-timeline")

        assert response.status_code == 200
        body = response.json()
        assert "data_points" in body


# ---------------------------------------------------------------------------
# AC3: Wordcloud Endpoint
# ---------------------------------------------------------------------------


class TestWordcloudEndpoint:
    """AC3: Wordcloud returns correct structure."""

    @patch("app.routers.analytics.get_wordcloud")
    def test_wordcloud_returns_200(
        self, mock_get_wordcloud: MagicMock
    ) -> None:
        """AC3: Returns 200 with words array."""
        from app.models.analytics import WordCloudResponse, WordEntry
        from app.main import app

        mock_get_wordcloud.return_value = WordCloudResponse(
            words=[WordEntry(word="saude", count=87)],
            total_unique_words=1,
        )

        with TestClient(app) as client:
            response = client.get("/api/v1/analytics/wordcloud")

        assert response.status_code == 200
        body = response.json()
        assert "words" in body
        assert len(body["words"]) == 1
        assert body["words"][0]["word"] == "saude"

    def test_word_frequency_filtering(self) -> None:
        """AC3: Stop words and short words are filtered out."""
        from app.services.analytics import _get_word_frequencies

        texts = [
            "a saude do Brasil precisa melhorar muito na escola",
            "saude e educacao sao prioridade para todos",
        ]

        result = _get_word_frequencies(texts, top_n=10)

        words = {w.word for w in result}
        # Stop words like 'a', 'do', 'de', 'na', 'e', 'sao' should NOT be present
        assert "a" not in words
        assert "do" not in words
        assert "de" not in words
        # Meaningful words SHOULD be present
        assert "saude" in words


# ---------------------------------------------------------------------------
# AC4: Themes Endpoint
# ---------------------------------------------------------------------------


class TestThemesEndpoint:
    """AC4: Theme distribution returns correct structure."""

    @patch("app.routers.analytics.get_theme_distribution")
    def test_themes_returns_200(
        self, mock_get_themes: MagicMock
    ) -> None:
        """AC4: Returns 200 with themes array."""
        from app.models.analytics import ThemeDistributionResponse
        from app.main import app

        mock_get_themes.return_value = ThemeDistributionResponse(themes=[])

        with TestClient(app) as client:
            response = client.get("/api/v1/analytics/themes")

        assert response.status_code == 200
        body = response.json()
        assert "themes" in body


# ---------------------------------------------------------------------------
# AC5: Posts Endpoint
# ---------------------------------------------------------------------------


class TestPostsEndpoint:
    """AC5: Post rankings returns correct structure."""

    @patch("app.routers.analytics.get_post_rankings")
    def test_posts_returns_200(
        self, mock_get_posts: MagicMock
    ) -> None:
        """AC5: Returns 200 with posts, total, limit, offset."""
        from app.models.analytics import PostRankingResponse
        from app.main import app

        mock_get_posts.return_value = PostRankingResponse(
            posts=[], total=0, limit=20, offset=0
        )

        with TestClient(app) as client:
            response = client.get("/api/v1/analytics/posts")

        assert response.status_code == 200
        body = response.json()
        assert "posts" in body
        assert "total" in body
        assert "limit" in body
        assert "offset" in body

    @patch("app.routers.analytics.get_post_rankings")
    def test_posts_with_sort_params(
        self, mock_get_posts: MagicMock
    ) -> None:
        """AC5: sort_by and order params are validated."""
        from app.models.analytics import PostRankingResponse
        from app.main import app

        mock_get_posts.return_value = PostRankingResponse(
            posts=[], total=0, limit=10, offset=5
        )

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/analytics/posts?sort_by=like_count&order=asc&limit=10&offset=5"
            )

        assert response.status_code == 200

    def test_posts_invalid_sort_by_returns_422(self) -> None:
        """AC5: Invalid sort_by returns 422."""
        from app.main import app

        with TestClient(app) as client:
            response = client.get(
                "/api/v1/analytics/posts?sort_by=invalid_field"
            )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# AC6: Comparison Endpoint
# ---------------------------------------------------------------------------


class TestComparisonEndpoint:
    """AC6: Comparison returns correct structure."""

    @patch("app.routers.analytics.get_comparison")
    def test_comparison_returns_200(
        self, mock_get_comparison: MagicMock
    ) -> None:
        """AC6: Returns 200 with candidates array."""
        from app.models.analytics import ComparisonResponse
        from app.main import app

        mock_get_comparison.return_value = ComparisonResponse(candidates=[])

        with TestClient(app) as client:
            response = client.get("/api/v1/analytics/comparison")

        assert response.status_code == 200
        body = response.json()
        assert "candidates" in body


# ---------------------------------------------------------------------------
# AC10: Zero-data edge cases
# ---------------------------------------------------------------------------


class TestAnalyticsNoData:
    """AC10: Endpoints with empty data return zeros, not 404."""

    @patch("app.services.analytics.get_supabase")
    def test_overview_empty_data_returns_zeros(
        self, mock_get_supabase: MagicMock
    ) -> None:
        """AC10: Candidate with no posts returns zeros, not error."""
        mock_sb = _mock_supabase_for_analytics()

        cand_table = _chainable_table_mock()
        cand_table.execute.return_value = MagicMock(
            data=[{"id": CANDIDATE_1_ID, "username": "charlles.evangelista", "display_name": None}]
        )
        mock_sb.table.side_effect = lambda name: (
            cand_table if name == "candidates" else _chainable_table_mock()
        )

        # RPC returns empty rows (no data)
        def rpc_side_effect(func_name: str, params: dict) -> MagicMock:
            result = MagicMock()
            result.execute.return_value = MagicMock(data=[])
            return result

        mock_sb.rpc.side_effect = rpc_side_effect
        mock_get_supabase.return_value = mock_sb

        from app.services.analytics import get_overview

        result = get_overview()

        assert len(result.candidates) == 1
        assert result.candidates[0].total_posts == 0
        assert result.candidates[0].total_comments == 0
