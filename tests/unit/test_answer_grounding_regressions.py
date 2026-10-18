from typing import Any
from uuid import uuid4

import pytest

from tenderlens.evaluation.evidence import joint_answer_correct, span_reciprocal_rank
from tenderlens.evaluation.real_dataset import RealEvaluationQuestion
from tenderlens.qa.models import AnswerDraft, DraftClaim, Evidence
from tenderlens.qa.providers import ExtractiveAnswerProvider
from tenderlens.qa.service import verify_claims
from tenderlens.retrieval.service import RetrievalHit


def evidence(text: str) -> list[Evidence]:
    return [
        Evidence(
            "C1",
            RetrievalHit(
                chunk_id=uuid4(),
                page_number=3,
                text=text,
                start_char=100,
                end_char=100 + len(text),
                rrf_score=0.03,
                semantic_score=0.8,
                lexical_score=0.7,
            ),
        )
    ]


@pytest.mark.parametrize(
    ("source", "claim", "quote", "question", "accepted"),
    [
        ("Maximum budget: 100 RUB.", "Budget: 900 RUB.", "100 RUB", "What is the budget?", False),
        (
            "Subcontracting is not allowed.",
            "Subcontracting is allowed.",
            "allowed",
            "Is subcontracting allowed?",
            True,
        ),
        ("Maximum budget: 100 RUB.", "Budget: 100 USD.", "100 RUB", "What is the budget?", True),
        ("Warranty: 12 months.", "Warranty: 12 months.", "12 months", "What is the budget?", False),
        (
            "Submission deadline is unspecified.",
            "Submission deadline is unspecified.",
            "Submission deadline",
            "What is the submission deadline?",
            False,
        ),
    ],
)
def test_verified_output_is_source_not_unchecked_paraphrase(
    source: str,
    claim: str,
    quote: str,
    question: str,
    accepted: bool,
) -> None:
    draft = AnswerDraft(
        cannot_answer=False,
        claims=[
            DraftClaim(text=claim, evidence_id="C1", quote=quote),
        ],
    )
    result = verify_claims(draft, evidence(source), max_claims=5, question=question)
    assert bool(result) is accepted
    if accepted:
        assert result[0].text == source
        assert result[0].citation.quote == source
        assert result[0].citation.start_char == 100
        assert result[0].citation.end_char == 100 + len(source)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What is the submission deadline?", "Submission deadline: 20 August 2026."),
        ("What is the delivery period?", "Delivery period: 60 calendar days."),
    ],
)
async def test_submission_and_delivery_are_not_interchangeable(
    question: str, expected: str
) -> None:
    items = evidence("Delivery period: 60 calendar days. Submission deadline: 20 August 2026.")
    draft = await ExtractiveAnswerProvider().generate(question, items)
    assert draft.claims[0].quote == expected


def gold() -> RealEvaluationQuestion:
    return RealEvaluationQuestion(
        id="budget-test",
        language="en",
        question="What is the budget?",
        expected_pages=[3],
        expected_quote_fragments=["Budget: 100 RUB"],
        expected_answers=["100 RUB"],
    )


@pytest.mark.parametrize(
    ("page", "quote", "answer", "expected"),
    [
        (3, "Budget: 100 RUB", "Budget: 100 RUB [1]", True),
        (2, "Budget: 100 RUB", "Budget: 100 RUB [1]", False),
        (3, "Warranty: 12 months", "Budget: 100 RUB [1]", False),
        (3, "Budget: 100 RUB", "Budget: 100 RUB plus 900 [1]", False),
    ],
)
def test_answer_and_quote_must_match_gold_together(
    page: int,
    quote: str,
    answer: str,
    expected: bool,
) -> None:
    payload: dict[str, Any] = {
        "grounded": True,
        "answer": answer,
        "citations": [{"page_number": page, "quote": quote}],
    }
    assert joint_answer_correct(payload, gold()) is expected


def test_missing_answer_gold_is_unmeasured_not_success() -> None:
    expected = gold().model_copy(update={"expected_answers": []})
    assert joint_answer_correct({}, expected) is None


def test_right_page_without_right_fragment_is_not_retrieval_success() -> None:
    assert (
        span_reciprocal_rank(
            [
                {"page_number": 3, "text": "Warranty: 12 months"},
                {"page_number": 3, "text": "Budget: 100 RUB"},
            ],
            gold(),
        )
        == 0.5
    )
    assert span_reciprocal_rank([], gold()) == 0.0
