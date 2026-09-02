# ──────────────────────────────────────────────────────────────────
# Makefile — Backend development commands
# ──────────────────────────────────────────────────────────────────
.DEFAULT_GOAL := help

.PHONY: help dev lint format typecheck test migrate infra

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

dev: ## Start the FastAPI dev server with hot-reload
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

lint: ## Run ruff linter
	uv run ruff check app/ tests/

format: ## Format code with ruff
	uv run ruff format app/ tests/
	uv run ruff check --fix app/ tests/

typecheck: ## Run mypy type checker
	uv run mypy app/

test: ## Run pytest
	uv run pytest tests/ -v --tb=short

migrate: ## Run Alembic migrations (head)
	uv run alembic upgrade head

infra: ## Start Postgres + Redis via Docker Compose
	docker compose up -d db redis
