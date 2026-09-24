from typing import Any

import pytest

from tenderlens.evaluation.quality_gate import evaluate_gate


def report() -> dict[str, Any]:
    return {
        "evaluation_version": "2.0",
        "manifest_sha256": "a" * 64,
        "answer_gold_complete": True,
        "answerable_questions": 19,
        "unanswerable_questions": 7,
        "reranked_questions": 19,
        "dataset": "holdout",
        "documents": 7,
        "questions": 26,
        "metrics": {
            "answer_joint_accuracy": 0.9,
            "retrieval_hit_rate_at_5": 0.9,
            "retrieval_mrr": 0.8,
            "citation_page_accuracy": 0.9,
            "citation_quote_accuracy": 0.9,
            "unanswerable_refusal_accuracy": 0.9,
            "ocr_success_rate": 1.0,
            "answer_latency_p95_ms": 100.0,
            "reranker_hit_rate_at_5": 0.9,
            "reranker_mrr": 0.85,
            "reranker_latency_p95_ms": 200.0,
        },
    }


def gate() -> dict[str, Any]:
    return {
        "minimum_dataset": {"documents": 7, "questions": 26},
        "baseline": {
            "retrieval_hit_rate_at_5": 0.75,
            "citation_page_accuracy": 0.7,
            "citation_quote_accuracy": 0.65,
            "unanswerable_refusal_accuracy": 0.7,
            "ocr_success_rate": 0.5,
            "answer_latency_p95_ms_max": 5000.0,
        },
        "reranker_promotion": {
            "minimum_mrr_improvement": 0.02,
            "allow_hit_rate_at_5_regression": False,
            "latency_p95_ms_max": 1500.0,
        },
    }


def test_retrieval_metrics_alone_cannot_promote_a_qa_pipeline() -> None:
    decision = evaluate_gate(report(), gate())

    assert decision["baseline_gate_passed"] is True
    assert decision["reranker_gate_passed"] is True
    assert decision["enable_reranker_by_default"] is False
    assert decision["promotion_failures"]


def test_quality_gate_blocks_good_reranker_when_citations_fail() -> None:
    measured = report()
    measured["metrics"]["citation_page_accuracy"] = 0.4

    decision = evaluate_gate(measured, gate())

    assert decision["baseline_gate_passed"] is False
    assert decision["reranker_gate_passed"] is True
    assert decision["enable_reranker_by_default"] is False
    assert decision["baseline_failures"] == ["baseline.citation_page_accuracy: 0.4 < 0.7"]


def test_quality_gate_blocks_reranker_regression() -> None:
    measured = report()
    measured["metrics"]["reranker_hit_rate_at_5"] = 0.8

    decision = evaluate_gate(measured, gate())

    assert decision["reranker_gate_passed"] is False
    assert "reranker Hit@5 regressed" in decision["reranker_failures"]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.1, 1.1, "0.9"])
def test_invalid_metrics_fail_closed(value: Any) -> None:
    measured = report()
    measured["metrics"]["citation_quote_accuracy"] = value
    decision = evaluate_gate(measured, gate())
    assert decision["baseline_gate_passed"] is False
    assert decision["enable_reranker_by_default"] is False


def test_incomplete_gold_cannot_pass_gate() -> None:
    measured = report()
    measured["answer_gold_complete"] = False
    measured["metrics"]["answer_joint_accuracy"] = None
    assert evaluate_gate(measured, gate())["baseline_gate_passed"] is False
