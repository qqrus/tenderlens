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


@pytest.mark.asyncio
async def test_extractive_provider_returns_verbatim_evidence() -> None:
    item = evidence()

    draft = await ExtractiveAnswerProvider().generate("What is the budget?", [item])

    assert draft.cannot_answer is False
    assert draft.claims[0].quote == item.hit.text
    assert draft.claims[0].evidence_id == "C1"


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
