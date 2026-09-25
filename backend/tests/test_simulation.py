from __future__ import annotations

import numpy as np
import pytest

from app.schemas import GraphQuery, Network, Neuron, SimulationConfig, Synapse
from app.simulation import LIFSimulator


def test_region_alias_is_supported() -> None:
    assert GraphQuery(region="visual").region.value == "optic_lobes"
    assert GraphQuery(region="mushroom_body").region.value == "mushroom_body"


def test_lif_propagates_a_delayed_synapse() -> None:
    graph = Network(
        region="visual",
        source="test-fixture",
        coordinate_space="test",
        units="normalized",
        neurons=[
            Neuron(id="a", label="a", region="visual", x=0, y=0, z=0, role="visual_input"),
            Neuron(id="b", label="b", region="visual", x=1, y=0, z=0, role="interneuron"),
        ],
        synapses=[Synapse(source="a", target="b", weight=2.0, delay_ms=5)],
    )
    simulator = LIFSimulator(
        graph,
        SimulationConfig(dt_ms=5, duration_ms=20, threshold=1.0, tau_ms=20),
    )
    simulator.step(np.asarray([2.0, 0.0], dtype=np.float32))
    result = simulator.step(np.asarray([0.0, 0.0], dtype=np.float32))
    assert result.spikes.tolist() == [1]


def test_no_mock_graph_is_served_when_flywire_is_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.delenv("FLYWIRE_DATA_FILE", raising=False)
    monkeypatch.delenv("FLYWIRE_GRAPH_URL", raising=False)
    with TestClient(app) as client:
        health = client.get("/api/health")
        providers = client.get("/api/providers")
        graph = client.get("/api/network?region=visual")

    assert health.status_code == 200
    assert health.json()["mock_fallback"] is False
    assert providers.status_code == 200
    assert providers.json()["mock"]["available"] is False
    assert graph.status_code == 503
    assert "FlyWire" in graph.json()["detail"]["error"]
