"""Supabase client singleton.

Provides ``get_supabase()`` which returns a lazily-initialized, process-wide
Supabase client using credentials from ``settings``.
"""

from supabase import Client, create_client

from app.core.config import settings

_client: Client | None = None


def get_supabase() -> Client:
    """Return the singleton Supabase client, creating it on first call."""
    global _client
    if _client is None:
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    return _client
