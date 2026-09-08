"""Pytest fixtures for API tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.core.database import get_db
from app.core.redis_client import close_redis
from app.main import app
from tests.db_helpers import (
    ensure_test_database_exists,
    get_test_database_url,
    reset_test_database,
    run_migrations,
    run_migrations_async,
)


@pytest_asyncio.fixture(autouse=True)
async def reset_redis_client() -> AsyncIterator[None]:
    """Ensure the global Redis client is closed between tests."""
    yield
    await close_redis()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Async HTTP client bound to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Dedicated PostgreSQL URL for integration tests."""
    return get_test_database_url()


@pytest.fixture(scope="session")
def migrated_databases(test_database_url: str) -> None:
    """Migrate main and test databases once per session, or skip if Postgres is down."""
    settings = get_settings()
    try:
        run_migrations(settings.database_url)
        asyncio.run(ensure_test_database_exists())
        run_migrations(test_database_url)
    except Exception as exc:  # noqa: BLE001 — skip with reason
        pytest.skip(f"PostgreSQL unavailable for integration tests: {exc}")


@pytest_asyncio.fixture
async def db_session(
    migrated_databases: None,
    test_database_url: str,
) -> AsyncIterator[AsyncSession]:
    """Yield a clean database session backed by migrated schema."""
    engine = create_async_engine(test_database_url, pool_pre_ping=True)
    try:
        await reset_test_database(engine)
        await run_migrations_async(test_database_url)

        session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        import app.core.database

        # Configure the existing global session_factory to use the test engine
        # so any module that has already imported it will use the test database
        original_engine = app.core.database.async_session_factory.kw["bind"]
        app.core.database.async_session_factory.configure(bind=engine)

        try:
            async with session_factory() as session:
                yield session
                await session.rollback()
        finally:
            app.core.database.async_session_factory.configure(bind=original_engine)
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """HTTP client with the database dependency overridden."""

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()
