"""Unit tests for pipeline orchestration and scheduler.

Story 1.7 AC1-AC10: Tests for scheduler initialization, concurrency lock,
manual trigger, health check, and suggestions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# AC1: Scheduler Initialization
# ---------------------------------------------------------------------------


class TestSchedulerInit:
    """AC1: APScheduler initializes and shuts down correctly."""

    @patch("app.scheduler.jobs.scheduler")
    def test_start_scheduler_adds_job(
        self, mock_scheduler: MagicMock
    ) -> None:
        """AC1a/b/c: Job is added and scheduler starts."""
        from app.scheduler.jobs import start_scheduler

        start_scheduler()

        mock_scheduler.add_job.assert_called_once()
        call_kwargs = mock_scheduler.add_job.call_args
        assert call_kwargs.kwargs.get("id") == "full_pipeline"
        assert call_kwargs.kwargs.get("replace_existing") is True
        mock_scheduler.start.assert_called_once()

    @patch("app.scheduler.jobs.scheduler")
    def test_shutdown_scheduler(self, mock_scheduler: MagicMock) -> None:
        """AC1d: Scheduler shuts down gracefully."""
        from app.scheduler.jobs import shutdown_scheduler

        mock_scheduler.running = True
        shutdown_scheduler()

        mock_scheduler.shutdown.assert_called_once_with(wait=False)

    @patch("app.scheduler.jobs.scheduler")
    def test_shutdown_not_running_noop(self, mock_scheduler: MagicMock) -> None:
        """Shutdown when not running does nothing."""
        from app.scheduler.jobs import shutdown_scheduler

        mock_scheduler.running = False
        shutdown_scheduler()

        mock_scheduler.shutdown.assert_not_called()


# ---------------------------------------------------------------------------
# AC3: Concurrency Lock
# ---------------------------------------------------------------------------


class TestConcurrencyLock:
    """AC3: Pipeline lock prevents concurrent runs."""

    def test_acquire_and_release(self) -> None:
        """AC3a/c: Acquire succeeds, release clears state."""
        from app.scheduler.lock import (
            acquire_pipeline_lock,
            get_current_run_id,
            is_pipeline_running,
            release_pipeline_lock,
        )

        run_id = uuid4()

        # Acquire
        assert acquire_pipeline_lock(run_id) is True
        assert is_pipeline_running() is True
        assert get_current_run_id() == run_id

        # Release
        release_pipeline_lock()
        assert is_pipeline_running() is False
        assert get_current_run_id() is None

    def test_second_acquire_fails(self) -> None:
        """AC3b: Second acquire while locked returns False."""
        from app.scheduler.lock import (
            acquire_pipeline_lock,
            release_pipeline_lock,
        )

        run_id_1 = uuid4()
        run_id_2 = uuid4()

        try:
            assert acquire_pipeline_lock(run_id_1) is True
            assert acquire_pipeline_lock(run_id_2) is False
        finally:
            release_pipeline_lock()

    def test_release_idempotent(self) -> None:
        """AC3c: Release is safe to call multiple times."""
        from app.scheduler.lock import release_pipeline_lock

        # Should not raise
        release_pipeline_lock()
        release_pipeline_lock()


# ---------------------------------------------------------------------------
# AC4: Manual Trigger Endpoint
# ---------------------------------------------------------------------------


class TestManualTriggerEndpoint:
    """AC4: POST /scraping/run triggers pipeline or returns 409."""

    @patch("app.routers.scraping.run_full_pipeline")
    @patch("app.routers.scraping.is_pipeline_running", return_value=False)
    def test_trigger_returns_202(
        self,
        mock_is_running: MagicMock,
        mock_run_pipeline: MagicMock,
    ) -> None:
        """AC4b: Lock free -> 202 Accepted."""
        from app.main import app

        with TestClient(app) as client:
            response = client.post("/api/v1/scraping/run")

        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "started"
        assert body["message"] == "Full pipeline initiated"
        assert "run_id" in body

    @patch("app.routers.scraping.get_current_run_id", return_value=uuid4())
    @patch("app.routers.scraping.is_pipeline_running", return_value=True)
    def test_trigger_returns_409_when_locked(
        self,
        mock_is_running: MagicMock,
        mock_get_run_id: MagicMock,
    ) -> None:
        """AC4c: Lock held -> 409 Conflict."""
        from app.main import app

        with TestClient(app) as client:
            response = client.post("/api/v1/scraping/run")

        assert response.status_code == 409
        body = response.json()
        assert "Pipeline already in progress" in body["detail"]


# ---------------------------------------------------------------------------
# AC5: Health Check with Scheduler
# ---------------------------------------------------------------------------


class TestHealthCheckScheduler:
    """AC5: Health endpoint includes scheduler status and last_scrape."""

    @patch("app.routers.health.is_scheduler_running", return_value=True)
    @patch("app.routers.health.get_supabase")
    def test_health_running_scheduler(
        self,
        mock_get_supabase: MagicMock,
        mock_is_running: MagicMock,
    ) -> None:
        """AC5: scheduler=running when active."""
        from app.main import app

        mock_sb = MagicMock()
        table_mock = _chainable_table_mock()
        table_mock.execute.return_value = MagicMock(data=[{"id": "x"}])
        mock_sb.table.return_value = table_mock

        # Mock rpc for get_last_successful_scrape
        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = MagicMock(
            data="2026-02-21T14:00:00+00:00"
        )
        mock_sb.rpc.return_value = rpc_mock
        mock_get_supabase.return_value = mock_sb

        with TestClient(app) as client:
            response = client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["database"] == "connected"
        assert body["scheduler"] == "running"
        assert body["last_scrape"] is not None

    @patch("app.routers.health.is_scheduler_running", return_value=False)
    @patch("app.routers.health.get_supabase")
    def test_health_stopped_scheduler(
        self,
        mock_get_supabase: MagicMock,
        mock_is_running: MagicMock,
    ) -> None:
        """AC5: scheduler=stopped when inactive."""
        from app.main import app

        mock_sb = MagicMock()
        table_mock = _chainable_table_mock()
        table_mock.execute.return_value = MagicMock(data=[{"id": "x"}])
        mock_sb.table.return_value = table_mock

        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = MagicMock(data=None)
        mock_sb.rpc.return_value = rpc_mock
        mock_get_supabase.return_value = mock_sb

        with TestClient(app) as client:
            response = client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["scheduler"] == "stopped"

    @patch("app.routers.health.is_scheduler_running", return_value=False)
    @patch(
        "app.routers.health.get_supabase",
        side_effect=Exception("Connection refused"),
    )
    def test_health_db_down_returns_503(
        self,
        mock_get_supabase: MagicMock,
        mock_is_running: MagicMock,
    ) -> None:
        """AC5: Database down returns 503."""
        from app.main import app

        with TestClient(app) as client:
            response = client.get("/health")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "degraded"
        assert body["database"] == "disconnected"


# ---------------------------------------------------------------------------
# AC6: Suggestions Endpoint
# ---------------------------------------------------------------------------


class TestSuggestionsEndpoint:
    """AC6/AC7: Strategic suggestions generation and persistence."""

    @patch("app.routers.suggestions.generate_strategic_suggestions")
    def test_suggestions_returns_200(
        self, mock_generate: AsyncMock
    ) -> None:
        """AC6: Returns 200 with suggestions list."""
        from app.models.suggestion import StrategicSuggestion, SuggestionsResponse
        from app.main import app

        mock_generate.return_value = SuggestionsResponse(
            suggestions=[
                StrategicSuggestion(
                    title="Explorar tema saude",
                    description="Posts sobre saude geram mais engajamento",
                    supporting_data="52 comentarios positivos",
                    priority="high",
                ),
                StrategicSuggestion(
                    title="Manter ritmo",
                    description="Manter publicacao consistente",
                    supporting_data="Tendencia de melhora +0.12",
                    priority="medium",
                ),
                StrategicSuggestion(
                    title="Responder seguranca",
                    description="Adversaria domina tema",
                    supporting_data="37 vs 28 comentarios",
                    priority="high",
                ),
            ],
            generated_at=datetime.now(timezone.utc),
            data_snapshot={
                "total_comments_analyzed": 1010,
                "last_scrape": "2026-02-21T14:00:00Z",
            },
        )

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/analytics/suggestions",
                json={"candidate_id": None},
            )

        assert response.status_code == 200
        body = response.json()
        assert len(body["suggestions"]) == 3
        assert body["suggestions"][0]["title"] == "Explorar tema saude"
        assert body["data_snapshot"]["total_comments_analyzed"] == 1010


# ---------------------------------------------------------------------------
# AC9: Pipeline Run Status
# ---------------------------------------------------------------------------


class TestPipelineRunStatus:
    """AC9: ScrapingRun status tracking."""

    @patch("app.services.pipeline.classify_all_unthemed_comments", return_value=5)
    @patch("app.services.pipeline.reclassify_ambiguous_comments")
    @patch("app.services.pipeline.analyze_comments_batch", return_value=[])
    @patch("app.services.pipeline.scrape_all_comments", return_value=10)
    @patch("app.services.pipeline.scrape_posts", return_value=[])
    @patch("app.services.pipeline._get_active_candidates")
    @patch("app.services.pipeline._get_unanalyzed_comments", return_value=[])
    @patch("app.services.pipeline.get_supabase")
    @patch("app.services.pipeline._create_scraping_run")
    @patch("app.services.pipeline.acquire_pipeline_lock", return_value=True)
    @patch("app.services.pipeline.release_pipeline_lock")
    def test_successful_pipeline_sets_success(
        self,
        mock_release: MagicMock,
        mock_acquire: MagicMock,
        mock_create_run: MagicMock,
        mock_get_supabase: MagicMock,
        mock_unanalyzed: MagicMock,
        mock_candidates: MagicMock,
        mock_scrape_posts: MagicMock,
        mock_scrape_comments: MagicMock,
        mock_batch: MagicMock,
        mock_reclassify: AsyncMock,
        mock_themes: MagicMock,
    ) -> None:
        """AC9: Successful pipeline sets status=success."""
        from app.services.pipeline import run_full_pipeline

        run_id = uuid4()
        mock_create_run.return_value = run_id
        mock_candidates.return_value = [{"id": str(uuid4()), "username": "test"}]
        mock_reclassify.return_value = {"reclassified_count": 0}

        mock_sb = MagicMock()
        mock_table = _chainable_table_mock()
        mock_table.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value = mock_table
        mock_get_supabase.return_value = mock_sb

        result = run_full_pipeline(trigger="manual")

        assert result["status"] == "success"
        mock_release.assert_called_once()
