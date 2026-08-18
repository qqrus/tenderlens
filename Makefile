.PHONY: install dev test lint format typecheck frontend-check evaluate migrate compose-up compose-down

install:
	uv sync --dev

dev:
	uv run uvicorn tenderlens.main:app --reload

test:
	uv run pytest

lint:
	uv run ruff format --check .
	uv run ruff check .

format:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy src

frontend-check:
	cd frontend && pnpm format:check && pnpm lint && pnpm typecheck && pnpm test && pnpm build && pnpm test:e2e

evaluate:
	uv run python scripts/evaluate.py

migrate:
	uv run alembic upgrade head

compose-up:
	docker compose up --build

compose-down:
	docker compose down

