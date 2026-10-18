import pytest
from pydantic import ValidationError

from tenderlens.evaluation.ocr import OcrEvaluationInput, OcrSample, edit_distance, evaluate_ocr


@pytest.mark.parametrize(
    ("reference", "prediction", "distance"),
    [
        ("abc", "abc", 0),
        ("abc", "axc", 1),
        ("abc", "ab", 1),
        ("ab", "abc", 1),
        ("abc", "", 3),
        ("", "abc", 3),
    ],
)
def test_edit_distance(reference: str, prediction: str, distance: int) -> None:
    assert edit_distance(reference, prediction) == distance


def test_missing_predictions_count_as_deletions_and_weighted_by_length() -> None:
    report = evaluate_ocr(
        OcrEvaluationInput(
            references=[OcrSample(id="a", text="one"), OcrSample(id="b", text="two three")],
            predictions=[OcrSample(id="a", text="one")],
        )
    )
    assert report.missing_predictions == 1
    assert report.cer == 9 / 12
    assert report.wer == 2 / 3
    assert report.results[1].cer == 1


def test_whitespace_normalization_does_not_hide_changed_digits() -> None:
    report = evaluate_ocr(
        OcrEvaluationInput(
            references=[OcrSample(id="a", text="Budget: 100\nRUB")],
            predictions=[OcrSample(id="a", text="Budget:  900 RUB")],
        )
    )
    assert report.results[0].character_errors == 1
    assert report.wer == 1 / 3
    assert "Budget" not in report.model_dump_json()


def test_insertions_can_make_error_rate_greater_than_one() -> None:
    report = evaluate_ocr(
        OcrEvaluationInput(
            references=[OcrSample(id="a", text="x")],
            predictions=[OcrSample(id="a", text="x y z")],
        )
    )
    assert report.cer == 4
    assert report.wer == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"references": [], "predictions": []},
        {"references": [{"id": "a", "text": " "}], "predictions": []},
        {"references": [{"id": "a", "text": "x"}], "predictions": [{"id": "b", "text": "x"}]},
        {"references": [{"id": "a", "text": "x"}] * 2, "predictions": []},
    ],
)
def test_invalid_inputs_rejected(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        OcrEvaluationInput.model_validate(payload)
