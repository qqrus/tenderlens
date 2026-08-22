import argparse
import json
import time
from pathlib import Path
from statistics import fmean
from typing import Any

import httpx

DEFAULT_API_URL = "http://localhost:8000/api/v1"
DEFAULT_PDF_DIR = Path("output/pdf/tenderlens-eval-v2")
DEFAULT_REPORT = Path("evals/pdf_pack_api_report_v2.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate generated PDFs through TenderLens API")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--poll-timeout", type=float, default=180)
    return parser.parse_args()


def wait_until_ready(
    client: httpx.Client, api_url: str, document_id: str, timeout: float
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"{api_url}/documents/{document_id}")
        response.raise_for_status()
        document: dict[str, Any] = response.json()
        if document["status"] == "ready":
            return document
        if document["status"] == "failed":
            raise RuntimeError(
                f"ingestion failed: {document.get('error_code')} {document.get('error_message')}"
            )
        time.sleep(0.25)
    raise TimeoutError(f"document {document_id} did not become ready")


def normalized_contains(container: str, expected: str) -> bool:
    return " ".join(expected.casefold().split()) in " ".join(container.casefold().split())


def main() -> int:
    args = parse_args()
    manifest = json.loads((args.pdf_dir / "manifest.json").read_text(encoding="utf-8"))
    results: list[dict[str, Any]] = []
    ingestion_latencies: list[float] = []
    question_latencies: list[float] = []
    refusal_results: list[dict[str, Any]] = []

    with httpx.Client(timeout=240, trust_env=False) as client:
        for index, expected_document in enumerate(manifest, start=1):
            pdf_path = args.pdf_dir / expected_document["filename"]
            started = time.perf_counter()
            with pdf_path.open("rb") as pdf_file:
                upload = client.post(
                    f"{args.api_url}/documents",
                    files={"file": (pdf_path.name, pdf_file, "application/pdf")},
                )
            upload.raise_for_status()
            document_id = upload.json()["document"]["id"]
            document = wait_until_ready(client, args.api_url, document_id, args.poll_timeout)
            ingestion_ms = (time.perf_counter() - started) * 1_000
            ingestion_latencies.append(ingestion_ms)

            file_response = client.get(f"{args.api_url}/documents/{document_id}/file")
            file_ok = (
                file_response.status_code == 200
                and file_response.headers.get("content-type") == "application/pdf"
                and file_response.content.startswith(b"%PDF-")
            )
            page_count_ok = document["page_count"] == expected_document["page_count"]
            print(
                f"[{index}/{len(manifest)}] {pdf_path.name}: "
                f"pages={document['page_count']} ingestion_ms={ingestion_ms:.0f}"
            )

            for expected_question in expected_document["questions"]:
                question_started = time.perf_counter()
                response = client.post(
                    f"{args.api_url}/documents/{document_id}/questions",
                    json={"question": expected_question["question"]},
                )
                latency_ms = (time.perf_counter() - question_started) * 1_000
                question_latencies.append(latency_ms)
                response.raise_for_status()
                answer = response.json()
                citation = answer["citations"][0] if answer["citations"] else None
                results.append(
                    {
                        "document_id": expected_document["document_id"],
                        "language": expected_document["language"],
                        "category": expected_question["category"],
                        "grounded": answer["grounded"],
                        "citation_page_correct": bool(
                            citation
                            and citation["page_number"] == expected_question["expected_page"]
                        ),
                        "answer_contains_expected": bool(
                            citation
                            and normalized_contains(
                                f"{answer['answer']} {citation['quote']}",
                                expected_question["expected_answer"],
                            )
                        ),
                        "expected_answer": expected_question["expected_answer"],
                        "answer": answer["answer"],
                        "citation_quote": citation["quote"] if citation else None,
                        "cited_page": citation["page_number"] if citation else None,
                        "expected_page": expected_question["expected_page"],
                        "file_ok": file_ok,
                        "page_count_ok": page_count_ok,
                        "latency_ms": round(latency_ms, 2),
                    }
                )
            for question in expected_document["unanswerable_questions"]:
                question_started = time.perf_counter()
                response = client.post(
                    f"{args.api_url}/documents/{document_id}/questions",
                    json={"question": question},
                )
                latency_ms = (time.perf_counter() - question_started) * 1_000
                question_latencies.append(latency_ms)
                response.raise_for_status()
                answer = response.json()
                refusal_results.append(
                    {
                        "document_id": expected_document["document_id"],
                        "language": expected_document["language"],
                        "question": question,
                        "correct_refusal": not answer["grounded"] and not answer["citations"],
                        "answer": answer["answer"],
                        "latency_ms": round(latency_ms, 2),
                    }
                )

    question_count = len(results)
    category_results: dict[str, dict[str, float | int]] = {}
    for category in sorted({item["category"] for item in results}):
        category_items = [item for item in results if item["category"] == category]
        category_results[category] = {
            "questions": len(category_items),
            "citation_page_accuracy": round(
                fmean(float(item["citation_page_correct"]) for item in category_items), 6
            ),
            "answer_value_accuracy": round(
                fmean(float(item["answer_contains_expected"]) for item in category_items), 6
            ),
        }
    report = {
        "corpus": "synthetic_tender_corpus_v2",
        "documents": len(manifest),
        "questions": question_count,
        "unanswerable_questions": len(refusal_results),
        "metrics": {
            "grounded_rate": round(fmean(float(item["grounded"]) for item in results), 6),
            "citation_page_accuracy": round(
                fmean(float(item["citation_page_correct"]) for item in results), 6
            ),
            "answer_value_accuracy": round(
                fmean(float(item["answer_contains_expected"]) for item in results), 6
            ),
            "unanswerable_refusal_accuracy": round(
                fmean(float(item["correct_refusal"]) for item in refusal_results), 6
            ),
            "file_endpoint_success": round(fmean(float(item["file_ok"]) for item in results), 6),
            "page_count_accuracy": round(
                fmean(float(item["page_count_ok"]) for item in results), 6
            ),
            "mean_ingestion_latency_ms": round(fmean(ingestion_latencies), 2),
            "mean_question_latency_ms": round(fmean(question_latencies), 2),
            "max_question_latency_ms": round(max(question_latencies), 2),
        },
        "by_category": category_results,
        "failures": [
            item
            for item in results
            if not all(
                (
                    item["grounded"],
                    item["citation_page_correct"],
                    item["answer_contains_expected"],
                    item["file_ok"],
                    item["page_count_ok"],
                )
            )
        ],
        "refusal_failures": [item for item in refusal_results if not item["correct_refusal"]],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        f"{json.dumps(report, ensure_ascii=False, indent=2)}\n", encoding="utf-8"
    )
    print(json.dumps({"metrics": report["metrics"], "by_category": category_results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
