from collections.abc import AsyncIterator, Sequence
from io import BytesIO
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import UploadFile
from reportlab.pdfgen import canvas
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.datastructures import Headers

from tenderlens.core.errors import AppError
from tenderlens.db.base import Base
from tenderlens.db.models.document import DocumentChunk, DocumentPage
from tenderlens.domain.documents import DocumentStatus, ExtractionMethod
from tenderlens.ingestion.chunking import PageAwareChunker
from tenderlens.ingestion.extractor import PdfTextExtractor
from tenderlens.ingestion.service import DocumentIngestionService
from tenderlens.ingestion.storage import FileSystemDocumentStorage


class FakeOcrEngine:
    def recognize_pages(self, path: Path, page_indexes: Sequence[int]) -> dict[int, str]:
        del path
        return {
            index: "Срок подачи заявок: 24 октября 2026 года. Бюджет: 500 000 рублей."
            for index in page_indexes
        }


def pdf_bytes(text: str | None) -> bytes:
    output = BytesIO()
    pdf = canvas.Canvas(output)
    if text:
        pdf.drawString(72, 750, text)
    pdf.showPage()
    pdf.save()
    return output.getvalue()


def upload(content: bytes, filename: str = "tender.pdf") -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": "application/pdf"}),
    )


@pytest_asyncio.fixture
async def service(tmp_path: Path) -> AsyncIterator[DocumentIngestionService]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    storage = FileSystemDocumentStorage(tmp_path / "uploads", 1024 * 1024)
    await storage.ensure_ready()
    yield DocumentIngestionService(
        session_factory,
        storage,
        PdfTextExtractor(max_pages=20),
        PageAwareChunker(chunk_size_chars=200, overlap_chars=20),
    )
    await engine.dispose()


@pytest.mark.asyncio
async def test_service_processes_and_deduplicates_document(
    service: DocumentIngestionService,
) -> None:
    content = pdf_bytes("Deadline: 20 August. Budget: 1000000 RUB.")

    document, deduplicated = await service.register_upload(upload(content))
    await service.process(document.id)
    processed = await service.get_document(document.id)
    duplicate, is_duplicate = await service.register_upload(upload(content, "copy.pdf"))

    assert deduplicated is False
    assert processed is not None
    assert processed.status == DocumentStatus.READY.value
    assert processed.page_count == 1
    assert processed.extraction_method == ExtractionMethod.NATIVE.value
    assert processed.ocr_page_count == 0
    assert processed.table_geometry is not None
    assert processed.table_geometry["status"] == "disabled"
    assert duplicate.id == document.id
    assert is_duplicate is True

    async with service.session_factory() as session:
        page_count = await session.scalar(select(func.count()).select_from(DocumentPage))
        chunk_count = await session.scalar(select(func.count()).select_from(DocumentChunk))
    assert page_count == 1
    assert chunk_count == 1

    documents, total = await service.list_documents(limit=10, offset=0)
    source = await service.get_document_source(document.id)
    assert total == 1
    assert [item.id for item in documents] == [document.id]
    assert source is not None
    assert source[1].read_bytes() == content


@pytest.mark.asyncio
async def test_service_marks_document_failed_when_ocr_is_required(
    service: DocumentIngestionService,
) -> None:
    document, _ = await service.register_upload(upload(pdf_bytes(None)))

    await service.process(document.id)
    processed = await service.get_document(document.id)

    assert processed is not None
    assert processed.status == DocumentStatus.FAILED.value
    assert processed.error_code == "no_extractable_text"


@pytest.mark.asyncio
async def test_service_persists_ocr_metadata(service: DocumentIngestionService) -> None:
    service.table_geometry_enabled = True
    service.extractor = PdfTextExtractor(max_pages=20, ocr_engine=FakeOcrEngine())
    document, _ = await service.register_upload(upload(pdf_bytes(None), "scan.pdf"))

    await service.process(document.id)
    processed = await service.get_document(document.id)

    assert processed is not None
    assert processed.status == DocumentStatus.READY.value
    assert processed.extraction_method == ExtractionMethod.OCR.value
    assert processed.ocr_page_count == 1
    assert processed.table_geometry["status"] == "unsupported"


@pytest.mark.asyncio
async def test_table_failure_does_not_break_text_ingestion(
    service: DocumentIngestionService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("fake private text must not appear in logs")

    monkeypatch.setattr("tenderlens.ingestion.service.build_geometry_snapshot", fail)
    document, _ = await service.register_upload(upload(pdf_bytes("Budget 100 RUB")))
    await service.process(document.id)
    processed = await service.get_document(document.id)
    assert processed.status == "ready"
    assert processed.table_geometry["status"] == "failed"


@pytest.mark.asyncio
async def test_service_reports_missing_source_file(
    service: DocumentIngestionService,
) -> None:
    document, _ = await service.register_upload(upload(pdf_bytes("Budget: 100 RUB")))
    service.storage.source_path(document.id).unlink()

    with pytest.raises(AppError) as error:
        await service.get_document_source(document.id)

    assert error.value.code == "document_file_not_found"


@pytest.fixture
def native_table_pdf() -> bytes:
    source = (
        Path(__file__).resolve().parents[2] / "output/pdf/tenderlens-eval-v2/ru-servers-001.pdf"
    )
    return source.read_bytes()


@pytest.mark.asyncio
async def test_native_pdf_geometry_survives_database_roundtrip(
    service: DocumentIngestionService,
    native_table_pdf: bytes,
) -> None:
    pytest.importorskip("pdfplumber")
    service.table_geometry_enabled = True
    document, _ = await service.register_upload(upload(native_table_pdf, "synthetic-tables.pdf"))
    await service.process(document.id)
    processed = await service.get_document(document.id)
    assert processed is not None and processed.status == "ready"
    snapshot = processed.table_geometry
    assert snapshot is not None and snapshot["status"] == "ready"
    assert snapshot["source_sha256"] == processed.sha256
    assert snapshot["extractor_version"].startswith("pdfplumber/")
    assert len(snapshot["tables"]) > 0
    for table in snapshot["tables"]:
        assert 1 <= table["page_number"] <= processed.page_count
        for row in table["rows"]:
            for cell in row:
                if cell is not None:
                    assert 0 <= cell["box"]["x0"] < cell["box"]["x1"] <= table["page_width"]
    duplicate, deduplicated = await service.register_upload(upload(native_table_pdf, "copy.pdf"))
    assert deduplicated and duplicate.table_geometry == snapshot
