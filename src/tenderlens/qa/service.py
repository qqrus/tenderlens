# ruff: noqa: RUF001  # Russian user-facing messages are intentional.
import re
from dataclasses import dataclass
from uuid import UUID

import structlog

from tenderlens.domain.text import numeric_tokens, sentence_spans
from tenderlens.qa.models import (
    AnswerDraft,
    Evidence,
    GroundedAnswer,
    VerifiedCitation,
)
from tenderlens.qa.plan_fields import field_spans, field_value, plan_intent
from tenderlens.qa.providers import (
    AnswerProvider,
    ExtractiveAnswerProvider,
    GenerationError,
    quote_answers_question,
)
from tenderlens.qa.table_evidence import select_table_rows
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

        verified = verify_claims(draft, evidence, max_claims=self.max_claims, question=question)
        if draft.cannot_answer or not verified:
            table = select_table_rows(question, evidence)
            return GroundedAnswer(
                answer=(
                    _ambiguous_table_message(question)
                    if table.applies and not table.rows
                    else _insufficient_evidence_message(question)
                ),
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
    question: str | None = None,
) -> list[_VerifiedClaim]:
    evidence_by_id = {item.evidence_id: item for item in evidence}
    table = select_table_rows(question or "", evidence)
    if table.applies and not table.rows:
        return []
    if question is not None and plan_intent(question):
        values = {
            field_value(question, item.hit.text[start:end])
            for item in evidence
            for start, end in field_spans(question, item.hit.text)
        }
        if len(values) != 1:
            return []
    verified: list[_VerifiedClaim] = []
    for claim in draft.claims[:max_claims]:
        item = evidence_by_id.get(claim.evidence_id)
        if item is None:
            continue
        span = _find_quote_span(item.hit.text, claim.quote)
        if span is None:
            continue
        local_start, local_end = span
        # Restore sentence context: a quoted substring must not drop "not", a date
        # qualifier or an exception. The model selects evidence, not the final wording.
        context_spans = (
            field_spans(question, item.hit.text)
            if question is not None and plan_intent(question)
            else sentence_spans(item.hit.text)
        )
        if table.applies:
            context_spans = [
                (start, end)
                for evidence_id, start, end in table.rows
                if evidence_id == claim.evidence_id and start <= local_start and end >= local_end
            ]
        containing = [
            (start, end) for start, end in context_spans if start < local_end and end > local_start
        ]
        if not containing:
            continue
        local_start, local_end = containing[0][0], containing[-1][1]
        source_quote = item.hit.text[local_start:local_end]
        if len(source_quote) > 2_000 or not claim.text.strip():
            continue
        if (
            not table.applies
            and question is not None
            and not quote_answers_question(question, source_quote)
        ):
            continue
        if any(
            previous.citation.chunk_id == item.hit.chunk_id
            and previous.citation.start_char == item.hit.start_char + local_start
            and previous.citation.end_char == item.hit.start_char + local_end
            for previous in verified
        ):
            continue
        if not numeric_tokens(claim.text) <= numeric_tokens(source_quote):
            logger.info("answer_claim_rejected", reason="unsupported_number")
            continue
        citation = VerifiedCitation(
            number=len(verified) + 1,
            chunk_id=item.hit.chunk_id,
            page_number=item.hit.page_number,
            quote=item.hit.text[local_start:local_end],
            start_char=item.hit.start_char + local_start,
            end_char=item.hit.start_char + local_end,
        )
        # Literal source wording avoids presenting an unchecked paraphrase as a fact.
        verified.append(_VerifiedClaim(text=" ".join(source_quote.split()), citation=citation))
    return verified


def _ambiguous_table_message(question: str) -> str:
    if re.search(r"[\u0400-\u04ff]", question):
        return (
            "Не удалось надёжно связать сумму с нужной строкой и столбцом таблицы. "
            "Проверьте исходную таблицу в PDF: структура или значение неоднозначны."
        )
    return (
        "The amount could not be reliably linked to the requested table row and column. "
        "Check the original PDF table: its structure or value is ambiguous."
    )


def _find_quote_span(source: str, quote: str) -> tuple[int, int] | None:
    if not quote.strip():
        return None
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
