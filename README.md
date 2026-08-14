# TenderLens

TenderLens is an AI-assisted service for extracting tender conditions, answering questions
with page-level evidence, and producing a risk checklist. It is not legal advice.

The project is under active development. The first milestone provides the production-style
FastAPI and PostgreSQL/pgvector foundation.

## Quick start

1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build`.
3. Open `http://localhost:8000/docs`.

Windows helpers:

```powershell
.\scripts\dev.ps1
.\scripts\test.ps1
```

## Development checks

```bash
uv sync --dev
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```

Models, API keys, uploaded documents, and personal data are intentionally excluded from the
repository.

