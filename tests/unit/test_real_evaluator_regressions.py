import runpy
from pathlib import Path
from unittest.mock import Mock

import pytest

EVALUATOR = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/evaluate_real.py"))


def test_empty_retrieval_does_not_call_model() -> None:
    scorer = Mock()
    assert EVALUATOR["rerank_hits"]("budget", [], scorer) == ([], 0.0)
    scorer.assert_not_called()


@pytest.mark.parametrize("scores", [[float("nan")], [float("inf")], []])
def test_invalid_reranker_scores_abort_evaluation(scores: list[float]) -> None:
    with pytest.raises(ValueError):
        EVALUATOR["rerank_hits"]("budget", [{"text": "Budget: 100 RUB"}], Mock(return_value=scores))


def test_empty_hits_remain_in_reranker_denominator() -> None:
    observation = {
        "document_id": "doc",
        "question_id": "q",
        "answerable": True,
        "extraction_profile": "native",
        "answer_latency_ms": 10,
        "search_latency_ms": 5,
        "hit_at_1": False,
        "hit_at_5": False,
        "reciprocal_rank": 0,
        "citation_page_correct": False,
        "citation_quote_correct": False,
        "reranker_hit_at_1": False,
        "reranker_hit_at_5": False,
        "reranker_reciprocal_rank": 0,
        "reranker_latency_ms": 0,
    }
    report = EVALUATOR["build_report"]("test", [observation])
    assert report["reranked_questions"] == report["answerable_questions"] == 1
    assert report["metrics"]["reranker_hit_rate_at_5"] == 0
    assert report["metrics"]["answer_joint_accuracy"] is None
    assert report["answer_gold_complete"] is False
