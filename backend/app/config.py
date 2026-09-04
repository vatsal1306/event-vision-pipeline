"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """Runtime settings for the API and workers.

    All keys from ``docs/component_backend.md`` §14 are present so later stories
    can read them without expanding this class again. Dummy defaults allow the
    app to boot locally without AWS, SMS, or Sentry.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "SpotMe"
    debug: bool = True
    environment: str = "development"
    api_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    secret_key: str = "dev-only-change-me"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/photoshare"
    database_pool_size: int = 20
    database_max_overflow: int = 10

    redis_url: str = "redis://localhost:6379/0"

    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-south-1"
    s3_bucket_originals: str = "platform-originals"
    s3_bucket_proxies: str = "platform-proxies"
    s3_bucket_assets: str = "platform-assets"
    s3_presigned_url_expiry: int = 3600

    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    jwt_guest_token_expire_days: int = 30

    otp_expiry_seconds: int = 300
    otp_max_attempts: int = 3
    otp_cooldown_seconds: int = 60

    sms_provider: str = "log"
    sms_api_key: str = ""
    sms_sender_id: str = "PHOTOS"

    email_provider: str = "none"
    email_from: str = "noreply@platform.com"
    ses_region: str = "ap-south-1"

    proxy_max_dimension: int = 2048
    proxy_quality: int = 82
    watermark_opacity: float = 0.4
    max_upload_size_bytes: int = 52_428_800

    sentry_dsn: str = ""

    @property
    def jwt_couple_token_expire_days(self) -> int:
        """Couple gallery JWTs share the guest session lifetime (30 days by default)."""
        return self.jwt_guest_token_expire_days


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance loaded from env and ``.env``."""
    return Settings()
