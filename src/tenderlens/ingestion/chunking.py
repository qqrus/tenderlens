import re

from tenderlens.domain.documents import ExtractedPage, TextChunk

SENTENCE_BOUNDARY = re.compile(r"[.!?;:]\s")


class PageAwareChunker:
    def __init__(self, chunk_size_chars: int, overlap_chars: int) -> None:
        if chunk_size_chars <= 0:
            raise ValueError("chunk_size_chars must be positive")
        if overlap_chars < 0 or overlap_chars >= chunk_size_chars:
            raise ValueError("overlap_chars must be non-negative and smaller than chunk size")
        self.chunk_size_chars = chunk_size_chars
        self.overlap_chars = overlap_chars

    def chunk_pages(self, pages: list[ExtractedPage]) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        for page in pages:
            chunks.extend(self.chunk_page(page))
        return chunks

    def chunk_page(self, page: ExtractedPage) -> list[TextChunk]:
        text = page.text
        if not text.strip():
            return []

        chunks: list[TextChunk] = []
        start = 0
        while start < len(text):
            hard_end = min(start + self.chunk_size_chars, len(text))
            end = self._find_boundary(text, start, hard_end)
            chunk_start, chunk_end = self._trim_range(text, start, end)

            if chunk_end > chunk_start:
                chunks.append(
                    TextChunk(
                        page_number=page.page_number,
                        chunk_index=len(chunks),
                        start_char=chunk_start,
                        end_char=chunk_end,
                        text=text[chunk_start:chunk_end],
                    )
                )

            if hard_end == len(text):
                break
            next_start = max(end - self.overlap_chars, start + 1)
            while next_start < end and text[next_start].isspace():
                next_start += 1
            start = next_start

        return chunks

    def _find_boundary(self, text: str, start: int, hard_end: int) -> int:
        if hard_end == len(text):
            return hard_end
        minimum_end = start + int(self.chunk_size_chars * 0.6)
        window = text[minimum_end:hard_end]

        for separator in ("\n\n", "\n"):
            position = window.rfind(separator)
            if position >= 0:
                return minimum_end + position + len(separator)

        sentence_ends = list(SENTENCE_BOUNDARY.finditer(window))
        if sentence_ends:
            return minimum_end + sentence_ends[-1].end()

        space = window.rfind(" ")
        if space >= 0:
            return minimum_end + space + 1
        return hard_end

    @staticmethod
    def _trim_range(text: str, start: int, end: int) -> tuple[int, int]:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return start, end
