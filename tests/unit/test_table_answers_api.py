from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from test_documents_api import FakeIngestionService, create_app, make_document


def snapshot() -> dict:
    def cell(text: str, left: int, top: int) -> dict:
        return {"text": text, "box": {"x0": left, "top": top, "x1": left + 40, "bottom": top + 20}}

    return {
        "source_sha256": "a" * 64,
        "status": "ready",
        "tables": [
            {
                "page_number": 2,
                "page_width": 100,
                "page_height": 200,
                "rows": [
                    [cell("Item", 0, 0), cell("Budget", 40, 0)],
                    [cell("Servers", 0, 20), cell("100 USD", 40, 20)],
                ],
            }
        ],
    }


def request_body() -> dict:
    return {
        "source_sha256": "a" * 64,
        "table_index": 0,
        "row_label": "Servers",
        "column_header": "Budget",
    }


def test_table_answer_returns_exact_cell_and_three_boxes() -> None:
    document = make_document()
    document.status = "ready"
    document.table_geometry = snapshot()
    with TestClient(create_app(FakeIngestionService(document))) as client:
        response = client.post(f"/api/v1/documents/{document.id}/table-answer", json=request_body())
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == str(document.id)
    assert data["source_sha256"] == document.sha256
    assert data["page_width"] == 100
    assert data["evidence"]["page_number"] == 2
    assert data["evidence"]["value"]["text"] == "100 USD"
    assert data["evidence"]["column_header"]["box"]["top"] == 0
    assert data["evidence"]["row_label"]["box"]["x0"] == 0


@pytest.mark.parametrize(
    "case,status",
    [
        ("stale", 409),
        ("disabled", 409),
        ("processing", 409),
        ("missing_table", 404),
        ("missing_cell", 422),
        ("empty_cell", 422),
        ("duplicate_row", 422),
        ("duplicate_header", 422),
        ("missing_document", 404),
        ("negative_index", 422),
        ("wrong_hash", 409),
    ],
)
def test_table_answer_refuses_unsupported_or_ambiguous_input(case: str, status: int) -> None:
    document = make_document()
    document.status = "ready"
    geometry = snapshot()
    body = request_body()
    rows = geometry["tables"][0]["rows"]
    if case == "stale":
        body["source_sha256"] = "b" * 64
    if case == "wrong_hash":
        geometry["source_sha256"] = "b" * 64
    if case == "disabled":
        geometry["status"] = "disabled"
    if case == "processing":
        document.status = "processing"
    if case == "missing_table":
        body["table_index"] = 1
    if case == "negative_index":
        body["table_index"] = -1
    if case == "missing_cell":
        rows[1][1] = None
    if case == "empty_cell":
        rows[1][1]["text"] = " "
    if case == "duplicate_row":
        rows.append(deepcopy(rows[1]))
    if case == "duplicate_header":
        rows[0][0]["text"] = "Budget"
    document.table_geometry = geometry
    with TestClient(
        create_app(FakeIngestionService(None if case == "missing_document" else document))
    ) as client:
        response = client.post(f"/api/v1/documents/{document.id}/table-answer", json=body)
    assert response.status_code == status
