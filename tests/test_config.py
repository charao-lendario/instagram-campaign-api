"""Unit tests for configuration, Supabase client, and /health endpoint.

Tests AC1 (settings loading), AC2 (singleton client), AC3 (health endpoint),
and AC5 (logging setup).
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestSettings:
    """AC1: Settings loading via pydantic-settings."""

    def test_settings_loads_required_fields(self) -> None:
        """Given env vars are set, settings loads without error."""
        env_overrides = {
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key-123",
            "APIFY_TOKEN": "apify_test",
            "LLM_API_KEY": "sk-test",
        }
        with patch.dict("os.environ", env_overrides, clear=False):
            from app.core.config import Settings

            s = Settings()  # type: ignore[call-arg]
            assert s.SUPABASE_URL == "https://test.supabase.co"
            assert s.SUPABASE_KEY == "test-key-123"
            assert s.APIFY_TOKEN == "apify_test"
            assert s.LLM_API_KEY == "sk-test"

    def test_settings_defaults(self) -> None:
        """Given minimal env vars, defaults are applied correctly."""
        env_overrides = {
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
        }
        with patch.dict("os.environ", env_overrides, clear=False):
            from app.core.config import Settings

            s = Settings()  # type: ignore[call-arg]
            assert s.LLM_PROVIDER == "openai"
            assert s.LLM_MODEL == "gpt-4o-mini"
            assert s.ALLOWED_ORIGINS == "*"
            assert s.SCRAPING_INTERVAL_HOURS == 6
            assert s.LOG_LEVEL == "INFO"


class TestSupabaseClient:
    """AC2: Supabase singleton client."""

    def test_get_supabase_returns_client(self) -> None:
        """Given valid settings, get_supabase returns a Client."""
        mock_client = MagicMock()
        with patch("app.db.supabase.create_client", return_value=mock_client):
            # Reset singleton
            import app.db.supabase as supa_mod

            supa_mod._client = None
            client = supa_mod.get_supabase()
            assert client is mock_client

    def test_get_supabase_is_singleton(self) -> None:
        """Given multiple calls, get_supabase returns the same instance."""
        mock_client = MagicMock()
        with patch("app.db.supabase.create_client", return_value=mock_client) as mock_create:
            import app.db.supabase as supa_mod

            supa_mod._client = None
            first = supa_mod.get_supabase()
            second = supa_mod.get_supabase()
            assert first is second
            mock_create.assert_called_once()


class TestHealthEndpoint:
    """AC3: GET /health returns proper payload."""

    def test_health_connected(
        self, test_client: TestClient, mock_supabase_module: MagicMock
    ) -> None:
        """Given Supabase is reachable, /health returns database=connected."""
        response = test_client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["database"] == "connected"
        assert body["scheduler"] == "stopped"
        assert body["last_scrape"] is None

    def test_health_disconnected(
        self, test_client: TestClient, mock_supabase_disconnected: MagicMock
    ) -> None:
        """Given Supabase is unreachable, /health returns database=disconnected."""
        response = test_client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["database"] == "disconnected"


class TestLogging:
    """AC5: Structured logging configuration."""

    def test_setup_logging_configures_root_logger(self) -> None:
        """Given setup_logging is called, root logger has a handler."""
        import logging

        from app.core.logging import setup_logging

        setup_logging()
        root = logging.getLogger()
        assert len(root.handlers) > 0
        # Verify format includes structured elements
        handler = root.handlers[0]
        assert handler.formatter is not None
        fmt = handler.formatter._fmt
        assert "%(levelname)" in fmt
        assert "%(asctime)" in fmt
        assert "%(name)" in fmt
