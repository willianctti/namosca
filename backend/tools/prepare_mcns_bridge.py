#!/usr/bin/env python3
"""Build a cross-dataset bridge from MCNS neuron annotations.

The MCNS annotation table contains explicit `flywireType` and `mancType`
cross-references. This tool keeps only descending and motor neurons and
summarizes their body-system/nerve information. It does not infer exact
muscle names beyond the annotations supplied by the datasets.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pyarrow.feather as feather


COLUMNS = [
    "bodyId", "flywireType", "mancBodyid", "mancType", "superclass", "type",
    "subclass", "class", "itoleeHl", "somaSide", "entryNerve", "exitNerve",
    "somaNeuromere", "rootSide", "matchingNotes",
]


def value(row: dict, key: str):
    result = row.get(key)
    if result is None or result == "":
        return None
    return result


def target_system(row: dict) -> str:
    """Infer a broad body system from MCNS/MANC nerve and class fields."""
    text = " ".join(
        str(value(row, key) or "")
        for key in ("subclass", "class", "entryNerve", "exitNerve", "mancType")
    ).lower()
    if any(token in text for token in ("proln", "legnp_t1", "dpron", "front_leg")):
        return "front_leg"
    if any(token in text for token in ("mesoln", "legnp_t2", "middle_leg")):
        return "middle_leg"
    if any(token in text for token in ("metaln", "legnp_t3", "hind_leg")):
        return "hind_leg"
    if any(token in text for token in ("admn", "pdmn", "mesoan", "wing", "haltere")):
        return "wing"
    if any(token in text for token in ("abn", "abdomen", "abdominal")):
        return "abdomen"
    return "unclassified"


def clean_row(row: dict) -> dict:
    out = {
        "mcns_body_id": int(row["bodyId"]),
        "mcns_type": value(row, "type"),
        "mcns_superclass": value(row, "superclass"),
        "manc_body_id": int(row["mancBodyid"]) if row.get("mancBodyid") is not None else None,
        "manc_type": value(row, "mancType"),
        "flywire_type": value(row, "flywireType"),
        "subclass": value(row, "subclass"),
        "class": value(row, "class"),
        "hemilineage": value(row, "itoleeHl"),
        "soma_side": value(row, "somaSide"),
        "entry_nerve": value(row, "entryNerve"),
        "exit_nerve": value(row, "exitNerve"),
        "soma_neuromere": value(row, "somaNeuromere"),
        "root_side": value(row, "rootSide"),
        "matching_notes": value(row, "matchingNotes"),
    }
    out["target_system"] = target_system(row)
    out["has_flywire_match"] = out["flywire_type"] is not None
    out["has_manc_match"] = out["manc_body_id"] is not None
    return out


def build_bridge(path: Path) -> dict:
    table = feather.read_table(path, columns=COLUMNS)
    all_rows = table.to_pylist()
    selected = []
    for row in all_rows:
        superclass = str(row.get("superclass") or "").lower()
        if superclass == "descending_neuron" or superclass.endswith("_motor") or superclass == "motor":
            selected.append(clean_row(row))
    descending = [r for r in selected if r["mcns_superclass"] == "descending_neuron"]
    motors = [r for r in selected if r["mcns_superclass"] != "descending_neuron"]
    system_counts = Counter(r["target_system"] for r in motors)
    return {
        "schema_version": "1.0",
        "dataset": "MCNS v1.0 (male CNS)",
        "source_file": path.name,
        "counts": {
            "annotation_rows": len(all_rows),
            "selected_descending": len(descending),
            "selected_motor": len(motors),
            "descending_with_flywire_match": sum(r["has_flywire_match"] for r in descending),
            "descending_with_manc_match": sum(r["has_manc_match"] for r in descending),
            "motor_with_flywire_match": sum(r["has_flywire_match"] for r in motors),
            "motor_with_manc_match": sum(r["has_manc_match"] for r in motors),
            "motor_systems": dict(system_counts),
        },
        "limitations": [
            "flywireType and mancType are cross-reference annotations, not shared root IDs",
            "target_system is broad; it is not an exact muscle-level atlas",
            "male MCNS annotations are used to bridge types across datasets and sex",
        ],
        "descending_neurons": descending,
        "motor_neurons": motors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.annotations.is_file():
        parser.error(f"file not found: {args.annotations}")
    bridge = build_bridge(args.annotations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        json.dump(bridge, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(bridge["counts"], ensure_ascii=False, indent=2))
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
