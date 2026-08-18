import re
from dataclasses import dataclass
from uuid import UUID

import structlog

from tenderlens.qa.models import (
    AnswerDraft,
    Evidence,
    GroundedAnswer,
    VerifiedCitation,
)
from tenderlens.qa.providers import AnswerProvider, ExtractiveAnswerProvider, GenerationError
from tenderlens.retrieval.service import HybridRetrievalService

logger = structlog.get_logger(__name__)

DISCLAIMER = "TenderLens provides document analysis, not legal advice."


@dataclass(frozen=True, slots=True)
class _VerifiedClaim:
    text: str
    citation: VerifiedCitation


class GroundedQuestionAnsweringService:
    def __init__(
        self,
        retrieval_service: HybridRetrievalService,
        provider: AnswerProvider,
        *,
        evidence_limit: int,
        max_claims: int,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.provider = provider
        self.fallback_provider = ExtractiveAnswerProvider()
        self.evidence_limit = evidence_limit
        self.max_claims = max_claims

    async def answer(self, document_id: UUID, question: str) -> GroundedAnswer:
        retrieval = await self.retrieval_service.search(
            document_id,
            question,
            self.evidence_limit,
        )
        evidence = [
            Evidence(evidence_id=f"C{index}", hit=hit)
            for index, hit in enumerate(retrieval.hits, start=1)
        ]
        answer_mode = self.provider.name
        try:
            draft = await self.provider.generate(question, evidence)
        except GenerationError as exc:
            logger.warning("answer_generation_failed", provider=self.provider.name, reason=str(exc))
            draft = await self.fallback_provider.generate(question, evidence)
            answer_mode = "extractive_fallback"

        verified = verify_claims(draft, evidence, max_claims=self.max_claims)
        if draft.cannot_answer or not verified:
            return GroundedAnswer(
                answer=_insufficient_evidence_message(question),
                citations=[],
                answer_mode=answer_mode,
                retrieval_mode=retrieval.mode,
                grounded=False,
                disclaimer=DISCLAIMER,
            )

        answer = " ".join(f"{claim.text.rstrip()} [{claim.citation.number}]" for claim in verified)
        return GroundedAnswer(
            answer=answer,
            citations=[claim.citation for claim in verified],
            answer_mode=answer_mode,
            retrieval_mode=retrieval.mode,
            grounded=True,
            disclaimer=DISCLAIMER,
        )


def verify_claims(
    draft: AnswerDraft,
    evidence: list[Evidence],
    *,
    max_claims: int,
) -> list[_VerifiedClaim]:
    evidence_by_id = {item.evidence_id: item for item in evidence}
    verified: list[_VerifiedClaim] = []
    for claim in draft.claims[:max_claims]:
        item = evidence_by_id.get(claim.evidence_id)
        if item is None:
            continue
        span = _find_quote_span(item.hit.text, claim.quote)
        if span is None:
            continue
        local_start, local_end = span
        citation = VerifiedCitation(
            number=len(verified) + 1,
            chunk_id=item.hit.chunk_id,
            page_number=item.hit.page_number,
            quote=item.hit.text[local_start:local_end],
            start_char=item.hit.start_char + local_start,
            end_char=item.hit.start_char + local_end,
        )
        verified.append(_VerifiedClaim(text=claim.text, citation=citation))
    return verified


def _find_quote_span(source: str, quote: str) -> tuple[int, int] | None:
    exact_start = source.find(quote)
    if exact_start >= 0:
        return exact_start, exact_start + len(quote)
    tokens = quote.split()
    if not tokens:
        return None
    whitespace_tolerant = r"\s+".join(re.escape(token) for token in tokens)
    match = re.search(whitespace_tolerant, source)
    if match is None:
        return None
    return match.span()


def _insufficient_evidence_message(question: str) -> str:
    if re.search(r"[\u0400-\u04ff]", question):
        return (
            "\u0412 \u043d\u0430\u0439\u0434\u0435\u043d\u043d\u044b\u0445 "
            "\u0444\u0440\u0430\u0433\u043c\u0435\u043d\u0442\u0430\u0445 "
            "\u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430 "
            "\u043d\u0435\u0434\u043e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u043e "
            "\u0434\u0430\u043d\u043d\u044b\u0445 \u0434\u043b\u044f "
            "\u0442\u043e\u0447\u043d\u043e\u0433\u043e "
            "\u043e\u0442\u0432\u0435\u0442\u0430."
        )
    return "The retrieved document fragments do not contain enough evidence for a precise answer."
