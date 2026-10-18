# OCR evaluation fixture

`ru-scanned-tender-001.pdf` is a six-page synthetic image-only procurement document. It contains
no real organization, address, signature, bank details, or personal data. A normal PDF text
extractor must return an empty string; TenderLens therefore has to use its local RU/EN OCR path.

Generate and verify the fixture:

```powershell
uv run python scripts/generate_ocr_fixture.py
```

Run the end-to-end OCR evaluation against Docker Compose:

```powershell
uv run python scripts/evaluate_ocr.py
```

The five-question manifest checks deadline, budget, delivery term, penalty, and one required
refusal. The evaluator makes a temporary metadata-only copy for every run, preventing upload
deduplication from hiding OCR latency. The reviewed Docker CPU baseline recognized all six pages
in 6.40 seconds and reached 1.0 for Retrieval Hit@5, MRR, citation-page accuracy,
citation-quote accuracy, refusal accuracy, and analysis category/page recall. Full observations are stored in
`baseline_v1.json`.

The fixture measures regression behaviour only and does not replace an independently annotated
real-document holdout. Printed upright text is the supported OCR target; handwriting, severe
blur, rotations, and exact table structure remain known limitations.
