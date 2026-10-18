"""Exact edit-distance evaluation of preselected OCR excerpts, not PDF ingestion."""

import hashlib
import unicodedata
from collections.abc import Sequence
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OcrSample(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1, max_length=120)
    text: str = Field(max_length=4000)


class OcrEvaluationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    references: list[OcrSample] = Field(min_length=1)
    predictions: list[OcrSample]

    @model_validator(mode="after")
    def validate_samples(self) -> Self:
        for samples in (self.references, self.predictions):
            if len({sample.id for sample in samples}) != len(samples):
                raise ValueError("sample IDs must be unique")
        if any(not sample.text.strip() for sample in self.references):
            raise ValueError(
                "references must contain text; blank-page detection is a separate task"
            )
        if {s.id for s in self.predictions} - {s.id for s in self.references}:
            raise ValueError("predictions contain unknown sample IDs")
        return self


class OcrScore(BaseModel):
    sample_id: str
    missing_prediction: bool
    reference_sha256: str
    prediction_sha256: str
    character_errors: int
    reference_characters: int
    word_errors: int
    reference_words: int
    cer: float
    wer: float


class OcrReport(BaseModel):
    evaluation_version: str = "ocr-excerpts-1.0"
    normalization: str = "NFC; collapse whitespace; preserve case, punctuation, digits and alphabet"
    samples: int
    missing_predictions: int
    cer: float
    wer: float
    results: list[OcrScore]


def normalize_ocr_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def edit_distance(reference: Sequence[str], prediction: Sequence[str]) -> int:
    """Levenshtein distance with linear memory; includes insertions and deletions."""
    if len(reference) < len(prediction):
        reference, prediction = prediction, reference
    previous = list(range(len(prediction) + 1))
    for row, expected in enumerate(reference, 1):
        current = [row]
        for column, actual in enumerate(prediction, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (expected != actual),
                )
            )
        previous = current
    return previous[-1]


def evaluate_ocr(data: OcrEvaluationInput) -> OcrReport:
    predictions = {sample.id: sample.text for sample in data.predictions}
    scores: list[OcrScore] = []
    for sample in data.references:
        raw_prediction = predictions.get(sample.id, "")
        reference = normalize_ocr_text(sample.text)
        prediction = normalize_ocr_text(raw_prediction)
        character_errors = edit_distance(reference, prediction)
        reference_words = reference.split()
        word_errors = edit_distance(reference_words, prediction.split())
        scores.append(
            OcrScore(
                sample_id=sample.id,
                missing_prediction=sample.id not in predictions,
                reference_sha256=hashlib.sha256(sample.text.encode()).hexdigest(),
                prediction_sha256=hashlib.sha256(raw_prediction.encode()).hexdigest(),
                character_errors=character_errors,
                reference_characters=len(reference),
                word_errors=word_errors,
                reference_words=len(reference_words),
                cer=character_errors / len(reference),
                wer=word_errors / len(reference_words),
            )
        )
    return OcrReport(
        samples=len(scores),
        missing_predictions=sum(s.missing_prediction for s in scores),
        cer=sum(s.character_errors for s in scores) / sum(s.reference_characters for s in scores),
        wer=sum(s.word_errors for s in scores) / sum(s.reference_words for s in scores),
        results=scores,
    )
