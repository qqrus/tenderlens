import hashlib
from pathlib import Path

import pytest

from tenderlens.domain.documents import ExtractedPage, ExtractionMethod, PdfExtractionResult
from tenderlens.ingestion.geometry_snapshot import build_geometry_snapshot


@pytest.mark.parametrize(
    ("enabled", "method", "max_pages", "expected"),
    [
        (False, ExtractionMethod.NATIVE, 20, "disabled"),
        (True, ExtractionMethod.OCR, 20, "unsupported"),
        (True, ExtractionMethod.MIXED, 20, "unsupported"),
        (True, ExtractionMethod.NATIVE, 0, "page_limit"),
    ],
)
def test_unsupported_work_is_skipped_without_reading_file(
    enabled: bool,
    method: ExtractionMethod,
    max_pages: int,
    expected: str,
) -> None:
    result = build_geometry_snapshot(
        Path("does-not-exist.pdf"),
        "a" * 64,
        PdfExtractionResult([ExtractedPage(1, "text")], method, 0),
        enabled=enabled,
        max_pages=max_pages,
    )
    assert result.status == expected


def test_source_hash_checked_and_extractor_version_recorded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "fixture.bin"
    source.write_bytes(b"fixture")
    monkeypatch.setattr("tenderlens.ingestion.geometry_snapshot.inspect_page_tables", lambda *_: [])
    monkeypatch.setattr("tenderlens.ingestion.geometry_snapshot.version", lambda _: "test")
    extraction = PdfExtractionResult([ExtractedPage(1, "text")], ExtractionMethod.NATIVE, 0)
    with pytest.raises(ValueError, match="hash"):
        build_geometry_snapshot(source, "a" * 64, extraction, enabled=True, max_pages=20)
    result = build_geometry_snapshot(
        source,
        hashlib.sha256(b"fixture").hexdigest(),
        extraction,
        enabled=True,
        max_pages=20,
    )
    assert result.status == "ready"
    assert result.extractor_version == "pdfplumber/test;lines-v1"
