"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
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
    trusted_proxies: list[str] = ["127.0.0.1"]

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/photoshare"
    # Per-process, and uvicorn runs several worker processes, so this is
    # multiplied by `WEB_CONCURRENCY`. Keep the product plus the Celery workers
    # comfortably under the PostgreSQL `max_connections` ceiling of 100.
    database_pool_size: int = 10
    database_max_overflow: int = 5

    redis_url: str = "redis://localhost:6379/0"

    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-south-1"
    # Compute-account IAM (start/stop GPU). Do not reuse storage-account S3 keys.
    aws_compute_access_key_id: str = ""
    aws_compute_secret_access_key: str = ""
    aws_compute_region: str = "ap-south-1"
    gpu_instance_id: str = ""
    gpu_idle_stop_minutes: int = 10
    # Comma-separated ops inboxes for stalled face-processing alerts.
    ops_alert_email: str = ""
    face_processing_stall_minutes: int = 30
    face_processing_requeue_seconds: int = 120
    # Heartbeats older than this are "worker missing" but not yet give-up.
    face_processing_heartbeat_fresh_seconds: int = 180
    # Blank means "derive the regional AWS endpoint". Set explicitly only for
    # S3-compatible stores such as MinIO.
    s3_endpoint_url: str = ""
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

    # log = no HTTP (local). fast2sms = Quick OTP via Fast2SMS (SMS_API_KEY required).
    sms_provider: str = "log"
    sms_api_key: str = ""
    sms_sender_id: str = "PHOTOS"

    email_provider: str = "none"
    email_from: str = "noreply@platform.com"
    email_from_name: str = "SpotMe"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    ses_region: str = "ap-south-1"

    @field_validator("smtp_password", mode="before")
    @classmethod
    def strip_smtp_password_spaces(cls, value: object) -> object:
        """Google App Passwords are often copied with spaces; SMTP rejects those."""
        if isinstance(value, str):
            return value.replace(" ", "").strip()
        return value

    @field_validator("smtp_user", "email_from", "ops_alert_email", mode="before")
    @classmethod
    def strip_smtp_identity(cls, value: object) -> object:
        """Trim accidental whitespace around the Workspace mailbox."""
        if isinstance(value, str):
            return value.strip()
        return value

    proxy_max_dimension: int = 2048
    proxy_quality: int = 82
    # Gallery grid tiles. Small enough that a 50-photo page is ~1.5 MB.
    thumb_max_dimension: int = 480
    thumb_quality: int = 70
    # Lightbox / full-screen viewer on phones and laptops.
    preview_max_dimension: int = 1280
    preview_quality: int = 78
    # Gallery images are fetched straight from S3 with presigned URLs. Expiry is
    # quantised to `gallery_url_cache_bucket_seconds` so the same photo yields a
    # byte-identical URL for the whole bucket and the browser HTTP cache can hit.
    # Total validity is therefore between one and two bucket widths.
    gallery_url_cache_bucket_seconds: int = 3600
    watermark_opacity: float = 0.4
    max_upload_size_bytes: int = 52_428_800

    sentry_dsn: str = ""

    @property
    def jwt_couple_token_expire_days(self) -> int:
        """Couple gallery JWTs share the guest session lifetime (30 days by default)."""
        return self.jwt_guest_token_expire_days

    @property
    def ops_alert_emails(self) -> list[str]:
        """Parse ``OPS_ALERT_EMAIL`` into unique, non-empty addresses."""
        seen: set[str] = set()
        emails: list[str] = []
        for part in self.ops_alert_email.split(","):
            address = part.strip()
            if not address or address.lower() in seen:
                continue
            seen.add(address.lower())
            emails.append(address)
        return emails


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance loaded from env and ``.env``."""
    return Settings()
