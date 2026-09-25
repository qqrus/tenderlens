"""Evaluate local OCR/reference excerpts without copying their text into a report."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from tenderlens.evaluation.ocr import OcrEvaluationInput, evaluate_ocr


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; choose a new report filename")
    raw = args.input.read_bytes()
    data = OcrEvaluationInput.model_validate_json(raw)
    report = evaluate_ocr(data).model_dump()
    report["input_sha256"] = hashlib.sha256(raw).hexdigest()
    report["measured_at"] = datetime.now(UTC).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        output.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps({key: report[key] for key in ("samples", "missing_predictions", "cer", "wer")})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
