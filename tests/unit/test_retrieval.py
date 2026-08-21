from collections.abc import AsyncIterator, Sequence
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tenderlens.core.errors import AppError
from tenderlens.db.base import Base
from tenderlens.db.models.document import Document, DocumentChunk, DocumentPage
from tenderlens.domain.documents import DocumentStatus
from tenderlens.retrieval.embeddings import EmbeddingError
from tenderlens.retrieval.indexing import ChunkIndexingService
from tenderlens.retrieval.service import (
    HybridRetrievalService,
    build_lexical_tsquery,
    expand_semantic_query,
    intent_match_score,
    reciprocal_rank_fusion,
)


class FakeEmbeddingProvider:
    dimensions = 384

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if self.fail:
            raise EmbeddingError("unavailable")
        return [[float(index == 0) for index in range(self.dimensions)] for _text in texts]

    async def embed_query(self, _text: str) -> list[float]:
        if self.fail:
            raise EmbeddingError("unavailable")
        return [1.0] + [0.0] * (self.dimensions - 1)


class FakeIndexer:
    async def index_missing(self, _document_id: UUID) -> int:
        return 0


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[Any]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield cast(async_sessionmaker[Any], factory)
    await engine.dispose()


def make_chunk(page_number: int, text: str) -> DocumentChunk:
    return DocumentChunk(
        id=uuid4(),
        document_id=uuid4(),
        page_id=uuid4(),
        page_number=page_number,
        chunk_index=0,
        start_char=0,
        end_char=len(text),
        text=text,
    )


def test_reciprocal_rank_fusion_rewards_cross_list_matches() -> None:
    first, second, third = uuid4(), uuid4(), uuid4()

    scores = reciprocal_rank_fusion([[first, second], [second, third]], rrf_k=60)

    assert scores[second] > scores[first]
    assert scores[second] > scores[third]


def test_semantic_query_expansion_adds_bilingual_tender_terms() -> None:
    question = (
        "\u041a\u0430\u043a\u0438\u0435 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u044b "
        "\u0438 \u043e\u043f\u044b\u0442 \u0434\u043e\u043b\u0436\u0435\u043d "
        "\u043f\u0440\u0435\u0434\u043e\u0441\u0442\u0430\u0432\u0438\u0442\u044c "
        "\u043f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a?"
    )
    expanded = expand_semantic_query(question)

    assert "supplier bidder" in expanded
    assert "documents evidence certificate" in expanded
    assert "experience completed projects" in expanded
    assert expand_semantic_query("maximum budget") == "maximum budget"


def test_lexical_query_uses_informative_terms_with_or_semantics() -> None:
    query = build_lexical_tsquery("Какова начальная максимальная цена?")

    assert query == "начальная | максимальная | цена"


def test_intent_score_prefers_value_bearing_budget_and_deadline_passages() -> None:
    budget_question = "Какова начальная максимальная цена?"
    budget_value = "Начальная цена: 42 600 000 рублей, включая НДС."
    english_budget_value = "The procurement budget is capped at USD 280,000."
    budget_explanation = "Обоснование начальной цены подготовлено рыночным методом."
    deadline_question = "Когда заканчивается прием заявок?"
    deadline_value = "Срок подачи заявок: 2 октября 2026 года в 12:00."
    deadline_distractor = "Дата проекта 14 августа 2026 года не является сроком подачи заявок."

    assert intent_match_score(budget_question, budget_value) == 1
    assert intent_match_score("What is the budget cap?", english_budget_value) == 1
    assert intent_match_score(budget_question, budget_explanation) == 0
    assert intent_match_score(deadline_question, deadline_value) == 1
    assert intent_match_score(deadline_question, deadline_distractor) == 0


@pytest.mark.asyncio
async def test_intent_reranker_promotes_exact_budget_clause(
    session_factory: async_sessionmaker[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    distractor = make_chunk(6, "Обоснование начальной цены подготовлено рыночным методом.")
    answer = make_chunk(4, "Начальная цена: 42 600 000 рублей, включая НДС.")
    service = HybridRetrievalService(
        cast(Any, session_factory),
        FakeEmbeddingProvider(),
        cast(Any, FakeIndexer()),
        dense_k=20,
        lexical_k=20,
        default_limit=5,
        rrf_k=60,
    )
    monkeypatch.setattr(service, "_validate_document", AsyncMock())
    monkeypatch.setattr(
        service,
        "_semantic_search",
        AsyncMock(return_value=[(distractor, 0.9), (answer, 0.5)]),
    )
    monkeypatch.setattr(service, "_lexical_search", AsyncMock(return_value=[]))

    result = await service.search(uuid4(), "Какова начальная максимальная цена?")

    assert result.hits[0].chunk_id == answer.id


@pytest.mark.asyncio
async def test_indexing_service_only_indexes_missing_chunks(
    session_factory: async_sessionmaker[Any],
) -> None:
    document_id = uuid4()
    page_id = uuid4()
    async with session_factory() as session:
        session.add(
            Document(
                id=document_id,
                original_filename="tender.pdf",
                content_type="application/pdf",
                sha256="b" * 64,
                size_bytes=100,
                status=DocumentStatus.READY.value,
                page_count=1,
            )
        )
        session.add(
            DocumentPage(
                id=page_id,
                document_id=document_id,
                page_number=1,
                text="Budget requirement",
                char_count=18,
            )
        )
        session.add(
            DocumentChunk(
                id=uuid4(),
                document_id=document_id,
                page_id=page_id,
                page_number=1,
                chunk_index=0,
                start_char=0,
                end_char=18,
                text="Budget requirement",
            )
        )
        await session.commit()

    indexer = ChunkIndexingService(
        cast(Any, session_factory),
        FakeEmbeddingProvider(),
        batch_size=1,
    )

    assert await indexer.index_missing(document_id) == 1
    assert await indexer.index_missing(document_id) == 0
    async with session_factory() as session:
        chunk = (await session.execute(select(DocumentChunk))).scalar_one()
    assert chunk.embedding is not None
    assert len(chunk.embedding) == 384


@pytest.mark.asyncio
async def test_hybrid_search_fuses_semantic_and_lexical_results(
    session_factory: async_sessionmaker[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    semantic_chunk = make_chunk(1, "submission deadline")
    shared_chunk = make_chunk(2, "maximum budget")
    lexical_chunk = make_chunk(3, "budget details")
    service = HybridRetrievalService(
        cast(Any, session_factory),
        FakeEmbeddingProvider(),
        cast(Any, FakeIndexer()),
        dense_k=20,
        lexical_k=20,
        default_limit=5,
        rrf_k=60,
    )
    monkeypatch.setattr(service, "_validate_document", AsyncMock())
    monkeypatch.setattr(
        service,
        "_semantic_search",
        AsyncMock(return_value=[(semantic_chunk, 0.7), (shared_chunk, 0.6)]),
    )
    monkeypatch.setattr(
        service,
        "_lexical_search",
        AsyncMock(return_value=[(shared_chunk, 0.9), (lexical_chunk, 0.5)]),
    )

    result = await service.search(uuid4(), "budget")

    assert result.mode == "hybrid"
    assert result.hits[0].chunk_id == shared_chunk.id
    assert result.hits[0].semantic_score == 0.6
    assert result.hits[0].lexical_score == 0.9


@pytest.mark.asyncio
async def test_search_falls_back_to_lexical_when_embeddings_fail(
    session_factory: async_sessionmaker[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    lexical_chunk = make_chunk(1, "exact budget")
    service = HybridRetrievalService(
        cast(Any, session_factory),
        FakeEmbeddingProvider(fail=True),
        cast(Any, FakeIndexer()),
        dense_k=20,
        lexical_k=20,
        default_limit=5,
        rrf_k=60,
    )
    monkeypatch.setattr(service, "_validate_document", AsyncMock())
    monkeypatch.setattr(
        service,
        "_lexical_search",
        AsyncMock(return_value=[(lexical_chunk, 1.0)]),
    )

    result = await service.search(uuid4(), "budget")

    assert result.mode == "lexical"
    assert [hit.chunk_id for hit in result.hits] == [lexical_chunk.id]


@pytest.mark.asyncio
async def test_search_rejects_missing_or_unready_document(
    session_factory: async_sessionmaker[Any],
) -> None:
    service = HybridRetrievalService(
        cast(Any, session_factory),
        FakeEmbeddingProvider(),
        cast(Any, FakeIndexer()),
        dense_k=20,
        lexical_k=20,
        default_limit=5,
        rrf_k=60,
    )
    missing_id = uuid4()
    with pytest.raises(AppError) as missing:
        await service._validate_document(missing_id)
    assert missing.value.status_code == 404

    document_id = uuid4()
    async with session_factory() as session:
        session.add(
            Document(
                id=document_id,
                original_filename="pending.pdf",
                content_type="application/pdf",
                sha256="c" * 64,
                size_bytes=100,
                status=DocumentStatus.PROCESSING.value,
            )
        )
        await session.commit()
    with pytest.raises(AppError) as pending:
        await service._validate_document(document_id)
    assert pending.value.status_code == 409
