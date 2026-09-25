#!/usr/bin/env python3
"""Resume os neurônios motores e descendentes do MANC a partir de CSV estáticos.

A tabela completa de conexões do MANC é lida uma vez em fluxo. A saída
contém os neurônios motores anotados, dicas amplas do sistema de destino e a
conectividade de entrada agregada. Não pretende ser um atlas completo de
músculos.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import Counter
from pathlib import Path
from typing import TextIO


def open_csv(path: Path) -> TextIO:
    """Abre um CSV normal ou compactado com gzip."""

    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def first(row: dict[str, str], *keys: str) -> str:
    """Devolve o primeiro campo preenchido entre os nomes informados."""

    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def rows(path: Path):
    """Lê as linhas de um CSV."""

    with open_csv(path) as stream:
        yield from csv.DictReader(stream)


def parse_float(value: str) -> float | None:
    """Converte um texto em decimal ou devolve None quando não consegue."""

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def target_system(record: dict[str, str]) -> str:
    """Devolve uma dica ampla de sistema, sem detalhes específicos de músculo."""

    class_code = record["class"].lower()
    nerve = record["nerve"].lower()
    sub_class = record["sub_class"].lower()
    if class_code == "fl" or "legnp_t1" in sub_class or "prothoracic_leg" in sub_class or "proln" in nerve:
        return "front_leg"
    if class_code == "ml" or "legnp_t2" in sub_class or "mesothoracic_leg" in sub_class or "mesoln" in nerve:
        return "middle_leg"
    if class_code == "hl" or "legnp_t3" in sub_class or "metathoracic_leg" in sub_class or "metaln" in nerve:
        return "hind_leg"
    if class_code == "wm" or "wing" in sub_class or "admn" in nerve or "pdmn" in nerve or "mesoan" in nerve:
        return "wing"
    if class_code == "hm" or "haltere" in sub_class or "metan" in nerve:
        return "haltere"
    if class_code == "ad" or "abdomen" in sub_class or "abn" in nerve:
        return "abdomen"
    if class_code == "nm" or "neck" in sub_class:
        return "neck"
    return "unclassified"


def load_attributes(path: Path) -> dict[str, dict[str, object]]:
    """Lê os atributos dos neurônios e calcula sua categoria ampla."""

    result: dict[str, dict[str, object]] = {}
    for row in rows(path):
        root_id = first(row, "Root ID", "root_id", "id")
        if not root_id:
            continue
        record: dict[str, object] = {
            "root_id": root_id,
            "top_region": first(row, "Top in/out region", "top_region"),
            "flow": first(row, "Flow", "flow"),
            "super_class": first(row, "Super Class", "super_class"),
            "class": first(row, "Class", "class"),
            "sub_class": first(row, "Sub Class", "sub_class"),
            "hemilineage": first(row, "Hemilineage", "hemilineage"),
            "nerve": first(row, "Nerve", "nerve"),
            "soma_side": first(row, "Soma side", "soma_side"),
            "primary_cell_type": first(row, "Primary Cell Type", "primary_cell_type"),
            "alternative_cell_types": first(row, "Alternative Cell Type(s)", "alternative_cell_types"),
            "predicted_nt": first(row, "Predicted NT type", "predicted_nt_type"),
            "predicted_nt_confidence": parse_float(first(row, "Predicted NT confidence")),
        }
        record["target_system"] = target_system(record)
        result[root_id] = record
    return result


def build_catalog(attributes_path: Path, connections_path: Path) -> dict[str, object]:
    """Monta o catálogo de motores e neurônios descendentes com suas conexões."""

    attributes = load_attributes(attributes_path)
    motor_ids = {
        root_id
        for root_id, record in attributes.items()
        if str(record["super_class"]).lower() == "motor"
    }
    descending_ids = {
        root_id
        for root_id, record in attributes.items()
        if str(record["super_class"]).lower() == "descending"
    }

    incoming: dict[str, Counter[str]] = {root_id: Counter() for root_id in motor_ids}
    outgoing: dict[str, Counter[str]] = {root_id: Counter() for root_id in motor_ids}
    direct_dn_motor: dict[str, int] = {root_id: 0 for root_id in motor_ids}
    connection_rows = 0
    motor_incoming_synapses = 0
    motor_outgoing_synapses = 0
    direct_dn_motor_rows = 0
    direct_dn_motor_synapses = 0

    for row in rows(connections_path):
        connection_rows += 1
        pre = first(row, "pre_root_id", "pre", "source", "from")
        post = first(row, "post_root_id", "post", "target", "to")
        try:
            syn_count = int(float(first(row, "syn_count", "synapse_count", "count", "weight") or 0))
        except (TypeError, ValueError):
            syn_count = 0
        if syn_count <= 0:
            continue
        if post in motor_ids:
            motor_incoming_synapses += syn_count
            incoming[post]["all"] += syn_count
            if pre in descending_ids:
                incoming[post]["descending"] += syn_count
                direct_dn_motor[post] += syn_count
                direct_dn_motor_rows += 1
                direct_dn_motor_synapses += syn_count
            if pre in attributes:
                incoming[post][str(attributes[pre]["super_class"]) or "unknown"] += syn_count
        if pre in motor_ids:
            motor_outgoing_synapses += syn_count
            outgoing[pre]["all"] += syn_count
            if post in attributes:
                outgoing[pre][str(attributes[post]["super_class"]) or "unknown"] += syn_count

    motors: list[dict[str, object]] = []
    for root_id in sorted(motor_ids, key=lambda value: int(value) if value.isdigit() else value):
        record = dict(attributes[root_id])
        record["incoming_synapses_by_source_class"] = dict(incoming[root_id])
        record["outgoing_synapses_by_target_class"] = dict(outgoing[root_id])
        record["direct_descending_input_synapses"] = direct_dn_motor[root_id]
        motors.append(record)

    descending = [
        dict(attributes[root_id])
        for root_id in sorted(descending_ids, key=lambda value: int(value) if value.isdigit() else value)
    ]
    system_counts = Counter(str(record["target_system"]) for record in motors)
    return {
        "schema_version": "1.0",
        "dataset": "MANC v1.2.1 (VNC)",
        "source_files": {
            "attributes": attributes_path.name,
            "connections": connections_path.name,
        },
        "counts": {
            "attribute_rows": len(attributes),
            "motor_neurons": len(motor_ids),
            "descending_neurons": len(descending_ids),
            "connection_rows": connection_rows,
            "motor_incoming_synapses": motor_incoming_synapses,
            "motor_outgoing_synapses": motor_outgoing_synapses,
            "direct_descending_to_motor_rows": direct_dn_motor_rows,
            "direct_descending_to_motor_synapses": direct_dn_motor_synapses,
            "motor_target_systems": dict(system_counts),
        },
        "limitations": [
            "target_system is a broad annotation hint, not a muscle-level map",
            "MANC nt_type is empty in the connection export; predicted NT comes from neuron attributes",
            "FAFB and MANC root IDs are different and require a cross-dataset bridge",
        ],
        "motor_neurons": motors,
        "descending_neurons": descending,
    }


def main() -> int:
    """Executa a criação do catálogo pela linha de comando."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attributes", type=Path, required=True)
    parser.add_argument("--connections", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.attributes, args.connections):
        if not path.is_file():
            parser.error(f"file not found: {path}")
    catalog = build_catalog(args.attributes, args.connections)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as stream:
        json.dump(catalog, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(catalog["counts"], ensure_ascii=False, indent=2))
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
