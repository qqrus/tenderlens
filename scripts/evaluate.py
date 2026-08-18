import argparse
import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
from reportlab.pdfgen import canvas

from tenderlens.evaluation.metrics import (
    accuracy,
    hit_at_k,
    mean,
    percentile,
    quote_contains_expected_fragment,
    reciprocal_rank,
)
from tenderlens.evaluation.models import EvaluationDataset

DEFAULT_API_URL = "http://localhost:8000/api/v1"
DEFAULT_DATASET = Path("evals/synthetic_tender_v1.json")
POLL_TIMEOUT_SECONDS = 30


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate TenderLens against a synthetic PDF.")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def load_dataset(path: Path) -> EvaluationDataset:
    return EvaluationDataset.model_validate_json(path.read_text(encoding="utf-8"))


def create_evaluation_pdf(path: Path, dataset: EvaluationDataset) -> None:
    pdf = canvas.Canvas(str(path))
    pdf.setTitle(dataset.name)
    pdf.setAuthor("TenderLens synthetic evaluation")
    for page_number, page_text in enumerate(dataset.pages, start=1):
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(72, 770, f"Synthetic tender - page {page_number}")
        pdf.setFont("Helvetica", 11)
        text = pdf.beginText(72, 730)
        for line in _wrap_text(page_text, width=88):
            text.textLine(line)
        pdf.drawText(text)
        pdf.showPage()
    pdf.save()


def _wrap_text(value: str, width: int) -> list[str]:
    words = value.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and len(candidate) > width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def upload_and_wait(client: httpx.Client, api_url: str, pdf_path: Path) -> str:
    with pdf_path.open("rb") as pdf_file:
        response = client.post(
            f"{api_url}/documents",
            files={"file": (pdf_path.name, pdf_file, "application/pdf")},
        )
    response.raise_for_status()
    document_id = response.json()["document"]["id"]
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        status_response = client.get(f"{api_url}/documents/{document_id}")
        status_response.raise_for_status()
        document = status_response.json()
        if document["status"] == "ready":
            return str(document_id)
        if document["status"] == "failed":
            raise RuntimeError(
                f"Evaluation PDF failed: {document['error_code']} {document['error_message']}"
            )
        time.sleep(0.25)
    raise TimeoutError("Evaluation PDF processing timed out.")


def timed_post(
    client: httpx.Client,
    url: str,
    payload: dict[str, Any] | None = None,
) -> tuple[httpx.Response, float]:
    started = time.perf_counter()
    response = client.post(url, json=payload)
    elapsed_ms = (time.perf_counter() - started) * 1_000
    response.raise_for_status()
    return response, elapsed_ms


def evaluate_questions(
    client: httpx.Client,
    api_url: str,
    document_id: str,
    dataset: EvaluationDataset,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    observations: list[dict[str, Any]] = []
    search_latencies: list[float] = []
    answer_latencies: list[float] = []
    citation_page_correct = 0
    citation_quote_correct = 0
    citation_total = 0

    for case in dataset.questions:
        search_response, search_ms = timed_post(
            client,
            f"{api_url}/documents/{document_id}/search",
            {"query": case.question, "limit": 5},
        )
        answer_response, answer_ms = timed_post(
            client,
            f"{api_url}/documents/{document_id}/questions",
            {"question": case.question},
        )
        search = search_response.json()
        answer = answer_response.json()
        retrieved_pages = [int(hit["page_number"]) for hit in search["hits"]]
        expected_pages = set(case.expected_pages)
        citations = answer["citations"]
        for citation in citations:
            citation_total += 1
            if int(citation["page_number"]) in expected_pages:
                citation_page_correct += 1
            if quote_contains_expected_fragment(
                str(citation["quote"]),
                case.expected_quote_fragments,
            ):
                citation_quote_correct += 1

        search_latencies.append(search_ms)
        answer_latencies.append(answer_ms)
        observations.append(
            {
                "id": case.id,
                "language": case.language,
                "expected_pages": case.expected_pages,
                "retrieved_pages": retrieved_pages,
                "reciprocal_rank": round(reciprocal_rank(retrieved_pages, expected_pages), 4),
                "hit_at_5": bool(hit_at_k(retrieved_pages, expected_pages, 5)),
                "citation_pages": [int(item["page_number"]) for item in citations],
                "grounded": bool(answer["grounded"]),
                "retrieval_mode": search["mode"],
                "search_latency_ms": round(search_ms, 2),
                "answer_latency_ms": round(answer_ms, 2),
            }
        )

    metrics = {
        "retrieval_hit_rate_at_5": round(
            mean([float(item["hit_at_5"]) for item in observations]), 4
        ),
        "retrieval_mrr": round(mean([float(item["reciprocal_rank"]) for item in observations]), 4),
        "citation_page_accuracy": round(accuracy(citation_page_correct, citation_total), 4),
        "citation_quote_accuracy": round(accuracy(citation_quote_correct, citation_total), 4),
        "grounded_answer_rate": round(mean([float(item["grounded"]) for item in observations]), 4),
        "search_latency_p50_ms": round(percentile(search_latencies, 0.5), 2),
        "search_latency_p95_ms": round(percentile(search_latencies, 0.95), 2),
        "answer_latency_p50_ms": round(percentile(answer_latencies, 0.5), 2),
        "answer_latency_p95_ms": round(percentile(answer_latencies, 0.95), 2),
    }
    return observations, metrics


def evaluate_analysis(
    client: httpx.Client,
    api_url: str,
    document_id: str,
    dataset: EvaluationDataset,
) -> tuple[list[dict[str, Any]], float, float, float]:
    response, latency_ms = timed_post(
        client,
        f"{api_url}/documents/{document_id}/analysis",
    )
    analysis = response.json()
    results: list[dict[str, Any]] = []
    categories_found = 0
    correct_pages = 0
    extracted_pages = 0
    for expectation in dataset.analysis_expectations:
        pages = [
            int(condition["citation"]["page_number"])
            for condition in analysis["conditions"]
            if condition["category"] == expectation.category.value
        ]
        matched = any(page in set(expectation.expected_pages) for page in pages)
        categories_found += int(matched)
        correct_pages += sum(page in set(expectation.expected_pages) for page in pages)
        extracted_pages += len(pages)
        results.append(
            {
                "category": expectation.category.value,
                "expected_pages": expectation.expected_pages,
                "extracted_pages": pages,
                "correct": matched,
            }
        )
    return (
        results,
        accuracy(categories_found, len(dataset.analysis_expectations)),
        accuracy(correct_pages, extracted_pages),
        latency_ms,
    )


def run_evaluation(api_url: str, dataset: EvaluationDataset) -> dict[str, Any]:
    with TemporaryDirectory(prefix="tenderlens-eval-") as directory:
        pdf_path = Path(directory) / f"{dataset.name}.pdf"
        create_evaluation_pdf(pdf_path, dataset)
        with httpx.Client(timeout=180, trust_env=False) as client:
            document_id = upload_and_wait(client, api_url, pdf_path)
            _, cold_start_ms = timed_post(
                client,
                f"{api_url}/documents/{document_id}/search",
                {"query": "tender contract overview", "limit": 5},
            )
            cases, metrics = evaluate_questions(client, api_url, document_id, dataset)
            analysis, analysis_recall, analysis_precision, analysis_ms = evaluate_analysis(
                client,
                api_url,
                document_id,
                dataset,
            )
    metrics["cold_start_search_latency_ms"] = round(cold_start_ms, 2)
    metrics["analysis_category_page_recall"] = round(analysis_recall, 4)
    metrics["analysis_category_page_precision"] = round(analysis_precision, 4)
    metrics["analysis_latency_ms"] = round(analysis_ms, 2)
    return {
        "dataset": dataset.name,
        "document_id": document_id,
        "question_count": len(dataset.questions),
        "metrics": metrics,
        "cases": cases,
        "analysis": analysis,
    }


def main() -> int:
    args = parse_args()
    dataset = load_dataset(args.dataset)
    result = run_evaluation(args.api_url.rstrip("/"), dataset)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
