$ErrorActionPreference = "Stop"

uv sync --dev
uv run uvicorn tenderlens.main:app --reload

