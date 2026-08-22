# ruff: noqa: RUF001  # Cyrillic patterns are intentional for bilingual extraction.

import re
from dataclasses import dataclass

from tenderlens.analysis.models import ConditionCategory, ExtractedCondition
from tenderlens.qa.models import VerifiedCitation
from tenderlens.retrieval.service import RetrievalHit


@dataclass(frozen=True, slots=True)
class CategorySpec:
    category: ConditionCategory
    queries: tuple[str, ...]
    keyword_pattern: re.Pattern[str]
    value_pattern: re.Pattern[str] | None = None
    requires_value: bool = False


DEADLINE_VALUE = re.compile(
    r"(?:"
    r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b"
    r"(?:\s*(?:г(?:ода)?\.?)?\s*(?:до|в|at)?\s*\d{1,2}[:.]\d{2})?"
    r"|\b\d{1,2}\s+(?:january|february|march|april|may|june|july|august|"
    r"september|october|november|december)\s+\d{4}"
    r"(?:\s+at\s+\d{1,2}:\d{2})?\b"
    r"|\b\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|"
    r"сентября|октября|ноября|декабря)\s+\d{4}(?:\s+года)?"
    r"(?:\s+(?:до|в)\s+\d{1,2}:\d{2})?"
    r"(?:\s+по\s+(?:московскому|местному)\s+времени)?"
    r"|\b(?:в\s+течение|не\s+позднее|within|no\s+later\s+than)\s+"
    r"\d+(?:\s*\([^)]*\))?\s+"
    r"(?:календарн(?:ого|ых|ые)?\s+|рабоч(?:его|их|ие)?\s+)?"
    r"(?:дн(?:я|ей|и)|час(?:а|ов)?|месяц(?:а|ев)?|days?|hours?|months?)\b"
    r")",
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
ACTIONABLE_REQUIREMENT = re.compile(
    r"(?:(?:участник|поставщик|исполнитель)\s+(?:должен|обязан)|"
    r"(?:bidder|supplier|contractor)\s+(?:must|shall))",
    re.IGNORECASE,
)

CATEGORY_SPECS = (
    CategorySpec(
        category=ConditionCategory.DEADLINE,
        queries=(
            "submission deadline due date",
            "прием заявок завершается московскому времени",
            "срок исполнения в течение календарных дней",
        ),
        keyword_pattern=re.compile(
            r"(?:deadline|due\s+date|submission\s+date|"
            r"срок(?:и|а|ом)?\s+(?:подачи|предоставления|окончания)|"
            r"дата\s+(?:подачи|окончания)|"
            r"подач\w*\s+заявк\w*|направ\w*\s+заявк\w*|"
            r"при[её]м\w*\s+заявок\s+заверша\w*)",
            re.IGNORECASE,
        ),
        value_pattern=DEADLINE_VALUE,
        requires_value=True,
    ),
    CategorySpec(
        category=ConditionCategory.BUDGET,
        queries=("maximum budget contract price", "бюджет начальная максимальная цена"),
        keyword_pattern=re.compile(
            r"(?:maximum\s+budget|budget|contract\s+(?:price|value)|"
            r"бюджет|начальн\w*\s+максимальн\w*\s+цен\w*|нмцк|"
            r"цена\s+(?:контракта|предложен\w*))",
            re.IGNORECASE,
        ),
        value_pattern=MONEY_VALUE,
        requires_value=True,
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
        requires_value=True,
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
                if (
                    spec.category == ConditionCategory.REQUIREMENT
                    and len(quote.split()) < 7
                    and ACTIONABLE_REQUIREMENT.search(quote) is None
                ):
                    continue
                keyword_matches = list(spec.keyword_pattern.finditer(quote))
                if not keyword_matches:
                    continue
                value_match = spec.value_pattern.search(quote) if spec.value_pattern else None
                if spec.requires_value and value_match is None:
                    continue
                normalized = " ".join(quote.casefold().split())
                if normalized in seen:
                    continue
                seen.add(normalized)
                value_bonus = 0.2 if value_match else 0
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
                    value=_display_value(spec, quote),
                    summary=quote,
                    match_score=score,
                    citation=citation,
                )
            )
        return conditions


def _display_value(spec: CategorySpec, quote: str) -> str | None:
    if spec.value_pattern is None:
        return None
    match = spec.value_pattern.search(quote)
    if match is None:
        return None
    return " ".join(match.group(0).strip(" .,:;").split())


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
