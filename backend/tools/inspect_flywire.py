#!/usr/bin/env python3
"""Inspect a large FlyWire/Codex export without loading it into memory.

Examples
--------
python tools/inspect_flywire.py data/flywire/connections.csv.gz
python tools/inspect_flywire.py data/flywire/cell_types.tsv --samples 3
python tools/inspect_flywire.py data/flywire/neurons.jsonl --json-lines
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from pathlib import Path
from typing import TextIO


def open_text(path: Path) -> TextIO:
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def inspect_csv(path: Path, samples: int, delimiter: str | None) -> dict[str, object]:
    with open_text(path) as stream:
        if delimiter is None:
            delimiter = "\t" if path.suffix.lower() in {".tsv", ".tab"} else ","
        reader = csv.reader(stream, delimiter=delimiter)
        # Read only a few rows; the full file may contain billions of cells.
        rows = []
        try:
            header = next(reader)
        except StopIteration:
            return {"format": "csv", "rows": 0, "columns": []}
        for _ in range(max(0, samples)):
            try:
                rows.append(next(reader))
            except StopIteration:
                break
    return {
        "format": "csv",
        "delimiter": "TAB" if delimiter == "\t" else "comma",
        "columns": header,
        "column_count": len(header),
        "sample_rows": rows,
    }


def inspect_json_lines(path: Path, samples: int) -> dict[str, object]:
    rows: list[object] = []
    with open_text(path) as stream:
        for _ in range(max(0, samples)):
            line = stream.readline()
            if not line:
                break
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                return {"format": "jsonl", "error": f"invalid JSON line: {exc}"}
    keys: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            for key in row:
                if key not in keys:
                    keys.append(key)
    return {"format": "jsonl", "keys": keys, "sample_rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="CSV, TSV, compressed CSV/TSV or JSONL file")
    parser.add_argument("--samples", type=int, default=2, help="Number of sample rows to print")
    parser.add_argument("--delimiter", choices=[",", "tab"], default=None)
    parser.add_argument("--json-lines", action="store_true", help="Force JSONL inspection")
    args = parser.parse_args()
    if not args.path.is_file():
        parser.error(f"file not found: {args.path}")
    delimiter = "\t" if args.delimiter == "tab" else args.delimiter
    try:
        result = (
            inspect_json_lines(args.path, args.samples)
            if args.json_lines or args.path.suffix.lower() in {".jsonl", ".ndjson"}
            else inspect_csv(args.path, args.samples, delimiter)
        )
    except (OSError, UnicodeError, csv.Error) as exc:
        print(f"could not inspect file: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
