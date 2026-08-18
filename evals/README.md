# TenderLens evaluation

The checked-in dataset is synthetic and contains no personal, confidential, or procurement
data. The script generates a PDF at runtime, uploads it through the public API, waits for
processing, and evaluates the same endpoints used by the frontend.

## Run

Start Docker Compose, then run:

```bash
uv run python scripts/evaluate.py
```

Windows:

```powershell
.\scripts\evaluate.ps1
```

To retain the full per-question output locally:

```bash
uv run python scripts/evaluate.py --output evals/reports/current.json
```

The `evals/reports/` directory is ignored because latency and document IDs are specific to
each local run. `evals/baseline.json` is a reviewed summary from one Docker CPU run.

## Metrics

- `retrieval_hit_rate_at_5`: fraction of questions whose expected page occurs in the top 5.
- `retrieval_mrr`: mean reciprocal rank of the first expected page.
- `citation_page_accuracy`: fraction of returned citations on an expected page.
- `citation_quote_accuracy`: fraction of citations containing the gold quote fragment.
- `grounded_answer_rate`: fraction of answers with at least one server-verified citation.
- `analysis_category_page_recall`: fraction of expected condition categories found on a gold page.
- `analysis_category_page_precision`: fraction of extracted category pages that are gold pages.
- latency percentiles: observed client-side request duration after the cold-start warmup.

## Limitations

This dataset is deliberately small and deterministic. It is useful for regression detection,
not for claiming production legal accuracy. Future datasets should include varied real-world
layouts that are licensed or generated for testing, negative/unanswerable questions, and OCR
fixtures. No real tenders containing personal data should be committed.
