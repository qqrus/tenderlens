import json
from pathlib import Path

import pytest

from tenderlens.ml.reranker import (
    DatasetSplit,
    RerankerExample,
    evaluate_ranking,
    expand_pairs,
    lexical_overlap_score,
    load_reranker_dataset,
    rank_examples,
    summarize_dataset,
    validate_reranker_dataset,
)


def make_example(
    *,
    example_id: str = "q-1",
    document_id: str = "doc-train",
    split: DatasetSplit = DatasetSplit.TRAIN,
) -> RerankerExample:
    return RerankerExample(
        id=example_id,
        document_id=document_id,
        split=split,
        language="ru",
        query="Какой размер пени?",
        positive="Пеня составляет 0,1% за каждый день просрочки.",
        negatives=[
            "Обеспечение заявки составляет 3% от начальной цены.",
            "Срок поставки составляет 60 календарных дней.",
        ],
        category="penalty",
    )


def test_dataset_rejects_document_leakage() -> None:
    examples = [
        make_example(),
        make_example(example_id="q-2", split=DatasetSplit.TEST),
    ]

    with pytest.raises(ValueError, match="document leakage"):
        validate_reranker_dataset(examples)


def test_dataset_loader_and_summary(tmp_path: Path) -> None:
    examples = [
        make_example(),
        make_example(
            example_id="q-validation",
            document_id="doc-validation",
            split=DatasetSplit.VALIDATION,
        ),
        make_example(example_id="q-test", document_id="doc-test", split=DatasetSplit.TEST),
    ]
    dataset_path = tmp_path / "reranker.jsonl"
    dataset_path.write_text(
        "\n".join(
            json.dumps(example.model_dump(mode="json"), ensure_ascii=False) for example in examples
        ),
        encoding="utf-8",
    )

    loaded = load_reranker_dataset(dataset_path)
    summary = summarize_dataset(loaded)

    assert summary.query_count == 3
    assert summary.pair_count == 9
    assert summary.document_count == 3
    assert summary.split_queries == {"train": 1, "validation": 1, "test": 1}


def test_expand_pairs_creates_positive_and_negative_labels() -> None:
    pairs = expand_pairs([make_example()])

    assert [pair.label for pair in pairs] == [1.0, 0.0, 0.0]
    assert all(pair.example_id == "q-1" for pair in pairs)


def test_ranking_metrics_reward_the_positive_passage() -> None:
    example = make_example()

    metrics = evaluate_ranking(
        [example],
        lambda pairs: [1.0 if "0,1%" in passage else 0.0 for _query, passage in pairs],
    )

    assert metrics.hit_at_1 == 1.0
    assert metrics.mrr == 1.0
    assert metrics.mean_positive_rank == 1.0


def test_tied_scores_are_not_treated_as_a_perfect_ranking() -> None:
    example = make_example()

    def scorer(pairs: list[tuple[str, str]]) -> list[float]:
        return [0.0] * len(pairs)

    metrics = evaluate_ranking([example], scorer)
    prediction = rank_examples([example], scorer)[0]

    assert metrics.hit_at_1 == 0.0
    assert metrics.hit_at_3 == 1.0
    assert metrics.mean_positive_rank == 3.0
    assert prediction.positive_rank == 3
    assert prediction.top_passage == example.negatives[-1]


def test_lexical_baseline_scores_related_text_higher() -> None:
    scores = lexical_overlap_score(
        [
            ("пеня за каждый день просрочки", "пеня 0,1 процента за каждый день просрочки"),
            ("пеня за каждый день просрочки", "гарантия на оборудование составляет три года"),
        ]
    )

    assert scores[0] > scores[1]
