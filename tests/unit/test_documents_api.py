from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tenderlens.api.dependencies import get_ingestion_service
from tenderlens.api.routes.documents import router
from tenderlens.core.errors import register_error_handlers
from tenderlens.db.models.document import Document
from tenderlens.domain.documents import DocumentStatus


class FakeIngestionService:
    def __init__(
        self,
        document: Document | None,
        deduplicated: bool = False,
        source_path: Path | None = None,
    ) -> None:
        self.document = document
        self.deduplicated = deduplicated
        self.source_path = source_path
        self.processed: list[UUID] = []

    async def register_upload(self, _file: object) -> tuple[Document, bool]:
        assert self.document is not None
        return self.document, self.deduplicated

    async def get_document(self, _document_id: UUID) -> Document | None:
        return self.document

    async def list_documents(self, *, limit: int, offset: int) -> tuple[list[Document], int]:
        documents = [] if self.document is None else [self.document]
        return documents[offset : offset + limit], len(documents)

    async def get_document_source(self, _document_id: UUID) -> tuple[Document, Path] | None:
        if self.document is None or self.source_path is None:
            return None
        return self.document, self.source_path

    async def process(self, document_id: UUID) -> None:
        self.processed.append(document_id)


def make_document() -> Document:
    now = datetime.now(UTC)
    return Document(
        id=uuid4(),
        original_filename="tender.pdf",
        content_type="application/pdf",
        sha256="a" * 64,
        size_bytes=100,
        status=DocumentStatus.UPLOADED.value,
        page_count=None,
        error_code=None,
        error_message=None,
        created_at=now,
        updated_at=now,
    )


def create_app(service: FakeIngestionService) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_ingestion_service] = lambda: service
    register_error_handlers(app)
    return app


def test_upload_schedules_processing() -> None:
    document = make_document()
    service = FakeIngestionService(document)

    with TestClient(create_app(service)) as client:
        response = client.post(
            "/api/v1/documents",
            files={"file": ("tender.pdf", BytesIO(b"%PDF-1.4"), "application/pdf")},
        )

    assert response.status_code == 202
    assert response.json()["document"]["id"] == str(document.id)
    assert service.processed == [document.id]


def test_duplicate_upload_is_not_scheduled_again() -> None:
    document = make_document()
    service = FakeIngestionService(document, deduplicated=True)

    with TestClient(create_app(service)) as client:
        response = client.post(
            "/api/v1/documents",
            files={"file": ("copy.pdf", BytesIO(b"%PDF-1.4"), "application/pdf")},
        )

    assert response.status_code == 202
    assert response.json()["deduplicated"] is True
    assert service.processed == []


def test_get_missing_document_returns_404() -> None:
    with TestClient(create_app(FakeIngestionService(None))) as client:
        response = client.get(f"/api/v1/documents/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


def test_list_documents_returns_pagination_metadata() -> None:
    document = make_document()

    with TestClient(create_app(FakeIngestionService(document))) as client:
        response = client.get("/api/v1/documents", params={"limit": 10, "offset": 0})

    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == str(document.id)
    assert response.json()["total"] == 1
    assert response.json()["limit"] == 10
    assert response.json()["offset"] == 0


def test_get_document_file_returns_private_inline_pdf(tmp_path: Path) -> None:
    document = make_document()
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\nfrontend viewer")

    with TestClient(create_app(FakeIngestionService(document, source_path=source))) as client:
        response = client.get(f"/api/v1/documents/{document.id}/file")

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4\nfrontend viewer"
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["content-disposition"].startswith("inline;")


def test_get_file_for_missing_document_returns_404() -> None:
    with TestClient(create_app(FakeIngestionService(None))) as client:
        response = client.get(f"/api/v1/documents/{uuid4()}/file")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"
