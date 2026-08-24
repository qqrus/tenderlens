# Real holdout quality report

## Outcome

The local TenderLens reranker is **not enabled by default**. It materially improves retrieval, but
the end-to-end citation gate fails. This is intentionally a conservative promotion decision.

| Metric | Baseline | Reranker | Gate / interpretation |
| --- | ---: | ---: | --- |
| Hit@1 | 0.736842 | 0.894737 | reranker improves first result |
| Hit@5 | 1.000000 | 1.000000 | no regression |
| MRR | 0.855263 | 0.938596 | +0.083333 |
| Citation page accuracy | 0.421053 | not integrated | below 0.70 gate |
| Citation quote accuracy | 0.368421 | not integrated | below 0.65 gate |
| Unanswerable refusal accuracy | 1.000000 | not applicable | passes |
| OCR success rate | 1.000000 | not applicable | both stress PDFs processed |
| Reranker latency p95 | — | 831.76 ms | below 1500 ms gate |

## What the result means

Retrieval is not the main bottleneck: the correct page appears in Top-5 for every answerable
question. The trained cross-encoder also improves first-result quality without losing recall.
Most end-to-end failures occur after retrieval, in the extractive answer provider:

- Russian questions over English evidence often have no shared lexical terms, so the provider
  refuses even though retrieval found the correct page.
- A relevant phrase can be cut at a chunk boundary; one retrieved chunk started with
  `ity should be...` instead of the preceding `Performance secur...`.
- Large table chunks contain several similar rows. The current sentence/segment heuristic may
  cite the first row rather than the specifically requested row.

## Next corrective stage

1. Add context-aware chunk stitching around adjacent chunks on the same page.
2. Use reranker scores when selecting answer evidence, not only in the offline comparison.
3. Replace bag-of-words quote selection with row/window extraction that preserves table labels and
   their values.
4. Add bilingual concept expansion for metadata questions, while keeping exact quote verification.
5. Re-run the frozen holdout without changing its questions or thresholds. Enable the reranker only
   if the full gate then passes.

Detailed observations remain in the ignored local report because they contain longer excerpts from
source documents. Aggregate results are published in `evals/real/result_v1.json`.
