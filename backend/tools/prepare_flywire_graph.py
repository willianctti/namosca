#!/usr/bin/env python3
"""Build a bounded, normalized FlyWire graph from FAFB static exports.

The importer streams the compressed CSV files and reads only selected SWC
members from the skeleton ZIP. It never extracts the complete 13 GB archive
or loads the full connection table into memory.

Example
-------
python tools/prepare_flywire_graph.py \
  --skeletons /data/flywire/sk_lod1_783_healed.zip \
  --neurons /data/flywire/neurons.csv.gz \
  --cell-types /data/flywire/consolidated_cell_types.csv.gz \
  --connections /data/flywire/connections_princeton_no_threshold.csv.gz \
  --group ME --neuropil ME_L \
  --min-synapses 5 --max-neurons 800 --max-synapses 4000 \
  --output /data/flywire/me_left_graph.json
"""

from __future__ import annotations

import argparse
import csv
import gzip
import heapq
import json
import math
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterator, TextIO


Edge = tuple[int, str, str, str, str]


def open_csv(path: Path) -> TextIO:
    """Open a plain or gzip-compressed CSV as text."""

    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def rows(path: Path) -> Iterator[dict[str, str]]:
    """Yield rows from a CSV without materializing the file."""

    with open_csv(path) as stream:
        yield from csv.DictReader(stream)


def first(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def matches_group(value: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    normalized = value.lower().replace("-", "_")
    return any(
        normalized == pattern.lower()
        or normalized.startswith(pattern.lower() + ".")
        or normalized.startswith(pattern.lower() + "_")
        for pattern in patterns
    )


def matches_neuropil(value: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    normalized = value.lower().replace("-", "_")
    return any(
        normalized == pattern.lower()
        or normalized.startswith(pattern.lower() + "_")
        or normalized.startswith(pattern.lower() + ".")
        for pattern in patterns
    )


def load_neurons(path: Path, groups: list[str]) -> tuple[dict[str, dict[str, str]], int]:
    """Load only the small metadata table, optionally filtered by group."""

    metadata: dict[str, dict[str, str]] = {}
    total = 0
    for row in rows(path):
        total += 1
        root_id = first(row, "root_id", "id", "cell_id")
        if not root_id or not matches_group(first(row, "group", "neuropil"), groups):
            continue
        metadata[root_id] = {
            "group": first(row, "group", "neuropil"),
            "nt_type": first(row, "nt_type", "neurotransmitter", "transmitter"),
        }
    return metadata, total


def load_cell_types(path: Path | None) -> dict[str, tuple[str, str]]:
    if path is None:
        return {}
    result: dict[str, tuple[str, str]] = {}
    for row in rows(path):
        root_id = first(row, "root_id", "id", "cell_id")
        if not root_id:
            continue
        result[root_id] = (
            first(row, "primary_type", "cell_type", "type"),
            first(row, "additional_type(s)", "additional_cell_types", "additional_types"),
        )
    return result


def iter_edges(
    path: Path,
    candidates: set[str],
    neuropils: list[str],
    min_synapses: int,
) -> Iterator[Edge]:
    """Yield filtered directed edges as (count, pre, post, neuropil, nt)."""

    for row in rows(path):
        pre = first(row, "pre_root_id", "pre", "source", "from")
        post = first(row, "post_root_id", "post", "target", "to")
        if not pre or not post or pre == post or pre not in candidates or post not in candidates:
            continue
        neuropil = first(row, "neuropil", "region", "compartment")
        if not matches_neuropil(neuropil, neuropils):
            continue
        try:
            count = int(float(first(row, "syn_count", "synapse_count", "count", "weight")))
        except (TypeError, ValueError):
            continue
        if count < min_synapses:
            continue
        yield count, pre, post, neuropil, first(row, "nt_type", "neurotransmitter")


def id_sort_key(value: str) -> tuple[int, int | str]:
    try:
        return 0, int(value)
    except ValueError:
        return 1, value


def read_swc_positions(
    archive_path: Path, selected: list[str]
) -> tuple[dict[str, tuple[float, float, float]], int]:
    """Read soma/first-point coordinates for selected IDs directly from ZIP."""

    positions: dict[str, tuple[float, float, float]] = {}
    missing = 0
    with zipfile.ZipFile(archive_path) as archive:
        names = {
            Path(info.filename).stem: info.filename
            for info in archive.infolist()
            if not info.is_dir() and info.filename.lower().endswith(".swc")
        }
        for root_id in selected:
            name = names.get(root_id)
            if not name:
                missing += 1
                continue
            position: tuple[float, float, float] | None = None
            first_point: tuple[float, float, float] | None = None
            with archive.open(name, "r") as raw:
                for line in raw:
                    if line.startswith(b"#"):
                        continue
                    fields = line.decode("utf-8", errors="replace").split()
                    if len(fields) < 5:
                        continue
                    try:
                        point = (float(fields[2]), float(fields[3]), float(fields[4]))
                        label = int(fields[1])
                    except (TypeError, ValueError):
                        continue
                    if not all(math.isfinite(value) for value in point):
                        continue
                    if first_point is None:
                        first_point = point
                    if label == 1:
                        position = point
                        break
            position = position or first_point
            if position is None:
                missing += 1
            else:
                positions[root_id] = position
    return positions, missing


def choose_edges(
    path: Path,
    selected: set[str],
    neuropils: list[str],
    min_synapses: int,
    max_synapses: int,
) -> tuple[list[Edge], int]:
    """Keep the strongest bounded set of edges without storing all matches."""

    heap: list[Edge] = []
    candidates = 0
    for edge in iter_edges(path, selected, neuropils, min_synapses):
        candidates += 1
        if len(heap) < max_synapses:
            heapq.heappush(heap, edge)
        elif edge > heap[0]:
            heapq.heapreplace(heap, edge)
    return sorted(heap, key=lambda item: (-item[0], item[1], item[2], item[3], item[4])), candidates


def build_graph(args: argparse.Namespace) -> dict[str, object]:
    neuron_meta, neuron_rows = load_neurons(args.neurons, args.group)
    if not neuron_meta:
        raise ValueError("no neurons remained after the group filter")
    candidates = set(neuron_meta)

    degree: Counter[str] = Counter()
    filtered_edges = 0
    for _count, pre, post, _neuropil, _nt in iter_edges(
        args.connections, candidates, args.neuropil, args.min_synapses
    ):
        degree[pre] += 1
        degree[post] += 1
        filtered_edges += 1
    if not degree:
        raise ValueError("no connections remained after the filters")

    selected = sorted(degree, key=lambda root: (-degree[root], id_sort_key(root)))
    selected = selected[: args.max_neurons]
    selected_set = set(selected)
    positions, missing_positions = read_swc_positions(args.skeletons, selected)
    selected = [root for root in selected if root in positions]
    selected_set = set(selected)
    if not selected:
        raise ValueError("selected neurons had no readable SWC positions")

    edges, selected_edge_candidates = choose_edges(
        args.connections,
        selected_set,
        args.neuropil,
        args.min_synapses,
        args.max_synapses,
    )
    edges = [edge for edge in edges if edge[1] in selected_set and edge[2] in selected_set]
    cell_types = load_cell_types(args.cell_types)
    node_neuropils: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for _count, pre, post, neuropil, _nt in edges:
        if neuropil:
            node_neuropils[pre][neuropil] += 1
            node_neuropils[post][neuropil] += 1

    neurons: list[dict[str, object]] = []
    for root_id in selected:
        primary_type, additional_types = cell_types.get(root_id, ("", ""))
        neuropil = node_neuropils[root_id].most_common(1)
        neuropil_name = neuropil[0][0] if neuropil else ""
        meta = neuron_meta[root_id]
        x, y, z = positions[root_id]
        neurons.append(
            {
                "id": root_id,
                "label": primary_type or root_id,
                "region": args.region,
                "x": x,
                "y": y,
                "z": z,
                "role": "unclassified",
                "cell_type": primary_type or None,
                "additional_cell_types": additional_types or None,
                "group": meta["group"] or None,
                "neuropil": neuropil_name or None,
                "nt_type": meta["nt_type"] or None,
            }
        )

    synapses: list[dict[str, object]] = []
    for count, pre, post, neuropil, nt_type in edges:
        normalized_weight = min(10.0, math.log1p(count))
        synapses.append(
            {
                "source": pre,
                "target": post,
                "weight": normalized_weight,
                "delay_ms": 1.0,
                "inhibitory": nt_type.upper() in {"GABA", "GLY"},
                "synapse_count": count,
                "neuropil": neuropil or None,
                "nt_type": nt_type or None,
            }
        )

    return {
        "schema_version": "1.0",
        "region": args.region,
        "source": "flywire",
        "coordinate_space": "swc_nanometers",
        "units": "nanometer",
        "neurons": neurons,
        "synapses": synapses,
        "truncated": len(selected) < len(degree) or len(edges) < selected_edge_candidates,
        "fallback": False,
        "metadata": {
            "dataset": "FAFB v783 (CB)",
            "source": "FlyWire Codex static exports",
            "source_files": {
                "skeletons": args.skeletons.name,
                "neurons": args.neurons.name,
                "cell_types": args.cell_types.name if args.cell_types else None,
                "connections": args.connections.name,
            },
            "selection": {
                "groups": args.group,
                "neuropils": args.neuropil,
                "min_synapses": args.min_synapses,
                "max_neurons": args.max_neurons,
                "max_synapses": args.max_synapses,
            },
            "counts": {
                "neuron_rows": neuron_rows,
                "candidate_neurons": len(candidates),
                "neurons_with_filtered_edges": len(degree),
                "filtered_connection_rows": filtered_edges,
                "selected_neurons": len(neurons),
                "selected_connection_candidates": selected_edge_candidates,
                "selected_synapses": len(synapses),
                "missing_selected_swc_positions": missing_positions,
            },
            "weight_policy": "min(10, log1p(syn_count))",
            "delay_policy": "1 ms assumed until a measured delay model is added",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skeletons", type=Path, required=True)
    parser.add_argument("--neurons", type=Path, required=True)
    parser.add_argument("--cell-types", type=Path)
    parser.add_argument("--connections", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--group", action="append", default=[])
    parser.add_argument("--neuropil", action="append", default=[])
    parser.add_argument("--min-synapses", type=int, default=5)
    parser.add_argument("--max-neurons", type=int, default=1000)
    parser.add_argument("--max-synapses", type=int, default=6000)
    parser.add_argument("--region", default="optic_lobes")
    args = parser.parse_args()
    if args.min_synapses < 1:
        parser.error("--min-synapses must be >= 1")
    if args.max_neurons < 1 or args.max_synapses < 1:
        parser.error("limits must be >= 1")
    for path in (args.skeletons, args.neurons, args.connections):
        if not path.is_file():
            parser.error(f"file not found: {path}")
    if args.cell_types and not args.cell_types.is_file():
        parser.error(f"file not found: {args.cell_types}")

    try:
        graph = build_graph(args)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as stream:
            json.dump(graph, stream, ensure_ascii=False, separators=(",", ":"))
            stream.write("\n")
    except (OSError, ValueError, zipfile.BadZipFile, csv.Error) as exc:
        print(f"could not build graph: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(graph["metadata"], ensure_ascii=False, indent=2))
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
