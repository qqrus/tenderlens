# TenderLens

TenderLens is an AI-assisted service for extracting tender conditions, answering questions
with page-level evidence, and producing a risk checklist. It is not legal advice.

The project is under active development. The first milestone provides the production-style
FastAPI and PostgreSQL/pgvector foundation.

## Quick start

1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build`.
3. Open the TenderLens interface at `http://localhost:5173`.

The interface is Russian by default and can be switched to English with the `RU / EN`
control. Exact quotes and PDF text always stay in the document's original language so that
citations remain verifiable. API documentation is available separately at
`http://localhost:8000/docs`.

Docker Compose starts PostgreSQL, FastAPI, and the production-built React frontend. PDF files
are downloaded through the checked API client and rendered locally by PDF.js.

Upload a PDF:

```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Content-Type: multipart/form-data" \
  -F "file=@tender.pdf"
```

The upload endpoint returns `202 Accepted`. Use `GET /api/v1/documents/{document_id}` to
poll the processing status. At this stage digitally generated PDFs are supported; scanned
documents return `no_extractable_text` until the OCR milestone is implemented.

List documents and open the original PDF in a browser viewer:

```bash
curl "http://localhost:8000/api/v1/documents?limit=20&offset=0"
curl http://localhost:8000/api/v1/documents/DOCUMENT_ID/file --output tender.pdf
```

The file endpoint uses an inline content disposition, supports the browser/PDF.js workflow,
and disables shared caching of uploaded tender documents.

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

Extract key conditions and build a risk checklist:

```bash
curl -X POST http://localhost:8000/api/v1/documents/DOCUMENT_ID/analysis
```

The analysis endpoint returns four condition categories: `deadline`, `budget`, `penalty`,
and `requirement`. Each extracted condition includes an exact quote, page, chunk ID,
page-relative character offsets, and a rule match score. Overlapping retrieval hits are
deduplicated.

The risk checklist is intentionally conservative. A risk based on a found condition carries
the same verified citation. If a category is not found, TenderLens creates an ungrounded
manual-review warning instead of claiming that the condition is absent from the original PDF.
This checklist helps navigate the document and is not legal advice.

With the Docker stack running, execute an end-to-end smoke test:

```bash
uv run python scripts/smoke_ingestion.py
```

## Evaluation baseline

TenderLens includes a separate synthetic dataset with English and Russian questions. The
evaluation creates a PDF at runtime and measures the real Docker API, retrieval, citations,
structured analysis, and latency.

```bash
uv run python scripts/evaluate.py
```

Baseline from one local Docker CPU run:

| Metric | Result |
| --- | ---: |
| Retrieval Hit@5 | 1.000 |
| Retrieval MRR | 1.000 |
| Citation page accuracy | 1.000 |
| Citation quote accuracy | 1.000 |
| Analysis category/page recall | 1.000 |
| Analysis category/page precision | 1.000 |
| Search latency p50 / p95 | 67.14 / 94.23 ms |
| Answer latency p50 / p95 | 68.17 / 81.15 ms |
| Cold-start search latency | 2410.55 ms |

An additional v2 pack contains 12 realistic synthetic procurement files: 240 pages, 96 known
answers and 24 questions with no answer in the document. Russian is the primary language and
four English files exercise multilingual retrieval. Each 20-page package includes a cover,
contents, legal context, information sheet, price justification, technical requirements,
acceptance, securities, liability, a condensed draft contract and annexes. The layout follows
the current GOST R 7.0.97-2025 conventions where applicable and every page is visibly marked as
synthetic. The reviewed Docker run reached 1.0 citation-page, exact-value and correct-refusal
accuracy, with mean question latency of 83.42 ms. Run it with:

```bash
uv run python scripts/verify_pdf_pack.py
uv run python scripts/smoke_pdf_pack.py
```

These results are regression baselines, not claims of legal accuracy. The documents are
programmatically generated fixtures, latency is hardware-dependent, generative LLM quality is
not measured in the default extractive mode, and scanned PDFs remain unsupported. See
[`evals/README.md`](evals/README.md) and [`evals/baseline.json`](evals/baseline.json).

## Custom ML training

TenderLens includes a reproducible training pipeline for a domain-specific passage reranker.
The v2 corpus has 24 synthetic RU/EN documents, 576 questions and 2,304 labeled pairs with
document-level splits and same-document hard negatives. Heavy model weights remain outside
Git and the production image.

```powershell
uv run python scripts/build_reranker_dataset.py --check
uv run python scripts/evaluate_reranker.py
.\scripts\train-reranker.ps1 -MaxSteps 1
```

Fine-tuning improved synthetic holdout Hit@1 from 0.875000 to 0.989583 and test MRR from
0.926215 to 0.993056. The model remains a `research_candidate`: it is not enabled in the API
until a separately reviewed real-document holdout confirms the result. See
[`docs/ml/reranker-training.md`](docs/ml/reranker-training.md) for the plain-language method,
measurements, one remaining error, and limitations.

Windows helpers:

```powershell
.\scripts\dev.ps1
.\scripts\test.ps1
.\scripts\test-all.ps1
```

## Development checks

```bash
uv sync --dev
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
cd frontend
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm test:e2e
```

Models, API keys, uploaded documents, and personal data are intentionally excluded from the
repository.
