import argparse
import json
import re
from pathlib import Path

from pypdf import PdfReader

DEFAULT_PDF_DIR = Path("output/pdf/tenderlens-eval-v2")


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
    for document in manifest:
        pdf_path = args.pdf_dir / document["filename"]
        reader = PdfReader(pdf_path)
        if len(reader.pages) != document["page_count"]:
            raise ValueError(f"page count mismatch: {pdf_path}")
        pages = [normalize(page.extract_text() or "") for page in reader.pages]
        if any(len(page) < 200 for page in pages):
            raise ValueError(f"page has too little extractable text: {pdf_path}")
        for question in document["questions"]:
            page_text = pages[question["expected_page"] - 1]
            if normalize(question["expected_quote"]) not in page_text:
                raise ValueError(
                    f"expected quote missing from {pdf_path} page {question['expected_page']}"
                )
            verified_questions += 1
        total_bytes += pdf_path.stat().st_size
    report = {
        "documents": len(manifest),
        "pages": sum(item["page_count"] for item in manifest),
        "verified_questions": verified_questions,
        "total_bytes": total_bytes,
        "status": "passed",
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
