"""Unit tests for sentiment analysis service and endpoints.

Story 1.4: VADER analysis tests (AC1-AC7)
Story 1.5: LLM fallback tests (AC1-AC8)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures / Helpers
# ---------------------------------------------------------------------------

CANDIDATE_ID = uuid4()
COMMENT_ID = uuid4()
POST_ID = uuid4()


def _chainable_table_mock() -> MagicMock:
    """Return a mock that supports fluent chaining."""
    m = MagicMock()
    for method in (
        "select", "insert", "upsert", "update", "eq", "limit",
        "in_", "gt", "lt", "is_",
    ):
        getattr(m, method).return_value = m
    return m


def _make_table_dispatch(**table_mocks: MagicMock) -> MagicMock:
    """Return a Supabase mock whose .table(name) dispatches to per-table mocks."""
    sb = MagicMock()

    def _table_side_effect(name: str) -> MagicMock:
        return table_mocks.get(name, MagicMock())

    sb.table.side_effect = _table_side_effect
    return sb


# ---------------------------------------------------------------------------
# Story 1.4 -- VADER Analysis Tests
# ---------------------------------------------------------------------------


class TestAnalyzeSentimentVader:
    """AC1, AC2: VADER scoring and threshold classification."""

    def test_positive_compound(self) -> None:
        """Given compound >= 0.05, label is positive."""
        from app.services.sentiment import analyze_sentiment_vader

        # "I love this!" typically yields a high positive compound
        result = analyze_sentiment_vader("I love this! Absolutely fantastic!")

        assert result["vader_compound"] >= 0.05
        assert result["vader_label"] == "positive"
        assert 0.0 <= result["vader_positive"] <= 1.0
        assert 0.0 <= result["vader_negative"] <= 1.0
        assert 0.0 <= result["vader_neutral"] <= 1.0

    def test_negative_compound(self) -> None:
        """Given compound <= -0.05, label is negative."""
        from app.services.sentiment import analyze_sentiment_vader

        result = analyze_sentiment_vader("This is terrible and awful and disgusting")

        assert result["vader_compound"] <= -0.05
        assert result["vader_label"] == "negative"

    def test_neutral_compound(self) -> None:
        """Given compound between -0.05 and 0.05, label is neutral."""
        from app.services.sentiment import analyze_sentiment_vader

        # A factual statement typically scores near 0
        result = analyze_sentiment_vader("The meeting is at 3pm")

        assert -0.05 < result["vader_compound"] < 0.05
        assert result["vader_label"] == "neutral"

    def test_boundary_positive_exact(self) -> None:
        """AC2: compound = 0.05 should be positive."""
        from app.services.sentiment import analyze_sentiment_vader
        from app.core.constants import VADER_POSITIVE_THRESHOLD

        # We test the threshold logic directly by checking the function logic
        # Mock _analyzer.polarity_scores to return exact boundary
        with patch("app.services.sentiment._analyzer") as mock_analyzer:
            mock_analyzer.polarity_scores.return_value = {
                "compound": 0.05,
                "pos": 0.1,
                "neg": 0.0,
                "neu": 0.9,
            }
            result = analyze_sentiment_vader("test")

        assert result["vader_compound"] == 0.05
        assert result["vader_label"] == "positive"

    def test_boundary_just_below_positive(self) -> None:
        """AC2: compound = 0.049 should be neutral."""
        from app.services.sentiment import analyze_sentiment_vader

        with patch("app.services.sentiment._analyzer") as mock_analyzer:
            mock_analyzer.polarity_scores.return_value = {
                "compound": 0.049,
                "pos": 0.05,
                "neg": 0.0,
                "neu": 0.95,
            }
            result = analyze_sentiment_vader("test")

        assert result["vader_compound"] == 0.049
        assert result["vader_label"] == "neutral"

    def test_boundary_negative_exact(self) -> None:
        """AC2: compound = -0.05 should be negative."""
        from app.services.sentiment import analyze_sentiment_vader

        with patch("app.services.sentiment._analyzer") as mock_analyzer:
            mock_analyzer.polarity_scores.return_value = {
                "compound": -0.05,
                "pos": 0.0,
                "neg": 0.1,
                "neu": 0.9,
            }
            result = analyze_sentiment_vader("test")

        assert result["vader_compound"] == -0.05
        assert result["vader_label"] == "negative"

    def test_boundary_just_above_negative(self) -> None:
        """AC2: compound = -0.049 should be neutral."""
        from app.services.sentiment import analyze_sentiment_vader

        with patch("app.services.sentiment._analyzer") as mock_analyzer:
            mock_analyzer.polarity_scores.return_value = {
                "compound": -0.049,
                "pos": 0.0,
                "neg": 0.05,
                "neu": 0.95,
            }
            result = analyze_sentiment_vader("test")

        assert result["vader_compound"] == -0.049
        assert result["vader_label"] == "neutral"

    def test_boundary_zero(self) -> None:
        """AC2: compound = 0.0 should be neutral."""
        from app.services.sentiment import analyze_sentiment_vader

        with patch("app.services.sentiment._analyzer") as mock_analyzer:
            mock_analyzer.polarity_scores.return_value = {
                "compound": 0.0,
                "pos": 0.0,
                "neg": 0.0,
                "neu": 1.0,
            }
            result = analyze_sentiment_vader("test")

        assert result["vader_compound"] == 0.0
        assert result["vader_label"] == "neutral"


class TestAnalyzeCommentsBatch:
    """AC3, AC4: Batch processing and deduplication."""

    @patch("app.services.sentiment.get_supabase")
    def test_batch_five_comments_all_new(
        self, mock_get_supabase: MagicMock
    ) -> None:
        """AC3: 5 comments, all without prior records, all get sentiment_scores."""
        from app.services.sentiment import analyze_comments_batch

        mock_table = _chainable_table_mock()
        # Each insert returns a successful result
        insert_results = []
        for i in range(5):
            cid = str(uuid4())
            insert_results.append(
                MagicMock(data=[{
                    "id": str(uuid4()),
                    "comment_id": cid,
                    "vader_compound": 0.1,
                    "final_label": "positive",
                }])
            )
        mock_table.execute.side_effect = insert_results
        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_get_supabase.return_value = mock_sb

        comments = [
            {"id": str(uuid4()), "text": f"Comment text number {i}"}
            for i in range(5)
        ]

        results = analyze_comments_batch(comments)

        assert len(results) == 5
        assert mock_table.insert.call_count == 5

    @patch("app.services.sentiment.get_supabase")
    def test_batch_empty_list(self, mock_get_supabase: MagicMock) -> None:
        """Given empty comment list, returns empty list without DB calls."""
        from app.services.sentiment import analyze_comments_batch

        results = analyze_comments_batch([])

        assert results == []
        mock_get_supabase.assert_not_called()

    @patch("app.services.sentiment.get_supabase")
    def test_batch_insert_failure_continues(
        self, mock_get_supabase: MagicMock
    ) -> None:
        """AC4: If insert fails (e.g., duplicate), skip and continue."""
        from app.services.sentiment import analyze_comments_batch

        mock_table = _chainable_table_mock()
        # First insert succeeds, second raises, third succeeds
        mock_table.execute.side_effect = [
            MagicMock(data=[{"id": str(uuid4()), "comment_id": str(uuid4())}]),
            Exception("UNIQUE constraint violation"),
            MagicMock(data=[{"id": str(uuid4()), "comment_id": str(uuid4())}]),
        ]
        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_get_supabase.return_value = mock_sb

        comments = [
            {"id": str(uuid4()), "text": f"Comment {i}"}
            for i in range(3)
        ]

        results = analyze_comments_batch(comments)

        assert len(results) == 2  # 1st and 3rd succeed


class TestRunVaderAnalysis:
    """AC5: Full orchestration of VADER analysis."""

    @patch("app.services.sentiment.analyze_comments_batch")
    @patch("app.services.sentiment._get_unanalyzed_comments")
    @patch("app.services.sentiment.get_supabase")
    def test_returns_correct_counts(
        self,
        mock_get_supabase: MagicMock,
        mock_get_unanalyzed: MagicMock,
        mock_batch: MagicMock,
    ) -> None:
        """AC5: Returns analyzed_count and skipped_count."""
        # Total comments = 10, unanalyzed = 7, so skipped = 3
        mock_comments_table = _chainable_table_mock()
        mock_comments_table.execute.return_value = MagicMock(
            data=[{"id": str(uuid4()), "text": "t"} for _ in range(10)]
        )
        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_comments_table
        mock_get_supabase.return_value = mock_sb

        mock_get_unanalyzed.return_value = [
            {"id": str(uuid4()), "text": "t"} for _ in range(7)
        ]
        mock_batch.return_value = [{"id": "x"} for _ in range(7)]

        from app.services.sentiment import run_vader_analysis

        result = run_vader_analysis()

        assert result["analyzed_count"] == 7
        assert result["skipped_count"] == 3


class TestGetSentimentSummary:
    """AC6: Sentiment summary aggregation."""

    @patch("app.services.sentiment.get_supabase")
    def test_summary_with_data(self, mock_get_supabase: MagicMock) -> None:
        """AC6: Returns correct counts and avg for a candidate."""
        cid = str(uuid4())
        post_id = str(uuid4())

        mock_candidates = _chainable_table_mock()
        mock_candidates.execute.return_value = MagicMock(
            data=[{"id": cid, "username": "charlles.evangelista"}]
        )

        mock_posts = _chainable_table_mock()
        mock_posts.execute.return_value = MagicMock(
            data=[{"id": post_id}]
        )

        mock_comments = _chainable_table_mock()
        comment_ids = [str(uuid4()) for _ in range(5)]
        mock_comments.execute.return_value = MagicMock(
            data=[{"id": c} for c in comment_ids]
        )

        mock_sentiment = _chainable_table_mock()
        mock_sentiment.execute.return_value = MagicMock(
            data=[
                {"final_label": "positive", "vader_compound": 0.5},
                {"final_label": "positive", "vader_compound": 0.3},
                {"final_label": "negative", "vader_compound": -0.4},
                {"final_label": "neutral", "vader_compound": 0.01},
                {"final_label": "neutral", "vader_compound": -0.02},
            ]
        )

        def table_dispatch(name: str) -> MagicMock:
            return {
                "candidates": mock_candidates,
                "posts": mock_posts,
                "comments": mock_comments,
                "sentiment_scores": mock_sentiment,
            }.get(name, MagicMock())

        mock_sb = MagicMock()
        mock_sb.table.side_effect = table_dispatch
        mock_get_supabase.return_value = mock_sb

        from app.services.sentiment import get_sentiment_summary

        result = get_sentiment_summary(cid)

        assert result["candidate_id"] == cid
        assert result["candidate_username"] == "charlles.evangelista"
        assert result["total_comments"] == 5
        assert result["positive_count"] == 2
        assert result["negative_count"] == 1
        assert result["neutral_count"] == 2
        # avg = (0.5 + 0.3 - 0.4 + 0.01 - 0.02) / 5 = 0.078
        assert abs(result["average_compound_score"] - 0.078) < 0.001

    @patch("app.services.sentiment.get_supabase")
    def test_summary_no_candidate(self, mock_get_supabase: MagicMock) -> None:
        """AC6: Candidate not found returns zeros."""
        mock_candidates = _chainable_table_mock()
        mock_candidates.execute.return_value = MagicMock(data=[])

        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_candidates
        mock_get_supabase.return_value = mock_sb

        from app.services.sentiment import get_sentiment_summary

        result = get_sentiment_summary(str(uuid4()))

        assert result["total_comments"] == 0
        assert result["positive_count"] == 0


# ---------------------------------------------------------------------------
# Story 1.4 -- Endpoint Tests
# ---------------------------------------------------------------------------


class TestSentimentEndpoints:
    """AC5, AC6: Endpoint HTTP tests."""

    @patch("app.routers.analysis.run_vader_analysis")
    def test_post_sentiment_returns_200(
        self, mock_run_vader: MagicMock
    ) -> None:
        """AC5: POST /analysis/sentiment returns 200 with counts."""
        from app.main import app

        mock_run_vader.return_value = {
            "analyzed_count": 342,
            "skipped_count": 58,
        }

        with TestClient(app) as client:
            response = client.post("/api/v1/analysis/sentiment")

        assert response.status_code == 200
        body = response.json()
        assert body["analyzed_count"] == 342
        assert body["skipped_count"] == 58
        assert body["message"] == "Sentiment analysis complete"

    @patch("app.routers.analysis.get_sentiment_summary")
    def test_get_summary_returns_200(
        self, mock_summary: MagicMock
    ) -> None:
        """AC6: GET /analysis/sentiment/summary returns aggregation."""
        from app.main import app

        cid = str(uuid4())
        mock_summary.return_value = {
            "candidate_id": cid,
            "candidate_username": "charlles.evangelista",
            "total_comments": 500,
            "positive_count": 210,
            "negative_count": 140,
            "neutral_count": 150,
            "average_compound_score": 0.12,
        }

        with TestClient(app) as client:
            response = client.get(
                f"/api/v1/analysis/sentiment/summary?candidate_id={cid}"
            )

        assert response.status_code == 200
        body = response.json()
        assert body["candidate_id"] == cid
        assert body["total_comments"] == 500
        assert body["positive_count"] == 210
        assert body["negative_count"] == 140
        assert body["neutral_count"] == 150

    def test_get_summary_missing_candidate_id_422(self) -> None:
        """Missing candidate_id query param returns 422."""
        from app.main import app

        with TestClient(app) as client:
            response = client.get("/api/v1/analysis/sentiment/summary")

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Story 1.5 -- LLM Fallback Tests
# ---------------------------------------------------------------------------


class TestAnalyzeSentimentLLM:
    """AC1, AC2 (1.5): LLM sentiment analysis via httpx."""

    @pytest.mark.asyncio
    async def test_llm_returns_valid_result(self) -> None:
        """AC1: Valid LLM response returns llm_label, llm_confidence, llm_model."""
        from app.services.sentiment import analyze_sentiment_llm

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "label": "negative",
                            "confidence": 0.85,
                        })
                    }
                }
            ]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await analyze_sentiment_llm("Este candidato e terrivel")

        assert result["llm_label"] == "negative"
        assert result["llm_confidence"] == 0.85
        assert result["llm_model"] == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_llm_prompt_structure(self) -> None:
        """AC2: Verify the request body matches the spec."""
        from app.services.sentiment import analyze_sentiment_llm, SENTIMENT_SYSTEM_PROMPT

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "label": "positive",
                            "confidence": 0.9,
                        })
                    }
                }
            ]
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await analyze_sentiment_llm("Bom trabalho do candidato")

            # Verify the request was sent with correct structure
            call_kwargs = mock_client.post.call_args
            request_json = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")

            assert request_json["temperature"] == 0.1
            assert request_json["max_tokens"] == 50
            assert request_json["messages"][0]["role"] == "system"
            assert request_json["messages"][0]["content"] == SENTIMENT_SYSTEM_PROMPT
            assert request_json["messages"][1]["role"] == "user"
            assert "Bom trabalho do candidato" in request_json["messages"][1]["content"]


class TestLLMConfidenceThreshold:
    """AC4 (1.5): Confidence threshold determines final_label."""

    @pytest.mark.asyncio
    @patch("app.services.sentiment.get_supabase")
    @patch("app.services.sentiment._get_ambiguous_comments")
    @patch("app.services.sentiment.analyze_sentiment_llm")
    async def test_high_confidence_upgrades_label(
        self,
        mock_llm: AsyncMock,
        mock_get_ambiguous: MagicMock,
        mock_get_supabase: MagicMock,
    ) -> None:
        """AC4: confidence=0.8 -> final_label = llm_label."""
        from app.services.sentiment import reclassify_ambiguous_comments

        cid = str(uuid4())
        mock_get_ambiguous.return_value = [
            {
                "comment_id": cid,
                "text": "Texto ambiguo que precisa de analise",
                "vader_compound": 0.01,
                "vader_label": "neutral",
            }
        ]

        mock_llm.return_value = {
            "llm_label": "positive",
            "llm_confidence": 0.8,
            "llm_model": "gpt-4o-mini",
        }

        mock_table = _chainable_table_mock()
        mock_table.execute.return_value = MagicMock(data=[])
        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_get_supabase.return_value = mock_sb

        result = await reclassify_ambiguous_comments()

        assert result["confidence_upgrades"] == 1
        assert result["retained_vader_label"] == 0

        # Verify update was called with llm_label as final_label
        update_call = mock_table.update.call_args
        update_data = update_call[0][0]
        assert update_data["final_label"] == "positive"
        assert update_data["llm_label"] == "positive"
        assert update_data["llm_confidence"] == 0.8

    @pytest.mark.asyncio
    @patch("app.services.sentiment.get_supabase")
    @patch("app.services.sentiment._get_ambiguous_comments")
    @patch("app.services.sentiment.analyze_sentiment_llm")
    async def test_low_confidence_retains_vader(
        self,
        mock_llm: AsyncMock,
        mock_get_ambiguous: MagicMock,
        mock_get_supabase: MagicMock,
    ) -> None:
        """AC4: confidence=0.5 -> final_label = vader_label (neutral)."""
        from app.services.sentiment import reclassify_ambiguous_comments

        cid = str(uuid4())
        mock_get_ambiguous.return_value = [
            {
                "comment_id": cid,
                "text": "Texto ambiguo que precisa de analise",
                "vader_compound": 0.01,
                "vader_label": "neutral",
            }
        ]

        mock_llm.return_value = {
            "llm_label": "positive",
            "llm_confidence": 0.5,
            "llm_model": "gpt-4o-mini",
        }

        mock_table = _chainable_table_mock()
        mock_table.execute.return_value = MagicMock(data=[])
        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_get_supabase.return_value = mock_sb

        result = await reclassify_ambiguous_comments()

        assert result["confidence_upgrades"] == 0
        assert result["retained_vader_label"] == 1

        # Verify update was called with vader_label as final_label
        update_call = mock_table.update.call_args
        update_data = update_call[0][0]
        assert update_data["final_label"] == "neutral"  # vader_label retained
        assert update_data["llm_label"] == "positive"  # but llm_label still saved
        assert update_data["llm_confidence"] == 0.5


class TestLLMApiFailure:
    """AC5 (1.5): LLM API failure handling."""

    @pytest.mark.asyncio
    @patch("app.services.sentiment.get_supabase")
    @patch("app.services.sentiment._get_ambiguous_comments")
    @patch("app.services.sentiment.analyze_sentiment_llm")
    async def test_api_failure_does_not_modify_record(
        self,
        mock_llm: AsyncMock,
        mock_get_ambiguous: MagicMock,
        mock_get_supabase: MagicMock,
    ) -> None:
        """AC5: API failure -- record NOT modified, processing continues."""
        from app.services.sentiment import reclassify_ambiguous_comments

        cid1 = str(uuid4())
        cid2 = str(uuid4())
        mock_get_ambiguous.return_value = [
            {
                "comment_id": cid1,
                "text": "Primeiro comentario ambiguo",
                "vader_compound": 0.01,
                "vader_label": "neutral",
            },
            {
                "comment_id": cid2,
                "text": "Segundo comentario ambiguo",
                "vader_compound": -0.01,
                "vader_label": "neutral",
            },
        ]

        # First call fails, second succeeds
        mock_llm.side_effect = [
            httpx.HTTPError("Connection timeout"),
            {
                "llm_label": "negative",
                "llm_confidence": 0.9,
                "llm_model": "gpt-4o-mini",
            },
        ]

        mock_table = _chainable_table_mock()
        mock_table.execute.return_value = MagicMock(data=[])
        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_get_supabase.return_value = mock_sb

        result = await reclassify_ambiguous_comments()

        # Only the second comment was reclassified
        assert result["reclassified_count"] == 1
        assert result["api_calls_made"] == 1
        assert result["confidence_upgrades"] == 1

        # update was called only once (for the second comment)
        assert mock_table.update.call_count == 1

    @pytest.mark.asyncio
    @patch("app.services.sentiment.get_supabase")
    @patch("app.services.sentiment._get_ambiguous_comments")
    @patch("app.services.sentiment.analyze_sentiment_llm")
    async def test_json_decode_error_continues(
        self,
        mock_llm: AsyncMock,
        mock_get_ambiguous: MagicMock,
        mock_get_supabase: MagicMock,
    ) -> None:
        """AC5: Invalid JSON from LLM -- skip, log, continue."""
        from app.services.sentiment import reclassify_ambiguous_comments

        mock_get_ambiguous.return_value = [
            {
                "comment_id": str(uuid4()),
                "text": "Comentario que gera JSON invalido",
                "vader_compound": 0.02,
                "vader_label": "neutral",
            },
        ]

        mock_llm.side_effect = json.JSONDecodeError("Expecting value", "", 0)

        mock_table = _chainable_table_mock()
        mock_sb = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_get_supabase.return_value = mock_sb

        result = await reclassify_ambiguous_comments()

        assert result["reclassified_count"] == 0
        assert result["api_calls_made"] == 0
        assert mock_table.update.call_count == 0


class TestGetAmbiguousComments:
    """AC3 (1.5): Filtering for ambiguous comments."""

    @patch("app.services.sentiment.get_supabase")
    def test_filters_by_compound_and_length(
        self, mock_get_supabase: MagicMock
    ) -> None:
        """AC3: Only comments with compound in (-0.05, 0.05) and text > 20 chars."""
        from app.services.sentiment import _get_ambiguous_comments

        cid_eligible = str(uuid4())
        cid_short = str(uuid4())

        mock_sentiment = _chainable_table_mock()
        mock_sentiment.execute.return_value = MagicMock(
            data=[
                {"comment_id": cid_eligible, "vader_compound": 0.01, "vader_label": "neutral"},
                {"comment_id": cid_short, "vader_compound": -0.02, "vader_label": "neutral"},
            ]
        )

        mock_comments = _chainable_table_mock()
        mock_comments.execute.return_value = MagicMock(
            data=[
                {"id": cid_eligible, "text": "Este e um comentario longo o suficiente para LLM"},
                {"id": cid_short, "text": "Curto"},  # <= 20 chars
            ]
        )

        def table_dispatch(name: str) -> MagicMock:
            return {
                "sentiment_scores": mock_sentiment,
                "comments": mock_comments,
            }.get(name, MagicMock())

        mock_sb = MagicMock()
        mock_sb.table.side_effect = table_dispatch
        mock_get_supabase.return_value = mock_sb

        result = _get_ambiguous_comments()

        assert len(result) == 1
        assert result[0]["comment_id"] == cid_eligible


# ---------------------------------------------------------------------------
# Story 1.5 -- Endpoint Tests
# ---------------------------------------------------------------------------


class TestLLMFallbackEndpoint:
    """AC6 (1.5): POST /analysis/sentiment/llm-fallback."""

    @patch("app.routers.analysis.reclassify_ambiguous_comments")
    def test_post_llm_fallback_returns_200(
        self, mock_reclassify: AsyncMock
    ) -> None:
        """AC6: Returns reclassification stats."""
        from app.main import app

        mock_reclassify.return_value = {
            "reclassified_count": 47,
            "api_calls_made": 47,
            "confidence_upgrades": 32,
            "retained_vader_label": 15,
        }

        with TestClient(app) as client:
            response = client.post("/api/v1/analysis/sentiment/llm-fallback")

        assert response.status_code == 200
        body = response.json()
        assert body["reclassified_count"] == 47
        assert body["api_calls_made"] == 47
        assert body["confidence_upgrades"] == 32
        assert body["retained_vader_label"] == 15
