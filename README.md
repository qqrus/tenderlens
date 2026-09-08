# TenderLens

TenderLens is an AI-assisted service for extracting tender conditions, answering questions
with page-level evidence, and producing a risk checklist. It is not legal advice.

The project is under active development. The current version provides a production-style
FastAPI and PostgreSQL/pgvector foundation, a React interface, hybrid retrieval, verified
citations, and local OCR for Russian and English scans.

## Release plan and current status

The canonical plan is [ROADMAP.md](ROADMAP.md) (Russian). See the
[2026-09-08 audit](docs/release-audit-2026-09-08.md) for tested capabilities,
known correctness issues, and the distinction between historical ML results and
current checks. The project is an experimental MVP, not yet a validated v1.0 release.

The selected **B — graphite workspace** is now implemented: PDF on the left, findings
on the right, readable values and a compact document library. See the
[implementation report](docs/design/graphite-implementation.md).
Screenshots use a real synthetic PDF with mocked API responses, not a new model evaluation:
[document library](docs/design/implemented-b-library.png) ·
[analysis workspace](docs/design/implemented-b-workspace.png).

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
poll the processing status. TenderLens first reads the native PDF text. Pages with little or
no text are rendered in memory and recognized locally with Tesseract (`rus+eng` by default).
The API and interface expose whether extraction was `native`, `ocr`, or `mixed`, including the
number of OCR pages. Docker Compose installs the OCR binary and language packs automatically.

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
The React PDF viewer opens the cited page, highlights matching text-layer fragments, and scrolls
the evidence into view. Highlighting uses the selectable PDF text layer and never changes the
original uploaded file.

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
not measured in the default extractive mode. See
[`evals/README.md`](evals/README.md) and [`evals/baseline.json`](evals/baseline.json).

The OCR benchmark is a separate six-page, image-only Russian tender. It contains no text layer,
so the whole ingestion and question-answering path must use local OCR. On the reviewed Docker
CPU run, all 6 pages were recognized in 6.40 seconds and the five-question check reached 1.0
for Retrieval Hit@5, MRR, citation-page accuracy, citation-quote accuracy, correct refusal, and
analysis category/page recall.

```powershell
uv run python scripts/generate_ocr_fixture.py
uv run python scripts/evaluate_ocr.py
```

Each evaluation run changes only temporary PDF metadata to bypass upload deduplication, ensuring
that ingestion latency measures real OCR rather than a cached result. See
[`evals/ocr/README.md`](evals/ocr/README.md) and
[`evals/ocr/baseline_v1.json`](evals/ocr/baseline_v1.json).

An independent real-document holdout lives under [`evals/real`](evals/real). Its five official
source PDFs remain local, while the reviewed source registry, SHA-256 checks, 26 safe manual
annotations, two deterministic OCR stress variants, aggregate metrics, and promotion thresholds
are reproducible from Git. The first real holdout run improved retrieval Hit@1 from 0.736842 to
0.894737, but citation accuracy failed the end-to-end gate, so the reranker remains disabled by
default. See [`docs/ml/real-holdout-report.md`](docs/ml/real-holdout-report.md).

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
and [`docs/ml/progress-report.md`](docs/ml/progress-report.md) for the current metric report,
measurements, one remaining error, and limitations.

Windows helpers:

```powershell
.\scripts\dev.ps1
.\scripts\test.ps1
.\scripts\test-all.ps1
```

When running through Docker, no host OCR installation is required. A direct host run needs
Tesseract with `rus` and `eng` language data available on `PATH`; alternatively set
`OCR_TESSERACT_COMMAND` to the executable path or `OCR_ENABLED=false`.

OCR is intentionally bounded to 80 low-text pages per document by default. It targets printed,
upright text; handwriting, severe blur, unusual rotations, and complex table reconstruction may
reduce quality. The original PDF remains available so every extracted claim can be checked.

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
