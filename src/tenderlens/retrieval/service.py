# ruff: noqa: RUF001  # Cyrillic intent and token patterns are intentional.

import re
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tenderlens.core.errors import AppError
from tenderlens.db.models.document import Document, DocumentChunk
from tenderlens.domain.documents import DocumentStatus
from tenderlens.retrieval.embeddings import EmbeddingError, EmbeddingProvider
from tenderlens.retrieval.indexing import ChunkIndexingService

logger = structlog.get_logger(__name__)

SEMANTIC_QUERY_EXPANSIONS: tuple[tuple[str, str], ...] = (
    (r"срок|дата", "deadline due date"),
    (r"бюджет|цен", "budget contract price"),
    (r"штраф|неустойк|пен[ияи]", "penalty fine liquidated damages"),
    (r"требован", "requirements eligibility"),
    (r"поставщик|участник", "supplier bidder"),
    (r"документ", "documents evidence certificate"),
    (r"опыт|проект", "experience completed projects"),
    (r"оплат", "payment"),
    (r"исполнен|контракт", "contract duration performance"),
    (r"гаранти", "warranty"),
)

LEXICAL_TOKEN_PATTERN = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+")
LEXICAL_STOP_WORDS = {
    "a",
    "an",
    "does",
    "is",
    "the",
    "what",
    "when",
    "which",
    "в",
    "где",
    "для",
    "до",
    "как",
    "какая",
    "какие",
    "каков",
    "какова",
    "какой",
    "когда",
    "на",
    "у",
    "что",
}

INTENT_RULES: tuple[tuple[re.Pattern[str], re.Pattern[str]], ...] = (
    (
        re.compile(
            r"начальн\w+.*цен|предельн\w+\s+бюджет|сумм\w+.*предлож|"
            r"maximum contract value|budget cap|offer not exceed",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:начальн\w+.*цен|предельн\w+\s+бюджет|цен\w+\s+предлож|"
            r"maximum (?:contract )?value|procurement budget|financial offer)"
            r".{0,260}(?:(?:руб|₽|RUB|USD|EUR|GBP)\s*\d[\d\s.,]*|"
            r"\d[\d\s.,]*\s*(?:руб|₽|RUB|USD|EUR|GBP))",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        re.compile(
            r"прием\w*\s+заяв|подат\w*\s+(?:заяв|предлож)|дедлайн.*подач|"
            r"proposal deadline|bid.*submit|submission cutoff",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:прием\w*\s+заяв|срок\w*\s+подач|направ\w+\s+заявк|"
            r"proposal deadline|proposals? must be received|submit.*offer no later)"
            r".{0,260}(?:\d{1,2}[:.]\d{2}|\d{1,2}\s+[A-Za-zА-Яа-яЁё]+\s+20\d{2})",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
)


def expand_semantic_query(query: str) -> str:
    expansions = [
        expansion
        for pattern, expansion in SEMANTIC_QUERY_EXPANSIONS
        if re.search(pattern, query, flags=re.IGNORECASE)
    ]
    if not expansions:
        return query
    return f"{query} {' '.join(expansions)}"


def build_lexical_tsquery(query: str) -> str:
    """Build a safe OR query so one conversational word cannot suppress all matches."""
    tokens = [
        token.casefold()
        for token in LEXICAL_TOKEN_PATTERN.findall(query)
        if len(token) >= 3 and token.casefold() not in LEXICAL_STOP_WORDS
    ]
    unique_tokens = list(dict.fromkeys(tokens))
    return " | ".join(unique_tokens)


def intent_match_score(query: str, passage: str) -> int:
    """Return a cheap high-precision reranking signal for common tender questions."""
    for question_pattern, evidence_pattern in INTENT_RULES:
        if question_pattern.search(query):
            return int(bool(evidence_pattern.search(passage)))
    return 0


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    chunk_id: UUID
    page_number: int
    text: str
    start_char: int
    end_char: int
    rrf_score: float
    semantic_score: float | None
    lexical_score: float | None


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    mode: str
    hits: list[RetrievalHit]


def reciprocal_rank_fusion(
    ranked_lists: list[list[UUID]],
    *,
    rrf_k: int,
) -> dict[UUID, float]:
    scores: dict[UUID, float] = {}
    for ranked_ids in ranked_lists:
        for rank, chunk_id in enumerate(ranked_ids, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    return scores


class HybridRetrievalService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_provider: EmbeddingProvider,
        indexing_service: ChunkIndexingService,
        *,
        dense_k: int,
        lexical_k: int,
        default_limit: int,
        rrf_k: int,
    ) -> None:
        self.session_factory = session_factory
        self.embedding_provider = embedding_provider
        self.indexing_service = indexing_service
        self.dense_k = dense_k
        self.lexical_k = lexical_k
        self.default_limit = default_limit
        self.rrf_k = rrf_k

    async def search(
        self, document_id: UUID, query: str, limit: int | None = None
    ) -> RetrievalResult:
        await self._validate_document(document_id)
        semantic_rows: list[tuple[DocumentChunk, float]] = []
        try:
            await self.indexing_service.index_missing(document_id)
            query_vector = await self.embedding_provider.embed_query(expand_semantic_query(query))
            semantic_rows = await self._semantic_search(document_id, query_vector)
        except EmbeddingError as exc:
            logger.warning(
                "semantic_retrieval_unavailable",
                document_id=str(document_id),
                reason=str(exc),
            )

        lexical_rows = await self._lexical_search(document_id, query)
        semantic_ids = [chunk.id for chunk, _score in semantic_rows]
        lexical_ids = [chunk.id for chunk, _score in lexical_rows]
        fused_scores = reciprocal_rank_fusion(
            [semantic_ids, lexical_ids],
            rrf_k=self.rrf_k,
        )
        final_limit = limit or self.default_limit
        chunks = {chunk.id: chunk for chunk, _score in [*semantic_rows, *lexical_rows]}
        intent_scores = {
            chunk_id: intent_match_score(query, chunk.text) for chunk_id, chunk in chunks.items()
        }
        ranked_ids = sorted(
            fused_scores,
            key=lambda chunk_id: (intent_scores[chunk_id], fused_scores[chunk_id]),
            reverse=True,
        )[:final_limit]

        semantic_scores = {chunk.id: score for chunk, score in semantic_rows}
        lexical_scores = {chunk.id: score for chunk, score in lexical_rows}
        hits = [
            RetrievalHit(
                chunk_id=chunk_id,
                page_number=chunks[chunk_id].page_number,
                text=chunks[chunk_id].text,
                start_char=chunks[chunk_id].start_char,
                end_char=chunks[chunk_id].end_char,
                rrf_score=fused_scores[chunk_id],
                semantic_score=semantic_scores.get(chunk_id),
                lexical_score=lexical_scores.get(chunk_id),
            )
            for chunk_id in ranked_ids
        ]
        return RetrievalResult(mode="hybrid" if semantic_rows else "lexical", hits=hits)

    async def _validate_document(self, document_id: UUID) -> None:
        async with self.session_factory() as session:
            document = await session.get(Document, document_id)
        if document is None:
            raise AppError(
                code="document_not_found",
                message="Document was not found.",
                status_code=404,
            )
        if document.status != DocumentStatus.READY.value:
            raise AppError(
                code="document_not_ready",
                message="Document processing has not completed.",
                status_code=409,
                details={"status": document.status},
            )

    async def _semantic_search(
        self,
        document_id: UUID,
        query_vector: list[float],
    ) -> list[tuple[DocumentChunk, float]]:
        embedding_column = cast(Any, DocumentChunk.embedding)
        distance = embedding_column.cosine_distance(query_vector).label("distance")
        async with self.session_factory() as session:
            rows = (
                await session.execute(
                    select(DocumentChunk, distance)
                    .where(
                        DocumentChunk.document_id == document_id,
                        DocumentChunk.embedding.is_not(None),
                    )
                    .order_by(distance)
                    .limit(self.dense_k)
                )
            ).all()
        return [(row[0], 1.0 - float(row[1])) for row in rows]

    async def _lexical_search(
        self,
        document_id: UUID,
        query: str,
    ) -> list[tuple[DocumentChunk, float]]:
        lexical_query = build_lexical_tsquery(query)
        if not lexical_query:
            return []
        ts_query = func.to_tsquery("simple", lexical_query)
        search_vector = func.to_tsvector("simple", func.coalesce(DocumentChunk.text, ""))
        rank = func.ts_rank_cd(search_vector, ts_query).label("rank")
        async with self.session_factory() as session:
            rows = (
                await session.execute(
                    select(DocumentChunk, rank)
                    .where(
                        DocumentChunk.document_id == document_id,
                        search_vector.op("@@")(ts_query),
                    )
                    .order_by(rank.desc())
                    .limit(self.lexical_k)
                )
            ).all()
        return [(row[0], float(row[1])) for row in rows]
