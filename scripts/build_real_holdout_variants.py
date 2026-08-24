import argparse
import io
import random
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas


@dataclass(frozen=True, slots=True)
class VariantSpec:
    source: str
    output: str
    pages: tuple[int, ...]
    rotation: int = 0
    skew_degrees: float = 0.0
    noise_seed: int = 0


VARIANTS = (
    VariantSpec(
        source="worldbank-georgia-procurement-plan.pdf",
        output="worldbank-georgia-table-skew-scan.pdf",
        pages=(1, 2, 3),
        skew_degrees=1.2,
        noise_seed=20260824,
    ),
    VariantSpec(
        source="worldbank-srilanka-procurement-plan.pdf",
        output="worldbank-srilanka-rotated-scan.pdf",
        pages=(1, 2, 3),
        rotation=90,
        noise_seed=20260825,
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic OCR stress variants from reviewed holdout PDFs."
    )
    parser.add_argument("--documents", type=Path, default=Path("evals/real/documents"))
    return parser.parse_args()


def render_page(document: pdfium.PdfDocument, page_number: int) -> Image.Image:
    page = document[page_number - 1]
    return page.render(scale=2.0).to_pil().convert("RGB")


def add_deterministic_scan_noise(image: Image.Image, seed: int) -> Image.Image:
    grayscale = ImageOps.grayscale(image)
    grayscale = ImageEnhance.Contrast(grayscale).enhance(0.92)
    grayscale = grayscale.filter(ImageFilter.GaussianBlur(radius=0.35))
    draw = ImageDraw.Draw(grayscale)
    rng = random.Random(seed)
    width, height = grayscale.size
    for _ in range(max(200, width * height // 3500)):
        x = rng.randrange(width)
        y = rng.randrange(height)
        shade = rng.choice((105, 125, 145, 205, 220))
        draw.point((x, y), fill=shade)
    for y in range(37, height, 173):
        draw.line((0, y, width, y), fill=235, width=1)
    return grayscale.convert("RGB")


def transform(image: Image.Image, spec: VariantSpec, page_index: int) -> Image.Image:
    transformed = add_deterministic_scan_noise(image, spec.noise_seed + page_index)
    if spec.skew_degrees:
        angle = spec.skew_degrees if page_index % 2 == 0 else -spec.skew_degrees
        transformed = transformed.rotate(angle, expand=True, fillcolor="white")
    if spec.rotation:
        transformed = transformed.rotate(-spec.rotation, expand=True, fillcolor="white")
    return transformed


def write_image_pdf(images: list[Image.Image], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    first_width, first_height = images[0].size
    canvas = Canvas(
        str(destination),
        pagesize=(first_width, first_height),
        pageCompression=1,
        invariant=1,
    )
    for image in images:
        width, height = image.size
        canvas.setPageSize((width, height))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=78, optimize=True)
        buffer.seek(0)
        canvas.drawImage(ImageReader(buffer), 0, 0, width=width, height=height)
        canvas.showPage()
    canvas.save()


def build_variant(documents: Path, spec: VariantSpec) -> Path:
    source = documents / spec.source
    if not source.is_file():
        raise FileNotFoundError(f"missing reviewed source PDF: {source}")
    document = pdfium.PdfDocument(source)
    try:
        images = [
            transform(render_page(document, page_number), spec, index)
            for index, page_number in enumerate(spec.pages)
        ]
    finally:
        document.close()
    destination = documents / spec.output
    write_image_pdf(images, destination)
    return destination


def main() -> int:
    args = parse_args()
    for spec in VARIANTS:
        output = build_variant(args.documents, spec)
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
