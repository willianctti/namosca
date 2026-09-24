"""Compatibility runtime for the small ``/neurons``/``/synapses`` demo API.

The primary API is stateless and uses a WebSocket session per visualization.
These helpers keep the endpoint names used by the early single-file prototype
working for simple frontends, without putting mutable state in module globals.
"""

from __future__ import annotations

import numpy as np

from app.schemas import Network, SimulationConfig
from app.simulation import LIFSimulator, StepResult


class LegacyRuntime:
    """One lightweight process-local LIF state for compatibility endpoints."""

    def __init__(self, network: Network) -> None:
        self.network = network
        self.config = SimulationConfig(dt_ms=5.0, duration_ms=1000.0)
        self.simulator = LIFSimulator(network, self.config)
        self.zero_input = np.zeros(self.simulator.neuron_count, dtype=np.float32)
        self.pulse_input = self.zero_input
        self.pulse_until_ms = 0.0
        self.last_spikes: set[str] = set()
        self.last_activity_ms: dict[str, float] = {}

    def inject(self, neuron_id: str, current: float) -> bool:
        """Inject a short current pulse into one known neuron."""

        index = self.simulator.index_by_id.get(neuron_id)
        if index is None:
            return False
        vector = np.zeros(self.simulator.neuron_count, dtype=np.float32)
        vector[index] = np.clip(current, -50.0, 50.0)
        self.pulse_input = vector
        self.pulse_until_ms = self.simulator._step_index * self.config.dt_ms + 100.0
        return True

    def step(self) -> StepResult:
        """Advance one compatibility step and remember recent spike IDs."""

        now_ms = self.simulator._step_index * self.config.dt_ms
        active = self.pulse_input if now_ms < self.pulse_until_ms else self.zero_input
        result = self.simulator.step(active)
        self.last_spikes = {self.simulator.neuron_ids[int(index)] for index in result.spikes}
        for neuron_id in self.last_spikes:
            self.last_activity_ms[neuron_id] = result.t_ms
        return result

    def reset(self) -> None:
        self.simulator.reset()
        self.pulse_input = self.zero_input
        self.pulse_until_ms = 0.0
        self.last_spikes.clear()
        self.last_activity_ms.clear()

    def neuron_payload(self) -> list[dict[str, object]]:
        """Return the legacy neuron shape with current membrane values."""

        payload: list[dict[str, object]] = []
        for index, neuron in enumerate(self.network.neurons):
            payload.append(
                {
                    "id": neuron.id,
                    "x": neuron.x,
                    "y": neuron.y,
                    "z": neuron.z,
                    "type": neuron.role,
                    "role": neuron.role,
                    "cell_type": neuron.cell_type,
                    "V_mem": round(float(self.simulator.voltage[index]), 2),
                    "spike": neuron.id in self.last_spikes,
                }
            )
        return payload
