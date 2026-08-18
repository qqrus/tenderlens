from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tenderlens.db.models.document import DocumentChunk
from tenderlens.retrieval.embeddings import EmbeddingProvider

logger = structlog.get_logger(__name__)


class ChunkIndexingService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_provider: EmbeddingProvider,
        batch_size: int = 32,
    ) -> None:
        self.session_factory = session_factory
        self.embedding_provider = embedding_provider
        self.batch_size = batch_size

    async def index_missing(self, document_id: UUID) -> int:
        async with self.session_factory() as session:
            rows = (
                await session.execute(
                    select(DocumentChunk.id, DocumentChunk.text)
                    .where(
                        DocumentChunk.document_id == document_id,
                        DocumentChunk.embedding.is_(None),
                    )
                    .order_by(DocumentChunk.page_number, DocumentChunk.chunk_index)
                )
            ).all()

        indexed = 0
        for offset in range(0, len(rows), self.batch_size):
            batch = rows[offset : offset + self.batch_size]
            vectors = await self.embedding_provider.embed_documents([row.text for row in batch])
            async with self.session_factory() as session:
                for row, vector in zip(batch, vectors, strict=True):
                    await session.execute(
                        update(DocumentChunk)
                        .where(DocumentChunk.id == row.id)
                        .values(embedding=vector)
                    )
                await session.commit()
            indexed += len(batch)

        if indexed:
            logger.info(
                "document_chunks_indexed",
                document_id=str(document_id),
                chunk_count=indexed,
            )
        return indexed
