import hashlib
from pathlib import Path, PurePath
from typing import Literal, Self

from pydantic import BaseModel, Field, HttpUrl, model_validator


class RealEvaluationQuestion(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,80}$")
    language: Literal["ru", "en"]
    question: str = Field(min_length=2, max_length=2_000)
    answerable: bool = True
    expected_pages: list[int] = Field(default_factory=list)
    expected_quote_fragments: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ground_truth(self) -> Self:
        if self.answerable and (not self.expected_pages or not self.expected_quote_fragments):
            raise ValueError("answerable questions require expected pages and quote fragments")
        if not self.answerable and (self.expected_pages or self.expected_quote_fragments):
            raise ValueError("unanswerable questions cannot contain expected evidence")
        if any(page < 1 for page in self.expected_pages):
            raise ValueError("expected page numbers must be positive")
        return self


class RealEvaluationDocument(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,80}$")
    filename: str = Field(pattern=r"(?i)^.+\.pdf$")
    language: Literal["ru", "en"]
    source_url: HttpUrl
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    personal_data_reviewed: Literal[True]
    redistribution: Literal["local_only", "permitted"] = "local_only"
    questions: list[RealEvaluationQuestion] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_document(self) -> Self:
        if PurePath(self.filename).name != self.filename:
            raise ValueError("filename must not contain a directory")
        if not any(question.answerable for question in self.questions):
            raise ValueError("each document requires at least one answerable question")
        if not any(not question.answerable for question in self.questions):
            raise ValueError("each document requires at least one unanswerable question")
        question_ids = [question.id for question in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("question ids must be unique within a document")
        return self


class RealEvaluationManifest(BaseModel):
    version: Literal["1.0"] = "1.0"
    name: str = Field(min_length=3, max_length=120)
    split: Literal["holdout"] = "holdout"
    documents: list[RealEvaluationDocument] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_documents(self) -> Self:
        document_ids = [document.id for document in self.documents]
        filenames = [document.filename.casefold() for document in self.documents]
        hashes = [document.sha256 for document in self.documents]
        if len(document_ids) != len(set(document_ids)):
            raise ValueError("document ids must be unique")
        if len(filenames) != len(set(filenames)):
            raise ValueError("document filenames must be unique")
        if len(hashes) != len(set(hashes)):
            raise ValueError("document hashes must be unique")
        return self


def load_real_evaluation_manifest(path: Path) -> RealEvaluationManifest:
    return RealEvaluationManifest.model_validate_json(path.read_text(encoding="utf-8"))


def validate_real_evaluation_files(
    manifest: RealEvaluationManifest,
    document_directory: Path,
) -> dict[str, int]:
    total_bytes = 0
    for document in manifest.documents:
        path = document_directory / document.filename
        if not path.is_file():
            raise ValueError(f"missing evaluation document: {document.filename}")
        if path.read_bytes()[:5] != b"%PDF-":
            raise ValueError(f"evaluation document is not a PDF: {document.filename}")
        digest = sha256_file(path)
        if digest != document.sha256:
            raise ValueError(f"SHA-256 mismatch for evaluation document: {document.filename}")
        total_bytes += path.stat().st_size

    questions = [question for document in manifest.documents for question in document.questions]
    return {
        "documents": len(manifest.documents),
        "questions": len(questions),
        "answerable_questions": sum(question.answerable for question in questions),
        "unanswerable_questions": sum(not question.answerable for question in questions),
        "total_bytes": total_bytes,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
