import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from tenderlens.ml.reranker import (
    DatasetSplit,
    evaluate_ranking,
    lexical_overlap_score,
    load_reranker_dataset,
    rank_examples,
    select_split,
    summarize_dataset,
)

DEFAULT_DATASET = Path("evals/reranker_dataset_v2.jsonl")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate TenderLens reranker candidates")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--scorer", choices=("lexical", "model"), default="lexical")
    parser.add_argument(
        "--model",
        default="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
        help="Hugging Face model ID or local trained model directory",
    )
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--mistakes-limit", type=int, default=50)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def build_model_scorer(model_name: str, batch_size: int) -> Any:
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise SystemExit(
            "Model evaluation requires ML dependencies. Run: uv sync --dev --extra ml"
        ) from exc

    model = CrossEncoder(model_name)

    def score_pairs(pairs: Sequence[tuple[str, str]]) -> list[float]:
        scores = model.predict(list(pairs), batch_size=batch_size, show_progress_bar=False)
        return [float(score) for score in scores]

    return score_pairs


def main() -> None:
    args = parse_args()
    examples = load_reranker_dataset(args.dataset)
    summary = summarize_dataset(examples)
    scorer = (
        lexical_overlap_score
        if args.scorer == "lexical"
        else build_model_scorer(args.model, args.batch_size)
    )

    report: dict[str, object] = {
        "dataset": str(args.dataset),
        "scorer": args.scorer,
        "model": args.model if args.scorer == "model" else None,
        "summary": asdict(summary),
        "splits": {},
    }
    split_results: dict[str, object] = {}
    for split in DatasetSplit:
        split_examples = select_split(examples, split)
        metrics = evaluate_ranking(split_examples, scorer)
        mistakes = [
            asdict(prediction)
            for prediction in rank_examples(split_examples, scorer)
            if prediction.positive_rank > 1
        ]
        split_results[split.value] = {
            "metrics": metrics.as_dict(),
            "mistake_count": len(mistakes),
            "mistakes": mistakes[: args.mistakes_limit],
        }
    report["splits"] = split_results

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
