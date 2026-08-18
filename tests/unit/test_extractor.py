from pathlib import Path

import pytest
from reportlab.pdfgen import canvas

from tenderlens.ingestion.extractor import PdfExtractionError, PdfTextExtractor


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

    pages = await PdfTextExtractor(max_pages=10).extract(path)

    assert [page.page_number for page in pages] == [1, 2]
    assert "Submission deadline" in pages[0].text
    assert "Budget" in pages[1].text


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
