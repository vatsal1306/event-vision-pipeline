.PHONY: dev lint format typecheck sync sync-ci test test-ci migrate docker-up

dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

lint:
	uv run ruff check app tests

format:
	uv run ruff format app tests
	uv run ruff check --fix app tests

typecheck:
	uv run mypy app

sync:
	uv sync --extra dev --extra ml

sync-ci:
	uv sync --extra dev

test: sync
	uv run pytest --cov=app --cov-report=term-missing

test-ci: sync-ci
	uv run pytest -m "not ml" --cov=app --cov-config=coverage.ci.ini --cov-report=term-missing

migrate:
	uv run alembic upgrade head

docker-up:
	docker compose up --build db redis backend
