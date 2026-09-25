# Real-document regression set (historical holdout)

## Current status — September 2026

This set has been inspected during development and is now a regression set, **not an
independent final holdout**. Historical annotations and result_v1.json are preserved.
The description below records its original composition, not a new human review.
The manifest has no independent answer gold (`expected_answers`), so evaluator v2
reports answer accuracy as null and blocks baseline admission until that gap is addressed.

The current gate never authorizes reranker promotion from retrieval scores alone.
It requires a future end-to-end candidate QA comparison and a new untouched test split;
the historical policy below is necessary but not sufficient.

OCR completion is not OCR correctness. See [OCR evaluation](ocr-evaluation.md)
for separate CER/WER measurement and the human review procedure.

This directory defines the privacy-reviewed evaluation set used for the final TenderLens quality
gate. It contains independently authored public procurement plans, manually written questions,
gold PDF pages, short gold fragments, and explicit unanswerable questions.

The source PDFs remain local under `evals/real/documents/`. Public availability does not imply
permission to redistribute a complete file, and a public PDF may still contain names, signatures,
contact details, or credentials. Git stores only official source URLs, SHA-256 digests, review
status, and short evaluation annotations.

## Dataset composition

- five native official World Bank procurement plans;
- two deterministic OCR stress variants derived from reviewed sources;
- 26 manually annotated questions: 19 answerable and 7 unanswerable;
- Russian cross-language questions over English evidence plus English questions;
- tables, repeated headers/footers, a slightly skewed noisy scan, and a 90-degree rotated scan.

`sources.json` records accepted and rejected candidates. `holdout.json` is the tracked gold
manifest. The holdout must not be converted into training examples or used to tune model weights.

## Reproduce locally

Download the five accepted files from the official URLs in `holdout.json` and preserve the listed
filenames. Then run:

```powershell
uv run python scripts/build_real_holdout_variants.py
uv run python scripts/validate_real_eval.py
docker compose up -d --build
uv run --extra ml python scripts/evaluate_real.py `
  --reranker-model models/tenderlens-reranker-v1/final
uv run python scripts/check_real_quality_gate.py
```

The evaluator writes detailed, ignored reports under `evals/real/reports/`. Those reports may
contain longer extracted quotes and are intentionally excluded from Git. The checked-in
`result_v1.json` contains only aggregate metrics and the promotion decision.

## Quality-gate policy

Thresholds are declared in `quality_gate.json` before evaluation. The reranker may become the API
default only when:

1. the baseline retrieval, citation, refusal, OCR, and latency gates pass;
2. reranking does not reduce Hit@5;
3. reranking improves MRR by at least the configured margin;
4. reranking latency remains below the configured p95 limit.

Failing the gate is a valid result. It identifies the next engineering task and prevents a model
from being promoted based only on synthetic data.
