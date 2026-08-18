from dataclasses import dataclass
from enum import StrEnum


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ExtractedPage:
    page_number: int
    text: str


@dataclass(frozen=True, slots=True)
class TextChunk:
    page_number: int
    chunk_index: int
    start_char: int
    end_char: int
    text: str
