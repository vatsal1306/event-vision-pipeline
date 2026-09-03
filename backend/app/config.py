"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the API and workers."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SpotMe"
    debug: bool = False
    environment: str = "development"
    api_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    secret_key: str = "dev-only-change-me"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/photoshare"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-south-1"
    s3_bucket_originals: str = "platform-originals"
    s3_bucket_proxies: str = "platform-proxies"
    s3_bucket_assets: str = "platform-assets"

    sms_provider: str = "log"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
