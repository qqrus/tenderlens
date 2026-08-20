import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from tenderlens.ml.reranker import (
    DatasetSplit,
    evaluate_ranking,
    expand_pairs,
    load_reranker_dataset,
    select_split,
    summarize_dataset,
)

DEFAULT_DATASET = Path("evals/reranker_seed_v1.jsonl")
DEFAULT_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tune the TenderLens passage reranker")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--base-model", default=DEFAULT_MODEL)
    parser.add_argument("--output-dir", type=Path, default=Path("models/tenderlens-reranker"))
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--max-steps", type=int, default=-1)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=384)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def load_training_stack() -> tuple[Any, Any, Any, Any]:
    try:
        from datasets import Dataset
        from sentence_transformers import CrossEncoder
        from sentence_transformers.cross_encoder import (
            CrossEncoderTrainer,
            CrossEncoderTrainingArguments,
        )
        from sentence_transformers.cross_encoder.losses import BinaryCrossEntropyLoss
    except ImportError as exc:
        raise SystemExit(
            "Training requires optional ML dependencies. Run: uv sync --dev --extra ml"
        ) from exc
    return (
        Dataset,
        CrossEncoder,
        CrossEncoderTrainer,
        (
            CrossEncoderTrainingArguments,
            BinaryCrossEntropyLoss,
        ),
    )


def model_scorer(model: Any, batch_size: int) -> Any:
    def score_pairs(pairs: Sequence[tuple[str, str]]) -> list[float]:
        scores = model.predict(list(pairs), batch_size=batch_size, show_progress_bar=False)
        return [float(score) for score in scores]

    return score_pairs


def main() -> None:
    args = parse_args()
    Dataset, CrossEncoder, CrossEncoderTrainer, training_components = load_training_stack()
    CrossEncoderTrainingArguments, BinaryCrossEntropyLoss = training_components

    examples = load_reranker_dataset(args.dataset)
    train_examples = select_split(examples, DatasetSplit.TRAIN)
    validation_examples = select_split(examples, DatasetSplit.VALIDATION)
    test_examples = select_split(examples, DatasetSplit.TEST)
    train_pairs = expand_pairs(train_examples)
    validation_pairs = expand_pairs(validation_examples)

    train_dataset = Dataset.from_dict(
        {
            "sentence1": [pair.query for pair in train_pairs],
            "sentence2": [pair.passage for pair in train_pairs],
            "label": [pair.label for pair in train_pairs],
        }
    )
    validation_dataset = Dataset.from_dict(
        {
            "sentence1": [pair.query for pair in validation_pairs],
            "sentence2": [pair.passage for pair in validation_pairs],
            "label": [pair.label for pair in validation_pairs],
        }
    )

    model = CrossEncoder(args.base_model, num_labels=1, max_length=args.max_length)
    score_pairs = model_scorer(model, args.batch_size)
    base_validation = evaluate_ranking(validation_examples, score_pairs)
    base_test = evaluate_ranking(test_examples, score_pairs)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    full_training = args.max_steps < 0
    training_args = CrossEncoderTrainingArguments(
        output_dir=str(args.output_dir / "checkpoints"),
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        warmup_steps=0.1,
        eval_strategy="steps" if args.max_steps > 0 else "epoch",
        eval_steps=1 if args.max_steps > 0 else None,
        save_strategy="epoch" if full_training else "no",
        load_best_model_at_end=full_training,
        metric_for_best_model="eval_loss" if full_training else None,
        greater_is_better=False if full_training else None,
        save_total_limit=1,
        logging_steps=1,
        dataloader_pin_memory=False,
        seed=args.seed,
        report_to="none",
    )
    trainer = CrossEncoderTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=validation_dataset,
        loss=BinaryCrossEntropyLoss(model),
    )
    trainer.train()

    final_model_dir = args.output_dir / "final"
    model.save_pretrained(str(final_model_dir))
    tuned_scorer = model_scorer(model, args.batch_size)
    report = {
        "dataset": str(args.dataset),
        "dataset_summary": asdict(summarize_dataset(examples)),
        "base_model": args.base_model,
        "final_model": str(final_model_dir),
        "training": {
            "epochs": args.epochs,
            "max_steps": args.max_steps,
            "batch_size": args.batch_size,
            "learning_rate": args.learning_rate,
            "max_length": args.max_length,
            "seed": args.seed,
        },
        "before_training": {
            "validation": base_validation.as_dict(),
            "test": base_test.as_dict(),
        },
        "after_training": {
            "validation": evaluate_ranking(validation_examples, tuned_scorer).as_dict(),
            "test": evaluate_ranking(test_examples, tuned_scorer).as_dict(),
        },
    }
    report_path = args.output_dir / "training_report.json"
    report_path.write_text(
        f"{json.dumps(report, ensure_ascii=False, indent=2)}\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
