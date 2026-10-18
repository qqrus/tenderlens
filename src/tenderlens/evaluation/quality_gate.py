from typing import Any


def evaluate_gate(report: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    metrics = report["metrics"]
    failures: list[str] = []
    minimum = gate["minimum_dataset"]
    for field in ("documents", "questions"):
        if int(report[field]) < int(minimum[field]):
            failures.append(f"dataset.{field}: {report[field]} < {minimum[field]}")

    baseline = gate["baseline"]
    for metric in (
        "retrieval_hit_rate_at_5",
        "citation_page_accuracy",
        "citation_quote_accuracy",
        "unanswerable_refusal_accuracy",
        "ocr_success_rate",
    ):
        if float(metrics[metric]) < float(baseline[metric]):
            failures.append(f"baseline.{metric}: {metrics[metric]} < {baseline[metric]}")
    latency_limit = float(baseline["answer_latency_p95_ms_max"])
    if float(metrics["answer_latency_p95_ms"]) > latency_limit:
        failures.append(
            f"baseline.answer_latency_p95_ms: {metrics['answer_latency_p95_ms']} > {latency_limit}"
        )

    promotion = gate["reranker_promotion"]
    reranker_failures: list[str] = []
    if metrics.get("reranker_mrr") is None:
        reranker_failures.append("reranker metrics are missing")
    else:
        improvement = float(metrics["reranker_mrr"]) - float(metrics["retrieval_mrr"])
        required = float(promotion["minimum_mrr_improvement"])
        if improvement < required:
            reranker_failures.append(f"mrr improvement: {improvement:.6f} < {required}")
        if not bool(promotion["allow_hit_rate_at_5_regression"]) and float(
            metrics["reranker_hit_rate_at_5"]
        ) < float(metrics["retrieval_hit_rate_at_5"]):
            reranker_failures.append("reranker Hit@5 regressed")
        reranker_latency = float(metrics["reranker_latency_p95_ms"])
        reranker_limit = float(promotion["latency_p95_ms_max"])
        if reranker_latency > reranker_limit:
            reranker_failures.append(f"reranker latency p95: {reranker_latency} > {reranker_limit}")

    return {
        "dataset": report["dataset"],
        "baseline_gate_passed": not failures,
        "reranker_gate_passed": not reranker_failures,
        "enable_reranker_by_default": not failures and not reranker_failures,
        "baseline_failures": failures,
        "reranker_failures": reranker_failures,
    }
