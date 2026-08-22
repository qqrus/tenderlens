# ruff: noqa: E501

import argparse
import html
import json
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from tenderlens.ml.synthetic_corpus import (
    QUESTION_TEMPLATES,
    TenderScenario,
    build_document_facts,
    load_scenarios,
)

DEFAULT_SCENARIOS = Path("evals/synthetic_tender_corpus_v2.json")
DEFAULT_OUTPUT_DIR = Path("output/pdf/tenderlens-eval-v2")
PAGE_COUNT = 20
FACT_PAGES = {
    "deadline": 4,
    "budget": 4,
    "delivery": 9,
    "payment": 11,
    "bid_security": 15,
    "performance_security": 16,
    "penalty": 17,
    "warranty": 18,
}

INK = colors.HexColor("#1E2935")
NAVY = colors.HexColor("#17365D")
BLUE = colors.HexColor("#2E5E9E")
MUTED = colors.HexColor("#66717F")
GRID = colors.HexColor("#ABB5C1")
LIGHT_GRID = colors.HexColor("#D9DFE7")
PALE_BLUE = colors.HexColor("#EDF3FA")
PALE_GRAY = colors.HexColor("#F5F6F8")
PALE_WARNING = colors.HexColor("#FFF5DD")
WARNING = colors.HexColor("#9A3F2E")

LEGAL_SOURCES = (
    {
        "title": "Федеральный закон от 05.04.2013 N 44-ФЗ",
        "url": "https://publication.pravo.gov.ru/Document/View/0001201304080023",
    },
    {
        "title": "ГОСТ Р 7.0.97-2025 (действует с 18.08.2025)",
        "url": "https://protect.gost.ru/gost/details/360994e3-9a70-47b9-ab3a-cf21809e26ed",
    },
)

UNANSWERABLE_QUESTIONS = {
    "ru": (
        "Какой номер страхового полиса указан для поставщика?",
        "Какой минимальный процент работ нужно передать субподрядчикам?",
    ),
    "en": (
        "What supplier insurance policy number is specified?",
        "What minimum percentage of work must be subcontracted?",
    ),
}

PROFILE_LABELS = {
    "ru": {
        "goods": "поставка товаров",
        "works": "выполнение работ",
        "services": "оказание услуг",
        "it": "ИТ-услуги и поставка решений",
        "energy": "строительно-монтажные и пусконаладочные работы",
    },
    "en": {
        "goods": "supply of goods",
        "works": "performance of works",
        "services": "provision of services",
        "it": "IT services and solution delivery",
        "energy": "construction and commissioning works",
    },
}

PROFILE_ROWS = {
    "ru": {
        "goods": (
            ("Комплектность", "Новый товар в полной комплектации"),
            ("Маркировка", "Изготовитель, серийный номер и дата выпуска читаемы"),
            ("Документация", "Паспорт, руководство и документы о качестве"),
            ("Упаковка", "Защита от повреждения при перевозке и хранении"),
        ),
        "works": (
            ("Организация", "План производства работ до допуска на объект"),
            ("Материалы", "Новые материалы с документами о качестве"),
            ("Документация", "Журналы, схемы и акты скрытых работ"),
            ("Безопасность", "Охрана труда, пожарный и пропускной режим"),
        ),
        "services": (
            ("План услуг", "График, роли и порядок эскалации"),
            ("Отчетность", "Объем, показатели качества и отклонения"),
            ("Персонал", "Квалификация и заменяемость специалистов"),
            ("Непрерывность", "Регистрация сбоев и корректирующих мер"),
        ),
        "it": (
            ("Совместимость", "Интеграция с тестовым контуром заказчика"),
            ("Документация", "Архитектура, инструкции и журнал изменений"),
            ("Защита данных", "Ролевой доступ и журналирование событий"),
            ("Тестирование", "Функциональные и приемочные испытания"),
        ),
        "energy": (
            ("Проектирование", "Согласование решений до заказа оборудования"),
            ("Оборудование", "Новое, комплектное и пригодное к режиму"),
            ("Испытания", "Индивидуальные, комплексные и нагрузочные"),
            ("Безопасность", "Допуск, охрана труда и электробезопасность"),
        ),
    },
    "en": {
        "goods": (
            ("Completeness", "New goods supplied as a complete operational set"),
            ("Identification", "Manufacturer, serial number and production date"),
            ("Documentation", "Manuals and quality evidence"),
            ("Packaging", "Protection during transport and storage"),
        ),
        "works": (
            ("Work plan", "Method statement approved before site access"),
            ("Materials", "New materials with quality evidence"),
            ("Records", "Site logs, as-built diagrams and inspection records"),
            ("Safety", "Occupational, fire and access requirements"),
        ),
        "services": (
            ("Service plan", "Schedule, roles and escalation procedure"),
            ("Reporting", "Scope, quality indicators and deviations"),
            ("Personnel", "Qualified staff and role coverage"),
            ("Continuity", "Incident and corrective-action records"),
        ),
        "it": (
            ("Compatibility", "Integration with the customer test environment"),
            ("Documentation", "Architecture, manuals and change log"),
            ("Data protection", "Role-based access and event logging"),
            ("Testing", "Functional and acceptance testing"),
        ),
        "energy": (
            ("Design", "Approval before major equipment ordering"),
            ("Equipment", "New, complete and suitable for stated duty"),
            ("Testing", "Individual, integrated and load tests"),
            ("Safety", "Access, occupational and electrical controls"),
        ),
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate realistic, safe, synthetic TenderLens procurement PDFs"
    )
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--all", action="store_true", help="Generate all scenarios, not samples only"
    )
    return parser.parse_args()


def register_fonts() -> tuple[str, str]:
    candidates = [
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
    ]
    for regular, bold in candidates:
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("TenderLensSans", str(regular)))
            pdfmetrics.registerFont(TTFont("TenderLensSansBold", str(bold)))
            return "TenderLensSans", "TenderLensSansBold"
    raise RuntimeError("No Unicode TrueType font was found")


def safe(value: object) -> str:
    return html.escape(str(value), quote=False)


def paragraph(text: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(safe(text), style)


def rich(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def build_styles(regular: str, bold: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "org": ParagraphStyle(
            "org",
            parent=base["Normal"],
            fontName=bold,
            fontSize=10,
            leading=13,
            alignment=TA_CENTER,
            textColor=INK,
        ),
        "approval": ParagraphStyle(
            "approval",
            parent=base["Normal"],
            fontName=regular,
            fontSize=8.5,
            leading=11,
            alignment=TA_LEFT,
            textColor=INK,
        ),
        "kind": ParagraphStyle(
            "kind",
            parent=base["Normal"],
            fontName=bold,
            fontSize=11,
            leading=14,
            alignment=TA_CENTER,
            textColor=NAVY,
        ),
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName=bold,
            fontSize=19,
            leading=24,
            alignment=TA_CENTER,
            textColor=INK,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontName=regular,
            fontSize=9.5,
            leading=13,
            alignment=TA_CENTER,
            textColor=MUTED,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName=bold,
            fontSize=13,
            leading=16,
            alignment=TA_LEFT,
            textColor=NAVY,
            spaceAfter=7,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName=bold,
            fontSize=10,
            leading=13,
            textColor=INK,
            spaceBefore=4,
            spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=9.2,
            leading=13.2,
            alignment=TA_JUSTIFY,
            firstLineIndent=12.5 * mm,
            textColor=INK,
            spaceAfter=5,
        ),
        "body_plain": ParagraphStyle(
            "body_plain",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=9.2,
            leading=13.2,
            alignment=TA_LEFT,
            textColor=INK,
            spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["Normal"],
            fontName=regular,
            fontSize=7.7,
            leading=10,
            textColor=MUTED,
        ),
        "table": ParagraphStyle(
            "table",
            parent=base["Normal"],
            fontName=regular,
            fontSize=8.1,
            leading=10.3,
            textColor=INK,
        ),
        "table_bold": ParagraphStyle(
            "table_bold",
            parent=base["Normal"],
            fontName=bold,
            fontSize=8.1,
            leading=10.3,
            textColor=INK,
        ),
        "fact": ParagraphStyle(
            "fact",
            parent=base["BodyText"],
            fontName=bold,
            fontSize=9.2,
            leading=13.2,
            textColor=INK,
        ),
        "warning": ParagraphStyle(
            "warning",
            parent=base["Normal"],
            fontName=bold,
            fontSize=8,
            leading=10.5,
            alignment=TA_CENTER,
            textColor=WARNING,
        ),
    }


def grid_table(
    rows: list[list[object]],
    widths: list[float],
    styles: dict[str, ParagraphStyle],
    *,
    header: bool = True,
) -> Table:
    rendered = [
        [
            cell
            if isinstance(cell, Paragraph)
            else paragraph(
                cell, styles["table_bold"] if header and row_index == 0 else styles["table"]
            )
            for cell in row
        ]
        for row_index, row in enumerate(rows)
    ]
    result = Table(rendered, colWidths=widths, repeatRows=1 if header else 0)
    commands: list[tuple[Any, ...]] = [
        ("BOX", (0, 0), (-1, -1), 0.6, GRID),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, LIGHT_GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        commands.append(("BACKGROUND", (0, 0), (-1, 0), PALE_BLUE))
    else:
        commands.append(("BACKGROUND", (0, 0), (0, -1), PALE_GRAY))
    result.setStyle(TableStyle(commands))
    return result


def fact_box(label: str, passage: str, styles: dict[str, ParagraphStyle]) -> Table:
    result = Table(
        [[paragraph(label, styles["table_bold"])], [paragraph(passage, styles["fact"])]],
        colWidths=[160 * mm],
    )
    result.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.8, BLUE),
                ("LINEBEFORE", (0, 0), (0, -1), 3, BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return result


def warning_box(text: str, styles: dict[str, ParagraphStyle]) -> Table:
    result = Table([[paragraph(text, styles["warning"])]], colWidths=[160 * mm])
    result.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_WARNING),
                ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#D9A64E")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return result


def prose(language: str, group: str) -> tuple[str, ...]:
    ru = {
        "legal": (
            "Комплект подготовлен как синтетический пример конкурентной закупки. При моделировании структуры учтены группы сведений, предусмотренные статьями 31, 33, 34, 42, 43, 44, 45, 51, 94 и 96 Федерального закона от 05.04.2013 N 44-ФЗ. Применимость нормы всегда зависит от способа закупки, объекта и действующей редакции законодательства.",
            "Описание объекта должно позволять сопоставить предложение с измеримыми характеристиками и не должно искусственно ограничивать число участников. Поэтому требования разделены на функциональные, технические, качественные и эксплуатационные показатели. Отсутствующие значения нельзя додумывать.",
            "Проект контракта моделирует распределение обязанностей, приемку, оплату, обеспечение и ответственность. Условия теста не являются типовыми условиями, правовым заключением или рекомендацией заказчику.",
            "В реальной закупке электронное взаимодействие осуществляется через ЕИС и площадку. Здесь адреса площадки, подписи и регистрационные данные намеренно заменены безопасными вымышленными значениями.",
        ),
        "general": (
            "Термины применяются в значении, установленном комплектом. Если специальное условие противоречит общему пояснению, для тестового сценария приоритет имеет условие на странице соответствующего раздела.",
            "Участник учитывает расходы на налоги, доставку, упаковку, материалы, персонал, документацию и иные затраты, связанные с предметом закупки. Отсутствие отдельной строки не создает право на дополнительную оплату.",
            "Разъяснения и изменения в реальной процедуре размещаются через предусмотренные законом средства. Переписка вне установленного канала не меняет условия и не создает преимуществ отдельному участнику.",
        ),
        "technical": (
            "Результат должен соответствовать назначению объекта, условиям эксплуатации и показателям в таблицах. Ссылки на стандарты и документы о качестве применяются в той мере, в какой они относятся к конкретному товару, работе или услуге.",
            "Эквивалентность оценивается по совокупности обязательных характеристик. Реклама, ссылка на сайт изготовителя или неподписанная презентация сами по себе не заменяют требуемое техническое описание.",
            "До начала исполнения стороны согласуют рабочие контакты, формат отчетности и доступ на объект. Такое согласование не меняет предмет, цену и иные существенные условия будущего контракта.",
        ),
        "acceptance": (
            "Приемка проводится с проверкой количества, комплектности, качества и соответствия техническому заданию. При необходимости проводятся испытания и экспертиза.",
            "Несоответствия фиксируются в мотивированном документе. Исполнитель устраняет относимые к нему недостатки и повторно предъявляет результат без переложения своих расходов на заказчика.",
            "Промежуточная приемка не лишает заказчика права ссылаться на скрытые недостатки, которые невозможно было установить обычным способом в момент проверки.",
        ),
        "application": (
            "Заявка формируется средствами электронной площадки и содержит сведения только в объеме, который допустимо требовать для соответствующего способа закупки. Отсутствие необязательного материала не должно быть самостоятельным основанием отклонения.",
            "Участник отвечает за достоверность сведений, полномочия подписанта и соответствие предложения. Файлы должны открываться стандартными средствами и не содержать исполняемый код.",
            "Комиссия рассматривает содержание, доступное к окончанию приема заявок. Исправление существенных сведений после срока данным комплектом не моделируется.",
        ),
        "contract": (
            "Стороны действуют добросовестно, своевременно обмениваются документами и назначают ответственных представителей. Изменение условий допускается только в предусмотренных законом и контрактом случаях.",
            "Исполнитель несет риск повреждения результата до приемки, если иное не следует из существа обязательства. Привлечение третьих лиц не освобождает его от ответственности перед заказчиком.",
            "Обстоятельства непреодолимой силы подтверждаются доказательствами и не прекращают обязательства автоматически. Сторона уведомляет контрагента и принимает разумные меры по уменьшению последствий.",
        ),
    }
    en = {
        "legal": (
            "This is an unofficial English evaluation copy of a fictional procurement package. References to Articles 31, 33, 34, 42, 43, 44, 45, 51, 94 and 96 of Federal Law No. 44-FZ reproduce realistic document density for multilingual RAG testing.",
            "A live Russian procurement is governed by its official Russian-language notice and the law applicable to its method, subject and publication date. Nothing here is a legal opinion, model contract or recommendation.",
            "The object description is organised into functional, technical, quality and operating requirements. Missing values must not be inferred, and marketing material does not replace requested evidence.",
            "Platform addresses, identifiers, signatures and personal data are replaced by fictional values. No response can be submitted and no legal relationship can arise from this file.",
        ),
        "general": (
            "Defined terms have the meaning given in this package. A specific requirement in the relevant section prevails over explanatory text for this evaluation scenario.",
            "The bidder accounts for taxes, transport, packaging, personnel, materials and documentation directly connected with performance. An omitted price line does not create an extra payment entitlement.",
            "In a live procedure, clarifications and amendments use the designated information system. Informal correspondence does not modify the terms or grant an individual advantage.",
        ),
        "technical": (
            "The result must fit its intended use, operating conditions and measurable table requirements. Standards and quality evidence apply only where relevant to the goods, works or services.",
            "Equivalence is assessed against all mandatory characteristics. Website links, promotional claims and unsigned presentations do not replace a required technical description.",
            "Before performance, the parties agree contacts, reporting formats and access. Such coordination cannot change the subject, price or other material terms.",
        ),
        "acceptance": (
            "Authorised representatives verify quantity, completeness, quality and conformity with the specification. Testing or independent examination may be used where appropriate.",
            "Non-conformities are recorded in a reasoned notice. The contractor corrects attributable defects and resubmits the result without shifting its corrective costs to the customer.",
            "Interim acceptance does not waive claims for latent defects that could not reasonably be detected during ordinary inspection.",
        ),
        "application": (
            "The bid contains only information and documents that may be requested for the relevant procurement method. Missing optional material is not an independent rejection ground.",
            "The bidder is responsible for accuracy, signatory authority and compliance. Uploaded files must open with standard software and must not contain executable code.",
            "The committee evaluates information available at the submission cutoff. Correction of material content after the deadline is not modelled here.",
        ),
        "contract": (
            "The parties act in good faith, exchange records promptly and appoint contacts. Contract changes are made only where permitted and in the required form.",
            "The contractor bears risk before acceptance unless the obligation requires otherwise. Subcontracting does not release responsibility to the customer.",
            "Force majeure requires evidence and does not automatically terminate obligations. The affected party gives prompt notice and mitigates consequences.",
        ),
    }
    return (ru if language == "ru" else en)[group]


def headings(language: str) -> list[str]:
    if language == "ru":
        return [
            "Титульный лист",
            "Содержание",
            "1. Статус документа и правовая основа",
            "2. Информационная карта закупки",
            "3. Планирование и идентификация",
            "4. Обоснование начальной (максимальной) цены",
            "5. Описание объекта закупки",
            "6. Функциональные, технические и качественные требования",
            "7. Место, этапы и сроки исполнения",
            "8. Порядок сдачи и приемки",
            "9. Цена контракта и порядок оплаты",
            "10. Требования к участникам закупки",
            "11. Состав заявки и порядок подачи",
            "12. Рассмотрение и оценка заявок",
            "13. Обеспечение заявки",
            "14. Обеспечение исполнения контракта",
            "15. Ответственность сторон и неустойка",
            "16. Гарантийные обязательства",
            "17. Основные условия проекта контракта",
            "18. Приложения и контрольные формы",
        ]
    return [
        "Cover",
        "Contents",
        "1. Document status and legal context",
        "2. Procurement information sheet",
        "3. Planning and identification",
        "4. Maximum contract value justification",
        "5. Procurement object description",
        "6. Functional, technical and quality requirements",
        "7. Place, milestones and performance schedule",
        "8. Handover and acceptance",
        "9. Contract price and payment",
        "10. Bidder requirements",
        "11. Bid contents and submission",
        "12. Bid review and evaluation",
        "13. Bid security",
        "14. Performance security",
        "15. Liability and liquidated damages",
        "16. Warranty obligations",
        "17. Draft contract key terms",
        "18. Annexes and control forms",
    ]


def cover(scenario: TenderScenario, styles: dict[str, ParagraphStyle]) -> list[Any]:
    ru = scenario.language == "ru"
    approval = (
        f"УТВЕРЖДЕНО<br/>для синтетического тестирования<br/>Рег. N {safe(scenario.reference)}<br/>21 августа 2026 г."
        if ru
        else f"APPROVED<br/>for synthetic evaluation<br/>Ref. {safe(scenario.reference)}<br/>21 August 2026"
    )
    return [
        Table([["", rich(approval, styles["approval"])]], colWidths=[94 * mm, 66 * mm]),
        Spacer(1, 17 * mm),
        rich(
            "ФИКТИВНОЕ УЧЕБНОЕ УЧРЕЖДЕНИЕ<br/>«ЦЕНТР ТЕСТИРОВАНИЯ TENDERLENS»"
            if ru
            else "FICTIONAL TRAINING AUTHORITY<br/>TENDERLENS EVALUATION CENTRE",
            styles["org"],
        ),
        Spacer(1, 17 * mm),
        paragraph(
            "КОМПЛЕКТ МАТЕРИАЛОВ КОНКУРЕНТНОЙ ЗАКУПКИ"
            if ru
            else "COMPETITIVE PROCUREMENT DOCUMENT PACKAGE",
            styles["kind"],
        ),
        Spacer(1, 4 * mm),
        paragraph(scenario.title, styles["title"]),
        Spacer(1, 8 * mm),
        grid_table(
            [
                ["Идентификатор" if ru else "Reference", scenario.reference],
                [
                    "Профиль" if ru else "Profile",
                    PROFILE_LABELS[scenario.language][scenario.profile],
                ],
                ["Редакция" if ru else "Version", "1.0 / 21.08.2026"],
            ],
            [46 * mm, 114 * mm],
            styles,
            header=False,
        ),
        Spacer(1, 12 * mm),
        warning_box(
            "СИНТЕТИЧЕСКИЙ ТЕСТОВЫЙ ДОКУМЕНТ. НЕ ЯВЛЯЕТСЯ ИЗВЕЩЕНИЕМ О ЗАКУПКЕ."
            if ru
            else "SYNTHETIC TEST DOCUMENT. NOT A PROCUREMENT NOTICE.",
            styles,
        ),
        Spacer(1, 8 * mm),
        paragraph(
            "Все организации, реквизиты, суммы и условия вымышлены. Не является юридической консультацией."
            if ru
            else "All entities, identifiers, amounts and terms are fictional. This is not legal advice.",
            styles["subtitle"],
        ),
        Spacer(1, 25 * mm),
        paragraph("Тестоград, 2026" if ru else "Testograd, 2026", styles["subtitle"]),
    ]


def contents_page(language: str, styles: dict[str, ParagraphStyle]) -> list[Any]:
    titles = headings(language)[2:]
    rows = [[title, str(index)] for index, title in enumerate(titles, start=3)]
    ru = language == "ru"
    return [
        grid_table(rows, [146 * mm, 14 * mm], styles, header=False),
        Spacer(1, 7 * mm),
        paragraph(
            "Разделы содержат близкие даты, проценты и сроки. Это проверяет, отличает ли TenderLens дедлайн заявки от срока исполнения, а обеспечение заявки - от обеспечения контракта."
            if ru
            else "Sections contain similar dates, percentages and periods. This tests whether TenderLens distinguishes the proposal deadline from performance and bid security from performance security.",
            styles["body"],
        ),
    ]


def body_pages(
    scenario: TenderScenario, facts: dict[str, Any], styles: dict[str, ParagraphStyle]
) -> list[list[Any]]:
    ru = scenario.language == "ru"
    b = styles["body"]
    h2 = styles["h2"]
    tech_rows = [["Показатель" if ru else "Parameter", "Требование" if ru else "Requirement"]]
    tech_rows.extend([list(row) for row in PROFILE_ROWS[scenario.language][scenario.profile]])

    legal = [paragraph(text, b) for text in prose(scenario.language, "legal")]
    legal += [
        paragraph("Нормативные ориентиры" if ru else "Reference sources", h2),
        grid_table(
            [["Документ" if ru else "Source", "Официальный адрес" if ru else "Official location"]]
            + [[item["title"], item["url"]] for item in LEGAL_SOURCES],
            [67 * mm, 93 * mm],
            styles,
        ),
        Spacer(1, 3 * mm),
        paragraph(
            "Дата сверки: 21.08.2026. Перед реальным применением проверяются действующая редакция, способ закупки и специальные ограничения."
            if ru
            else "Checked on 21 August 2026. A live use requires verification of current law, method and special restrictions.",
            styles["small"],
        ),
    ]

    info = [
        grid_table(
            [
                ["Параметр" if ru else "Field", "Сведения" if ru else "Information"],
                [
                    "Заказчик" if ru else "Customer",
                    "Фиктивное учебное учреждение «Центр тестирования TenderLens»"
                    if ru
                    else "Fictional Training Authority - TenderLens Evaluation Centre",
                ],
                [
                    "Адрес" if ru else "Address",
                    "г. Тестоград, ул. Проектная, д. 1 (вымышленный адрес)"
                    if ru
                    else "1 Project Street, Testograd (fictional address)",
                ],
                ["Контакт" if ru else "Contact", "procurement@example.invalid; +7 (000) 000-00-00"],
                [
                    "Способ" if ru else "Method",
                    "Электронный конкурс (учебная модель)"
                    if ru
                    else "Electronic competition (evaluation model)",
                ],
                ["Объект" if ru else "Subject", scenario.title],
            ],
            [48 * mm, 112 * mm],
            styles,
        ),
        Spacer(1, 5 * mm),
        fact_box(
            "2.1. Срок подачи заявок" if ru else "2.1. Proposal deadline",
            facts["deadline"].passage,
            styles,
        ),
        Spacer(1, 4 * mm),
        fact_box(
            "2.2. Начальная цена" if ru else "2.2. Maximum value", facts["budget"].passage, styles
        ),
        Spacer(1, 4 * mm),
        paragraph(
            "Запросы о разъяснении, изменение извещения и отмена реальной процедуры выполняются в порядке статьи 42 Закона N 44-ФЗ. В этом макете они недоступны."
            if ru
            else "In a live procurement, clarifications, amendments and cancellation follow Article 42 of Federal Law No. 44-FZ. They are unavailable here.",
            b,
        ),
    ]

    planning = [
        grid_table(
            [
                [
                    "Реквизит" if ru else "Identifier",
                    "Значение" if ru else "Value",
                    "Примечание" if ru else "Note",
                ],
                [
                    "Условный ИКЗ" if ru else "Fictional procurement code",
                    scenario.reference.replace("TL-", "SYN-") + "-000000",
                    "Не реальный ИКЗ" if ru else "Not a real code",
                ],
                [
                    "План-график" if ru else "Plan",
                    "2026-TEST",
                    "В ЕИС отсутствует" if ru else "Not in EIS",
                ],
                [
                    "Финансирование" if ru else "Funding",
                    "Условный учебный бюджет" if ru else "Fictional training budget",
                    "Оплата не производится" if ru else "No funds payable",
                ],
                [
                    "Классификация" if ru else "Classification",
                    "TEST-00.00.00",
                    "Служебный код" if ru else "Evaluation-only code",
                ],
            ],
            [44 * mm, 61 * mm, 55 * mm],
            styles,
        ),
        Spacer(1, 5 * mm),
        *[paragraph(text, b) for text in prose(scenario.language, "general")],
        paragraph(
            "Дата проекта комплекта - 14 августа 2026 года. Она не совпадает со сроком подачи заявок или сроком исполнения."
            if ru
            else "The package draft date is 14 August 2026. It is neither the proposal deadline nor the performance period.",
            b,
        ),
    ]

    price = [
        paragraph(
            "Начальная цена рассчитана условным методом сопоставимых рыночных цен. Исходные котировки исключены, чтобы набор не содержал реквизиты реальных контрагентов."
            if ru
            else "The maximum value is modelled using comparable market information. Source quotes are excluded so no genuine counterparty details enter the dataset.",
            b,
        ),
        grid_table(
            [
                [
                    "N",
                    "Источник" if ru else "Source",
                    "Сведения" if ru else "Data",
                    "Вес" if ru else "Weight",
                ],
                [
                    "1",
                    "Ценовая информация A" if ru else "Market response A",
                    "Обезличено" if ru else "Redacted",
                    "33,3%",
                ],
                [
                    "2",
                    "Ценовая информация B" if ru else "Market response B",
                    "Обезличено" if ru else "Redacted",
                    "33,3%",
                ],
                [
                    "3",
                    "Сопоставимый контракт C" if ru else "Comparable contract C",
                    "Обезличено" if ru else "Redacted",
                    "33,4%",
                ],
            ],
            [12 * mm, 66 * mm, 56 * mm, 26 * mm],
            styles,
        ),
        Spacer(1, 5 * mm),
        paragraph(
            "Расчет включает расходы на исполнение и обязательные платежи в объеме, указанном в информационной карте. Отдельная компенсация обычных расходов не предусмотрена."
            if ru
            else "The estimate includes performance costs and mandatory payments stated in the information sheet. Ordinary costs are not reimbursed separately.",
            b,
        ),
        paragraph(
            "Плановый резерв 2% - внутренний индикатор макета. Он не увеличивает начальную цену, не является обеспечением и не оплачивается исполнителю."
            if ru
            else "A 2% internal planning reserve is an evaluation indicator. It does not increase the maximum value, is not security and is not payable.",
            b,
        ),
        warning_box(
            f"Контрольное значение начальной цены приведено на странице {FACT_PAGES['budget']}."
            if ru
            else f"The controlling maximum value appears on page {FACT_PAGES['budget']}.",
            styles,
        ),
    ]

    description = [
        paragraph(
            (
                f"Предмет закупки: {scenario.title}. Результат передается в полном объеме, пригодном для использования по назначению, с документацией и подтверждающими материалами."
                if ru
                else f"Procurement subject: {scenario.title}. The complete result is delivered fit for purpose with documentation and supporting records."
            ),
            b,
        ),
        *[paragraph(text, b) for text in prose(scenario.language, "technical")],
        grid_table(
            [
                ["Элемент" if ru else "Element", "Описание" if ru else "Description"],
                ["Основной результат" if ru else "Primary result", scenario.title],
                [
                    "Сопутствующий" if ru else "Supporting result",
                    "Документация, отчет и протокол испытаний"
                    if ru
                    else "Documentation, reporting and test record",
                ],
                [
                    "Место" if ru else "Location",
                    "Условный объект в г. Тестограде"
                    if ru
                    else "Fictional customer site in Testograd",
                ],
                [
                    "Исключения" if ru else "Exclusions",
                    "Прямо не указанные работы и поставки"
                    if ru
                    else "Work and supply not expressly included",
                ],
            ],
            [48 * mm, 112 * mm],
            styles,
        ),
    ]

    quality = [
        grid_table(tech_rows, [54 * mm, 106 * mm], styles),
        Spacer(1, 5 * mm),
        paragraph(
            "Показатели читаются совместно с описанием объекта. Слова «не менее», «не более», диапазон и точное значение имеют различный смысл; конкретное предложение указывается там, где это требует форма заявки."
            if ru
            else "Requirements are read with the object description. Minimum, maximum, range and exact values differ; a concrete offer is stated where the bid form requires it.",
            b,
        ),
        paragraph(
            "Контроль включает входную проверку, промежуточный контроль и итоговую приемку. Внутренняя проверка отчета до 5 рабочих дней не является сроком оплаты и не продлевает исполнение."
            if ru
            else "Control includes incoming, interim and final checks. Internal report review of up to five business days is not the payment term and does not extend performance.",
            b,
        ),
        paragraph(
            "Разъяснение характеристик не должно менять существо предложения. Недостоверные сведения оцениваются в порядке, применимом к процедуре."
            if ru
            else "Clarification must not change the substance of the offer. Inaccurate information is handled under the applicable procedure.",
            b,
        ),
    ]

    delivery = [
        fact_box(
            "7.1. Срок исполнения обязательств" if ru else "7.1. Performance period",
            facts["delivery"].passage,
            styles,
        ),
        Spacer(1, 5 * mm),
        grid_table(
            [
                [
                    "Этап" if ru else "Milestone",
                    "Содержание" if ru else "Scope",
                    "Контроль" if ru else "Control",
                ],
                [
                    "1",
                    "План и исходные данные" if ru else "Plan and inputs",
                    "Протокол запуска" if ru else "Kick-off record",
                ],
                [
                    "2",
                    "Основной объем" if ru else "Main scope",
                    "Промежуточный отчет" if ru else "Interim report",
                ],
                [
                    "3",
                    "Испытания и передача" if ru else "Testing and handover",
                    "Итоговый акт" if ru else "Final certificate",
                ],
            ],
            [20 * mm, 87 * mm, 53 * mm],
            styles,
        ),
        Spacer(1, 5 * mm),
        paragraph(
            "Место исполнения - условный объект в г. Тестограде или защищенный тестовый контур, если допускается удаленная работа. Режим доступа согласуется организационно."
            if ru
            else "Performance occurs at the fictional Testograd site or a protected test environment where remote work is suitable. Access is coordinated separately.",
            b,
        ),
        paragraph(
            "Уведомление о готовности направляется за 3 рабочих дня. Этот организационный срок не является дедлайном подачи заявки."
            if ru
            else "A readiness notice is sent three business days before handover. This is not the proposal deadline.",
            b,
        ),
    ]

    acceptance = [paragraph(text, b) for text in prose(scenario.language, "acceptance")]
    acceptance += [
        grid_table(
            [
                ["Проверка" if ru else "Check", "Документ" if ru else "Evidence"],
                [
                    "Количество и комплектность" if ru else "Quantity and completeness",
                    "Накладная или ведомость" if ru else "Delivery note or schedule",
                ],
                [
                    "Качество" if ru else "Quality",
                    "Протокол проверки / испытаний" if ru else "Inspection or test record",
                ],
                [
                    "Документация" if ru else "Documentation",
                    "Реестр переданных материалов" if ru else "Delivered-material register",
                ],
                [
                    "Устранение замечаний" if ru else "Correction",
                    "Повторный акт" if ru else "Repeat inspection record",
                ],
            ],
            [66 * mm, 94 * mm],
            styles,
        ),
        Spacer(1, 4 * mm),
        paragraph(
            "Документальная проверка занимает до 7 рабочих дней после полного предъявления. Это срок проверки, а не срок оплаты."
            if ru
            else "Document review may take seven business days after complete submission. It is an inspection period, not the payment term.",
            b,
        ),
    ]

    payment = [
        fact_box(
            "9.1. Срок и основание оплаты" if ru else "9.1. Payment timing and basis",
            facts["payment"].passage,
            styles,
        ),
        Spacer(1, 5 * mm),
        paragraph(
            "Цена включает необходимые расходы. Безналичная оплата основана на документе о приемке и предусмотренном расчетном документе. Аванс и расходы на финансирование отдельно не компенсируются."
            if ru
            else "The price includes required costs. Cashless payment is based on acceptance and the specified billing record. Advance and financing costs are not reimbursed.",
            b,
        ),
        grid_table(
            [
                [
                    "Документ" if ru else "Document",
                    "Назначение" if ru else "Purpose",
                    "Когда" if ru else "Timing",
                ],
                [
                    "Акт" if ru else "Acceptance certificate",
                    "Подтверждение результата" if ru else "Confirms result",
                    "После проверки" if ru else "After inspection",
                ],
                [
                    "Счет" if ru else "Invoice",
                    "Расчетный документ" if ru else "Billing record",
                    "Вместе с актом" if ru else "With acceptance",
                ],
                [
                    "Отчет" if ru else "Report",
                    "Раскрывает объем" if ru else "Describes scope",
                    "До приемки" if ru else "Before acceptance",
                ],
            ],
            [54 * mm, 64 * mm, 42 * mm],
            styles,
        ),
        Spacer(1, 5 * mm),
        paragraph(
            "Ошибочно перечисленные средства возвращаются в течение 5 рабочих дней после уведомления. Это не меняет основной срок оплаты."
            if ru
            else "Erroneously transferred funds are returned within five business days after notice. This does not alter the main payment term.",
            b,
        ),
    ]

    participant = [
        paragraph(
            "Единые требования моделируются по смыслу статьи 31 Закона N 44-ФЗ. Перечень не подтверждает достаточность для любого реального предмета закупки."
            if ru
            else "Common bidder requirements are modelled on Article 31 of Federal Law No. 44-FZ. The list is not sufficient guidance for a live procurement.",
            b,
        ),
        grid_table(
            [
                ["Группа" if ru else "Group", "Проверка" if ru else "Review"],
                [
                    "Правоспособность" if ru else "Legal capacity",
                    "Регистрация и полномочия подписанта"
                    if ru
                    else "Registration and signatory authority",
                ],
                [
                    "Надежность" if ru else "Integrity",
                    "Отсутствие применимых оснований недопуска"
                    if ru
                    else "No applicable exclusion ground",
                ],
                [
                    "Конфликт интересов" if ru else "Conflict",
                    "Декларация в применимом объеме" if ru else "Declaration where applicable",
                ],
                [
                    "Специальный допуск" if ru else "Authorisation",
                    "Только при прямом основании" if ru else "Only where expressly justified",
                ],
            ],
            [55 * mm, 105 * mm],
            styles,
        ),
        Spacer(1, 5 * mm),
        paragraph(
            "Дополнительные требования допустимы только при наличии правового основания и должны быть сформулированы так, чтобы участник мог однозначно определить состав подтверждающих сведений."
            if ru
            else "Additional bidder requirements need a legal basis and must identify the supporting information unambiguously.",
            b,
        ),
    ]

    application = [paragraph(text, b) for text in prose(scenario.language, "application")]
    application += [
        grid_table(
            [
                [
                    "Часть" if ru else "Part",
                    "Содержание" if ru else "Content",
                    "Форма" if ru else "Form",
                ],
                [
                    "Участник" if ru else "Bidder",
                    "Идентификация и полномочия" if ru else "Identity and authority",
                    "Поля площадки" if ru else "Platform fields",
                ],
                [
                    "Предложение" if ru else "Offer",
                    "Характеристики и согласие" if ru else "Characteristics and consent",
                    "Электронный документ" if ru else "Electronic document",
                ],
                [
                    "Цена" if ru else "Price",
                    "Ценовое предложение" if ru else "Financial offer",
                    "Средства площадки" if ru else "Platform interface",
                ],
                [
                    "Подтверждения" if ru else "Evidence",
                    "Только при основании" if ru else "Only where justified",
                    "PDF / данные" if ru else "PDF / data",
                ],
            ],
            [42 * mm, 72 * mm, 46 * mm],
            styles,
        ),
        Spacer(1, 4 * mm),
        paragraph(
            "Внутренняя проверка файла за 30 минут до отправки - рекомендация участнику, а не официальный дедлайн."
            if ru
            else "An internal file check 30 minutes before upload is workflow advice, not the official deadline.",
            b,
        ),
    ]

    evaluation = [
        paragraph(
            "Рассмотрение начинается с проверки соответствия извещению. Оценка применяется только к заявкам, допущенным к дальнейшему сопоставлению по правилам моделируемого способа."
            if ru
            else "Review starts with notice compliance. Evaluation applies only to bids eligible for further comparison under the modelled method.",
            b,
        ),
        grid_table(
            [
                [
                    "Этап" if ru else "Stage",
                    "Действие" if ru else "Action",
                    "Результат" if ru else "Outcome",
                ],
                [
                    "1",
                    "Комплектность и полномочия" if ru else "Completeness and authority",
                    "Содержательная проверка" if ru else "Substantive review",
                ],
                [
                    "2",
                    "Характеристики" if ru else "Technical compliance",
                    "Соответствует / нет" if ru else "Compliant / not",
                ],
                [
                    "3",
                    "Цена" if ru else "Financial offer",
                    "Допустимое предложение" if ru else "Admissible offer",
                ],
                [
                    "4",
                    "Протокол" if ru else "Protocol",
                    "Решение и основания" if ru else "Decision and reasons",
                ],
            ],
            [18 * mm, 82 * mm, 60 * mm],
            styles,
        ),
        Spacer(1, 5 * mm),
        paragraph(
            "Внутренняя подготовка протокола до 2 рабочих дней не является сроком заявки, оплаты или исполнения. Причина несоответствия связывается с конкретным требованием."
            if ru
            else "An internal two-business-day protocol target is not the bid, payment or performance term. Non-compliance must link to a requirement.",
            b,
        ),
        paragraph(
            "Вывод TenderLens не заменяет закупочную комиссию и не имеет юридического значения."
            if ru
            else "A TenderLens output does not replace the procurement committee and has no legal effect.",
            b,
        ),
    ]

    def security(category: str, performance: bool) -> list[Any]:
        label = (
            ("14.1. Размер обеспечения исполнения" if ru else "14.1. Performance security amount")
            if performance
            else ("13.1. Размер обеспечения заявки" if ru else "13.1. Bid security amount")
        )
        articles = "45 и 96" if performance else "44 и 45"
        extra = (
            "Проверка обеспечения до 3 рабочих дней не является гарантийным сроком результата."
            if performance and ru
            else "Review of security for up to three business days is not the result warranty period."
            if performance
            else "Техническая блокировка средств не меняет размер обеспечения и не является штрафом."
            if ru
            else "A technical funds hold does not change the amount and is not a penalty."
        )
        return [
            fact_box(label, facts[category].passage, styles),
            Spacer(1, 5 * mm),
            paragraph(
                (
                    f"Форма, срок действия и предоставление моделируются с учетом статей {articles} Закона N 44-ФЗ. Реальные банковские реквизиты и номера гарантий исключены."
                    if ru
                    else f"Form, validity and submission are modelled with reference to Articles {articles} of Federal Law No. 44-FZ. Real bank details and guarantee numbers are excluded."
                ),
                b,
            ),
            grid_table(
                [
                    [
                        "Способ" if ru else "Instrument",
                        "Отражение в макете" if ru else "Treatment",
                        "Контроль" if ru else "Control",
                    ],
                    [
                        "Денежные средства" if ru else "Funds",
                        "Без реквизитов" if ru else "Without bank details",
                        "Размер и назначение" if ru else "Amount and purpose",
                    ],
                    [
                        "Независимая гарантия" if ru else "Independent guarantee",
                        "Без номера и гаранта" if ru else "Without number or guarantor",
                        "Срок и условия" if ru else "Validity and terms",
                    ],
                ],
                [48 * mm, 70 * mm, 42 * mm],
                styles,
            ),
            Spacer(1, 5 * mm),
            paragraph(extra, b),
            paragraph(
                "Возврат или прекращение обеспечения зависит от формы и стадии процедуры. Банковские операции не моделируются."
                if ru
                else "Release of security depends on the instrument and procedural stage. Banking operations are not modelled.",
                b,
            ),
        ]

    liability = [
        fact_box(
            "15.1. Просрочка исполнения" if ru else "15.1. Delay in performance",
            facts["penalty"].passage,
            styles,
        ),
        Spacer(1, 5 * mm),
        paragraph(
            "Неустойка не освобождает от исполнения и устранения нарушения. Основание, период и расчет фиксируются в требовании или ином контрактном документе."
            if ru
            else "Liquidated damages do not release performance or correction. The basis, period and calculation are recorded in a contract document.",
            b,
        ),
        grid_table(
            [
                [
                    "Нарушение" if ru else "Breach",
                    "Документ" if ru else "Record",
                    "Последствие" if ru else "Consequence",
                ],
                [
                    "Просрочка" if ru else "Delay",
                    "Расчет периода" if ru else "Period calculation",
                    "Пеня по условию" if ru else "Specific-clause penalty",
                ],
                [
                    "Недостаток" if ru else "Defect",
                    "Акт несоответствия" if ru else "Non-conformity record",
                    "Устранение" if ru else "Correction",
                ],
                [
                    "Нет документа" if ru else "Missing record",
                    "Уведомление" if ru else "Notice",
                    "Представление" if ru else "Submission",
                ],
            ],
            [48 * mm, 52 * mm, 60 * mm],
            styles,
        ),
        Spacer(1, 5 * mm),
        paragraph(
            "Служебный срок ответа на претензию 10 рабочих дней не является ограничением пени и не относится к оплате."
            if ru
            else "A ten-business-day claim response target is neither a penalty cap nor the payment term.",
            b,
        ),
    ]

    warranty = [
        fact_box(
            "16.1. Гарантийный срок" if ru else "16.1. Warranty period",
            facts["warranty"].passage,
            styles,
        ),
        Spacer(1, 5 * mm),
        paragraph(
            "В течение гарантии исполнитель регистрирует обращение, диагностирует относимый недостаток и устраняет его за свой счет при ненадлежащем исполнении."
            if ru
            else "During warranty, the contractor registers, diagnoses and corrects attributable defects at its own cost.",
            b,
        ),
        grid_table(
            [
                [
                    "Действие" if ru else "Action",
                    "Целевой срок" if ru else "Target",
                    "Результат" if ru else "Output",
                ],
                [
                    "Регистрация" if ru else "Registration",
                    "1 рабочий день" if ru else "1 business day",
                    "Номер обращения" if ru else "Ticket reference",
                ],
                [
                    "Диагностика" if ru else "Diagnosis",
                    "До 5 рабочих дней" if ru else "Up to 5 business days",
                    "Причина и план" if ru else "Cause and plan",
                ],
                [
                    "Устранение" if ru else "Correction",
                    "По плану" if ru else "Agreed plan",
                    "Акт устранения" if ru else "Correction record",
                ],
            ],
            [55 * mm, 48 * mm, 57 * mm],
            styles,
        ),
        Spacer(1, 5 * mm),
        paragraph(
            "Срок диагностики не заменяет общий гарантийный срок. Гарантия исключает документированное неправильное использование и вмешательство третьих лиц."
            if ru
            else "The diagnosis target does not replace the warranty period. Warranty excludes documented misuse and third-party interference.",
            b,
        ),
    ]

    contract = [
        paragraph(
            (
                f"Фиктивный заказчик поручает, а условный исполнитель принимает обязательство исполнить предмет: {scenario.title}. Цена, сроки, оплата и обеспечение определяются соответствующими разделами."
                if ru
                else f"The fictional customer appoints a hypothetical contractor to perform: {scenario.title}. Price, timing, payment and security follow the relevant sections."
            ),
            b,
        ),
        *[paragraph(text, b) for text in prose(scenario.language, "contract")],
        paragraph("17.1. Существенные условия" if ru else "17.1. Material terms", h2),
        grid_table(
            [
                ["Условие" if ru else "Term", "Источник" if ru else "Source"],
                ["Предмет" if ru else "Subject", "Разделы 5-6" if ru else "Sections 5-6"],
                ["Срок" if ru else "Performance", "Раздел 7" if ru else "Section 7"],
                [
                    "Приемка и оплата" if ru else "Acceptance and payment",
                    "Разделы 8-9" if ru else "Sections 8-9",
                ],
                ["Обеспечение" if ru else "Security", "Раздел 14" if ru else "Section 14"],
                [
                    "Ответственность и гарантия" if ru else "Liability and warranty",
                    "Разделы 15-16" if ru else "Sections 15-16",
                ],
            ],
            [73 * mm, 87 * mm],
            styles,
        ),
        Spacer(1, 4 * mm),
        paragraph(
            "Реквизиты сторон, подписи, печати и банковские счета намеренно отсутствуют. Реальные данные запрещено добавлять в публичный набор."
            if ru
            else "Party details, signatures, seals and bank accounts are intentionally absent. Real data must not be added to the public dataset.",
            b,
        ),
    ]

    annex = [
        paragraph("Приложение 1. Реестр документов" if ru else "Annex 1. Document register", h2),
        grid_table(
            [
                ["N", "Наименование" if ru else "Name", "Статус" if ru else "Status"],
                [
                    "1",
                    "Информационная карта" if ru else "Information sheet",
                    "Включено" if ru else "Included",
                ],
                [
                    "2",
                    "Описание объекта" if ru else "Object description",
                    "Включено" if ru else "Included",
                ],
                [
                    "3",
                    "Обоснование цены" if ru else "Price justification",
                    "Без исходных котировок" if ru else "No source quotes",
                ],
                [
                    "4",
                    "Проект контракта" if ru else "Draft contract",
                    "Сокращенная версия" if ru else "Condensed version",
                ],
                [
                    "5",
                    "Форма приемки" if ru else "Acceptance form",
                    "Незаполненная" if ru else "Blank",
                ],
            ],
            [12 * mm, 95 * mm, 53 * mm],
            styles,
        ),
        Spacer(1, 6 * mm),
        paragraph("Приложение 2. Контроль приемки" if ru else "Annex 2. Acceptance checklist", h2),
        grid_table(
            [
                [
                    "Показатель" if ru else "Check",
                    "Да" if ru else "Yes",
                    "Нет" if ru else "No",
                    "Комментарий" if ru else "Comment",
                ],
                ["Объем соответствует" if ru else "Scope complete", "", "", ""],
                ["Документация передана" if ru else "Documents delivered", "", "", ""],
                ["Испытания пройдены" if ru else "Tests passed", "", "", ""],
                ["Замечания устранены" if ru else "Defects corrected", "", "", ""],
            ],
            [75 * mm, 15 * mm, 15 * mm, 55 * mm],
            styles,
        ),
        Spacer(1, 6 * mm),
        warning_box(
            "КОНЕЦ СИНТЕТИЧЕСКОГО КОМПЛЕКТА. Создано для regression-тестов TenderLens."
            if ru
            else "END OF SYNTHETIC PACKAGE. Generated for TenderLens regression tests.",
            styles,
        ),
        Spacer(1, 5 * mm),
        paragraph(
            (
                f"Электронная подпись не формируется. Воспроизводимость: сценарий {scenario.id}, корпус v2, структура {PAGE_COUNT} страниц."
                if ru
                else f"No electronic signature is created. Reproducibility: scenario {scenario.id}, corpus v2, {PAGE_COUNT}-page structure."
            ),
            b,
        ),
    ]

    return [
        legal,
        info,
        planning,
        price,
        description,
        quality,
        delivery,
        acceptance,
        payment,
        participant,
        application,
        evaluation,
        security("bid_security", False),
        security("performance_security", True),
        liability,
        warranty,
        contract,
        annex,
    ]


def draw_chrome(
    canvas: Any, document: Any, scenario: TenderScenario, regular: str, bold: str
) -> None:
    width, height = A4
    ru = scenario.language == "ru"
    canvas.saveState()
    if document.page > 1:
        canvas.setFillColor(INK)
        canvas.setFont(regular, 8)
        canvas.drawCentredString(width / 2, height - 10 * mm, str(document.page))
        canvas.setStrokeColor(LIGHT_GRID)
        canvas.line(25 * mm, height - 14 * mm, width - 15 * mm, height - 14 * mm)
        canvas.setFont(bold, 7.4)
        canvas.setFillColor(MUTED)
        canvas.drawString(25 * mm, height - 10 * mm, scenario.reference)
        canvas.drawRightString(
            width - 15 * mm,
            height - 10 * mm,
            "TenderLens / учебный комплект" if ru else "TenderLens / evaluation package",
        )
    canvas.setStrokeColor(LIGHT_GRID)
    canvas.line(25 * mm, 15 * mm, width - 15 * mm, 15 * mm)
    canvas.setFont(bold, 6.7)
    canvas.setFillColor(WARNING)
    footer = (
        "СИНТЕТИЧЕСКИЙ ТЕСТОВЫЙ ДОКУМЕНТ. НЕ ЯВЛЯЕТСЯ ИЗВЕЩЕНИЕМ О ЗАКУПКЕ."
        if ru
        else "SYNTHETIC TEST DOCUMENT. NOT A PROCUREMENT NOTICE."
    )
    canvas.drawCentredString(width / 2, 10 * mm, footer)
    canvas.restoreState()


def build_pdf(scenario: TenderScenario, output_path: Path) -> dict[str, Any]:
    regular, bold = register_fonts()
    styles = build_styles(regular, bold)
    facts = {fact.category: fact for fact in build_document_facts(scenario)}
    page_titles = headings(scenario.language)
    pages = [cover(scenario, styles), contents_page(scenario.language, styles)]
    pages.extend(body_pages(scenario, facts, styles))
    if len(pages) != PAGE_COUNT:
        raise ValueError(f"generator produced {len(pages)} page definitions")

    document = BaseDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=15 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=scenario.title,
        author="TenderLens synthetic evaluation corpus",
        subject="Realistic synthetic procurement package for RAG evaluation",
        creator="TenderLens PDF fixture generator",
    )
    frame = Frame(
        document.leftMargin,
        document.bottomMargin,
        document.width,
        document.height,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    document.addPageTemplates(
        [
            PageTemplate(
                id="content",
                frames=[frame],
                onPage=lambda canvas, doc: draw_chrome(canvas, doc, scenario, regular, bold),
            )
        ]
    )

    story: list[Any] = []
    for index, (title, elements) in enumerate(zip(page_titles, pages, strict=True), start=1):
        if index > 1:
            story.append(paragraph(title, styles["h1"]))
        story.extend(elements)
        if index < PAGE_COUNT:
            story.append(PageBreak())
    document.build(story)

    return {
        "document_id": scenario.id,
        "filename": output_path.name,
        "title": scenario.title,
        "reference": scenario.reference,
        "language": scenario.language,
        "split": scenario.split.value,
        "profile": scenario.profile,
        "page_count": PAGE_COUNT,
        "format_version": "realistic-procurement-v1",
        "layout_reference": "GOST R 7.0.97-2025",
        "synthetic": True,
        "legal_basis": list(LEGAL_SOURCES),
        "questions": [
            {
                "category": category,
                "question": QUESTION_TEMPLATES[scenario.language][category][0],
                "expected_answer": getattr(scenario, category),
                "expected_quote": fact.passage,
                "expected_page": FACT_PAGES[category],
            }
            for category, fact in facts.items()
        ],
        "unanswerable_questions": list(UNANSWERABLE_QUESTIONS[scenario.language]),
    }


def main() -> None:
    args = parse_args()
    scenarios = load_scenarios(args.scenarios)
    selected = scenarios if args.all else [item for item in scenarios if item.pdf_sample]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for scenario in selected:
        output_path = args.output_dir / f"{scenario.id}.pdf"
        manifest.append(build_pdf(scenario, output_path))
        print(f"created {output_path}")
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(
        f"{json.dumps(manifest, ensure_ascii=False, indent=2)}\n", encoding="utf-8"
    )
    print(f"created {manifest_path}")


if __name__ == "__main__":
    main()
