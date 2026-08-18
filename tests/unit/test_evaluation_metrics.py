import pytest

from tenderlens.evaluation.metrics import (
    accuracy,
    hit_at_k,
    mean,
    percentile,
    quote_contains_expected_fragment,
    reciprocal_rank,
)


def test_retrieval_metrics_reward_expected_page_rank() -> None:
    pages = [4, 2, 1]

    assert hit_at_k(pages, {2}, 1) == 0.0
    assert hit_at_k(pages, {2}, 2) == 1.0
    assert reciprocal_rank(pages, {2}) == 0.5
    assert reciprocal_rank(pages, {9}) == 0.0


def test_accuracy_and_mean_handle_empty_inputs() -> None:
    assert accuracy(3, 4) == 0.75
    assert accuracy(0, 0) == 0.0
    assert mean([0.5, 1.0]) == 0.75
    assert mean([]) == 0.0


def test_percentile_uses_linear_interpolation() -> None:
    assert percentile([10.0, 20.0, 30.0, 40.0], 0.5) == 25.0
    assert percentile([10.0, 20.0, 30.0, 40.0], 0.95) == pytest.approx(38.5)
    assert percentile([], 0.95) == 0.0
    with pytest.raises(ValueError):
        percentile([1.0], 1.1)


def test_quote_match_is_case_and_whitespace_tolerant() -> None:
    assert quote_contains_expected_fragment(
        "Maximum  budget: 1 000 000 RUB",
        ["maximum budget: 1 000 000 rub"],
    )
    assert not quote_contains_expected_fragment("Deadline: tomorrow", ["Maximum budget"])
