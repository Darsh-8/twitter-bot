from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"
    dry_run: bool = True

    database_url: str = "postgresql+asyncpg://newsbot:newsbot@localhost:5432/newsbot"
    redis_url: str = "redis://localhost:6379/0"

    llm_provider: Literal["anthropic", "openai", "groq", "gemini"] = "anthropic"
    llm_model_anthropic: str = "claude-sonnet-4-5"
    llm_model_openai: str = "gpt-4o-mini"
    llm_model_groq: str = "llama-3.3-70b-versatile"
    llm_model_gemini: str = "gemini-2.0-flash"
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    groq_api_keys: SecretStr | None = None
    gemini_api_key: SecretStr | None = None

    x_api_key: SecretStr | None = None
    x_api_secret: SecretStr | None = None
    x_access_token: SecretStr | None = None
    x_access_token_secret: SecretStr | None = None
    x_bearer_token: SecretStr | None = None

    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_article_age_days: int = 7
    max_articles_per_source_per_poll: int = 10
    max_stories_per_cycle: int = 20
    llm_call_delay_seconds: float = 3.0
    source_poll_delay_seconds: float = 2.0

    dedup_similarity_threshold: float = 0.83
    confidence_threshold: float = 0.6
    breaking_confidence_threshold: float = 0.4
    importance_threshold: float = 0.55
    research_importance_threshold: float = 0.75
    pending_story_max_age_hours: int = 48
    max_story_age_for_posting_hours: int = 24

    max_tweets_per_day: int = 8
    min_post_interval_minutes: int = 45
    min_breaking_interval_minutes: int = 10
    poll_interval_minutes: int = 5

    enable_story_council: bool = True
    council_approval_threshold: float = 0.6
    council_max_candidates_per_cycle: int = 3

    timezone: str = "UTC"
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "console"

    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 8000

    celery_task_always_eager: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
