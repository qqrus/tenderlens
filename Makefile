.PHONY: install dev test lint format typecheck frontend-check evaluate ml-install ml-dataset ml-baseline ml-train-smoke pdf-test-pack migrate compose-up compose-down

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

ml-install:
	uv sync --dev --extra ml

ml-dataset:
	uv run python scripts/build_reranker_dataset.py

ml-baseline:
	uv run python scripts/evaluate_reranker.py

ml-train-smoke:
	uv run --extra ml python scripts/train_reranker.py --max-steps 1 --output-dir models/tenderlens-reranker-smoke

pdf-test-pack:
	uv run python scripts/generate_synthetic_pdfs.py

migrate:
	uv run alembic upgrade head

compose-up:
	docker compose up --build

compose-down:
	docker compose down

