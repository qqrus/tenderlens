from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from tenderlens.ingestion.table_geometry import (
    Box,
    PageTable,
    TableCell,
    inspect_page_tables,
    select_cell,
)


def cell(text: str, x: float = 0, y: float = 0) -> TableCell:
    return TableCell(text=text, box=Box(x0=x, top=y, x1=x + 10, bottom=y + 10))


def table() -> PageTable:
    return PageTable(
        page_number=3,
        page_width=100,
        page_height=100,
        rows=[
            [cell("Category"), cell("Prior\nReview", 20)],
            [cell("Firms", y=20), cell("900 USD", 20, 20)],
            [cell("Individuals", y=40), cell("300 USD", 20, 40)],
        ],
    )


def test_row_and_column_intersection_keeps_three_source_boxes() -> None:
    match = select_cell([table()], "Individuals", "Prior Review")
    assert match is not None
    assert match.value.text == "300 USD"
    assert match.value.box.top == match.row_label.box.top == 40
    assert match.column_header.box.top == 0
    assert match.page_number == 3


def test_missing_merged_cell_is_not_filled_from_neighbor() -> None:
    data = table()
    data.rows[2][1] = None
    assert select_cell([data], "Individuals", "Prior Review") is None


def test_conflicting_tables_are_not_silently_ranked() -> None:
    assert select_cell([table(), table()], "Individuals", "Prior Review") is None


def test_wrong_label_or_header_returns_no_evidence() -> None:
    assert select_cell([table()], "Individual", "Prior Review") is None
    assert select_cell([table()], "Individuals", "Cost") is None


@pytest.mark.parametrize(
    "values",
    [
        {"x0": 0, "top": 0, "x1": float("nan"), "bottom": 1},
        {"x0": 5, "top": 0, "x1": 1, "bottom": 1},
        {"x0": 0, "top": -1, "x1": 1, "bottom": 1},
    ],
)
def test_invalid_geometry_rejected(values: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        Box.model_validate(values)


def test_outside_page_rejected() -> None:
    with pytest.raises(ValidationError):
        PageTable(page_number=1, page_width=5, page_height=5, rows=[[cell("x")]])


def test_adapter_preserves_missing_cell_and_native_boxes(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_table = SimpleNamespace(
        rows=[SimpleNamespace(cells=[(0, 0, 10, 10), None])],
        extract=lambda: [["Header", None]],
    )
    page = SimpleNamespace(width=100, height=200, find_tables=lambda: [raw_table])
    library = SimpleNamespace(open=lambda _: nullcontext(SimpleNamespace(pages=[page])))
    monkeypatch.setattr(
        "tenderlens.ingestion.table_geometry.importlib.import_module", lambda _: library
    )
    result = inspect_page_tables(Path("unused.pdf"), [1])
    assert result[0].rows[0][1] is None
    assert result[0].rows[0][0].box.x1 == 10
    with pytest.raises(ValueError, match="outside"):
        inspect_page_tables(Path("unused.pdf"), [2])
    with pytest.raises(ValueError, match="unique"):
        inspect_page_tables(Path("unused.pdf"), [1, 1])
