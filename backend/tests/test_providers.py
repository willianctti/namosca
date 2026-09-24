from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.providers.flywire import FlyWireProvider
from app.schemas import Region


@pytest.mark.asyncio
async def test_flywire_json_file_adapter(tmp_path: Path) -> None:
    source = {
        "neurons": [
            {
                "id": "v1",
                "region": "optic_lobes",
                "position": {"x": 1, "y": 2, "z": 3},
                "role": "visual_input",
            },
            {
                "id": "v2",
                "region": "optic_lobes",
                "xyz": [4, 5, 6],
                "role": "interneuron",
            },
        ],
        "connections": [
            {"pre": "v1", "post": "v2", "strength": 0.75, "latency_ms": 2}
        ],
    }
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    async with httpx.AsyncClient() as client:
        provider = FlyWireProvider(client, data_file=str(path))
        graph = await provider.fetch_network(
            Region.OPTIC_LOBES,
            max_neurons=10,
            max_synapses=10,
        )
    assert [n.id for n in graph.neurons] == ["v1", "v2"]
    assert graph.synapses[0].source == "v1"
    assert graph.synapses[0].target == "v2"
    assert graph.synapses[0].weight == 0.75
