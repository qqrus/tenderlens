# ruff: noqa: RUF001  # The verifier checks an intentional Russian disclaimer.

import argparse
import json
import re
from pathlib import Path

from pypdf import PdfReader

DEFAULT_PDF_DIR = Path("output/pdf/tenderlens-eval-v2")
EXPECTED_FORMAT_VERSION = "realistic-procurement-v1"
EXPECTED_LAYOUT_REFERENCE = "GOST R 7.0.97-2025"
MIN_PAGE_CHARACTERS = 350
MIN_DOCUMENT_CHARACTERS = 12_000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify generated TenderLens PDF test pack")
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    return parser.parse_args()


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def main() -> None:
    args = parse_args()
    manifest = json.loads((args.pdf_dir / "manifest.json").read_text(encoding="utf-8"))
    verified_questions = 0
    total_bytes = 0
    total_characters = 0
    for document in manifest:
        if document.get("format_version") != EXPECTED_FORMAT_VERSION:
            raise ValueError(f"unexpected format version: {document['filename']}")
        if document.get("layout_reference") != EXPECTED_LAYOUT_REFERENCE:
            raise ValueError(f"unexpected layout reference: {document['filename']}")
        if document.get("synthetic") is not True:
            raise ValueError(f"document is not marked synthetic: {document['filename']}")
        pdf_path = args.pdf_dir / document["filename"]
        reader = PdfReader(pdf_path)
        if len(reader.pages) != document["page_count"]:
            raise ValueError(f"page count mismatch: {pdf_path}")
        if document["page_count"] != 20:
            raise ValueError(f"realistic fixture must contain 20 pages: {pdf_path}")
        if reader.metadata is None or reader.metadata.title != document["title"]:
            raise ValueError(f"PDF title metadata mismatch: {pdf_path}")
        pages = [normalize(page.extract_text() or "") for page in reader.pages]
        if any(len(page) < MIN_PAGE_CHARACTERS for page in pages):
            raise ValueError(f"page has too little extractable text: {pdf_path}")
        document_text = " ".join(pages)
        if len(document_text) < MIN_DOCUMENT_CHARACTERS:
            raise ValueError(f"document is too short to be a realistic fixture: {pdf_path}")
        disclaimer = (
            "синтетический тестовый документ. не является извещением о закупке."
            if document["language"] == "ru"
            else "synthetic test document. not a procurement notice."
        )
        if any(disclaimer not in page for page in pages):
            raise ValueError(f"synthetic disclaimer missing from a page: {pdf_path}")
        if "44-фз" not in pages[2] or "7.0.97-2025" not in pages[2]:
            raise ValueError(f"legal and layout references missing from page 3: {pdf_path}")
        for question in document["questions"]:
            page_text = pages[question["expected_page"] - 1]
            if normalize(question["expected_quote"]) not in page_text:
                raise ValueError(
                    f"expected quote missing from {pdf_path} page {question['expected_page']}"
                )
            verified_questions += 1
        total_bytes += pdf_path.stat().st_size
        total_characters += len(document_text)
    report = {
        "documents": len(manifest),
        "pages": sum(item["page_count"] for item in manifest),
        "verified_questions": verified_questions,
        "total_bytes": total_bytes,
        "total_characters": total_characters,
        "status": "passed",
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
