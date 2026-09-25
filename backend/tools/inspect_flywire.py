#!/usr/bin/env python3
"""Inspeciona uma exportação grande do FlyWire/Codex sem carregá-la na memória.

Exemplos
--------
python tools/inspect_flywire.py data/flywire/sk_lod1_783_healed.zip
python tools/inspect_flywire.py data/flywire/connections.csv.gz
python tools/inspect_flywire.py data/flywire/cell_types.tsv --samples 3
python tools/inspect_flywire.py data/flywire/neurons.jsonl --json-lines
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import TextIO


def open_text(path: Path) -> TextIO:
    """Abre um arquivo de texto normal ou compactado com gzip."""

    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def inspect_csv(path: Path, samples: int, delimiter: str | None) -> dict[str, object]:
    """Lê apenas algumas linhas de um CSV ou TSV."""

    with open_text(path) as stream:
        if delimiter is None:
            delimiter = "\t" if path.suffix.lower() in {".tsv", ".tab"} else ","
        reader = csv.reader(stream, delimiter=delimiter)
        # Lê apenas algumas linhas; o arquivo inteiro pode ter bilhões de células.
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
    """Lê algumas linhas de um arquivo JSONL."""

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


def inspect_zip(path: Path, samples: int) -> dict[str, object]:
    """Inspeciona o diretório central de um ZIP e lê poucos arquivos SWC."""

    try:
        with zipfile.ZipFile(path) as archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            extensions = Counter(
                Path(info.filename).suffix.lower() or "<none>" for info in infos
            )
            swc_infos = [info for info in infos if info.filename.lower().endswith(".swc")]
            sample_members: list[dict[str, object]] = []
            for info in swc_infos[: max(0, samples)]:
                with archive.open(info, "r") as raw:
                    text = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
                    comments: list[str] = []
                    rows: list[str] = []
                    for line in text:
                        line = line.rstrip("\r\n")
                        if line.startswith("#"):
                            comments.append(line)
                        else:
                            rows.append(line)
                            if len(rows) >= samples:
                                break
                sample_members.append(
                    {
                        "name": info.filename,
                        "compressed_bytes": info.compress_size,
                        "uncompressed_bytes": info.file_size,
                        "comments": comments[:12],
                        "sample_rows": rows,
                    }
                )
            return {
                "format": "zip",
                "entries": len(infos),
                "swc_files": len(swc_infos),
                "extensions": dict(extensions),
                "sample_members": sample_members,
            }
    except zipfile.BadZipFile as exc:
        raise OSError(f"invalid ZIP archive: {exc}") from exc


def main() -> int:
    """Inspeciona o arquivo escolhido pela linha de comando."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        type=Path,
        help="ZIP, CSV, TSV, compressed CSV/TSV or JSONL file",
    )
    parser.add_argument("--samples", type=int, default=2, help="Number of sample rows/files to print")
    parser.add_argument("--delimiter", choices=[",", "tab"], default=None)
    parser.add_argument("--json-lines", action="store_true", help="Force JSONL inspection")
    args = parser.parse_args()
    if not args.path.is_file():
        parser.error(f"file not found: {args.path}")
    delimiter = "\t" if args.delimiter == "tab" else args.delimiter
    try:
        if args.path.suffix.lower() == ".zip" and not args.json_lines:
            result = inspect_zip(args.path, args.samples)
        elif args.json_lines or args.path.suffix.lower() in {".jsonl", ".ndjson"}:
            result = inspect_json_lines(args.path, args.samples)
        else:
            result = inspect_csv(args.path, args.samples, delimiter)
    except (OSError, UnicodeError, csv.Error) as exc:
        print(f"could not inspect file: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
