"""Small, deterministic text primitives shared by extraction and answer verification."""

# ruff: noqa: RUF001  # Russian abbreviations are intentional.
import re

ABBREVIATION = re.compile(r"\b(?:руб|г|стр|ст|mr|mrs|no)\.$", re.IGNORECASE)
NUMBER = re.compile(r"\d+(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)*")


def normalized_text(text: str) -> str:
    return " ".join(text.casefold().split())


def numeric_tokens(text: str) -> set[str]:
    return {re.sub(r"\s", "", match.group()).replace(",", ".") for match in NUMBER.finditer(text)}


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Preserve wrapped lines, decimal points and complete sentences with original offsets."""
    spans: list[tuple[int, int]] = []
    start = 0
    for match in re.finditer(r"[.!?;](?=\s|$)|\n\s*\n", text):
        end = match.end()
        prefix = text[start:end].strip()
        if match.group() == "." and (
            ABBREVIATION.search(prefix) or re.fullmatch(r"\d+(?:\.\d+)*\.", prefix)
        ):
            continue
        spans.append((start, end))
        start = end
    if start < len(text):
        spans.append((start, len(text)))
    result = []
    for start, end in spans:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            result.append((start, end))
    return result
