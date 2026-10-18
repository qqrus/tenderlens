"""Opt-in geometry diagnostic; extracted document text must remain local."""

import argparse
import hashlib
import json
from pathlib import Path

from tenderlens.ingestion.table_geometry import inspect_page_tables, select_cell


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--pages", type=int, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--row-label")
    parser.add_argument("--column-header")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("choose a new output filename; reports are not overwritten")
    if bool(args.row_label) != bool(args.column_header):
        parser.error("row-label and column-header must be supplied together")
    tables = inspect_page_tables(args.pdf, args.pages)
    selected = select_cell(tables, args.row_label, args.column_header) if args.row_label else None
    report = {
        "version": "geometry-prototype-1",
        "source_sha256": hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
        "coordinate_system": "PDF points, origin top-left; not character offsets",
        "tables": [table.model_dump() for table in tables],
        "selection": selected.model_dump() if selected else None,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        output.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"tables": len(tables), "selection_found": selected is not None}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
