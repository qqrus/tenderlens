import json
import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from statistics import fmean
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

TOKEN_PATTERN = re.compile(r"[\w]+", flags=re.UNICODE)


class DatasetSplit(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


class RerankerExample(BaseModel):
    id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    split: DatasetSplit
    language: str = Field(pattern=r"^(en|ru)$")
    query: str = Field(min_length=3)
    positive: str = Field(min_length=3)
    negatives: list[str] = Field(min_length=2)
    category: str = Field(min_length=1)

    @field_validator("id", "document_id", "query", "positive", "category")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("negatives")
    @classmethod
    def strip_negatives(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values]

    @model_validator(mode="after")
    def validate_candidates(self) -> Self:
        normalized_positive = normalize_text(self.positive)
        normalized_negatives = [normalize_text(value) for value in self.negatives]
        if normalized_positive in normalized_negatives:
            raise ValueError("positive passage must not be repeated as a negative")
        if len(normalized_negatives) != len(set(normalized_negatives)):
            raise ValueError("negative passages must be unique")
        return self


@dataclass(frozen=True, slots=True)
class PairExample:
    example_id: str
    document_id: str
    query: str
    passage: str
    label: float


@dataclass(frozen=True, slots=True)
class DatasetSummary:
    query_count: int
    pair_count: int
    document_count: int
    split_queries: dict[str, int]
    languages: dict[str, int]


@dataclass(frozen=True, slots=True)
class RankingMetrics:
    query_count: int
    hit_at_1: float
    hit_at_3: float
    mrr: float
    ndcg_at_3: float
    mean_positive_rank: float

    def as_dict(self) -> dict[str, int | float]:
        return {
            "query_count": self.query_count,
            "hit_at_1": round(self.hit_at_1, 6),
            "hit_at_3": round(self.hit_at_3, 6),
            "mrr": round(self.mrr, 6),
            "ndcg_at_3": round(self.ndcg_at_3, 6),
            "mean_positive_rank": round(self.mean_positive_rank, 6),
        }


@dataclass(frozen=True, slots=True)
class RankingPrediction:
    example_id: str
    document_id: str
    category: str
    positive_rank: int
    positive_score: float
    top_passage: str
    top_score: float


ScorePairs = Callable[[Sequence[tuple[str, str]]], Sequence[float]]


def load_reranker_dataset(path: Path) -> list[RerankerExample]:
    examples: list[RerankerExample] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            examples.append(RerankerExample.model_validate_json(line))
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid reranker dataset line {line_number}: {exc}") from exc
    validate_reranker_dataset(examples)
    return examples


def validate_reranker_dataset(examples: Sequence[RerankerExample]) -> None:
    if not examples:
        raise ValueError("reranker dataset must not be empty")

    ids: set[str] = set()
    document_splits: dict[str, DatasetSplit] = {}
    present_splits: set[DatasetSplit] = set()
    for example in examples:
        if example.id in ids:
            raise ValueError(f"duplicate example id: {example.id}")
        ids.add(example.id)
        present_splits.add(example.split)

        previous_split = document_splits.setdefault(example.document_id, example.split)
        if previous_split != example.split:
            raise ValueError(
                f"document leakage: {example.document_id} occurs in "
                f"{previous_split.value} and {example.split.value}"
            )

    missing_splits = set(DatasetSplit) - present_splits
    if missing_splits:
        names = ", ".join(sorted(split.value for split in missing_splits))
        raise ValueError(f"dataset is missing required splits: {names}")


def summarize_dataset(examples: Sequence[RerankerExample]) -> DatasetSummary:
    split_queries = {split.value: 0 for split in DatasetSplit}
    languages: dict[str, int] = {}
    pair_count = 0
    for example in examples:
        split_queries[example.split.value] += 1
        languages[example.language] = languages.get(example.language, 0) + 1
        pair_count += 1 + len(example.negatives)
    return DatasetSummary(
        query_count=len(examples),
        pair_count=pair_count,
        document_count=len({example.document_id for example in examples}),
        split_queries=split_queries,
        languages=languages,
    )


def select_split(examples: Sequence[RerankerExample], split: DatasetSplit) -> list[RerankerExample]:
    return [example for example in examples if example.split == split]


def expand_pairs(examples: Sequence[RerankerExample]) -> list[PairExample]:
    pairs: list[PairExample] = []
    for example in examples:
        pairs.append(
            PairExample(
                example_id=example.id,
                document_id=example.document_id,
                query=example.query,
                passage=example.positive,
                label=1.0,
            )
        )
        pairs.extend(
            PairExample(
                example_id=example.id,
                document_id=example.document_id,
                query=example.query,
                passage=negative,
                label=0.0,
            )
            for negative in example.negatives
        )
    return pairs


def evaluate_ranking(
    examples: Sequence[RerankerExample], score_pairs: ScorePairs
) -> RankingMetrics:
    predictions = rank_examples(examples, score_pairs)
    if not predictions:
        return RankingMetrics(0, 0.0, 0.0, 0.0, 0.0, 0.0)

    ranks = [prediction.positive_rank for prediction in predictions]
    return RankingMetrics(
        query_count=len(ranks),
        hit_at_1=fmean(float(rank <= 1) for rank in ranks),
        hit_at_3=fmean(float(rank <= 3) for rank in ranks),
        mrr=fmean(1.0 / rank for rank in ranks),
        ndcg_at_3=fmean(1.0 / math.log2(rank + 1) if rank <= 3 else 0.0 for rank in ranks),
        mean_positive_rank=fmean(ranks),
    )


def rank_examples(
    examples: Sequence[RerankerExample], score_pairs: ScorePairs
) -> list[RankingPrediction]:
    predictions: list[RankingPrediction] = []
    for example in examples:
        passages = [example.positive, *example.negatives]
        scores = [float(score) for score in score_pairs([(example.query, p) for p in passages])]
        if len(scores) != len(passages):
            raise ValueError("scorer returned a different number of scores than input pairs")
        positive_score = scores[0]
        # A tied negative is counted ahead of the positive. This pessimistic rule prevents a
        # weak scorer that assigns the same score to everything from receiving a perfect result.
        positive_rank = 1 + sum(score >= positive_score for score in scores[1:])
        top_index = max(range(len(scores)), key=lambda index: (scores[index], index))
        predictions.append(
            RankingPrediction(
                example_id=example.id,
                document_id=example.document_id,
                category=example.category,
                positive_rank=positive_rank,
                positive_score=positive_score,
                top_passage=passages[top_index],
                top_score=scores[top_index],
            )
        )
    return predictions


def lexical_overlap_score(pairs: Sequence[tuple[str, str]]) -> list[float]:
    scores: list[float] = []
    for query, passage in pairs:
        query_tokens = set(tokenize(query))
        passage_tokens = set(tokenize(passage))
        if not query_tokens or not passage_tokens:
            scores.append(0.0)
            continue
        overlap = len(query_tokens & passage_tokens)
        scores.append(overlap / math.sqrt(len(query_tokens) * len(passage_tokens)))
    return scores


def normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def tokenize(value: str) -> list[str]:
    return [
        match.group(0)
        for match in TOKEN_PATTERN.finditer(value.casefold())
        if len(match.group(0)) > 2
    ]
