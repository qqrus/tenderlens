# ruff: noqa: RUF001
from uuid import uuid4

import pytest

from tenderlens.qa.models import AnswerDraft, DraftClaim, Evidence
from tenderlens.qa.providers import ExtractiveAnswerProvider
from tenderlens.qa.service import verify_claims
from tenderlens.retrieval.service import RetrievalHit

FIELD = "Period covered by this Procurement Plan: March 2028 – April 2029"
QUESTION = "Какой период охватывает план закупок?"


def item(text: str, number: int = 1) -> Evidence:
    return Evidence(
        f"C{number}",
        RetrievalHit(
            chunk_id=uuid4(),
            page_number=number,
            text=text,
            start_char=50,
            end_char=50 + len(text),
            rrf_score=0.03,
            semantic_score=0.8,
            lexical_score=0.5,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        QUESTION,
        "За какой период составлен план закупок?",
        "What period does the procurement plan cover?",
    ],
)
async def test_bilingual_period_keeps_label_and_offsets(question: str) -> None:
    field = FIELD.replace(": ", ":\n")
    source = "Project: Example\n" + field + "\nPreamble\nLaw dated May 2020."
    evidence = [item(source)]
    draft = await ExtractiveAnswerProvider().generate(question, evidence)
    result = verify_claims(draft, evidence, max_claims=5, question=question)
    assert result[0].citation.quote == field
    assert result[0].citation.start_char == 50 + source.index(field)
    assert "2020" not in result[0].text


@pytest.mark.asyncio
async def test_agreement_date_is_not_submission_date() -> None:
    field = "Procurement Plan agreed as of November 12, 2028"
    evidence = [item("Submission deadline: December 15, 2028.\n" + field + "\nRef. No.")]
    draft = await ExtractiveAnswerProvider().generate(
        "На какую дату был согласован план закупок?",
        evidence,
    )
    assert draft.claims[0].quote == field


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source",
    [
        "Contract period: March 2028 – April 2029",
        "Period covered by this Procurement Plan: not specified",
        "Period covered by this Procurement Plan: March 2028",
        FIELD + " except as amended",
        "Do not use " + FIELD,
    ],
)
async def test_no_guess_from_missing_or_qualified_field(source: str) -> None:
    draft = await ExtractiveAnswerProvider().generate(QUESTION, [item(source)])
    assert draft.cannot_answer


@pytest.mark.asyncio
async def test_conflicting_values_block_both_extractor_and_llm() -> None:
    evidence = [item(FIELD), item(FIELD.replace("2029", "2030"), 2)]
    assert (await ExtractiveAnswerProvider().generate(QUESTION, evidence)).cannot_answer
    draft = AnswerDraft(
        cannot_answer=False,
        claims=[
            DraftClaim(text=FIELD, quote=FIELD, evidence_id="C1"),
        ],
    )
    assert verify_claims(draft, evidence, question=QUESTION, max_claims=5) == []


@pytest.mark.asyncio
async def test_duplicate_equal_values_are_not_a_conflict() -> None:
    result = await ExtractiveAnswerProvider().generate(QUESTION, [item(FIELD), item(FIELD, 2)])
    assert not result.cannot_answer
