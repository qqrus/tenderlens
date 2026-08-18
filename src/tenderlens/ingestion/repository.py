from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tenderlens.db.models.document import Document, DocumentChunk, DocumentPage
from tenderlens.domain.documents import DocumentStatus, ExtractedPage, TextChunk
from tenderlens.ingestion.storage import StoredUpload


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, document_id: UUID) -> Document | None:
        return await self.session.get(Document, document_id)

    async def get_by_sha256(self, sha256: str) -> Document | None:
        result = await self.session.execute(select(Document).where(Document.sha256 == sha256))
        return result.scalar_one_or_none()

    async def list_documents(self, *, limit: int, offset: int) -> tuple[list[Document], int]:
        documents = (
            await self.session.scalars(
                select(Document)
                .order_by(Document.created_at.desc(), Document.id.desc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
        total = await self.session.scalar(select(func.count(Document.id)))
        return list(documents), int(total or 0)

    def add_upload(self, stored: StoredUpload) -> Document:
        document = Document(
            id=stored.document_id,
            original_filename=stored.original_filename,
            content_type=stored.content_type,
            sha256=stored.sha256,
            size_bytes=stored.size_bytes,
            status=DocumentStatus.UPLOADED.value,
        )
        self.session.add(document)
        return document

    async def mark_processing(self, document_id: UUID) -> Document | None:
        document = await self.get(document_id)
        if document is None:
            return None
        document.status = DocumentStatus.PROCESSING.value
        document.error_code = None
        document.error_message = None
        return document

    async def save_extraction(
        self,
        document: Document,
        pages: list[ExtractedPage],
        chunks: list[TextChunk],
    ) -> None:
        pages_by_number: dict[int, DocumentPage] = {}
        for extracted_page in pages:
            page = DocumentPage(
                id=uuid4(),
                document_id=document.id,
                page_number=extracted_page.page_number,
                text=extracted_page.text,
                char_count=len(extracted_page.text),
            )
            pages_by_number[page.page_number] = page
            self.session.add(page)

        for chunk in chunks:
            page = pages_by_number[chunk.page_number]
            self.session.add(
                DocumentChunk(
                    document_id=document.id,
                    page_id=page.id,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    text=chunk.text,
                )
            )

        document.page_count = len(pages)
        document.status = DocumentStatus.READY.value
        document.error_code = None
        document.error_message = None

    async def mark_failed(self, document_id: UUID, code: str, message: str) -> None:
        document = await self.get(document_id)
        if document is None:
            return
        document.status = DocumentStatus.FAILED.value
        document.error_code = code
        document.error_message = message
