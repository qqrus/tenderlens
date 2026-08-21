# TenderLens synthetic PDF pack v2

These 12 files are fictional test tenders generated from
`evals/synthetic_tender_corpus_v2.json`. They contain no personal data and may be uploaded to
TenderLens locally or used in screenshots and demos.

Each PDF has three pages and eight known conditions: submission deadline, budget, delivery,
payment, bid security, performance security, delay penalty, and warranty. `manifest.json`
contains the expected answer value, verbatim source fragment, and page for 96 questions plus
24 questions that must produce an evidence-insufficient refusal.

Recommended first manual checks:

- `ru-servers-001.pdf` - Russian goods procurement;
- `ru-road-005.pdf` - Russian works procurement;
- `en-cloud-011.pdf` - English IT services;
- `en-cyber-024.pdf` - held-out English test scenario.

Regenerate and verify:

```powershell
uv run python scripts/generate_synthetic_pdfs.py
uv run python scripts/verify_pdf_pack.py
```

These fixtures are designed for regression testing. They do not demonstrate legal accuracy,
OCR support, or performance on arbitrary public tenders.
