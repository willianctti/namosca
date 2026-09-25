"""Translate LIF spikes into data-backed MCNS Dm → DN → MN routes."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_dm_routes(path: Path | None) -> dict[str, list[dict[str, Any]]]:
    if path is None or not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for route in data.get("routes", []):
        for dm_type in route.get("dm_types", []):
            if dm_type:
                result[str(dm_type)].append(route)
    return dict(result)


def summarize_motor_output(network: Any, frames: list[Any], routes_by_dm: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    cell_types = {str(neuron.id): str(neuron.cell_type or "") for neuron in network.neurons}
    active_dm: set[str] = set()
    for frame in frames:
        for neuron_id in frame.spikes:
            cell_type = cell_types.get(neuron_id)
            if cell_type in routes_by_dm:
                active_dm.add(cell_type)
    systems: dict[str, int] = defaultdict(int)
    dn_types: set[str] = set()
    mn_types: set[str] = set()
    for dm_type in sorted(active_dm):
        for route in routes_by_dm[dm_type]:
            system = route.get("target_system", "unclassified")
            systems[system] += int(route.get("dn_to_mn_synapses", 0))
            if route.get("dn_type"): dn_types.add(str(route["dn_type"]))
            if route.get("mn_manc_type"): mn_types.add(str(route["mn_manc_type"]))
    return {
        "available": bool(routes_by_dm),
        "active_dm_types": sorted(active_dm),
        "active_dm_count": len(active_dm),
        "systems": dict(sorted(systems.items(), key=lambda pair: -pair[1])),
        "downstream_dn_types": sorted(dn_types),
        "downstream_mn_types": sorted(mn_types),
        "interpretation": "weights are aggregate MCNS connectome weights from Dm → DN → MN; they are not measured muscle force or joint movement",
    }
