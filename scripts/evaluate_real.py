import argparse
import json
import math
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from tenderlens.evaluation.evidence import (
    evidence_matches,
    joint_answer_correct,
    span_reciprocal_rank,
)
from tenderlens.evaluation.metrics import (
    hit_at_k,
    mean,
    percentile,
    quote_contains_expected_fragment,
    reciprocal_rank,
)
from tenderlens.evaluation.real_dataset import (
    RealEvaluationDocument,
    load_real_evaluation_manifest,
    sha256_file,
    validate_real_evaluation_files,
)

DEFAULT_API_URL = "http://localhost:8000/api/v1"
DEFAULT_MANIFEST = Path("evals/real/holdout.json")
DEFAULT_DOCUMENTS = Path("evals/real/documents")
DEFAULT_REPORT = Path("evals/real/reports/current.json")
ScorePairs = Callable[[Sequence[tuple[str, str]]], Sequence[float]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate TenderLens on the private real-document holdout."
    )
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--documents", type=Path, default=DEFAULT_DOCUMENTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--poll-timeout", type=float, default=180)
    parser.add_argument("--candidate-limit", type=int, default=20)
    parser.add_argument(
        "--reranker-model",
        help="Optional Hugging Face ID or local CrossEncoder directory.",
    )
    parser.add_argument("--reranker-batch-size", type=int, default=8)
    return parser.parse_args()


def wait_until_ready(
    client: httpx.Client, api_url: str, document_id: str, timeout: float
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"{api_url}/documents/{document_id}")
        response.raise_for_status()
        document = response.json()
        if document["status"] == "ready":
            return dict(document)
        if document["status"] == "failed":
            raise RuntimeError(
                f"evaluation ingestion failed: {document.get('error_code')} "
                f"{document.get('error_message')}"
            )
        time.sleep(0.25)
    raise TimeoutError(f"document {document_id} did not become ready")


def timed_post(
    client: httpx.Client,
    url: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    response = client.post(url, json=payload)
    elapsed_ms = (time.perf_counter() - started) * 1_000
    response.raise_for_status()
    return response.json(), elapsed_ms


def upload_document(
    client: httpx.Client,
    api_url: str,
    pdf_path: Path,
    timeout: float,
) -> tuple[str, dict[str, Any], float]:
    started = time.perf_counter()
    with pdf_path.open("rb") as source:
        response = client.post(
            f"{api_url}/documents",
            files={"file": (pdf_path.name, source, "application/pdf")},
        )
    response.raise_for_status()
    document_id = str(response.json()["document"]["id"])
    document = wait_until_ready(client, api_url, document_id, timeout)
    ingestion_latency_ms = (time.perf_counter() - started) * 1_000
    return document_id, document, ingestion_latency_ms


def build_reranker(model_name: str, batch_size: int) -> ScorePairs:
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise SystemExit(
            "Reranker evaluation requires ML dependencies. Run: uv sync --dev --extra ml"
        ) from exc

    model = CrossEncoder(model_name)

    def score_pairs(pairs: Sequence[tuple[str, str]]) -> list[float]:
        scores = model.predict(list(pairs), batch_size=batch_size, show_progress_bar=False)
        return [float(score) for score in scores]

    return score_pairs


def rerank_hits(
    query: str,
    hits: list[dict[str, Any]],
    scorer: ScorePairs,
) -> tuple[list[dict[str, Any]], float]:
    started = time.perf_counter()
    if not hits:
        return [], 0.0
    scores = list(scorer([(query, str(hit["text"])) for hit in hits]))
    latency_ms = (time.perf_counter() - started) * 1_000
    if len(scores) != len(hits):
        raise ValueError("reranker returned a different number of scores than candidates")
    if not all(math.isfinite(score) for score in scores):
        raise ValueError("reranker scores must be finite")
    ranked = [
        hit
        for _score, _index, hit in sorted(
            zip(scores, range(len(hits)), hits, strict=True),
            key=lambda item: (item[0], -item[1]),
            reverse=True,
        )
    ]
    return ranked, latency_ms


def evaluate_document(
    client: httpx.Client,
    api_url: str,
    document_id: str,
    expected: RealEvaluationDocument,
    document_metadata: dict[str, Any],
    ingestion_latency_ms: float,
    candidate_limit: int,
    reranker: ScorePairs | None,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for question in expected.questions:
        answer, answer_latency = timed_post(
            client,
            f"{api_url}/documents/{document_id}/questions",
            {"question": question.question},
        )
        observation: dict[str, Any] = {
            "document_id": expected.id,
            "question_id": question.id,
            "language": question.language,
            "answerable": question.answerable,
            "extraction_profile": expected.extraction_profile,
            "extraction_method": document_metadata.get("extraction_method"),
            "ocr_page_count": int(document_metadata.get("ocr_page_count", 0)),
            "ingestion_latency_ms": round(ingestion_latency_ms, 2),
            "grounded": bool(answer["grounded"]),
            "answer": str(answer["answer"]),
            "citation_pages": [item["page_number"] for item in answer["citations"]],
            "citation_quotes": [str(item["quote"]) for item in answer["citations"]],
            "answer_latency_ms": round(answer_latency, 2),
        }
        if question.answerable:
            search, search_latency = timed_post(
                client,
                f"{api_url}/documents/{document_id}/search",
                {"query": question.question, "limit": candidate_limit},
            )
            hits = list(search["hits"])
            retrieved_pages = [int(item["page_number"]) for item in hits]
            expected_pages = set(question.expected_pages)
            observation.update(
                {
                    "span_hit_at_5": any(
                        evidence_matches(int(h["page_number"]), str(h["text"]), question)
                        for h in hits[:5]
                    ),
                    "span_reciprocal_rank": span_reciprocal_rank(hits, question),
                    "citation_joint_correct": any(
                        evidence_matches(int(c["page_number"]), str(c["quote"]), question)
                        for c in answer["citations"]
                    ),
                    "answer_joint_correct": joint_answer_correct(answer, question),
                    "false_refusal": not answer["grounded"],
                    "retrieved_pages": retrieved_pages,
                    "hit_at_1": bool(hit_at_k(retrieved_pages, expected_pages, 1)),
                    "hit_at_5": bool(hit_at_k(retrieved_pages, expected_pages, 5)),
                    "reciprocal_rank": reciprocal_rank(retrieved_pages, expected_pages),
                    "citation_page_correct": any(
                        int(item["page_number"]) in expected_pages for item in answer["citations"]
                    ),
                    "citation_quote_correct": any(
                        quote_contains_expected_fragment(
                            str(item["quote"]), question.expected_quote_fragments
                        )
                        for item in answer["citations"]
                    ),
                    "search_latency_ms": round(search_latency, 2),
                }
            )
            if reranker is not None:
                reranked, reranker_latency = rerank_hits(question.question, hits, reranker)
                reranked_pages = [int(item["page_number"]) for item in reranked]
                observation.update(
                    {
                        "reranked_pages": reranked_pages,
                        "reranker_hit_at_1": bool(hit_at_k(reranked_pages, expected_pages, 1)),
                        "reranker_hit_at_5": bool(hit_at_k(reranked_pages, expected_pages, 5)),
                        "reranker_reciprocal_rank": reciprocal_rank(reranked_pages, expected_pages),
                        "reranker_latency_ms": round(reranker_latency, 2),
                    }
                )
        else:
            observation["correct_refusal"] = not answer["grounded"] and not answer["citations"]
        observations.append(observation)
    return observations


def profile_metrics(observations: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    profiles: dict[str, dict[str, float]] = {}
    for profile in sorted({str(item["extraction_profile"]) for item in observations}):
        selected = [item for item in observations if item["extraction_profile"] == profile]
        answerable = [item for item in selected if item["answerable"]]
        profiles[profile] = {
            "questions": float(len(selected)),
            "retrieval_hit_rate_at_5": round(
                mean([float(item.get("hit_at_5", False)) for item in answerable]), 6
            ),
            "citation_page_accuracy": round(
                mean([float(item.get("citation_page_correct", False)) for item in answerable]),
                6,
            ),
            "citation_quote_accuracy": round(
                mean([float(item.get("citation_quote_correct", False)) for item in answerable]),
                6,
            ),
        }
    return profiles


def build_report(name: str, observations: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [item for item in observations if item["answerable"]]
    unanswerable = [item for item in observations if not item["answerable"]]
    search_latencies = [float(item["search_latency_ms"]) for item in answerable]
    answer_latencies = [float(item["answer_latency_ms"]) for item in observations]
    reranked = [item for item in answerable if "reranker_hit_at_5" in item]
    scan_documents = {
        str(item["document_id"]): item
        for item in observations
        if item["extraction_profile"] != "native"
    }
    ocr_success_rate = mean(
        [
            float(
                item.get("extraction_method") in {"ocr", "mixed"}
                and int(item.get("ocr_page_count", 0)) > 0
            )
            for item in scan_documents.values()
        ]
    )
    return {
        "evaluation_version": "2.0",
        "measured_at": datetime.now(UTC).isoformat(),
        "answer_gold_complete": bool(answerable)
        and all(item.get("answer_joint_correct") is not None for item in answerable),
        "answerable_questions": len(answerable),
        "unanswerable_questions": len(unanswerable),
        "reranked_questions": len(reranked),
        "candidate_qa_evaluated": False,
        "dataset": name,
        "documents": len({str(item["document_id"]) for item in observations}),
        "questions": len(observations),
        "metrics": {
            "retrieval_span_hit_rate_at_5": round(
                mean([float(item.get("span_hit_at_5", False)) for item in answerable]), 6
            ),
            "retrieval_span_mrr": round(
                mean([float(item.get("span_reciprocal_rank", 0)) for item in answerable]), 6
            ),
            "citation_joint_accuracy": round(
                mean([float(item.get("citation_joint_correct", False)) for item in answerable]), 6
            ),
            "answer_joint_accuracy": (
                round(mean([float(item["answer_joint_correct"]) for item in answerable]), 6)
                if answerable
                and all(item.get("answer_joint_correct") is not None for item in answerable)
                else None
            ),
            "false_refusal_rate": round(
                mean([float(item.get("false_refusal", False)) for item in answerable]), 6
            ),
            "retrieval_hit_rate_at_1": round(
                mean([float(item["hit_at_1"]) for item in answerable]), 6
            ),
            "retrieval_hit_rate_at_5": round(
                mean([float(item["hit_at_5"]) for item in answerable]), 6
            ),
            "retrieval_mrr": round(
                mean([float(item["reciprocal_rank"]) for item in answerable]), 6
            ),
            "citation_page_accuracy": round(
                mean([float(item["citation_page_correct"]) for item in answerable]), 6
            ),
            "citation_quote_accuracy": round(
                mean([float(item["citation_quote_correct"]) for item in answerable]), 6
            ),
            "unanswerable_refusal_accuracy": round(
                mean([float(item["correct_refusal"]) for item in unanswerable]), 6
            ),
            "search_latency_p50_ms": round(percentile(search_latencies, 0.5), 2),
            "search_latency_p95_ms": round(percentile(search_latencies, 0.95), 2),
            "answer_latency_p50_ms": round(percentile(answer_latencies, 0.5), 2),
            "answer_latency_p95_ms": round(percentile(answer_latencies, 0.95), 2),
            "ocr_success_rate": round(ocr_success_rate, 6),
            "reranker_hit_rate_at_1": (
                round(mean([float(item["reranker_hit_at_1"]) for item in reranked]), 6)
                if reranked
                else None
            ),
            "reranker_hit_rate_at_5": (
                round(mean([float(item["reranker_hit_at_5"]) for item in reranked]), 6)
                if reranked
                else None
            ),
            "reranker_mrr": (
                round(
                    mean([float(item["reranker_reciprocal_rank"]) for item in reranked]),
                    6,
                )
                if reranked
                else None
            ),
            "reranker_latency_p95_ms": (
                round(
                    percentile([float(item["reranker_latency_ms"]) for item in reranked], 0.95),
                    2,
                )
                if reranked
                else None
            ),
        },
        "profiles": profile_metrics(observations),
        "failures": [
            item
            for item in observations
            if (
                item["answerable"]
                and not all(
                    (
                        item["hit_at_5"],
                        item.get("citation_joint_correct", False),
                        item.get("answer_joint_correct", False),
                    )
                )
            )
            or (not item["answerable"] and not item["correct_refusal"])
        ],
        "observations": observations,
    }


def main() -> int:
    args = parse_args()
    manifest = load_real_evaluation_manifest(args.manifest)
    validate_real_evaluation_files(manifest, args.documents)
    api_url = args.api_url.rstrip("/")
    reranker = (
        build_reranker(args.reranker_model, args.reranker_batch_size)
        if args.reranker_model
        else None
    )
    observations: list[dict[str, Any]] = []
    with httpx.Client(timeout=240, trust_env=False) as client:
        for expected in manifest.documents:
            document_id, metadata, ingestion_latency_ms = upload_document(
                client,
                api_url,
                args.documents / expected.filename,
                args.poll_timeout,
            )
            observations.extend(
                evaluate_document(
                    client,
                    api_url,
                    document_id,
                    expected,
                    metadata,
                    ingestion_latency_ms,
                    args.candidate_limit,
                    reranker,
                )
            )
    report = build_report(manifest.name, observations)
    report["manifest_sha256"] = sha256_file(args.manifest)
    report["evaluation_config"] = {
        "candidate_limit": args.candidate_limit,
        "reranker_model": args.reranker_model,
        "reranker_batch_size": args.reranker_batch_size,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    args.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
