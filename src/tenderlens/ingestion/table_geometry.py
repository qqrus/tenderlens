"""Opt-in native-PDF table inspection. Not yet part of ingestion or QA."""

import importlib
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field, FiniteFloat, model_validator

from tenderlens.domain.text import normalized_text


class Box(BaseModel):
    x0: FiniteFloat = Field(ge=0)
    top: FiniteFloat = Field(ge=0)
    x1: FiniteFloat = Field(ge=0)
    bottom: FiniteFloat = Field(ge=0)

    @model_validator(mode="after")
    def validate_area(self) -> Self:
        if self.x1 <= self.x0 or self.bottom <= self.top:
            raise ValueError("cell box must have positive area")
        return self


class TableCell(BaseModel):
    text: str
    box: Box


class PageTable(BaseModel):
    page_number: int = Field(ge=1)
    page_width: FiniteFloat = Field(gt=0)
    page_height: FiniteFloat = Field(gt=0)
    rows: list[list[TableCell | None]]

    @model_validator(mode="after")
    def validate_grid(self) -> Self:
        if not self.rows or not self.rows[0]:
            raise ValueError("table must contain cells")
        if any(len(row) != len(self.rows[0]) for row in self.rows):
            raise ValueError("table must preserve rectangular column positions")
        for row in self.rows:
            for cell in row:
                if cell and (cell.box.x1 > self.page_width or cell.box.bottom > self.page_height):
                    raise ValueError("cell exceeds page bounds")
        return self


class CellEvidence(BaseModel):
    page_number: int
    row_label: TableCell
    column_header: TableCell
    value: TableCell


def select_cell(
    tables: list[PageTable],
    row_label: str,
    column_header: str,
) -> CellEvidence | None:
    """Require one unambiguous direct row/header intersection; never fill merged cells."""
    if not row_label.strip() or not column_header.strip():
        return None
    matches: list[CellEvidence] = []
    for table in tables:
        # Prototype supports one header row and a first-column row label only.
        columns = [
            i
            for i, cell in enumerate(table.rows[0])
            if cell and normalized_text(cell.text) == normalized_text(column_header)
        ]
        for row in table.rows[1:]:
            label = row[0]
            if label is None or normalized_text(label.text) != normalized_text(row_label):
                continue
            for column in columns:
                value = row[column]
                header = table.rows[0][column]
                if value is not None and value.text.strip() and header is not None:
                    matches.append(
                        CellEvidence(
                            page_number=table.page_number,
                            row_label=label,
                            column_header=header,
                            value=value,
                        )
                    )
    return matches[0] if len(matches) == 1 else None


def inspect_page_tables(path: Path, page_numbers: list[int]) -> list[PageTable]:
    """Read line-delimited native tables. Coordinates are PDF points from top-left."""
    try:
        pdfplumber = importlib.import_module("pdfplumber")
    except ModuleNotFoundError as exc:
        raise RuntimeError("Table inspection requires: uv sync --extra tables") from exc

    if not page_numbers or len(set(page_numbers)) != len(page_numbers):
        raise ValueError("choose unique one-based page numbers")
    result: list[PageTable] = []
    with pdfplumber.open(path) as pdf:
        if any(page < 1 or page > len(pdf.pages) for page in page_numbers):
            raise ValueError("page number outside PDF")
        for page_number in page_numbers:
            page = pdf.pages[page_number - 1]
            for table in page.find_tables():
                text_rows = table.extract()
                rows: list[list[TableCell | None]] = []
                for geometry_row, text_row in zip(table.rows, text_rows, strict=True):
                    cells: list[TableCell | None] = []
                    for bounds, text in zip(geometry_row.cells, text_row, strict=True):
                        if bounds is None:
                            cells.append(None)
                        else:
                            x0, top, x1, bottom = bounds
                            cells.append(
                                TableCell(
                                    text=text or "",
                                    box=Box(x0=x0, top=top, x1=x1, bottom=bottom),
                                )
                            )
                    rows.append(cells)
                result.append(
                    PageTable(
                        page_number=page_number,
                        page_width=page.width,
                        page_height=page.height,
                        rows=rows,
                    )
                )
    return result
