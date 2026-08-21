import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from tenderlens.evaluation.real_dataset import (
    RealEvaluationManifest,
    validate_real_evaluation_files,
)


def build_manifest(pdf: bytes) -> RealEvaluationManifest:
    return RealEvaluationManifest.model_validate(
        {
            "name": "independent-real-holdout-v1",
            "documents": [
                {
                    "id": "public-tender-001",
                    "filename": "public-tender-001.pdf",
                    "language": "ru",
                    "source_url": "https://example.gov.invalid/public-tender-001.pdf",
                    "sha256": hashlib.sha256(pdf).hexdigest(),
                    "personal_data_reviewed": True,
                    "questions": [
                        {
                            "id": "public-tender-001-budget",
                            "language": "ru",
                            "question": "Какова начальная цена контракта?",
                            "expected_pages": [4],
                            "expected_quote_fragments": ["начальная цена"],
                        },
                        {
                            "id": "public-tender-001-insurance",
                            "language": "ru",
                            "question": "Какой номер страхового полиса?",
                            "answerable": False,
                        },
                    ],
                }
            ],
        }
    )


def test_real_manifest_validates_local_pdf_and_hash(tmp_path: Path) -> None:
    pdf = b"%PDF-1.7\nsynthetic unit-test placeholder"
    (tmp_path / "public-tender-001.pdf").write_bytes(pdf)

    summary = validate_real_evaluation_files(build_manifest(pdf), tmp_path)

    assert summary == {
        "documents": 1,
        "questions": 2,
        "answerable_questions": 1,
        "unanswerable_questions": 1,
        "total_bytes": len(pdf),
    }


def test_real_manifest_rejects_unreviewed_personal_data() -> None:
    pdf = b"%PDF-1.7"
    payload = build_manifest(pdf).model_dump(mode="json")
    payload["documents"][0]["personal_data_reviewed"] = False

    with pytest.raises(ValidationError, match="personal_data_reviewed"):
        RealEvaluationManifest.model_validate(payload)


def test_real_manifest_rejects_wrong_file_hash(tmp_path: Path) -> None:
    pdf = b"%PDF-1.7\nexpected"
    (tmp_path / "public-tender-001.pdf").write_bytes(b"%PDF-1.7\nchanged")

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        validate_real_evaluation_files(build_manifest(pdf), tmp_path)
