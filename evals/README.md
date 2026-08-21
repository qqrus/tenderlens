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

## Reranker training evaluation

The deterministic [`reranker_dataset_v2.jsonl`](reranker_dataset_v2.jsonl) contains 576
queries and 2,304 labeled pairs from 24 synthetic RU/EN documents. Documents, not individual
questions, are assigned to train/validation/test, and every query receives three same-document
hard negatives:

```bash
uv run python scripts/evaluate_reranker.py
uv run python scripts/build_reranker_dataset.py --check
```

The tuned model improved test Hit@1 from 0.875 to 0.989583 on the synthetic holdout. It remains
a `research_candidate` until independently reviewed real documents confirm the result. See
[`reranker_experiment_v1.json`](reranker_experiment_v1.json) and
[`docs/ml/reranker-training.md`](../docs/ml/reranker-training.md).

## PDF pack evaluation

Twelve generated 20-page procurement packages and their manifest live in
[`output/pdf/tenderlens-eval-v2`](../output/pdf/tenderlens-eval-v2). The 240-page pack covers 96
known answers across eight categories plus 24 questions whose topics are absent. Russian is the
primary language and four English packages test multilingual retrieval. Each document includes
legal boilerplate, similar dates and percentages, technical requirements, a draft contract and
annexes; every page is marked as synthetic. With Docker Compose running:

```bash
uv run python scripts/verify_pdf_pack.py
uv run python scripts/smoke_pdf_pack.py
```

The reviewed run achieved 1.0 citation-page, exact-value, and correct-refusal accuracy on this
synthetic regression pack, with 83.42 ms mean question latency after warm-up. It does not measure
arbitrary layouts, OCR, or legal correctness.
