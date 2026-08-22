from uuid import uuid4

from tenderlens.analysis.extractor import CATEGORY_SPECS, RuleBasedConditionExtractor
from tenderlens.analysis.models import ConditionCategory
from tenderlens.retrieval.service import RetrievalHit


def make_hit(text: str, page: int = 1, start_char: int = 0) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=uuid4(),
        page_number=page,
        text=text,
        start_char=start_char,
        end_char=start_char + len(text),
        rrf_score=0.03,
        semantic_score=0.8,
        lexical_score=0.7,
    )


def spec(category: ConditionCategory):  # type: ignore[no-untyped-def]
    return next(item for item in CATEGORY_SPECS if item.category == category)


def test_extracts_budget_with_exact_page_offsets() -> None:
    text = "Introduction. Maximum budget: 1 000 000 RUB. Payment terms follow."
    hit = make_hit(text, page=2, start_char=100)
    extractor = RuleBasedConditionExtractor(max_items_per_category=5)

    conditions = extractor.extract(
        spec(ConditionCategory.BUDGET),
        [hit],
        citation_start=4,
    )

    assert len(conditions) == 1
    condition = conditions[0]
    assert condition.category == ConditionCategory.BUDGET
    assert condition.value == "1 000 000 RUB"
    assert condition.summary == "Maximum budget: 1 000 000 RUB."
    assert condition.citation.number == 4
    assert condition.citation.page_number == 2
    local_start = text.index(condition.summary)
    assert condition.citation.start_char == 100 + local_start
    assert condition.citation.end_char == 100 + local_start + len(condition.summary)
    assert condition.match_score > 0.8


def test_deduplicates_overlapping_retrieval_hits() -> None:
    quote = "Penalty: 0.1% of the contract value per day."
    extractor = RuleBasedConditionExtractor(max_items_per_category=5)

    conditions = extractor.extract(
        spec(ConditionCategory.PENALTY),
        [make_hit(quote, page=3), make_hit(quote, page=3)],
        citation_start=1,
    )

    assert len(conditions) == 1
    assert conditions[0].summary == quote
    assert conditions[0].value == "0.1%"


def test_budget_rejects_contract_value_mention_without_money() -> None:
    text = "Penalty: 0.1% of the contract value for each day of delay."
    extractor = RuleBasedConditionExtractor(max_items_per_category=5)

    conditions = extractor.extract(
        spec(ConditionCategory.BUDGET),
        [make_hit(text, page=3)],
        citation_start=1,
    )

    assert conditions == []


def test_supports_russian_requirement_keywords() -> None:
    text = (
        "\u0423\u0447\u0430\u0441\u0442\u043d\u0438\u043a "
        "\u0434\u043e\u043b\u0436\u0435\u043d "
        "\u0438\u043c\u0435\u0442\u044c "
        "\u0441\u0435\u0440\u0442\u0438\u0444\u0438\u043a\u0430\u0442 ISO 9001."
    )
    extractor = RuleBasedConditionExtractor(max_items_per_category=5)

    conditions = extractor.extract(
        spec(ConditionCategory.REQUIREMENT),
        [make_hit(text)],
        citation_start=1,
    )

    assert conditions[0].summary == text
    assert conditions[0].value is None


def test_extracts_russian_deadline_with_date_and_time() -> None:
    text = (
        "Участник должен направить заявку не позднее 17 ноября 2026 года "
        "в 15:15 по московскому времени."
    )
    extractor = RuleBasedConditionExtractor(max_items_per_category=5)

    conditions = extractor.extract(
        spec(ConditionCategory.DEADLINE),
        [make_hit(text)],
        citation_start=1,
    )

    assert conditions[0].value == "17 ноября 2026 года в 15:15 по московскому времени"


def test_deadline_rejects_generic_mention_without_date_or_duration() -> None:
    text = "Срок подачи заявки определяется положениями извещения."
    extractor = RuleBasedConditionExtractor(max_items_per_category=5)

    conditions = extractor.extract(
        spec(ConditionCategory.DEADLINE),
        [make_hit(text)],
        citation_start=1,
    )

    assert conditions == []


def test_extracts_submission_deadline_worded_as_application_acceptance() -> None:
    text = "Прием заявок завершается 18 сентября 2026 года в 11:00 по московскому времени."
    extractor = RuleBasedConditionExtractor(max_items_per_category=5)

    conditions = extractor.extract(
        spec(ConditionCategory.DEADLINE),
        [make_hit(text, page=4)],
        citation_start=1,
    )

    assert conditions[0].value == "18 сентября 2026 года в 11:00 по московскому времени"


def test_extracts_budget_from_offer_price_sentence() -> None:
    text = "Цена предложения не может превышать 18 400 000 рублей, включая НДС."
    extractor = RuleBasedConditionExtractor(max_items_per_category=5)

    conditions = extractor.extract(
        spec(ConditionCategory.BUDGET),
        [make_hit(text, page=4)],
        citation_start=1,
    )

    assert conditions[0].value == "18 400 000 рублей"


def test_penalty_requires_a_numeric_value() -> None:
    text = "Ответственность сторон и неустойка."
    extractor = RuleBasedConditionExtractor(max_items_per_category=5)

    conditions = extractor.extract(
        spec(ConditionCategory.PENALTY),
        [make_hit(text)],
        citation_start=1,
    )

    assert conditions == []


def test_requirement_ignores_short_section_heading() -> None:
    text = "Требования к участникам закупки."
    extractor = RuleBasedConditionExtractor(max_items_per_category=5)

    conditions = extractor.extract(
        spec(ConditionCategory.REQUIREMENT),
        [make_hit(text)],
        citation_start=1,
    )

    assert conditions == []
