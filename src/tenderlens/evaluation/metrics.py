import math
from collections.abc import Sequence
from statistics import fmean


def hit_at_k(retrieved_pages: Sequence[int], expected_pages: set[int], k: int) -> float:
    return float(any(page in expected_pages for page in retrieved_pages[:k]))


def reciprocal_rank(retrieved_pages: Sequence[int], expected_pages: set[int]) -> float:
    for rank, page in enumerate(retrieved_pages, start=1):
        if page in expected_pages:
            return 1.0 / rank
    return 0.0


def mean(values: Sequence[float]) -> float:
    return fmean(values) if values else 0.0


def accuracy(correct: int, total: int) -> float:
    return correct / total if total else 0.0


def percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    if not 0 <= quantile <= 1:
        raise ValueError("quantile must be between 0 and 1")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def quote_contains_expected_fragment(quote: str, fragments: Sequence[str]) -> bool:
    normalized_quote = " ".join(quote.casefold().split())
    return any(" ".join(fragment.casefold().split()) in normalized_quote for fragment in fragments)
