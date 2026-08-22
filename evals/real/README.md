# Independent real-document holdout

This directory defines the safe workflow for evaluating TenderLens on independently authored
public procurement documents. The PDF files and completed local manifest are intentionally not
committed. Public availability does not guarantee that a document is free of signatures,
personal data, bank details, or redistribution restrictions.

## Collection protocol

1. Download a candidate only from its official publisher into `evals/real/documents/`.
2. Review every page for personal data, signatures, secrets, and redistribution restrictions.
3. Keep the PDF local unless redistribution is explicitly permitted.
4. Copy `manifest.example.json` to `manifest.local.json` and record the source URL, SHA-256,
   language, and `personal_data_reviewed: true`.
5. Add at least one answerable and one genuinely unanswerable question per document. Annotate
   expected pages and short quote fragments without copying long copyrighted passages.
6. Run the validator before any metric calculation:

```powershell
uv run python scripts/validate_real_eval.py
uv run python scripts/evaluate_real.py
```

The holdout must never be used to generate training examples or tune thresholds. It exists only
for final comparison of baseline retrieval and TenderLens-Reranker.

## Candidate official sources

`sources.json` records starting points discovered on official public-sector websites. Candidate
status does not mean that a file has passed privacy or reuse review. Do not automate downloads or
commit the resulting documents.
