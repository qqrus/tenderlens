"""Versioned geometry sidecar; never substitutes for ordinary text offsets."""

import hashlib
from importlib.metadata import version
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from tenderlens.domain.documents import ExtractionMethod, PdfExtractionResult
from tenderlens.ingestion.table_geometry import PageTable, inspect_page_tables


class GeometrySnapshot(BaseModel):
    schema_version: Literal["1"] = "1"
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal["not_processed", "disabled", "unsupported", "page_limit", "ready", "failed"]
    coordinate_system: Literal["pdf_points_top_left"] = "pdf_points_top_left"
    extractor_version: str | None = None
    tables: list[PageTable] = Field(default_factory=list)


def build_geometry_snapshot(
    path: Path,
    source_sha256: str,
    extraction: PdfExtractionResult,
    *,
    enabled: bool,
    max_pages: int,
) -> GeometrySnapshot:
    if not enabled:
        return GeometrySnapshot(source_sha256=source_sha256, status="disabled")
    if extraction.method != ExtractionMethod.NATIVE:
        return GeometrySnapshot(source_sha256=source_sha256, status="unsupported")
    if len(extraction.pages) > max_pages:
        return GeometrySnapshot(source_sha256=source_sha256, status="page_limit")
    with path.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != source_sha256:
            raise ValueError("source hash mismatch")
    tables = inspect_page_tables(path, [page.page_number for page in extraction.pages])
    return GeometrySnapshot(
        source_sha256=source_sha256,
        status="ready",
        tables=tables,
        extractor_version=f"pdfplumber/{version('pdfplumber')};lines-v1",
    )
