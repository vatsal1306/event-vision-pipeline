"""Helpers for PostgreSQL-backed integration tests."""

from __future__ import annotations

import asyncio
import os
from urllib.parse import urlparse, urlunparse

from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import command
from app.config import get_settings

TEST_DATABASE_NAME = "photoshare_test"


def get_test_database_url() -> str:
    """Return the async URL for the dedicated test database."""
    override = os.environ.get("TEST_DATABASE_URL")
    if override:
        return override

    settings = get_settings()
    parsed = urlparse(settings.database_url)
    test_path = f"/{TEST_DATABASE_NAME}"
    return urlunparse(parsed._replace(path=test_path))


def get_admin_database_url() -> str:
    """Return an async URL connected to the default postgres database."""
    settings = get_settings()
    parsed = urlparse(settings.database_url)
    return urlunparse(parsed._replace(path="/postgres"))


async def ensure_test_database_exists() -> None:
    """Create the test database when PostgreSQL is reachable."""
    admin_engine = create_async_engine(
        get_admin_database_url(),
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with admin_engine.connect() as connection:
            exists = await connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": TEST_DATABASE_NAME},
            )
            if exists is None:
                await connection.execute(text(f'CREATE DATABASE "{TEST_DATABASE_NAME}"'))
    finally:
        await admin_engine.dispose()


def run_migrations(database_url: str) -> None:
    """Apply Alembic migrations to the given database URL.

    Uses Alembic's async env, which calls ``asyncio.run()``. Only call this from
    synchronous contexts (for example ``make migrate``), not from pytest async
    fixtures that already have a running event loop.
    """
    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    try:
        command.upgrade(alembic_cfg, "head")
    finally:
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url


async def run_migrations_async(database_url: str) -> None:
    """Apply Alembic migrations from an async test without nesting event loops."""
    await asyncio.to_thread(run_migrations, database_url)


async def reset_test_database(engine: AsyncEngine) -> None:
    """Drop and recreate the public schema for a clean test slate."""
    async with engine.begin() as connection:
        await connection.execute(text("DROP SCHEMA public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))
        await connection.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
        await connection.execute(text("GRANT ALL ON SCHEMA public TO public"))
