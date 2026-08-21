import argparse
import json
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
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
NAVY = colors.HexColor("#102342")
BLUE = colors.HexColor("#2367D1")
PALE_BLUE = colors.HexColor("#EAF1FC")
SLATE = colors.HexColor("#506078")
LIGHT_BORDER = colors.HexColor("#D4DCE8")
PALE_WARNING = colors.HexColor("#FFF5DD")
RU_PROFILE_NAMES = {
    "goods": "товары",
    "works": "работы",
    "services": "услуги",
    "it": "информационные технологии",
    "energy": "энергетика",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate safe synthetic TenderLens PDFs")
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


def build_pdf(scenario: TenderScenario, output_path: Path) -> dict[str, Any]:
    regular_font, bold_font = register_fonts()
    styles = build_styles(regular_font, bold_font)
    facts = build_document_facts(scenario)
    facts_by_page: dict[int, list[Any]] = {1: [], 2: [], 3: []}
    for fact in facts:
        facts_by_page[fact.page_number].append(fact)

    document = BaseDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=22 * mm,
        bottomMargin=20 * mm,
        title=scenario.title,
        author="TenderLens synthetic evaluation corpus",
        subject="Synthetic tender document for testing only",
    )
    frame = Frame(document.leftMargin, document.bottomMargin, document.width, document.height)
    document.addPageTemplates(
        [
            PageTemplate(
                id="content",
                frames=[frame],
                onPage=lambda canvas, doc: draw_page_chrome(
                    canvas, doc, scenario, regular_font, bold_font
                ),
            )
        ]
    )

    ru = scenario.language == "ru"
    synthetic_label = "СИНТЕТИЧЕСКИЙ ТЕСТОВЫЙ ДОКУМЕНТ" if ru else "SYNTHETIC TEST DOCUMENT"
    story: list[Any] = [
        Paragraph(synthetic_label, styles["eyebrow"]),
        Spacer(1, 5 * mm),
        Paragraph(scenario.title, styles["title"]),
        Spacer(1, 3 * mm),
        metadata_table(scenario, styles),
        Spacer(1, 7 * mm),
        warning_box(scenario, styles),
        Spacer(1, 7 * mm),
        Paragraph("1. Основные параметры" if ru else "1. Key parameters", styles["h1"]),
        Spacer(1, 2 * mm),
    ]
    story.extend(fact_blocks(facts_by_page[1], styles, start_number=1))
    story.extend(
        [
            PageBreak(),
            Paragraph(
                "2. Исполнение и расчеты" if ru else "2. Performance and payment",
                styles["h1"],
            ),
            Spacer(1, 3 * mm),
        ]
    )
    story.extend(fact_blocks(facts_by_page[2], styles, start_number=3))
    story.extend(
        [
            PageBreak(),
            Paragraph(
                "3. Обеспечение и ответственность" if ru else "3. Security and liability",
                styles["h1"],
            ),
            Spacer(1, 3 * mm),
        ]
    )
    story.extend(fact_blocks(facts_by_page[3], styles, start_number=6))
    story.extend(
        [
            Spacer(1, 8 * mm),
            Paragraph(
                (
                    "Документ создан исключительно для разработки и проверки TenderLens. "
                    "Все организации, суммы и условия вымышлены. Это не юридическая консультация."
                    if ru
                    else "This document exists solely for TenderLens development and evaluation. "
                    "All entities, amounts and terms are fictional. This is not legal advice."
                ),
                styles["note"],
            ),
        ]
    )
    document.build(story)

    return {
        "document_id": scenario.id,
        "filename": output_path.name,
        "title": scenario.title,
        "reference": scenario.reference,
        "language": scenario.language,
        "split": scenario.split.value,
        "profile": scenario.profile,
        "page_count": 3,
        "questions": [
            {
                "category": fact.category,
                "question": QUESTION_TEMPLATES[scenario.language][fact.category][0],
                "expected_answer": getattr(scenario, fact.category),
                "expected_quote": fact.passage,
                "expected_page": fact.page_number,
            }
            for fact in facts
        ],
    }


def build_styles(regular_font: str, bold_font: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle(
            "eyebrow",
            parent=base["Normal"],
            fontName=bold_font,
            fontSize=8,
            leading=10,
            textColor=BLUE,
            spaceAfter=0,
        ),
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName=bold_font,
            fontSize=24,
            leading=29,
            textColor=NAVY,
            alignment=TA_CENTER,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName=bold_font,
            fontSize=16,
            leading=20,
            textColor=NAVY,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName=bold_font,
            fontSize=11,
            leading=14,
            textColor=NAVY,
            spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName=regular_font,
            fontSize=10.5,
            leading=16,
            textColor=colors.HexColor("#24344D"),
        ),
        "meta": ParagraphStyle(
            "meta",
            parent=base["Normal"],
            fontName=regular_font,
            fontSize=9,
            leading=12,
            textColor=SLATE,
        ),
        "note": ParagraphStyle(
            "note",
            parent=base["Normal"],
            fontName=regular_font,
            fontSize=8.5,
            leading=12,
            textColor=SLATE,
        ),
    }


def metadata_table(scenario: TenderScenario, styles: dict[str, ParagraphStyle]) -> Table:
    ru = scenario.language == "ru"
    profile = RU_PROFILE_NAMES.get(scenario.profile, scenario.profile) if ru else scenario.profile
    rows = [
        ["Идентификатор" if ru else "Reference", scenario.reference],
        ["Тип закупки" if ru else "Procurement type", profile],
        ["Набор данных" if ru else "Dataset split", scenario.split.value],
    ]
    table = Table(
        [
            [Paragraph(label, styles["meta"]), Paragraph(value, styles["meta"])]
            for label, value in rows
        ],
        colWidths=[45 * mm, 105 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), PALE_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.6, LIGHT_BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LIGHT_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def warning_box(scenario: TenderScenario, styles: dict[str, ParagraphStyle]) -> Table:
    text = (
        "Важно: это вымышленный тендер без персональных данных. Он предназначен только для тестов."
        if scenario.language == "ru"
        else "Important: this is a fictional tender with no personal data. It is for testing only."
    )
    box = Table([[Paragraph(text, styles["body"])]], colWidths=[150 * mm])
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PALE_WARNING),
                ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#E7BE62")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return box


def fact_blocks(
    facts: list[Any], styles: dict[str, ParagraphStyle], *, start_number: int
) -> list[Any]:
    blocks: list[Any] = []
    for offset, fact in enumerate(facts):
        block = Table(
            [
                [
                    Paragraph(f"{start_number + offset}. {fact.heading}", styles["h2"]),
                ],
                [Paragraph(fact.passage, styles["body"])],
            ],
            colWidths=[150 * mm],
        )
        block.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), PALE_BLUE),
                    ("BOX", (0, 0), (-1, -1), 0.6, LIGHT_BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        blocks.extend([KeepTogether([block]), Spacer(1, 5 * mm)])
    return blocks


def draw_page_chrome(
    canvas: Any,
    document: Any,
    scenario: TenderScenario,
    regular_font: str,
    bold_font: str,
) -> None:
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 10 * mm, width, 10 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont(bold_font, 9)
    canvas.drawString(22 * mm, height - 6.5 * mm, "TenderLens")
    canvas.setStrokeColor(LIGHT_BORDER)
    canvas.line(22 * mm, 14 * mm, width - 22 * mm, 14 * mm)
    canvas.setFillColor(SLATE)
    canvas.setFont(regular_font, 8)
    canvas.drawString(22 * mm, 9 * mm, scenario.reference)
    canvas.drawRightString(
        width - 22 * mm,
        9 * mm,
        f"Page {document.page}" if scenario.language == "en" else f"Страница {document.page}",
    )
    canvas.restoreState()


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
