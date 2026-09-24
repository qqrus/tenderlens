from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, ValidationError

Rate = Annotated[FiniteFloat, Field(ge=0, le=1)]
Latency = Annotated[FiniteFloat, Field(ge=0)]


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")


class Metrics(StrictModel):
    retrieval_hit_rate_at_5: Rate
    retrieval_mrr: Rate
    citation_page_accuracy: Rate
    citation_quote_accuracy: Rate
    unanswerable_refusal_accuracy: Rate
    ocr_success_rate: Rate
    answer_latency_p95_ms: Latency
    answer_joint_accuracy: Rate | None = None
    reranker_hit_rate_at_5: Rate | None = None
    reranker_mrr: Rate | None = None
    reranker_latency_p95_ms: Latency | None = None


class Report(StrictModel):
    evaluation_version: Literal["2.0"]
    dataset: str
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    documents: int = Field(gt=0)
    questions: int = Field(gt=0)
    answerable_questions: int = Field(gt=0)
    unanswerable_questions: int = Field(gt=0)
    reranked_questions: int = Field(ge=0)
    answer_gold_complete: bool
    metrics: Metrics


class MinimumDataset(StrictModel):
    documents: int = Field(gt=0)
    questions: int = Field(gt=0)


class Baseline(StrictModel):
    retrieval_hit_rate_at_5: Rate
    citation_page_accuracy: Rate
    citation_quote_accuracy: Rate
    unanswerable_refusal_accuracy: Rate
    ocr_success_rate: Rate
    answer_latency_p95_ms_max: Latency
    answer_joint_accuracy: Rate = 0.8


class Promotion(StrictModel):
    minimum_mrr_improvement: Rate
    allow_hit_rate_at_5_regression: bool
    latency_p95_ms_max: Latency


class Gate(StrictModel):
    minimum_dataset: MinimumDataset
    baseline: Baseline
    reranker_promotion: Promotion


def evaluate_gate(report: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed_report = Report.model_validate(report)
        parsed_gate = Gate.model_validate(gate)
    except ValidationError as exc:
        return {
            "dataset": str(report.get("dataset", "unknown")),
            "baseline_gate_passed": False,
            "reranker_gate_passed": False,
            "enable_reranker_by_default": False,
            "baseline_failures": [
                f"invalid_report_or_gate: {error['loc']} ({error['type']})"
                for error in exc.errors()
            ],
            "reranker_failures": ["invalid_report_or_gate"],
            "promotion_failures": ["A complete, finite v2 report is required."],
        }
    report = parsed_report.model_dump()
    gate = parsed_gate.model_dump()
    metrics = report["metrics"]
    failures: list[str] = []
    if report["answerable_questions"] + report["unanswerable_questions"] != report["questions"]:
        failures.append("dataset.question_counts_mismatch")
    if not report["answer_gold_complete"] or metrics["answer_joint_accuracy"] is None:
        failures.append("baseline.complete_answer_gold_required")
    elif metrics["answer_joint_accuracy"] < gate["baseline"]["answer_joint_accuracy"]:
        failures.append("baseline.answer_joint_accuracy_below_threshold")
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
    if any(
        metrics.get(key) is None
        for key in ("reranker_mrr", "reranker_hit_rate_at_5", "reranker_latency_p95_ms")
    ):
        reranker_failures.append("reranker metrics are missing")
    else:
        if report["reranked_questions"] != report["answerable_questions"]:
            reranker_failures.append("reranker question coverage is incomplete")
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
        # The current evaluator only reranks search hits. It cannot authorize a
        # different QA pipeline, regardless of a self-reported boolean in the JSON.
        "enable_reranker_by_default": False,
        "promotion_failures": ["Candidate end-to-end QA has not been evaluated by this evaluator."],
        "baseline_failures": failures,
        "reranker_failures": reranker_failures,
    }
