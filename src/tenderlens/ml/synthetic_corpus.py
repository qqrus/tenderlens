import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from tenderlens.ml.reranker import DatasetSplit, RerankerExample, lexical_overlap_score

FACT_CATEGORIES = (
    "deadline",
    "budget",
    "delivery",
    "payment",
    "bid_security",
    "performance_security",
    "penalty",
    "warranty",
)

FACT_PAGES = {
    "deadline": 1,
    "budget": 1,
    "delivery": 2,
    "payment": 2,
    "warranty": 2,
    "bid_security": 3,
    "performance_security": 3,
    "penalty": 3,
}

HEADINGS = {
    "ru": {
        "deadline": "Срок подачи заявок",
        "budget": "Начальная цена",
        "delivery": "Срок исполнения",
        "payment": "Порядок оплаты",
        "bid_security": "Обеспечение заявки",
        "performance_security": "Обеспечение исполнения контракта",
        "penalty": "Ответственность за просрочку",
        "warranty": "Гарантийный срок",
    },
    "en": {
        "deadline": "Submission deadline",
        "budget": "Maximum contract value",
        "delivery": "Delivery period",
        "payment": "Payment terms",
        "bid_security": "Bid security",
        "performance_security": "Performance security",
        "penalty": "Delay penalty",
        "warranty": "Warranty period",
    },
}

PASSAGE_TEMPLATES = {
    "ru": {
        "deadline": (
            "Прием заявок завершается {value}. Заявки после этого момента не рассматриваются.",
            "Последний срок подачи предложения: {value}. Опоздавшая заявка отклоняется.",
            "Участник должен направить заявку не позднее {value}; перенос срока не предусмотрен.",
        ),
        "budget": (
            "Начальная максимальная цена контракта составляет {value}. Сумма включает обязательные расходы.",
            "Предельный бюджет закупки установлен в размере {value}, включая предусмотренные налоги.",
            "Цена предложения не может превышать {value}. Превышение является основанием для отклонения.",
        ),
        "delivery": (
            "Поставка и ввод в эксплуатацию должны быть завершены {value}.",
            "Исполнитель обязан завершить весь объем работ {value}.",
            "Установленный срок исполнения обязательств: {value}.",
        ),
        "payment": (
            "Оплата производится {value}. Авансовый платеж не предусмотрен.",
            "Заказчик перечисляет оплату {value}; основанием служит подписанный документ о приемке.",
            "Расчет с исполнителем выполняется {value}. До приемки оплата не производится.",
        ),
        "bid_security": (
            "Обеспечение заявки составляет {value}. Оно предоставляется до окончания срока подачи заявок.",
            "Для участия требуется обеспечение заявки в размере {value} от начальной цены.",
            "Участник вносит обеспечение заявки: {value}. Без него заявка не допускается.",
        ),
        "performance_security": (
            "Обеспечение исполнения контракта установлено в размере {value}. Оно предоставляется победителем.",
            "До подписания договора победитель предоставляет обеспечение исполнения: {value} от цены контракта.",
            "Размер обеспечения надлежащего исполнения обязательств равен {value}.",
        ),
        "penalty": (
            "За просрочку начисляется пеня {value}. Общий размер пени ограничен 10% цены контракта.",
            "Ответственность исполнителя за каждый день задержки: {value}, но не более 10% цены договора.",
            "При нарушении срока заказчик удерживает неустойку {value} за каждый календарный день просрочки.",
        ),
        "warranty": (
            "Гарантийный срок составляет {value}. Он начинается после подписания итогового акта приемки.",
            "Исполнитель предоставляет гарантию {value}, исчисляемую с даты окончательной приемки.",
            "На результат закупки действует гарантия продолжительностью {value} после приемки.",
        ),
    },
    "en": {
        "deadline": (
            "Proposals must be received by {value}. Late submissions will not be considered.",
            "The final proposal submission deadline is {value}; any late bid will be rejected.",
            "The bidder shall submit its offer no later than {value}. No deadline extension is planned.",
        ),
        "budget": (
            "The maximum contract value is {value}. This amount includes all mandatory supplier costs.",
            "The procurement budget is capped at {value}, inclusive of applicable taxes.",
            "A financial offer must not exceed {value}. Any excess makes the offer non-compliant.",
        ),
        "delivery": (
            "Delivery and commissioning must be completed {value}.",
            "The contractor shall complete the entire scope {value}.",
            "The required performance period is {value}.",
        ),
        "payment": (
            "Payment will be made {value}. No advance payment is available.",
            "The customer pays {value}, based on the signed acceptance certificate.",
            "The supplier will receive payment {value}. Nothing is payable before acceptance.",
        ),
        "bid_security": (
            "Bid security is {value}. It must be provided before the proposal deadline.",
            "Participation requires bid security equal to {value} of the maximum contract value.",
            "Each bidder shall lodge bid security of {value}; an unsecured bid is inadmissible.",
        ),
        "performance_security": (
            "Performance security is set at {value}. The successful bidder must provide it.",
            "Before signature, the winner shall provide performance security of {value} of the contract price.",
            "Security for proper contract performance equals {value}.",
        ),
        "penalty": (
            "A delay penalty of {value} applies. Total delay penalties are capped at 10% of contract value.",
            "For every day of delay, the contractor is liable for {value}, up to 10% of the contract price.",
            "If a deadline is missed, liquidated damages of {value} are charged for each calendar day.",
        ),
        "warranty": (
            "The warranty period is {value}. It starts when the final acceptance certificate is signed.",
            "The contractor provides a warranty of {value}, calculated from final acceptance.",
            "The procurement result is covered by a {value} warranty after acceptance.",
        ),
    },
}

QUESTION_TEMPLATES = {
    "ru": {
        "deadline": (
            "Когда заканчивается прием заявок?",
            "До какой даты можно подать предложение?",
            "Назовите точный дедлайн подачи заявки.",
        ),
        "budget": (
            "Какова начальная максимальная цена?",
            "Какой предельный бюджет закупки?",
            "Какую сумму не должно превышать предложение?",
        ),
        "delivery": (
            "Какой срок исполнения контракта?",
            "Когда нужно завершить поставку или работы?",
            "Сколько времени отведено на выполнение обязательств?",
        ),
        "payment": (
            "В какой срок заказчик оплачивает результат?",
            "Какие условия оплаты указаны?",
            "Когда исполнитель получит оплату после приемки?",
        ),
        "bid_security": (
            "Каков размер обеспечения заявки?",
            "Сколько нужно внести для участия в закупке?",
            "Какое обеспечение требуется именно для подачи заявки?",
        ),
        "performance_security": (
            "Каков размер обеспечения исполнения контракта?",
            "Какую гарантию исполнения предоставляет победитель?",
            "Сколько составляет обеспечение обязательств по контракту?",
        ),
        "penalty": (
            "Какая пеня начисляется за просрочку?",
            "Какова ответственность за каждый день задержки?",
            "Укажите размер неустойки при нарушении срока.",
        ),
        "warranty": (
            "Какой гарантийный срок установлен?",
            "Сколько действует гарантия после приемки?",
            "Какова продолжительность гарантии на результат?",
        ),
    },
    "en": {
        "deadline": (
            "When is the proposal deadline?",
            "Until what date may a bid be submitted?",
            "State the exact submission cutoff.",
        ),
        "budget": (
            "What is the maximum contract value?",
            "What budget cap applies to this procurement?",
            "What amount must the financial offer not exceed?",
        ),
        "delivery": (
            "What is the contract delivery period?",
            "When must delivery or work be completed?",
            "How long is allowed for performance?",
        ),
        "payment": (
            "When will the customer pay after acceptance?",
            "What payment terms are specified?",
            "How soon does the supplier receive payment?",
        ),
        "bid_security": (
            "What is the bid security amount?",
            "How much security is needed to participate?",
            "What security applies specifically to the bid?",
        ),
        "performance_security": (
            "What is the performance security amount?",
            "What contract security must the winner provide?",
            "How much security covers proper performance?",
        ),
        "penalty": (
            "What penalty applies to late performance?",
            "What is charged for each day of delay?",
            "State the liquidated damages for a missed deadline.",
        ),
        "warranty": (
            "What warranty period is required?",
            "How long does the warranty last after acceptance?",
            "What is the duration of warranty coverage?",
        ),
    },
}

CONFUSION_GROUPS = {
    "deadline": ("delivery", "payment", "warranty"),
    "budget": ("bid_security", "performance_security", "penalty"),
    "delivery": ("deadline", "warranty", "payment"),
    "payment": ("delivery", "deadline", "budget"),
    "bid_security": ("performance_security", "penalty", "budget"),
    "performance_security": ("bid_security", "penalty", "budget"),
    "penalty": ("bid_security", "performance_security", "payment"),
    "warranty": ("delivery", "payment", "deadline"),
}


class TenderScenario(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    split: DatasetSplit
    language: str = Field(pattern=r"^(ru|en)$")
    profile: str
    title: str
    reference: str
    deadline: str
    budget: str
    delivery: str
    payment: str
    bid_security: str
    performance_security: str
    penalty: str
    warranty: str
    pdf_sample: bool = False


@dataclass(frozen=True, slots=True)
class DocumentFact:
    category: str
    heading: str
    passage: str
    page_number: int


def load_scenarios(path: Path) -> list[TenderScenario]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    scenarios = [TenderScenario.model_validate(item) for item in payload]
    if len({scenario.id for scenario in scenarios}) != len(scenarios):
        raise ValueError("scenario ids must be unique")
    if set(FACT_CATEGORIES) - set(TenderScenario.model_fields):
        raise ValueError("scenario schema does not contain every fact category")
    return scenarios


def build_document_facts(scenario: TenderScenario) -> list[DocumentFact]:
    facts: list[DocumentFact] = []
    for category in FACT_CATEGORIES:
        templates = PASSAGE_TEMPLATES[scenario.language][category]
        variant = _stable_variant(scenario.id, category, len(templates))
        value = getattr(scenario, category)
        facts.append(
            DocumentFact(
                category=category,
                heading=HEADINGS[scenario.language][category],
                passage=templates[variant].format(value=value),
                page_number=FACT_PAGES[category],
            )
        )
    return facts


def build_reranker_examples(scenarios: list[TenderScenario]) -> list[RerankerExample]:
    examples: list[RerankerExample] = []
    for scenario in scenarios:
        facts = build_document_facts(scenario)
        by_category = {fact.category: fact for fact in facts}
        for category in FACT_CATEGORIES:
            positive = by_category[category]
            for question_index, query in enumerate(
                QUESTION_TEMPLATES[scenario.language][category], start=1
            ):
                negatives = select_hard_negatives(query, category, facts)
                examples.append(
                    RerankerExample(
                        id=f"{scenario.id}-{category}-q{question_index}",
                        document_id=scenario.id,
                        split=scenario.split,
                        language=scenario.language,
                        query=query,
                        positive=positive.passage,
                        negatives=[fact.passage for fact in negatives],
                        category=category,
                        source_page=positive.page_number,
                        negative_categories=[fact.category for fact in negatives],
                    )
                )
    return examples


def select_hard_negatives(
    query: str,
    positive_category: str,
    facts: list[DocumentFact],
    *,
    limit: int = 3,
) -> list[DocumentFact]:
    preferred = set(CONFUSION_GROUPS[positive_category])
    candidates = [fact for fact in facts if fact.category != positive_category]
    scores = lexical_overlap_score([(query, fact.passage) for fact in candidates])
    ranked = sorted(
        zip(candidates, scores, strict=True),
        key=lambda item: (item[0].category in preferred, item[1], item[0].category),
        reverse=True,
    )
    return [fact for fact, _score in ranked[:limit]]


def _stable_variant(document_id: str, category: str, variant_count: int) -> int:
    return sum(ord(character) for character in f"{document_id}:{category}") % variant_count
