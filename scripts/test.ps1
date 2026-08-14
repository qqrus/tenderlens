$ErrorActionPreference = "Stop"

uv sync --dev
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest

