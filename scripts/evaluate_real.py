import argparse
import json
import time
from pathlib import Path
from typing import Any

import httpx

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
    validate_real_evaluation_files,
)

DEFAULT_API_URL = "http://localhost:8000/api/v1"
DEFAULT_MANIFEST = Path("evals/real/manifest.local.json")
DEFAULT_DOCUMENTS = Path("evals/real/documents")
DEFAULT_REPORT = Path("evals/real/reports/current.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate TenderLens on the private real-document holdout."
    )
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--documents", type=Path, default=DEFAULT_DOCUMENTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--poll-timeout", type=float, default=180)
    return parser.parse_args()


def wait_until_ready(client: httpx.Client, api_url: str, document_id: str, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"{api_url}/documents/{document_id}")
        response.raise_for_status()
        document = response.json()
        if document["status"] == "ready":
            return
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
) -> str:
    with pdf_path.open("rb") as source:
        response = client.post(
            f"{api_url}/documents",
            files={"file": (pdf_path.name, source, "application/pdf")},
        )
    response.raise_for_status()
    document_id = str(response.json()["document"]["id"])
    wait_until_ready(client, api_url, document_id, timeout)
    return document_id


def evaluate_document(
    client: httpx.Client,
    api_url: str,
    document_id: str,
    expected: RealEvaluationDocument,
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
            "grounded": bool(answer["grounded"]),
            "citation_pages": [item["page_number"] for item in answer["citations"]],
            "answer_latency_ms": round(answer_latency, 2),
        }
        if question.answerable:
            search, search_latency = timed_post(
                client,
                f"{api_url}/documents/{document_id}/search",
                {"query": question.question, "limit": 5},
            )
            retrieved_pages = [int(item["page_number"]) for item in search["hits"]]
            expected_pages = set(question.expected_pages)
            observation.update(
                {
                    "retrieved_pages": retrieved_pages,
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
        else:
            observation["correct_refusal"] = not answer["grounded"] and not answer["citations"]
        observations.append(observation)
    return observations


def build_report(name: str, observations: list[dict[str, Any]]) -> dict[str, Any]:
    answerable = [item for item in observations if item["answerable"]]
    unanswerable = [item for item in observations if not item["answerable"]]
    search_latencies = [float(item["search_latency_ms"]) for item in answerable]
    answer_latencies = [float(item["answer_latency_ms"]) for item in observations]
    return {
        "dataset": name,
        "documents": len({str(item["document_id"]) for item in observations}),
        "questions": len(observations),
        "metrics": {
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
        },
        "failures": [
            item
            for item in observations
            if (
                item["answerable"]
                and not all(
                    (
                        item["hit_at_5"],
                        item["citation_page_correct"],
                        item["citation_quote_correct"],
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
    observations: list[dict[str, Any]] = []
    with httpx.Client(timeout=240, trust_env=False) as client:
        for expected in manifest.documents:
            document_id = upload_document(
                client,
                api_url,
                args.documents / expected.filename,
                args.poll_timeout,
            )
            observations.extend(evaluate_document(client, api_url, document_id, expected))
    report = build_report(manifest.name, observations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    args.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
