"""Simulation orchestration for local LIF and optional Axobug responses."""

from __future__ import annotations

from typing import Any

from app.providers.axobug import AxobugClient, AxobugError
from app.schemas import Network, SimulationRequest, SimulationResult, SimulationStats, SpikeFrame
from app.simulation import _network_summary, run_local


class SimulationService:
    """Run simulations and normalize remote/local results."""

    def __init__(self, axobug: AxobugClient) -> None:
        self.axobug = axobug

    async def run(self, network: Network, request: SimulationRequest) -> SimulationResult:
        """Execute the requested engine, falling back to LIF when needed."""

        if request.engine == "axobug":
            try:
                return await self._run_axobug(network, request)
            except (AxobugError, KeyError, TypeError, ValueError) as exc:
                result = await run_local(network, request.model_copy(update={"engine": "lif"}))
                return result.model_copy(
                    update={
                        "engine_requested": "axobug",
                        "engine_used": "lif",
                        "fallback": True,
                        "fallback_reason": str(exc),
                    }
                )
        return await run_local(network, request)

    async def _run_axobug(self, network: Network, request: SimulationRequest) -> SimulationResult:
        """Map Axobug's documented spike frames to the normalized wire schema."""

        # Axobug accepts only four fixed durations in the public alpha.
        duration_ms = _nearest_axobug_duration(request.config.duration_ms)
        stimulus_name = _map_stimulus(request)
        remote = await self.axobug.run(
            stimulus=stimulus_name,
            intensity=min(2.0, max(0.0, request.stimulus.intensity)),
            duration_ms=duration_ms,
            seed=42,
            view="full",
        )
        raw_frames = remote.get("frames", [])
        frames: list[SpikeFrame] = []
        total_spikes = int(remote.get("total_spikes", 0) or 0)
        responding: set[str] = set()
        for raw_frame in raw_frames:
            if not isinstance(raw_frame, dict):
                continue
            raw_indices = raw_frame.get("spikes", [])
            if not isinstance(raw_indices, list):
                continue
            indices: list[int] = []
            ids: list[str] = []
            for value in raw_indices[: request.config.max_spikes_per_frame]:
                try:
                    index = int(value)
                except (TypeError, ValueError):
                    continue
                indices.append(index)
                if 0 <= index < len(network.neurons):
                    identifier = network.neurons[index].id
                else:
                    identifier = f"atlas-{index}"
                ids.append(identifier)
                responding.add(identifier)
            frame_channels = raw_frame.get("channels")
            if not isinstance(frame_channels, dict):
                frame_channels = None
            else:
                frame_channels = {
                    str(key): float(value)
                    for key, value in frame_channels.items()
                    if isinstance(value, (int, float))
                }
            frames.append(
                SpikeFrame(
                    t_ms=float(raw_frame.get("t", 0.0) or 0.0),
                    spikes=ids,
                    spike_indices=indices,
                    total_spikes=int(raw_frame.get("total", total_spikes) or 0),
                    active_neurons=len(indices),
                    channels=frame_channels,
                )
            )
        metadata: dict[str, Any] = {
            "remote_model": remote.get("model"),
            "remote_run_id": remote.get("id"),
            "remote_stimulus": stimulus_name,
            "remote_duration_ms": duration_ms,
            "remote_note": "Axobug returns atlas neuron indices; graph IDs are mapped by index for display.",
        }
        if remote.get("channels") is not None:
            metadata["channels"] = remote.get("channels")
        if remote.get("drive") is not None:
            metadata["drive"] = remote.get("drive")
        stats = SimulationStats(
            steps=len(frames),
            total_spikes=total_spikes,
            responding_neurons=len(responding),
            peak_active_neurons=max((frame.active_neurons for frame in frames), default=0),
            elapsed_simulated_ms=duration_ms,
            truncated_frames=False,
        )
        return SimulationResult(
            engine_requested="axobug",
            engine_used="axobug",
            network=_network_summary(network),
            frames=frames,
            stats=stats,
            metadata=metadata,
        )


def _nearest_axobug_duration(duration_ms: float) -> int:
    """Map a requested duration to Axobug's documented allowed values."""

    allowed = (50, 100, 150, 200)
    return min(allowed, key=lambda value: abs(value - duration_ms))


def _map_stimulus(request: SimulationRequest) -> str:
    """Use the first explicit Axobug-compatible stimulus or a safe default."""

    # The local schema intentionally leaves stimulus names open-ended. A UI can
    # send an Axobug name through this small metadata convention.
    explicit = request.stimulus.role
    if explicit in {"loom", "sugar", "food", "scent", "touch", "sound", "color", "humidity", "heat", "bitter", "quiet"}:
        return explicit
    if request.stimulus.role:
        return "loom"
    return "loom"
