# ruff: noqa: RUF001  # Russian synthetic procurement text is intentional.

import argparse
from io import BytesIO
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium  # type: ignore[import-untyped]
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

DEFAULT_OUTPUT = Path("output/pdf/tenderlens-eval-ocr/ru-scanned-tender-001.pdf")
SOURCE_PATH = Path("tmp/pdfs/ru-scanned-tender-001-source.pdf")
PAGE_COUNT = 6


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the image-only TenderLens OCR fixture.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dpi", type=int, default=170)
    return parser.parse_args()


def register_fonts() -> tuple[str, str]:
    candidates = (
        (
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
        ),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
    )
    for regular, bold in candidates:
        if regular.is_file() and bold.is_file():
            pdfmetrics.registerFont(TTFont("OcrFixtureSans", str(regular)))
            pdfmetrics.registerFont(TTFont("OcrFixtureSansBold", str(bold)))
            return "OcrFixtureSans", "OcrFixtureSansBold"
    raise RuntimeError("No Unicode TrueType font was found")


def page_footer(output: canvas.Canvas, document: Any) -> None:
    del document
    output.saveState()
    output.setStrokeColor(colors.HexColor("#B7C2CF"))
    output.line(20 * mm, 18 * mm, 190 * mm, 18 * mm)
    output.setFont("OcrFixtureSans", 7.5)
    output.setFillColor(colors.HexColor("#66717F"))
    output.drawString(20 * mm, 12 * mm, "TL-OCR-RU-001 · СИНТЕТИЧЕСКИЙ ТЕСТОВЫЙ ДОКУМЕНТ")
    output.drawRightString(190 * mm, 12 * mm, f"Страница {output.getPageNumber()} из {PAGE_COUNT}")
    output.restoreState()


def build_source(path: Path) -> None:
    regular, bold = register_fonts()
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "TitleRu",
        parent=styles["Title"],
        fontName=bold,
        fontSize=22,
        leading=27,
        textColor=colors.HexColor("#17365D"),
        alignment=TA_CENTER,
        spaceAfter=12 * mm,
    )
    heading = ParagraphStyle(
        "HeadingRu",
        parent=styles["Heading1"],
        fontName=bold,
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#17365D"),
        spaceAfter=6 * mm,
    )
    subheading = ParagraphStyle(
        "SubheadingRu",
        parent=styles["Heading2"],
        fontName=bold,
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#2E5E9E"),
        spaceBefore=4 * mm,
        spaceAfter=3 * mm,
    )
    body = ParagraphStyle(
        "BodyRu",
        parent=styles["BodyText"],
        fontName=regular,
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#1E2935"),
        spaceAfter=4 * mm,
    )
    small = ParagraphStyle(
        "SmallRu",
        parent=body,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#66717F"),
    )
    story: list[Any] = []

    story.extend(
        [
            Spacer(1, 34 * mm),
            Paragraph("ИЗВЕЩЕНИЕ О ПРОВЕДЕНИИ ЭЛЕКТРОННОГО КОНКУРСА", title),
            Paragraph("Поставка вычислительного оборудования для учебного центра", heading),
            Spacer(1, 8 * mm),
            _table(
                [
                    ["Идентификатор", "TL-OCR-RU-001"],
                    ["Заказчик", "Фиктивное учреждение «Учебный центр»"],
                    ["Год", "2026"],
                    ["Статус", "Синтетический OCR-fixture"],
                ],
                regular,
                bold,
            ),
            Spacer(1, 14 * mm),
            Paragraph(
                "Документ создан только для автоматической проверки TenderLens. "
                "Он не является извещением о закупке, не содержит реальных реквизитов, "
                "подписей и персональных данных.",
                small,
            ),
            PageBreak(),
            Paragraph("1. Правовая основа и общие положения", heading),
            Paragraph(
                "Учебная структура документа воспроизводит типичные разделы закупочной "
                "документации. Упоминания Федерального закона от 05.04.2013 N 44-ФЗ "
                "приведены исключительно как "
                "контекст для проверки поиска среди юридических формулировок.",
                body,
            ),
            Paragraph("1.1. Порядок толкования", subheading),
            Paragraph(
                "Участник самостоятельно проверяет полноту сведений, требования к составу заявки, "
                "формат электронных документов и порядок подачи через электронную площадку. "
                "Общие пояснения не изменяют конкретные числовые условия информационной карты.",
                body,
            ),
            Paragraph("1.2. Ограничение ответственности", subheading),
            Paragraph(
                "Автоматический анализ помогает находить фрагменты, но не заменяет "
                "закупочную комиссию или юридическую консультацию. До принятия решения "
                "пользователь сверяет вывод с PDF.",
                body,
            ),
            PageBreak(),
            Paragraph("2. Информационная карта закупки", heading),
            _table(
                [
                    ["Параметр", "Сведения"],
                    ["Предмет", "Поставка 24 серверов и монтажного комплекта"],
                    ["Способ", "Электронный конкурс (учебная модель)"],
                    ["Регион", "г. Тестоград, вымышленный адрес"],
                ],
                regular,
                bold,
            ),
            Paragraph("2.1. Срок подачи заявок", subheading),
            Paragraph(
                "Прием заявок завершается 24 октября 2026 года в 14:30 по московскому времени. "
                "Документы, поступившие позднее указанного момента, не рассматриваются.",
                body,
            ),
            Paragraph("2.2. Начальная максимальная цена", subheading),
            Paragraph(
                "Начальная максимальная цена контракта составляет 12 750 000 рублей, включая НДС. "
                "Цена предложения участника не может превышать указанное значение.",
                body,
            ),
            PageBreak(),
            Paragraph("3. Требования к участнику и заявке", heading),
            Paragraph(
                "Участник должен подтвердить право осуществлять поставку оборудования, "
                "отсутствие недоимки в предусмотренных законом случаях и полномочия лица, "
                "подписывающего заявку.",
                body,
            ),
            Paragraph(
                "В техническом предложении указываются производитель, модель, количество, "
                "срок гарантии и характеристики каждого вида оборудования. Замена "
                "обязательного документа "
                "письмом в свободной форме не допускается.",
                body,
            ),
            _table(
                [
                    ["Контроль", "Подтверждение"],
                    ["Полномочия", "Электронная подпись или доверенность"],
                    ["Характеристики", "Структурированное техническое предложение"],
                    ["Опыт", "Договоры и акты при наличии основания"],
                ],
                regular,
                bold,
            ),
            PageBreak(),
            Paragraph("4. Срок исполнения и порядок оплаты", heading),
            Paragraph("4.1. Поставка", subheading),
            Paragraph(
                "Поставщик обязан завершить поставку и монтаж в течение 60 календарных дней с даты "
                "заключения контракта. Уведомление о готовности направляется не позднее чем за три "
                "рабочих дня до доставки.",
                body,
            ),
            Paragraph("4.2. Приемка и расчеты", subheading),
            Paragraph(
                "Оплата производится в течение 15 рабочих дней после подписания документа "
                "о приемке. Аванс не предусмотрен; цена включает доставку, упаковку, "
                "монтаж и обязательные платежи.",
                body,
            ),
            PageBreak(),
            Paragraph("5. Ответственность сторон", heading),
            Paragraph("5.1. Пеня за просрочку", subheading),
            Paragraph(
                "За каждый день просрочки поставщик уплачивает пеню в размере 0,2% стоимости "
                "просроченного обязательства, но не более 10% цены контракта.",
                body,
            ),
            Paragraph("5.2. Документирование нарушения", subheading),
            Paragraph(
                "Основание и период начисления фиксируются в требовании заказчика. "
                "Уплата неустойки "
                "не освобождает поставщика от исполнения обязательств и устранения недостатков.",
                body,
            ),
            Spacer(1, 12 * mm),
            Paragraph(
                "Конец синтетического комплекта. Банковские реквизиты, подписи, номера страховых "
                "полисов и сведения о реальных лицах намеренно отсутствуют.",
                small,
            ),
        ]
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=24 * mm,
        bottomMargin=24 * mm,
        title="TenderLens OCR synthetic fixture",
        author="TenderLens",
    )
    document.build(story, onFirstPage=page_footer, onLaterPages=page_footer)


def _table(rows: list[list[str]], regular: str, bold: str) -> Table:
    table = Table(rows, colWidths=[52 * mm, 115 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), regular),
                ("FONTNAME", (0, 0), (-1, 0), bold),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("LEADING", (0, 0), (-1, -1), 11),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF1F8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#17365D")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ABB5C1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def rasterize_to_image_only(source: Path, output: Path, dpi: int) -> None:
    document = pdfium.PdfDocument(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = canvas.Canvas(str(output), pagesize=A4, pageCompression=1)
    try:
        for index in range(len(document)):
            page = document[index]
            bitmap = page.render(scale=dpi / 72)
            image = bitmap.to_pil().convert("RGB")
            encoded = BytesIO()
            image.save(encoded, format="JPEG", quality=88, optimize=True)
            encoded.seek(0)
            rendered.drawImage(ImageReader(encoded), 0, 0, width=A4[0], height=A4[1])
            rendered.showPage()
            image.close()
            bitmap.close()
            page.close()
    finally:
        document.close()
    rendered.save()


def verify_image_only_pdf(path: Path) -> None:
    reader = PdfReader(path)
    if len(reader.pages) != PAGE_COUNT:
        raise RuntimeError(f"Expected {PAGE_COUNT} pages, got {len(reader.pages)}")
    extracted = [page.extract_text() or "" for page in reader.pages]
    if any(text.strip() for text in extracted):
        raise RuntimeError("OCR fixture must not contain an extractable text layer")


def main() -> int:
    args = parse_args()
    build_source(SOURCE_PATH)
    try:
        rasterize_to_image_only(SOURCE_PATH, args.output, args.dpi)
        verify_image_only_pdf(args.output)
    finally:
        SOURCE_PATH.unlink(missing_ok=True)
    print(f"Created image-only PDF: {args.output} ({PAGE_COUNT} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
