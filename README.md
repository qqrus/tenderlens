# TenderLens

TenderLens is an AI-assisted service for extracting tender conditions, answering questions
with page-level evidence, and producing a risk checklist. It is not legal advice.

The project is under active development. The first milestone provides the production-style
FastAPI and PostgreSQL/pgvector foundation.

## Quick start

1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build`.
3. Open `http://localhost:8000/docs`.

Upload a PDF:

```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Content-Type: multipart/form-data" \
  -F "file=@tender.pdf"
```

The upload endpoint returns `202 Accepted`. Use `GET /api/v1/documents/{document_id}` to
poll the processing status. At this stage digitally generated PDFs are supported; scanned
documents return `no_extractable_text` until the OCR milestone is implemented.

Search within a processed document:

```bash
curl -X POST http://localhost:8000/api/v1/documents/DOCUMENT_ID/search \
  -H "Content-Type: application/json" \
  -d '{"query": "maximum budget", "limit": 5}'
```

The first semantic search downloads a multilingual ONNX embedding model into the Docker
`models_data` volume. Search combines PostgreSQL full-text results and pgvector cosine
similarity with Reciprocal Rank Fusion. If the embedding model is temporarily unavailable,
the endpoint degrades to lexical search instead of failing the request.

Ask a question with server-verified citations:

```bash
curl -X POST http://localhost:8000/api/v1/documents/DOCUMENT_ID/questions \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the maximum budget?"}'
```

The response contains an answer plus citations with the source page, chunk ID, exact quote,
and page-relative character offsets. TenderLens accepts only quotes found in retrieved chunks;
unknown evidence IDs and invented quotes are removed before the response is returned.

The zero-cost `extractive` answer mode works without a model or API key. For fluent generated
answers, set one of these options in your local `.env` (never commit the key):

```dotenv
# Local Ollama
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:4b

# Or OpenAI Responses API
LLM_PROVIDER=openai
LLM_MODEL=YOUR_OPENAI_MODEL
OPENAI_API_KEY=YOUR_LOCAL_SECRET
```

If Ollama or OpenAI is unavailable during a request, TenderLens falls back to a verified
extractive answer rather than returning an unsupported model claim.

With the Docker stack running, execute an end-to-end smoke test:

```bash
uv run python scripts/smoke_ingestion.py
```

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
