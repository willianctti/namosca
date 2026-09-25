#!/usr/bin/env python3
"""Build data-backed MCNS Dm → descending → motor routes in two streaming passes."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import pyarrow.feather as feather


def target_system(row: dict) -> str:
    text = " ".join(str(row.get(key) or "") for key in ("subclass", "class", "entryNerve", "exitNerve", "mancType")).lower()
    if any(x in text for x in ("proln", "legnp_t1", "dpron")): return "front_leg"
    if any(x in text for x in ("mesoln", "legnp_t2")): return "middle_leg"
    if any(x in text for x in ("metaln", "legnp_t3")): return "hind_leg"
    if any(x in text for x in ("admn", "pdmn", "mesoan", "wing")): return "wing"
    if any(x in text for x in ("abn", "abdomen", "abdominal")): return "abdomen"
    return "unclassified"


def load_annotations(path: Path):
    table = feather.read_table(path, columns=["bodyId", "flywireType", "mancBodyid", "mancType", "superclass", "type", "subclass", "class", "entryNerve", "exitNerve", "somaSide", "itoleeHl"])
    return {int(r["bodyId"]): r for r in table.to_pylist()}


def batches(path: Path):
    table = feather.read_table(path, columns=["body_pre", "body_post", "weight"])
    yield from table.to_batches(max_chunksize=2_000_000)


def build(annotations_path: Path, connections_path: Path) -> dict:
    meta = load_annotations(annotations_path)
    dm = {body for body, row in meta.items() if str(row.get("flywireType") or "").lower().startswith("dm")}
    first = defaultdict(int)
    for batch in batches(connections_path):
        pre = batch.column(0).to_pylist(); post = batch.column(1).to_pylist(); weight = batch.column(2).to_pylist()
        for source, target, value in zip(pre, post, weight):
            source = int(source); target = int(target)
            if source in dm and meta.get(target, {}).get("superclass") == "descending_neuron":
                first[(source, target)] += int(value)
    descending = {target for _, target in first}
    second = defaultdict(int)
    for batch in batches(connections_path):
        pre = batch.column(0).to_pylist(); post = batch.column(1).to_pylist(); weight = batch.column(2).to_pylist()
        for source, target, value in zip(pre, post, weight):
            source = int(source); target = int(target)
            if source in descending and str(meta.get(target, {}).get("superclass") or "").endswith("_motor"):
                second[(source, target)] += int(value)
    routes = []
    for (dn, motor), weight in sorted(second.items(), key=lambda item: -item[1]):
        source_dm = sorted({source for (source, target), value in first.items() if target == dn and value})
        dm_types = sorted({str(meta[source].get("flywireType")) for source in source_dm})
        routes.append({
            "mcns_dm_body_ids": source_dm,
            "dm_types": dm_types,
            "mcns_dm_to_dn_synapses": sum(first[(source, dn)] for source in source_dm),
            "dn_body_id": dn,
            "dn_type": meta[dn].get("flywireType"),
            "dn_manc_type": meta[dn].get("mancType"),
            "mn_body_id": motor,
            "mn_type": meta[motor].get("flywireType"),
            "mn_manc_type": meta[motor].get("mancType"),
            "mn_superclass": meta[motor].get("superclass"),
            "target_system": target_system(meta[motor]),
            "dn_to_mn_synapses": weight,
        })
    return {
        "schema_version": "1.0",
        "dataset": "MCNS v1.0",
        "counts": {
            "annotation_bodies": len(meta),
            "dm_bodies": len(dm),
            "dm_to_descending_edges": len(first),
            "descending_intermediates": len(descending),
            "dn_to_motor_edges": len(routes),
            "dm_to_motor_paths": len(routes),
            "direct_dm_to_motor_edges": 0,
        },
        "interpretation": "A Dm → DN → MN path is observed in the MCNS connectome; target_system is broad and does not prove exact muscle movement.",
        "routes": routes,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--connections", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = build(args.annotations, args.connections)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], ensure_ascii=False, indent=2))
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__": raise SystemExit(main())
