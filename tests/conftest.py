"""Shared test fixtures.

Provides a ``test_client`` for FastAPI, mock Supabase client, and mock Apify
client fixtures for use across all test modules.
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def mock_supabase() -> Generator[MagicMock, None, None]:
    """Patch ``get_supabase`` to return a mock Supabase client."""
    mock_client = MagicMock()
    with patch("app.db.supabase.get_supabase", return_value=mock_client) as _:
        yield mock_client


@pytest.fixture()
def mock_supabase_module() -> Generator[MagicMock, None, None]:
    """Patch the Supabase client at module level in the health router."""
    mock_client = MagicMock()
    # Mock the select -> limit -> execute chain
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_limit = MagicMock()

    mock_client.table.return_value = mock_table
    mock_table.select.return_value = mock_select
    mock_select.limit.return_value = mock_limit
    mock_limit.execute.return_value = MagicMock()  # non-None result

    with patch("app.routers.health.get_supabase", return_value=mock_client):
        yield mock_client


@pytest.fixture()
def mock_supabase_disconnected() -> Generator[MagicMock, None, None]:
    """Patch ``get_supabase`` to simulate a disconnected database."""
    with patch(
        "app.routers.health.get_supabase",
        side_effect=Exception("Connection refused"),
    ):
        yield MagicMock()


@pytest.fixture()
def mock_apify() -> Generator[MagicMock, None, None]:
    """Provide a mock Apify client for scraping tests."""
    mock_client = MagicMock()
    yield mock_client


@pytest.fixture()
def test_client() -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient."""
    from app.main import app

    with TestClient(app) as client:
        yield client
