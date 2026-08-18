import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx
from reportlab.pdfgen import canvas

API_URL = "http://localhost:8000/api/v1"
POLL_TIMEOUT_SECONDS = 30


def create_sample_pdf(path: Path) -> None:
    pdf = canvas.Canvas(str(path))
    pdf.drawString(72, 750, "Submission deadline: 20 August 2026")
    pdf.showPage()
    pdf.drawString(72, 750, "Maximum budget: 1000000 RUB")
    pdf.showPage()
    pdf.drawString(72, 750, "Penalty: 0.1% of contract value per day")
    pdf.showPage()
    pdf.drawString(72, 750, "Supplier must provide an ISO 9001 certificate")
    pdf.showPage()
    pdf.save()


def main() -> int:
    with TemporaryDirectory(prefix="tenderlens-smoke-") as directory:
        pdf_path = Path(directory) / "sample-tender.pdf"
        create_sample_pdf(pdf_path)

        with (
            httpx.Client(timeout=180, trust_env=False) as client,
            pdf_path.open("rb") as pdf_file,
        ):
            response = client.post(
                f"{API_URL}/documents",
                files={"file": (pdf_path.name, pdf_file, "application/pdf")},
            )
            response.raise_for_status()
            payload = response.json()
            document_id = payload["document"]["id"]

            deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                status_response = client.get(f"{API_URL}/documents/{document_id}")
                status_response.raise_for_status()
                document = status_response.json()
                if document["status"] == "ready":
                    print(f"ingestion ready: id={document_id} pages={document['page_count']}")
                    search_response = client.post(
                        f"{API_URL}/documents/{document_id}/search",
                        json={"query": "maximum budget", "limit": 3},
                    )
                    search_response.raise_for_status()
                    search = search_response.json()
                    if not search["hits"]:
                        print("retrieval returned no hits", file=sys.stderr)
                        return 1
                    print(
                        f"retrieval ready: mode={search['mode']} "
                        f"top_page={search['hits'][0]['page_number']}"
                    )
                    answer_response = client.post(
                        f"{API_URL}/documents/{document_id}/questions",
                        json={"question": "What is the maximum budget?"},
                    )
                    answer_response.raise_for_status()
                    answer = answer_response.json()
                    if not answer["grounded"] or not answer["citations"]:
                        print("question answering returned no verified citation", file=sys.stderr)
                        return 1
                    if answer["citations"][0]["page_number"] != 2:
                        print("question answering cited the wrong page", file=sys.stderr)
                        return 1
                    print(
                        f"grounded answer ready: mode={answer['answer_mode']} "
                        f"citation_page={answer['citations'][0]['page_number']}"
                    )
                    analysis_response = client.post(f"{API_URL}/documents/{document_id}/analysis")
                    analysis_response.raise_for_status()
                    analysis = analysis_response.json()
                    found = set(analysis["coverage"]["found_categories"])
                    expected = {"deadline", "budget", "penalty", "requirement"}
                    if found != expected:
                        print(
                            f"analysis coverage mismatch: {sorted(found)}",
                            file=sys.stderr,
                        )
                        return 1
                    penalty_risk = next(
                        risk for risk in analysis["risks"] if risk["rule_id"] == "penalty_exposure"
                    )
                    if penalty_risk["citation"]["page_number"] != 3:
                        print("analysis cited the wrong penalty page", file=sys.stderr)
                        return 1
                    print(
                        "analysis ready: categories=4 "
                        f"penalty_page={penalty_risk['citation']['page_number']}"
                    )
                    return 0
                if document["status"] == "failed":
                    print(
                        f"ingestion failed: {document['error_code']} {document['error_message']}",
                        file=sys.stderr,
                    )
                    return 1
                time.sleep(0.25)

    print("ingestion timed out", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
