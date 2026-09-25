#!/usr/bin/env python3
"""Find direct descending-to-motor routes using MCNS↔MANC cross-references."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import defaultdict
from pathlib import Path


def open_csv(path: Path):
    return gzip.open(path, "rt", encoding="utf-8", newline="") if path.suffix == ".gz" else path.open("r", encoding="utf-8", newline="")


def rows(path: Path):
    with open_csv(path) as stream:
        yield from csv.DictReader(stream)


def build_routes(bridge_path: Path, manc_attributes_path: Path, manc_connections_path: Path) -> dict:
    bridge = json.loads(bridge_path.read_text(encoding="utf-8"))
    attrs = {}
    for row in rows(manc_attributes_path):
        attrs[row["Root ID"]] = row
    descending = {
        str(int(r["manc_body_id"])): r
        for r in bridge["descending_neurons"]
        if r.get("manc_body_id") is not None
    }
    motors = {
        str(int(r["manc_body_id"])): r
        for r in bridge["motor_neurons"]
        if r.get("manc_body_id") is not None
    }
    direct = defaultdict(lambda: {"synapses": 0, "rows": 0, "motors": defaultdict(int)})
    for row in rows(manc_connections_path):
        pre, post = row.get("pre_root_id"), row.get("post_root_id")
        if pre not in descending or post not in motors:
            continue
        try:
            weight = int(float(row.get("syn_count") or 0))
        except ValueError:
            weight = 0
        if weight <= 0:
            continue
        route = direct[pre]
        route["synapses"] += weight
        route["rows"] += 1
        route["motors"][post] += weight
    result = []
    for dn_id, route in sorted(direct.items(), key=lambda item: -item[1]["synapses"]):
        dn = descending[dn_id]
        motor_list = sorted(route["motors"].items(), key=lambda item: -item[1])
        result.append({
            "dn_manc_body_id": int(dn_id),
            "dn_flywire_type": dn.get("flywire_type"),
            "dn_manc_type": dn.get("manc_type"),
            "dn_hemilineage": dn.get("hemilineage"),
            "dn_soma_side": dn.get("soma_side"),
            "direct_synapses": route["synapses"],
            "direct_connection_rows": route["rows"],
            "motors": [
                {
                    "mn_manc_body_id": int(mn_id),
                    "mn_manc_type": motors[mn_id].get("manc_type"),
                    "target_system": motors[mn_id].get("target_system"),
                    "synapses": weight,
                }
                for mn_id, weight in motor_list
            ],
        })
    return {
        "schema_version": "1.0",
        "source": "MCNS v1.0 cross-references joined to MANC v1.2.1 edges",
        "counts": {
            "bridge_descending_with_manc": len(descending),
            "bridge_motor_with_manc": len(motors),
            "descending_with_direct_motor_route": len(result),
            "direct_connection_rows": sum(r["direct_connection_rows"] for r in result),
            "direct_synapses": sum(r["direct_synapses"] for r in result),
        },
        "routes": result,
        "limitations": [
            "This pass contains direct descending-to-motor edges only; indirect premotor paths are not yet included.",
            "Target systems are broad nerve/segment annotations, not a complete muscle atlas.",
            "Cross-dataset correspondence is by type annotations, not shared root IDs.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge", type=Path, required=True)
    parser.add_argument("--manc-attributes", type=Path, required=True)
    parser.add_argument("--manc-connections", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_routes(args.bridge, args.manc_attributes, args.manc_connections)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], ensure_ascii=False, indent=2))
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
