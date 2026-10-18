from collections.abc import Sequence
from pathlib import Path

import pytest
from reportlab.pdfgen import canvas

from tenderlens.domain.documents import ExtractionMethod
from tenderlens.ingestion.extractor import (
    PdfExtractionError,
    PdfTextExtractor,
    TesseractPdfOcr,
)


class FakeOcrEngine:
    def __init__(self, texts: dict[int, str]) -> None:
        self.texts = texts
        self.requested_pages: list[int] = []

    def recognize_pages(self, path: Path, page_indexes: Sequence[int]) -> dict[int, str]:
        del path
        self.requested_pages = list(page_indexes)
        return {index: self.texts.get(index, "") for index in page_indexes}


def create_pdf(path: Path, page_texts: list[str | None]) -> None:
    pdf = canvas.Canvas(str(path))
    for text in page_texts:
        if text:
            pdf.drawString(72, 750, text)
        pdf.showPage()
    pdf.save()


@pytest.mark.asyncio
async def test_extractor_preserves_page_numbers(tmp_path: Path) -> None:
    path = tmp_path / "two-pages.pdf"
    create_pdf(path, ["Submission deadline: 20 August", "Budget: 1000000 RUB"])

    result = await PdfTextExtractor(max_pages=10).extract(path)

    assert [page.page_number for page in result.pages] == [1, 2]
    assert "Submission deadline" in result.pages[0].text
    assert "Budget" in result.pages[1].text
    assert result.method == ExtractionMethod.NATIVE
    assert result.ocr_page_count == 0


@pytest.mark.asyncio
async def test_extractor_rejects_pdf_without_text(tmp_path: Path) -> None:
    path = tmp_path / "blank.pdf"
    create_pdf(path, [None])

    with pytest.raises(PdfExtractionError) as error:
        await PdfTextExtractor(max_pages=10).extract(path)

    assert error.value.code == "no_extractable_text"


@pytest.mark.asyncio
async def test_extractor_enforces_page_limit(tmp_path: Path) -> None:
    path = tmp_path / "two-pages.pdf"
    create_pdf(path, ["one", "two"])

    with pytest.raises(PdfExtractionError) as error:
        await PdfTextExtractor(max_pages=1).extract(path)

    assert error.value.code == "too_many_pages"


@pytest.mark.asyncio
async def test_extractor_rejects_corrupt_pdf(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"%PDF-1.4\ncorrupt")

    with pytest.raises(PdfExtractionError) as error:
        await PdfTextExtractor(max_pages=10).extract(path)

    assert error.value.code == "unreadable_pdf"


@pytest.mark.asyncio
async def test_extractor_uses_ocr_for_image_only_pages(tmp_path: Path) -> None:
    path = tmp_path / "scan.pdf"
    create_pdf(path, [None])
    ocr = FakeOcrEngine({0: "Срок подачи заявок: 24 октября 2026 года."})

    result = await PdfTextExtractor(max_pages=10, ocr_engine=ocr).extract(path)

    assert ocr.requested_pages == [0]
    assert result.pages[0].text == "Срок подачи заявок: 24 октября 2026 года."
    assert result.method == ExtractionMethod.OCR
    assert result.ocr_page_count == 1


@pytest.mark.asyncio
async def test_extractor_combines_native_and_ocr_pages(tmp_path: Path) -> None:
    path = tmp_path / "mixed.pdf"
    create_pdf(path, ["Native text that is long enough to skip OCR extraction.", None])
    ocr = FakeOcrEngine({1: "Recognized second page with tender conditions."})

    result = await PdfTextExtractor(max_pages=10, ocr_engine=ocr).extract(path)

    assert ocr.requested_pages == [1]
    assert result.method == ExtractionMethod.MIXED
    assert result.ocr_page_count == 1


@pytest.mark.asyncio
async def test_extractor_enforces_ocr_page_limit(tmp_path: Path) -> None:
    path = tmp_path / "long-scan.pdf"
    create_pdf(path, [None, None])
    ocr = FakeOcrEngine({})

    with pytest.raises(PdfExtractionError) as error:
        await PdfTextExtractor(max_pages=10, ocr_engine=ocr, ocr_max_pages=1).extract(path)

    assert error.value.code == "ocr_page_limit_exceeded"


def test_tesseract_reports_missing_executable_before_rendering(tmp_path: Path) -> None:
    engine = TesseractPdfOcr(
        command="missing-tenderlens-tesseract",
        languages="rus+eng",
        dpi=200,
        timeout_seconds=10,
    )

    with pytest.raises(PdfExtractionError) as error:
        engine.recognize_pages(tmp_path / "scan.pdf", [0])

    assert error.value.code == "ocr_unavailable"
