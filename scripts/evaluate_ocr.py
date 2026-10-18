import argparse
import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field
from pypdf import PdfReader, PdfWriter

from tenderlens.evaluation.metrics import (
    hit_at_k,
    mean,
    percentile,
    quote_contains_expected_fragment,
    reciprocal_rank,
)

DEFAULT_API_URL = "http://localhost:8000/api/v1"
DEFAULT_MANIFEST = Path("evals/ocr/manifest.json")
DEFAULT_REPORT = Path("evals/ocr/baseline_v1.json")


class OcrQuestion(BaseModel):
    id: str
    question: str
    answerable: bool
    expected_pages: list[int]
    expected_fragments: list[str]


class OcrAnalysisExpectation(BaseModel):
    category: str
    expected_pages: list[int]


class OcrManifest(BaseModel):
    version: str
    dataset: str
    document: Path
    language: str
    pages: int = Field(gt=0)
    analysis_expectations: list[OcrAnalysisExpectation]
    questions: list[OcrQuestion]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate TenderLens OCR, retrieval, and citations end to end."
    )
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--poll-timeout", type=float, default=240)
    return parser.parse_args()


def load_manifest(path: Path) -> OcrManifest:
    return OcrManifest.model_validate_json(path.read_text(encoding="utf-8"))


def verify_image_only_pdf(path: Path, expected_pages: int) -> int:
    reader = PdfReader(path)
    if len(reader.pages) != expected_pages:
        raise ValueError(f"Expected {expected_pages} pages, found {len(reader.pages)}")
    native_text_pages = sum(bool((page.extract_text() or "").strip()) for page in reader.pages)
    if native_text_pages:
        raise ValueError("OCR evaluation document unexpectedly contains a text layer")
    return native_text_pages


def create_unique_upload_copy(source: Path, destination: Path) -> None:
    """Change only metadata so every benchmark run performs OCR instead of deduping."""
    reader = PdfReader(source)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata(
        {
            "/Title": "TenderLens OCR evaluation",
            "/TenderLensRunId": str(uuid4()),
        }
    )
    with destination.open("wb") as output:
        writer.write(output)


def upload_and_wait(
    client: httpx.Client,
    api_url: str,
    pdf_path: Path,
    timeout: float,
) -> tuple[str, dict[str, Any], float, bool]:
    started = time.perf_counter()
    with pdf_path.open("rb") as source:
        response = client.post(
            f"{api_url}/documents",
            files={"file": (pdf_path.name, source, "application/pdf")},
        )
    response.raise_for_status()
    upload = response.json()
    document_id = str(upload["document"]["id"])
    deduplicated = bool(upload["deduplicated"])

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status_response = client.get(f"{api_url}/documents/{document_id}")
        status_response.raise_for_status()
        document = status_response.json()
        if document["status"] == "ready":
            latency_ms = (time.perf_counter() - started) * 1_000
            return document_id, document, latency_ms, deduplicated
        if document["status"] == "failed":
            raise RuntimeError(
                f"OCR ingestion failed: {document.get('error_code')} "
                f"{document.get('error_message')}"
            )
        time.sleep(0.25)
    raise TimeoutError(f"Document {document_id} did not become ready")


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


def evaluate_questions(
    client: httpx.Client,
    api_url: str,
    document_id: str,
    questions: list[OcrQuestion],
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for case in questions:
        answer, answer_latency = timed_post(
            client,
            f"{api_url}/documents/{document_id}/questions",
            {"question": case.question},
        )
        citations = answer["citations"]
        observation: dict[str, Any] = {
            "id": case.id,
            "question": case.question,
            "answerable": case.answerable,
            "answer": answer["answer"],
            "grounded": bool(answer["grounded"]),
            "citation_pages": [int(item["page_number"]) for item in citations],
            "answer_latency_ms": round(answer_latency, 2),
        }
        if case.answerable:
            search, search_latency = timed_post(
                client,
                f"{api_url}/documents/{document_id}/search",
                {"query": case.question, "limit": 5},
            )
            retrieved_pages = [int(item["page_number"]) for item in search["hits"]]
            expected_pages = set(case.expected_pages)
            observation.update(
                {
                    "retrieved_pages": retrieved_pages,
                    "retrieval_mode": search["mode"],
                    "hit_at_5": bool(hit_at_k(retrieved_pages, expected_pages, 5)),
                    "reciprocal_rank": reciprocal_rank(retrieved_pages, expected_pages),
                    "citation_page_correct": any(
                        int(item["page_number"]) in expected_pages for item in citations
                    ),
                    "citation_quote_correct": any(
                        quote_contains_expected_fragment(
                            str(item["quote"]), case.expected_fragments
                        )
                        for item in citations
                    ),
                    "search_latency_ms": round(search_latency, 2),
                }
            )
        else:
            observation["correct_refusal"] = not answer["grounded"] and not citations
        observations.append(observation)
    return observations


def evaluate_analysis(
    client: httpx.Client,
    api_url: str,
    document_id: str,
    expectations: list[OcrAnalysisExpectation],
) -> tuple[list[dict[str, Any]], float]:
    analysis, latency_ms = timed_post(
        client,
        f"{api_url}/documents/{document_id}/analysis",
        {},
    )
    observations: list[dict[str, Any]] = []
    for expectation in expectations:
        expected_pages = set(expectation.expected_pages)
        extracted_pages = [
            int(condition["citation"]["page_number"])
            for condition in analysis["conditions"]
            if condition["category"] == expectation.category
        ]
        observations.append(
            {
                "category": expectation.category,
                "expected_pages": expectation.expected_pages,
                "extracted_pages": extracted_pages,
                "correct": any(page in expected_pages for page in extracted_pages),
            }
        )
    return observations, latency_ms


def build_report(
    manifest: OcrManifest,
    document: dict[str, Any],
    native_text_pages: int,
    ingestion_latency_ms: float,
    deduplicated: bool,
    observations: list[dict[str, Any]],
    analysis_observations: list[dict[str, Any]],
    analysis_latency_ms: float,
) -> dict[str, Any]:
    answerable = [item for item in observations if item["answerable"]]
    unanswerable = [item for item in observations if not item["answerable"]]
    search_latencies = [float(item["search_latency_ms"]) for item in answerable]
    answer_latencies = [float(item["answer_latency_ms"]) for item in observations]
    ocr_page_count = int(document["ocr_page_count"])
    return {
        "dataset": manifest.dataset,
        "version": manifest.version,
        "document": str(manifest.document).replace("\\", "/"),
        "document_id": str(document["id"]),
        "extraction": {
            "method": document["extraction_method"],
            "page_count": int(document["page_count"]),
            "native_text_pages": native_text_pages,
            "ocr_page_count": ocr_page_count,
            "ocr_page_ratio": round(ocr_page_count / manifest.pages, 6),
            "deduplicated": deduplicated,
            "ingestion_latency_ms": round(ingestion_latency_ms, 2),
        },
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
            "analysis_category_page_recall": round(
                mean([float(item["correct"]) for item in analysis_observations]), 6
            ),
            "search_latency_p50_ms": round(percentile(search_latencies, 0.5), 2),
            "search_latency_p95_ms": round(percentile(search_latencies, 0.95), 2),
            "answer_latency_p50_ms": round(percentile(answer_latencies, 0.5), 2),
            "answer_latency_p95_ms": round(percentile(answer_latencies, 0.95), 2),
            "analysis_latency_ms": round(analysis_latency_ms, 2),
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
        "analysis_failures": [item for item in analysis_observations if not item["correct"]],
        "analysis": analysis_observations,
        "observations": observations,
    }


def main() -> int:
    args = parse_args()
    manifest = load_manifest(args.manifest)
    native_text_pages = verify_image_only_pdf(manifest.document, manifest.pages)
    api_url = args.api_url.rstrip("/")
    with TemporaryDirectory(prefix="tenderlens-ocr-eval-") as directory:
        upload_path = Path(directory) / manifest.document.name
        create_unique_upload_copy(manifest.document, upload_path)
        verify_image_only_pdf(upload_path, manifest.pages)
        with httpx.Client(timeout=300, trust_env=False) as client:
            document_id, document, ingestion_latency_ms, deduplicated = upload_and_wait(
                client, api_url, upload_path, args.poll_timeout
            )
            if deduplicated:
                raise RuntimeError("OCR benchmark unexpectedly reused a cached document")
            if document["extraction_method"] != "ocr":
                raise RuntimeError(
                    f"Expected OCR extraction, got {document['extraction_method']!r}"
                )
            if int(document["ocr_page_count"]) != manifest.pages:
                raise RuntimeError(
                    f"Expected {manifest.pages} OCR pages, got {document['ocr_page_count']}"
                )
            observations = evaluate_questions(client, api_url, document_id, manifest.questions)
            analysis_observations, analysis_latency_ms = evaluate_analysis(
                client,
                api_url,
                document_id,
                manifest.analysis_expectations,
            )

    report = build_report(
        manifest,
        document,
        native_text_pages,
        ingestion_latency_ms,
        deduplicated,
        observations,
        analysis_observations,
        analysis_latency_ms,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    args.output.write_text(f"{rendered}\n", encoding="utf-8")
    print(
        json.dumps(
            {"extraction": report["extraction"], "metrics": report["metrics"]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
