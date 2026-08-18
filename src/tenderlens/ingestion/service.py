from pathlib import Path
from uuid import UUID, uuid4

import structlog
from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tenderlens.core.errors import AppError
from tenderlens.db.models.document import Document
from tenderlens.ingestion.chunking import PageAwareChunker
from tenderlens.ingestion.extractor import PdfExtractionError, PdfTextExtractor
from tenderlens.ingestion.repository import DocumentRepository
from tenderlens.ingestion.storage import FileSystemDocumentStorage

logger = structlog.get_logger(__name__)


class DocumentIngestionService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        storage: FileSystemDocumentStorage,
        extractor: PdfTextExtractor,
        chunker: PageAwareChunker,
    ) -> None:
        self.session_factory = session_factory
        self.storage = storage
        self.extractor = extractor
        self.chunker = chunker

    async def register_upload(self, upload: UploadFile) -> tuple[Document, bool]:
        document_id = uuid4()
        stored = await self.storage.save(document_id, upload)

        async with self.session_factory() as session:
            repository = DocumentRepository(session)
            existing = await repository.get_by_sha256(stored.sha256)
            if existing is not None:
                await self.storage.delete(document_id)
                return existing, True

            document = repository.add_upload(stored)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                await self.storage.delete(document_id)
                existing = await repository.get_by_sha256(stored.sha256)
                if existing is None:
                    raise
                return existing, True
            await session.refresh(document)
            return document, False

    async def get_document(self, document_id: UUID) -> Document | None:
        async with self.session_factory() as session:
            return await DocumentRepository(session).get(document_id)

    async def list_documents(self, *, limit: int, offset: int) -> tuple[list[Document], int]:
        async with self.session_factory() as session:
            return await DocumentRepository(session).list_documents(limit=limit, offset=offset)

    async def get_document_source(self, document_id: UUID) -> tuple[Document, Path] | None:
        document = await self.get_document(document_id)
        if document is None:
            return None
        source = self.storage.source_path(document_id)
        if not source.is_file():
            raise AppError(
                code="document_file_not_found",
                message="The original PDF is not available.",
                status_code=404,
            )
        return document, source

    async def process(self, document_id: UUID) -> None:
        async with self.session_factory() as session:
            repository = DocumentRepository(session)
            document = await repository.mark_processing(document_id)
            if document is None:
                logger.warning("document_processing_skipped", document_id=str(document_id))
                return
            await session.commit()

        try:
            pages = await self.extractor.extract(self.storage.source_path(document_id))
            chunks = self.chunker.chunk_pages(pages)
            async with self.session_factory() as session:
                repository = DocumentRepository(session)
                document = await repository.get(document_id)
                if document is None:
                    logger.warning("document_processing_skipped", document_id=str(document_id))
                    return
                await repository.save_extraction(document, pages, chunks)
                await session.commit()
            logger.info(
                "document_processed",
                document_id=str(document_id),
                page_count=len(pages),
                chunk_count=len(chunks),
            )
        except PdfExtractionError as exc:
            await self._mark_failed(document_id, exc.code, exc.message)
        except Exception:
            logger.exception("document_processing_failed", document_id=str(document_id))
            await self._mark_failed(
                document_id,
                "processing_failed",
                "Document processing failed unexpectedly.",
            )

    async def _mark_failed(self, document_id: UUID, code: str, message: str) -> None:
        async with self.session_factory() as session:
            await DocumentRepository(session).mark_failed(document_id, code, message)
            await session.commit()
        logger.warning(
            "document_marked_failed",
            document_id=str(document_id),
            error_code=code,
        )
