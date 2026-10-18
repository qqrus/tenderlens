"""Version 2 literal-gold checks. These are not a semantic entailment judge."""

import re
from typing import Any

from tenderlens.domain.text import normalized_text, numeric_tokens
from tenderlens.evaluation.real_dataset import RealEvaluationQuestion


def contains_all(text: str, fragments: list[str]) -> bool:
    normalized = normalized_text(text)
    return bool(fragments) and all(
        bool(fragment.strip()) and normalized_text(fragment) in normalized for fragment in fragments
    )


def evidence_matches(page: int, text: str, expected: RealEvaluationQuestion) -> bool:
    return page in expected.expected_pages and contains_all(text, expected.expected_quote_fragments)


def joint_answer_correct(answer: dict[str, Any], expected: RealEvaluationQuestion) -> bool | None:
    # Legacy manifests have no independently specified answer gold: do not invent it.
    if not expected.expected_answers:
        return None
    citations = answer.get("citations", [])
    if not answer.get("grounded") or not citations:
        return False
    if not all(
        evidence_matches(int(c["page_number"]), str(c["quote"]), expected) for c in citations
    ):
        return False
    text = re.sub(r"\[\d+\]", "", str(answer["answer"]))
    supported_numbers = numeric_tokens(" ".join(str(c["quote"]) for c in citations))
    return (
        contains_all(text, expected.expected_answers) and numeric_tokens(text) <= supported_numbers
    )


def span_reciprocal_rank(hits: list[dict[str, Any]], expected: RealEvaluationQuestion) -> float:
    return next(
        (
            1 / rank
            for rank, hit in enumerate(hits, 1)
            if evidence_matches(int(hit["page_number"]), str(hit["text"]), expected)
        ),
        0.0,
    )
