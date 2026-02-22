"""Application configuration via pydantic-settings.

Loads all settings from environment variables with sensible defaults.
A global `settings` singleton is available for import throughout the app.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str

    # Apify
    APIFY_TOKEN: str = ""
    APIFY_POST_ACTOR_ID: str = "apify/instagram-post-scraper"
    APIFY_COMMENT_ACTOR_ID: str = "apify/instagram-comment-scraper"

    # LLM
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_API_KEY: str = ""

    # CORS
    ALLOWED_ORIGINS: str = "*"

    # Scheduler
    SCRAPING_INTERVAL_HOURS: int = 6

    # Logging
    LOG_LEVEL: str = "INFO"


settings = Settings()  # type: ignore[call-arg]
