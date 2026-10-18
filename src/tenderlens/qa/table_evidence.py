"""Conservative handling of explicitly delimited two-column monetary tables."""

# ruff: noqa: RUF001
import re
from dataclasses import dataclass

from tenderlens.domain.text import normalized_text
from tenderlens.qa.models import Evidence

MONEY_QUESTION = re.compile(
    r"cost|price|amount|budget|threshold|стоим|цен[ауы]|сумм|бюджет|порог", re.I
)
LABEL = re.compile(r"^(?:description|item|наименование|позиция)$", re.I)
VALUE = re.compile(r"^(?:cost|price|amount|стоимость|цена|сумма)(?:\s*\([^)]*\))?$", re.I)
MONEY = re.compile(
    r"^(?:(?:USD|EUR|RUB|₽|руб\.)\s*)?"
    r"(?:\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?: \d{3})*(?:[.,]\d{1,2})?)"
    r"\s*(?:USD|EUR|RUB|₽|руб\.)?$",
    re.I,
)


@dataclass(frozen=True)
class TableSelection:
    applies: bool
    rows: tuple[tuple[str, int, int], ...] = ()


def select_table_rows(question: str, evidence: list[Evidence]) -> TableSelection:
    if not MONEY_QUESTION.search(question):
        return TableSelection(False)
    applicable = False
    candidates: list[tuple[str, int, int, str]] = []
    malformed_match = False
    normalized_question = normalized_text(question)
    for item in evidence:
        source = item.hit.text
        active = False
        offset = 0
        for line in source.splitlines(keepends=True):
            raw = line.rstrip("\r\n")
            separator = "|" if "|" in raw else "\t" if "\t" in raw else None
            if separator is None:
                active = False
                offset += len(line)
                continue
            cells = [cell.strip() for cell in raw.strip().strip("|").split(separator)]
            if len(cells) >= 2 and LABEL.fullmatch(cells[0]) and VALUE.fullmatch(cells[1]):
                applicable = True
                active = len(cells) == 2
            elif active and not all(re.fullmatch(r"[-: ]*", cell) for cell in cells):
                label = normalized_text(cells[0])
                # Exact bounded row label, not a loose shared word such as "equipment".
                if label and re.search(
                    r"(?<!\w)" + re.escape(label) + r"(?!\w)", normalized_question
                ):
                    if len(cells) != 2 or not MONEY.fullmatch(cells[1]):
                        malformed_match = True
                    else:
                        candidates.append(
                            (item.evidence_id, offset, offset + len(raw), normalized_text(raw))
                        )
            offset += len(line)
    if malformed_match or len({row[3] for row in candidates}) != 1:
        return TableSelection(applicable)
    return TableSelection(applicable, tuple(row[:3] for row in candidates))
