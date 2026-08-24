import re
import shutil
import subprocess
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from typing import Protocol

import pypdfium2 as pdfium  # type: ignore[import-untyped]
from anyio import to_thread
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from tenderlens.domain.documents import ExtractedPage, ExtractionMethod, PdfExtractionResult


class PdfExtractionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class OcrEngine(Protocol):
    def recognize_pages(self, path: Path, page_indexes: Sequence[int]) -> dict[int, str]: ...


class TesseractPdfOcr:
    def __init__(
        self,
        *,
        command: str,
        languages: str,
        dpi: int,
        timeout_seconds: float,
    ) -> None:
        self.command = command
        self.languages = languages
        self.dpi = dpi
        self.timeout_seconds = timeout_seconds

    def recognize_pages(self, path: Path, page_indexes: Sequence[int]) -> dict[int, str]:
        executable = shutil.which(self.command)
        if executable is None:
            raise PdfExtractionError(
                "ocr_unavailable",
                "OCR is enabled, but the Tesseract executable is not available.",
            )

        try:
            document = pdfium.PdfDocument(path)
        except Exception as exc:
            raise PdfExtractionError(
                "ocr_render_failed",
                "The PDF could not be rendered for OCR.",
            ) from exc

        recognized: dict[int, str] = {}
        try:
            for page_index in page_indexes:
                recognized[page_index] = self._recognize_page(
                    document,
                    page_index,
                    executable,
                )
        finally:
            document.close()
        return recognized

    def _recognize_page(
        self,
        document: pdfium.PdfDocument,
        page_index: int,
        executable: str,
    ) -> str:
        page = document[page_index]
        bitmap = None
        image = None
        try:
            bitmap = page.render(scale=self.dpi / 72)
            image = bitmap.to_pil().convert("RGB")
            encoded = BytesIO()
            image.save(encoded, format="PNG")
            try:
                completed = subprocess.run(
                    [
                        executable,
                        "stdin",
                        "stdout",
                        "-l",
                        self.languages,
                        "--oem",
                        "1",
                        "--psm",
                        "3",
                    ],
                    input=encoded.getvalue(),
                    capture_output=True,
                    check=False,
                    timeout=self.timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise PdfExtractionError(
                    "ocr_timeout",
                    f"OCR timed out on page {page_index + 1}.",
                ) from exc
            if completed.returncode != 0:
                details = completed.stderr.decode("utf-8", errors="replace").strip()
                raise PdfExtractionError(
                    "ocr_failed",
                    f"OCR failed on page {page_index + 1}: {details[:240]}",
                )
            return completed.stdout.decode("utf-8", errors="replace")
        except PdfExtractionError:
            raise
        except Exception as exc:
            raise PdfExtractionError(
                "ocr_render_failed",
                f"Page {page_index + 1} could not be rendered for OCR.",
            ) from exc
        finally:
            if image is not None:
                image.close()
            if bitmap is not None:
                bitmap.close()
            page.close()


class PdfTextExtractor:
    def __init__(
        self,
        max_pages: int,
        *,
        ocr_engine: OcrEngine | None = None,
        ocr_min_text_chars: int = 40,
        ocr_max_pages: int = 80,
    ) -> None:
        self.max_pages = max_pages
        self.ocr_engine = ocr_engine
        self.ocr_min_text_chars = ocr_min_text_chars
        self.ocr_max_pages = ocr_max_pages

    async def extract(self, path: Path) -> PdfExtractionResult:
        return await to_thread.run_sync(self._extract_sync, path)

    def _extract_sync(self, path: Path) -> PdfExtractionResult:
        try:
            reader = PdfReader(path)
        except (PdfReadError, OSError, ValueError) as exc:
            raise PdfExtractionError(
                "unreadable_pdf", "The PDF structure could not be read."
            ) from exc

        if reader.is_encrypted and reader.decrypt("") == 0:
            raise PdfExtractionError("encrypted_pdf", "Password-protected PDFs are not supported.")
        if len(reader.pages) > self.max_pages:
            raise PdfExtractionError(
                "too_many_pages",
                f"The PDF contains more than {self.max_pages} pages.",
            )

        native_texts: list[str] = []
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:
                raise PdfExtractionError(
                    "page_extraction_failed",
                    f"Text extraction failed on page {page_number}.",
                ) from exc
            native_texts.append(self._normalize_text(text))

        if not native_texts:
            raise PdfExtractionError("empty_pdf", "The PDF does not contain any pages.")

        ocr_candidates = [
            index
            for index, text in enumerate(native_texts)
            if self._meaningful_char_count(text) < self.ocr_min_text_chars
        ]
        if self.ocr_engine is not None and ocr_candidates:
            if len(ocr_candidates) > self.ocr_max_pages:
                raise PdfExtractionError(
                    "ocr_page_limit_exceeded",
                    f"OCR is limited to {self.ocr_max_pages} pages per document.",
                )
            ocr_texts = self.ocr_engine.recognize_pages(path, ocr_candidates)
        else:
            ocr_texts = {}

        pages: list[ExtractedPage] = []
        ocr_page_count = 0
        for index, native_text in enumerate(native_texts):
            ocr_text = self._normalize_text(ocr_texts.get(index, ""))
            if self._meaningful_char_count(ocr_text) > self._meaningful_char_count(native_text):
                text = ocr_text
                ocr_page_count += 1
            else:
                text = native_text
            pages.append(ExtractedPage(page_number=index + 1, text=text))

        if not any(page.text.strip() for page in pages):
            raise PdfExtractionError(
                "no_extractable_text",
                "No text was found after native extraction and OCR.",
            )

        if ocr_page_count == 0:
            method = ExtractionMethod.NATIVE
        elif ocr_page_count == len(pages):
            method = ExtractionMethod.OCR
        else:
            method = ExtractionMethod.MIXED
        return PdfExtractionResult(
            pages=pages,
            method=method,
            ocr_page_count=ocr_page_count,
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.rstrip() for line in text.split("\n")]
        normalized = "\n".join(lines).strip()
        return re.sub(r"\n{3,}", "\n\n", normalized)

    @staticmethod
    def _meaningful_char_count(text: str) -> int:
        return sum(character.isalnum() for character in text)
