#!/usr/bin/env python3
"""Summarize MCNS/MANC descending output by body system and cell type."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def build_summary(routes_path: Path) -> dict:
    source = json.loads(routes_path.read_text(encoding="utf-8"))
    by_type = defaultdict(lambda: {
        "flywire_type": None,
        "manc_types": set(),
        "hemilineages": set(),
        "sides": set(),
        "systems": defaultdict(int),
        "direct_synapses": 0,
        "direct_connection_rows": 0,
        "route_count": 0,
    })
    for route in source["routes"]:
        key = route.get("dn_flywire_type") or route.get("dn_manc_type") or f"manc:{route['dn_manc_body_id']}"
        item = by_type[key]
        item["flywire_type"] = route.get("dn_flywire_type")
        item["manc_types"].add(route.get("dn_manc_type") or "")
        if route.get("dn_hemilineage"):
            item["hemilineages"].add(route["dn_hemilineage"])
        if route.get("dn_soma_side"):
            item["sides"].add(route["dn_soma_side"])
        item["direct_synapses"] += route["direct_synapses"]
        item["direct_connection_rows"] += route["direct_connection_rows"]
        item["route_count"] += 1
        for motor in route["motors"]:
            item["systems"][motor["target_system"]] += motor["synapses"]

    records = []
    for key, item in sorted(by_type.items(), key=lambda pair: -pair[1]["direct_synapses"]):
        records.append({
            "driver_type": key,
            "flywire_type": item["flywire_type"],
            "manc_types": sorted(x for x in item["manc_types"] if x),
            "hemilineages": sorted(item["hemilineages"]),
            "sides": sorted(item["sides"]),
            "direct_synapses": item["direct_synapses"],
            "direct_connection_rows": item["direct_connection_rows"],
            "route_count": item["route_count"],
            "systems": dict(sorted(item["systems"].items(), key=lambda pair: -pair[1])),
        })

    system_totals = defaultdict(int)
    type_totals = defaultdict(int)
    for record in records:
        for system, value in record["systems"].items():
            system_totals[system] += value
        for system, value in record["systems"].items():
            type_totals[system] += 1

    return {
        "schema_version": "1.0",
        "source": "dn_motor_routes.json",
        "counts": {
            "unique_descending_driver_types": len(records),
            "driver_types_reaching_legs": sum(any(s in {"front_leg", "middle_leg", "hind_leg"} for s in r["systems"]) for r in records),
            "driver_types_reaching_wing": sum("wing" in r["systems"] for r in records),
            "system_synapse_totals": dict(sorted(system_totals.items(), key=lambda pair: -pair[1])),
            "driver_type_counts_by_system": dict(type_totals),
        },
        "interpretation": {
            "direct_route": "observed direct edge from a descending neuron to a motor neuron",
            "body_system": "broad system inferred from MCNS/MANC nerve and motor annotation fields",
            "not_proven": "does not prove a specific behavior or exact muscle-to-joint biomechanics",
        },
        "driver_types": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_summary(args.routes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], ensure_ascii=False, indent=2))
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
