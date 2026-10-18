from uuid import uuid4

import pytest

from tenderlens.qa.models import AnswerDraft, DraftClaim, Evidence
from tenderlens.qa.providers import ExtractiveAnswerProvider, quote_answers_question
from tenderlens.qa.service import verify_claims
from tenderlens.qa.table_evidence import select_table_rows
from tenderlens.retrieval.service import RetrievalHit


def item(text: str) -> Evidence:
    return Evidence(
        "C1",
        RetrievalHit(
            chunk_id=uuid4(),
            page_number=4,
            text=text,
            start_char=100,
            end_char=100 + len(text),
            rrf_score=0.03,
            semantic_score=0.8,
            lexical_score=0.5,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("separator", [" | ", "\t"])
async def test_selects_requested_row_not_neighbor(separator: str) -> None:
    text = "\n".join(
        separator.join(row)
        for row in [
            ("Item", "Cost (USD)"),
            ("Printer A", "100"),
            ("Printer B", "900"),
        ]
    )
    evidence = [item(text)]
    question = "What is the cost of Printer B?"
    draft = await ExtractiveAnswerProvider().generate(question, evidence)
    result = verify_claims(draft, evidence, question=question, max_claims=5)
    assert len(result) == 1
    quote = "Printer B" + separator + "900"
    assert result[0].citation.quote == quote
    assert result[0].citation.start_char == 100 + text.index(quote)
    assert "Printer A" not in result[0].text


@pytest.mark.parametrize(
    "text",
    [
        "Item | Cost\nPrinter B | 900\nPrinter B | 100",
        "Item | Cost\nPrinter B | not specified",
        "Item | Cost | Actual\nPrinter B | 900 | 100",
        "Item | Cost\nPrinter B | 31,500,00 0",
        "Item | Cost\nPrinter B | 900 subject to approval",
        "Item | Cost\nPrinter A | 900",
    ],
)
def test_ambiguous_tables_block_even_llm_claims(text: str) -> None:
    evidence = [item(text)]
    question = "What is the cost of Printer B?"
    selection = select_table_rows(question, evidence)
    assert selection.applies and not selection.rows
    draft = AnswerDraft(
        cannot_answer=False,
        claims=[
            DraftClaim(text="The cost is 900.", evidence_id="C1", quote="900"),
        ],
    )
    assert verify_claims(draft, evidence, question=question, max_claims=5) == []


def test_llm_cannot_cite_other_row_with_same_number() -> None:
    text = "Item | Cost\nPrinter A | 900\nPrinter B | 900"
    draft = AnswerDraft(
        cannot_answer=False,
        claims=[
            DraftClaim(text="Printer B costs 900.", evidence_id="C1", quote="Printer A | 900"),
        ],
    )
    assert verify_claims(draft, [item(text)], question="Cost of Printer B?", max_claims=5) == []


def test_non_table_budget_is_unchanged() -> None:
    assert not select_table_rows("What is the budget?", [item("Maximum budget: 900 USD.")]).applies


def test_consultants_question_cannot_be_answered_by_works_threshold() -> None:
    assert not quote_answers_question(
        "What is the prior review threshold for consultants?",
        "Works: prior review threshold 500,000 USD.",
    )


def test_consultant_cost_is_not_a_prior_review_threshold() -> None:
    assert not quote_answers_question(
        "What is the prior review threshold for individual consultants?",
        "Individual consultants: actual cost 4,500 USD. Post review.",
    )


def test_explicit_prior_review_condition_is_eligible() -> None:
    assert quote_answers_question(
        "What is the prior review threshold for individual consultants?",
        "Individual consultants: prior review threshold is 800,000 USD.",
    )
