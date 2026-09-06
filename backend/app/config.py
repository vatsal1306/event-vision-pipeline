"""Application configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Application
    app_name: str = "AI Photo Sharing Platform"
    debug: bool = False
    environment: str = "development"  # development, staging, production
    api_base_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    secret_key: str = "dummy_secret_for_local_dev"  # for JWT signing

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # AWS S3
    aws_access_key_id: str = "dummy"
    aws_secret_access_key: str = "dummy"
    aws_region: str = "ap-south-1"
    s3_bucket_originals: str = "platform-originals"
    s3_bucket_proxies: str = "platform-proxies"
    s3_bucket_assets: str = "platform-assets"  # logos, watermarks
    s3_presigned_url_expiry: int = 3600  # 1 hour

    # JWT
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    jwt_guest_token_expire_days: int = 30

    # OTP
    otp_expiry_seconds: int = 300
    otp_max_attempts: int = 3
    otp_cooldown_seconds: int = 60

    # SMS Provider
    sms_provider: str = "log"  # log | msg91 | twilio — Phase 1: log OTP
    sms_api_key: str = ""
    sms_sender_id: str = "PHOTOS"

    # Email
    email_provider: str = "none"  # none | log | ses | smtp — Phase 1: none/log
    email_from: str = "noreply@platform.com"
    ses_region: str = "ap-south-1"

    # Processing
    proxy_max_dimension: int = 2048
    proxy_quality: int = 82
    watermark_opacity: float = 0.4
    max_upload_size_bytes: int = 52428800  # 50MB

    # Sentry
    sentry_dsn: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
