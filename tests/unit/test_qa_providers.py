# ruff: noqa: RUF001  # Cyrillic test fixtures are intentional.

from uuid import uuid4

import pytest

from tenderlens.qa.models import Evidence
from tenderlens.qa.providers import (
    ExtractiveAnswerProvider,
    GenerationError,
    _openai_output_text,
    build_user_prompt,
)
from tenderlens.retrieval.service import RetrievalHit


def evidence(text: str = "Maximum budget: 1000000 RUB") -> Evidence:
    return Evidence(
        evidence_id="C1",
        hit=RetrievalHit(
            chunk_id=uuid4(),
            page_number=2,
            text=text,
            start_char=10,
            end_char=10 + len(text),
            rrf_score=0.03,
            semantic_score=0.8,
            lexical_score=0.7,
        ),
    )


def evidence_with_id(text: str, evidence_id: str) -> Evidence:
    item = evidence(text)
    return Evidence(evidence_id=evidence_id, hit=item.hit)


@pytest.mark.asyncio
async def test_extractive_provider_returns_verbatim_evidence() -> None:
    item = evidence()

    draft = await ExtractiveAnswerProvider().generate("What is the budget?", [item])

    assert draft.cannot_answer is False
    assert draft.claims[0].quote == item.hit.text
    assert draft.claims[0].evidence_id == "C1"


@pytest.mark.asyncio
async def test_extractive_provider_selects_relevant_sentence_across_evidence() -> None:
    unrelated = evidence_with_id("Оплата выполняется в течение 30 дней.", "C1")
    relevant = evidence_with_id(
        "Общие положения. Участник должен предоставить сертификат и подтвердить опыт.",
        "C2",
    )

    draft = await ExtractiveAnswerProvider().generate(
        "Какие требования предъявляются к участнику?",
        [unrelated, relevant],
    )

    assert draft.claims[0].evidence_id == "C2"
    assert draft.claims[0].quote == "Участник должен предоставить сертификат и подтвердить опыт."


@pytest.mark.asyncio
async def test_extractive_provider_distinguishes_payment_from_other_periods() -> None:
    item = evidence(
        "Поставка выполняется в течение 60 дней. "
        "Оплата производится в течение 12 рабочих дней после приемки. "
        "Гарантийный срок составляет 36 месяцев."
    )

    draft = await ExtractiveAnswerProvider().generate(
        "В какой срок заказчик оплачивает результат?", [item]
    )

    assert draft.claims[0].quote == ("Оплата производится в течение 12 рабочих дней после приемки.")


@pytest.mark.asyncio
async def test_extractive_provider_distinguishes_bid_and_performance_security() -> None:
    bid = evidence_with_id("Обеспечение заявки составляет 1%.", "C1")
    performance = evidence_with_id(
        "Обеспечение исполнения контракта установлено в размере 5%.", "C2"
    )

    bid_draft = await ExtractiveAnswerProvider().generate(
        "Каков размер обеспечения заявки?", [performance, bid]
    )
    performance_draft = await ExtractiveAnswerProvider().generate(
        "Каков размер обеспечения исполнения контракта?", [bid, performance]
    )

    assert bid_draft.claims[0].evidence_id == "C1"
    assert performance_draft.claims[0].evidence_id == "C2"


@pytest.mark.asyncio
async def test_extractive_provider_distinguishes_delivery_from_warranty_and_penalty() -> None:
    item = evidence(
        "Срок исполнения обязательств: 110 календарных дней. "
        "Гарантийный срок Исполнитель предоставляет гарантию 36 месяцев. "
        "Пеня составляет 0,05% стоимости незавершенных работ."
    )

    draft = await ExtractiveAnswerProvider().generate("Какой срок исполнения контракта?", [item])

    assert draft.claims[0].quote == "Срок исполнения обязательств: 110 календарных дней."


def test_prompt_marks_evidence_and_page() -> None:
    prompt = build_user_prompt("What is the budget?", [evidence()])

    assert '<C1 page="2">' in prompt
    assert "Maximum budget" in prompt


def test_openai_output_text_reads_responses_api_message() -> None:
    payload = {
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": '{"claims": []}'}],
            }
        ]
    }

    assert _openai_output_text(payload) == '{"claims": []}'


def test_openai_output_text_rejects_missing_message() -> None:
    with pytest.raises(GenerationError):
        _openai_output_text({"output": []})
