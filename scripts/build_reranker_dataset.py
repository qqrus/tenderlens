import argparse
import json
from dataclasses import asdict
from pathlib import Path

from tenderlens.ml.reranker import summarize_dataset, validate_reranker_dataset
from tenderlens.ml.synthetic_corpus import build_reranker_examples, load_scenarios

DEFAULT_SCENARIOS = Path("evals/synthetic_tender_corpus_v2.json")
DEFAULT_OUTPUT = Path("evals/reranker_dataset_v2.jsonl")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the deterministic TenderLens v2 dataset")
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the checked-in dataset differs from deterministic generation",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    examples = build_reranker_examples(load_scenarios(args.scenarios))
    validate_reranker_dataset(examples)
    rendered = "\n".join(
        json.dumps(example.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
        for example in examples
    )
    expected_content = f"{rendered}\n"
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != expected_content:
            raise SystemExit(
                f"{args.output} is stale; run: uv run python scripts/build_reranker_dataset.py"
            )
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(expected_content, encoding="utf-8")
    print(json.dumps(asdict(summarize_dataset(examples)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
