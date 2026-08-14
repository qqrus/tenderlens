from io import BytesIO
from uuid import uuid4

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from tenderlens.core.errors import AppError
from tenderlens.ingestion.storage import FileSystemDocumentStorage


def make_upload(content: bytes, filename: str = "tender.pdf") -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": "application/pdf"}),
    )


@pytest.mark.asyncio
async def test_storage_streams_pdf_and_sanitizes_filename(tmp_path: object) -> None:
    from pathlib import Path

    root = Path(str(tmp_path)) / "uploads"
    storage = FileSystemDocumentStorage(root, max_upload_size_bytes=1_024)
    await storage.ensure_ready()
    document_id = uuid4()

    stored = await storage.save(
        document_id,
        make_upload(b"%PDF-1.4\nexample", "../unsafe/tender.pdf"),
    )

    assert stored.original_filename == "tender.pdf"
    assert stored.path == storage.source_path(document_id)
    assert stored.path.read_bytes() == b"%PDF-1.4\nexample"
    assert len(stored.sha256) == 64


@pytest.mark.asyncio
async def test_storage_rejects_non_pdf_and_cleans_up(tmp_path: object) -> None:
    from pathlib import Path

    storage = FileSystemDocumentStorage(Path(str(tmp_path)), max_upload_size_bytes=1_024)
    document_id = uuid4()

    with pytest.raises(AppError, match="valid PDF") as error:
        await storage.save(document_id, make_upload(b"not a pdf"))

    assert error.value.code == "invalid_pdf"
    assert not storage.source_path(document_id).exists()


@pytest.mark.asyncio
async def test_storage_enforces_size_limit_and_cleans_up(tmp_path: object) -> None:
    from pathlib import Path

    storage = FileSystemDocumentStorage(Path(str(tmp_path)), max_upload_size_bytes=8)
    document_id = uuid4()

    with pytest.raises(AppError) as error:
        await storage.save(document_id, make_upload(b"%PDF-1.4 oversized"))

    assert error.value.code == "document_too_large"
    assert not storage.source_path(document_id).exists()
