import re
from pathlib import Path

from anyio import to_thread
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from tenderlens.domain.documents import ExtractedPage


class PdfExtractionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class PdfTextExtractor:
    def __init__(self, max_pages: int) -> None:
        self.max_pages = max_pages

    async def extract(self, path: Path) -> list[ExtractedPage]:
        return await to_thread.run_sync(self._extract_sync, path)

    def _extract_sync(self, path: Path) -> list[ExtractedPage]:
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

        pages: list[ExtractedPage] = []
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as exc:
                raise PdfExtractionError(
                    "page_extraction_failed",
                    f"Text extraction failed on page {page_number}.",
                ) from exc
            pages.append(
                ExtractedPage(
                    page_number=page_number,
                    text=self._normalize_text(text),
                )
            )

        if not pages:
            raise PdfExtractionError("empty_pdf", "The PDF does not contain any pages.")
        if not any(page.text.strip() for page in pages):
            raise PdfExtractionError(
                "no_extractable_text",
                "No text was found. The PDF may require OCR.",
            )
        return pages

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.rstrip() for line in text.split("\n")]
        normalized = "\n".join(lines).strip()
        return re.sub(r"\n{3,}", "\n\n", normalized)
