$ErrorActionPreference = "Stop"

uv sync --dev
uv run python scripts/evaluate.py @args
