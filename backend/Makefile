.PHONY: dev lint format typecheck test docker-up

dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

lint:
	uv run ruff check app tests

format:
	uv run ruff format app tests
	uv run ruff check --fix app tests

typecheck:
	uv run mypy app

test:
	uv run pytest

docker-up:
	docker compose up --build db redis backend
