# ruff: noqa: RUF001  # Cyrillic patterns are intentional for bilingual extraction.

import re
from dataclasses import dataclass

from tenderlens.analysis.models import ConditionCategory, ExtractedCondition
from tenderlens.qa.models import VerifiedCitation
from tenderlens.retrieval.service import RetrievalHit


@dataclass(frozen=True, slots=True)
class CategorySpec:
    category: ConditionCategory
    queries: tuple[str, str]
    keyword_pattern: re.Pattern[str]
    value_pattern: re.Pattern[str] | None = None


DATE_VALUE = re.compile(
    r"(?:\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b|"
    r"\b\d{1,2}\s+(?:january|february|march|april|may|june|july|august|"
    r"september|october|november|december)\s+\d{4}\b|"
    r"\b\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|"
    r"сентября|октября|ноября|декабря)\s+\d{4}\b)",
    re.IGNORECASE,
)
MONEY_VALUE = re.compile(
    r"\b\d[\d\s.,]*\s*(?:₽|руб(?:\.|лей|ля|ль)?|RUB|USD|EUR|доллар(?:ов|а)?|евро)\b",
    re.IGNORECASE,
)
PENALTY_VALUE = re.compile(
    r"(?:\b\d+(?:[.,]\d+)?\s*%|"
    r"\b\d[\d\s.,]*\s*(?:₽|руб(?:\.|лей|ля|ль)?|RUB|USD|EUR)\b)",
    re.IGNORECASE,
)

CATEGORY_SPECS = (
    CategorySpec(
        category=ConditionCategory.DEADLINE,
        queries=("submission deadline due date", "срок подачи дата окончания"),
        keyword_pattern=re.compile(
            r"(?:deadline|due\s+date|submission\s+date|"
            r"срок(?:и|а|ом)?\s+(?:подачи|предоставления|окончания)|"
            r"дата\s+(?:подачи|окончания))",
            re.IGNORECASE,
        ),
        value_pattern=DATE_VALUE,
    ),
    CategorySpec(
        category=ConditionCategory.BUDGET,
        queries=("maximum budget contract price", "бюджет начальная максимальная цена"),
        keyword_pattern=re.compile(
            r"(?:maximum\s+budget|budget|contract\s+(?:price|value)|"
            r"бюджет|начальн\w*\s+максимальн\w*\s+цен\w*|нмцк|цена\s+контракта)",
            re.IGNORECASE,
        ),
        value_pattern=MONEY_VALUE,
    ),
    CategorySpec(
        category=ConditionCategory.PENALTY,
        queries=("penalty fine liquidated damages", "штраф пени неустойка"),
        keyword_pattern=re.compile(
            r"(?:penalt(?:y|ies)|fine|liquidated\s+damages|"
            r"штраф\w*|пен(?:я|и|ей)|неустойк\w*)",
            re.IGNORECASE,
        ),
        value_pattern=PENALTY_VALUE,
    ),
    CategorySpec(
        category=ConditionCategory.REQUIREMENT,
        queries=("bidder supplier eligibility requirements", "требования к участнику поставщику"),
        keyword_pattern=re.compile(
            r"(?:eligibility|qualification|requirement|bidder\s+(?:must|shall)|"
            r"supplier\s+(?:must|shall)|требован\w*|"
            r"(?:участник|поставщик)\s+(?:должен|обязан))",
            re.IGNORECASE,
        ),
    ),
)

SEGMENT_PATTERN = re.compile(r".+?(?:[!?;](?=\s|$)|\.(?=\s|$)|\n|$)", re.DOTALL)


class RuleBasedConditionExtractor:
    def __init__(self, max_items_per_category: int) -> None:
        self.max_items_per_category = max_items_per_category

    def extract(
        self,
        spec: CategorySpec,
        hits: list[RetrievalHit],
        *,
        citation_start: int,
    ) -> list[ExtractedCondition]:
        candidates: list[tuple[float, RetrievalHit, int, int]] = []
        seen: set[str] = set()
        for hit in hits:
            for local_start, local_end in _segments(hit.text):
                quote = hit.text[local_start:local_end]
                keyword_matches = list(spec.keyword_pattern.finditer(quote))
                if not keyword_matches:
                    continue
                normalized = " ".join(quote.casefold().split())
                if normalized in seen:
                    continue
                seen.add(normalized)
                value_bonus = 0.2 if spec.value_pattern and spec.value_pattern.search(quote) else 0
                score = min(0.99, 0.55 + 0.08 * len(keyword_matches) + value_bonus)
                candidates.append((score, hit, local_start, local_end))

        candidates.sort(key=lambda item: (-item[0], item[1].page_number, item[2]))
        conditions: list[ExtractedCondition] = []
        for offset, (score, hit, local_start, local_end) in enumerate(
            candidates[: self.max_items_per_category]
        ):
            quote = hit.text[local_start:local_end]
            citation = VerifiedCitation(
                number=citation_start + offset,
                chunk_id=hit.chunk_id,
                page_number=hit.page_number,
                quote=quote,
                start_char=hit.start_char + local_start,
                end_char=hit.start_char + local_end,
            )
            conditions.append(
                ExtractedCondition(
                    category=spec.category,
                    summary=quote,
                    match_score=score,
                    citation=citation,
                )
            )
        return conditions


def _segments(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in SEGMENT_PATTERN.finditer(text):
        start, end = match.span()
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            spans.append((start, end))
    return spans
