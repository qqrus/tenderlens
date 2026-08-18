from uuid import UUID, uuid4

import pytest

from tenderlens.qa.models import AnswerDraft, DraftClaim
from tenderlens.qa.providers import GenerationError
from tenderlens.qa.service import GroundedQuestionAnsweringService, verify_claims
from tenderlens.retrieval.service import RetrievalHit, RetrievalResult


def hit(text: str = "Maximum budget:\n1 000 000 RUB") -> RetrievalHit:
    return RetrievalHit(
        chunk_id=uuid4(),
        page_number=3,
        text=text,
        start_char=100,
        end_char=100 + len(text),
        rrf_score=0.03,
        semantic_score=0.82,
        lexical_score=0.7,
    )


class FakeRetrievalService:
    def __init__(self, hits: list[RetrievalHit]) -> None:
        self.hits = hits

    async def search(self, _document_id: UUID, _query: str, limit: int) -> RetrievalResult:
        return RetrievalResult(mode="hybrid", hits=self.hits[:limit])


class ValidProvider:
    name = "test_llm"

    async def generate(self, _question: str, _evidence: object) -> AnswerDraft:
        return AnswerDraft(
            cannot_answer=False,
            claims=[
                DraftClaim(
                    text="The maximum budget is 1 000 000 RUB.",
                    evidence_id="C1",
                    quote="Maximum budget: 1 000 000 RUB",
                )
            ],
        )


class InvalidCitationProvider:
    name = "invalid_llm"

    async def generate(self, _question: str, _evidence: object) -> AnswerDraft:
        return AnswerDraft(
            cannot_answer=False,
            claims=[DraftClaim(text="Invented claim", evidence_id="C99", quote="Not in document")],
        )


class FailingProvider:
    name = "offline_llm"

    async def generate(self, _question: str, _evidence: object) -> AnswerDraft:
        raise GenerationError("offline")


@pytest.mark.asyncio
async def test_answer_contains_server_verified_page_and_offsets() -> None:
    source_hit = hit()
    service = GroundedQuestionAnsweringService(
        FakeRetrievalService([source_hit]),  # type: ignore[arg-type]
        ValidProvider(),
        evidence_limit=5,
        max_claims=5,
    )

    result = await service.answer(uuid4(), "What is the maximum budget?")

    assert result.grounded is True
    assert result.answer.endswith("[1]")
    assert result.citations[0].page_number == 3
    assert result.citations[0].quote == source_hit.text
    assert result.citations[0].start_char == 100
    assert result.citations[0].end_char == 100 + len(source_hit.text)


@pytest.mark.asyncio
async def test_unverified_claim_is_not_returned() -> None:
    service = GroundedQuestionAnsweringService(
        FakeRetrievalService([hit()]),  # type: ignore[arg-type]
        InvalidCitationProvider(),
        evidence_limit=5,
        max_claims=5,
    )

    result = await service.answer(
        uuid4(), "\u041a\u0430\u043a\u043e\u0439 \u0431\u044e\u0434\u0436\u0435\u0442?"
    )

    assert result.grounded is False
    assert result.citations == []
    expected = (
        "\u043d\u0435\u0434\u043e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u043e "
        "\u0434\u0430\u043d\u043d\u044b\u0445"
    )
    assert expected in result.answer


@pytest.mark.asyncio
async def test_provider_failure_degrades_to_verified_extractive_answer() -> None:
    service = GroundedQuestionAnsweringService(
        FakeRetrievalService([hit("Submission deadline: 20 August 2026")]),  # type: ignore[arg-type]
        FailingProvider(),
        evidence_limit=5,
        max_claims=5,
    )

    result = await service.answer(uuid4(), "What is the deadline?")

    assert result.grounded is True
    assert result.answer_mode == "extractive_fallback"
    assert result.citations[0].quote == "Submission deadline: 20 August 2026"


def test_verifier_rejects_quote_from_wrong_evidence() -> None:
    from tenderlens.qa.models import Evidence

    source_hit = hit("Deadline: 20 August")
    draft = AnswerDraft(
        cannot_answer=False,
        claims=[DraftClaim(text="Budget", evidence_id="C1", quote="Budget: 100")],
    )

    assert verify_claims(draft, [Evidence("C1", source_hit)], max_claims=5) == []
