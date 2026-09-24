"""Pydantic contracts shared by HTTP, WebSocket and provider adapters."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Region(str, Enum):
    """Supported subnetwork presets."""

    OPTIC_LOBES = "optic_lobes"
    DESCENDING = "descending"
    MOTOR = "motor"
    MUSHROOM_BODY = "mushroom_body"
    ALL = "all"


_REGION_ALIASES: dict[str, Region] = {
    "optic_lobes": Region.OPTIC_LOBES,
    "optic_lobe": Region.OPTIC_LOBES,
    "lobos_opticos": Region.OPTIC_LOBES,
    "lobo_optico": Region.OPTIC_LOBES,
    "visual": Region.OPTIC_LOBES,
    "visao": Region.OPTIC_LOBES,
    "vision": Region.OPTIC_LOBES,
    "descending": Region.DESCENDING,
    "descendentes": Region.DESCENDING,
    "neuronios_descendentes": Region.DESCENDING,
    "motor": Region.MOTOR,
    "motores": Region.MOTOR,
    "motor_neurons": Region.MOTOR,
    "motor_cortex": Region.DESCENDING,
    "mushroom_body": Region.MUSHROOM_BODY,
    "all": Region.ALL,
    "all_brain": Region.ALL,
    "c_whole_brain": Region.ALL,
}


def normalize_region(value: str | Region | None) -> Region:
    """Normalize English/Portuguese region aliases.

    Unknown values are rejected instead of silently selecting a different
    biological dataset, which is important for reproducibility.
    """

    if isinstance(value, Region):
        return value
    if value is None:
        value = "optic_lobes"
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    normalized = normalized.replace("ó", "o").replace("ã", "a").replace("ç", "c")
    if normalized in _REGION_ALIASES:
        return _REGION_ALIASES[normalized]
    raise ValueError(
        f"unknown region '{value}'; use optic_lobes, descending, motor, mushroom_body, or all"
    )


class StrictModel(BaseModel):
    """Base model that ignores unknown provider fields safely."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class Neuron(StrictModel):
    """A point-like neuron representation suitable for Three.js."""

    id: str
    label: str
    region: str
    x: float
    y: float
    z: float
    role: str = "interneuron"
    cell_type: str | None = None


class Synapse(StrictModel):
    """Directed chemical synapse between two neuron IDs."""

    source: str
    target: str
    weight: float = Field(ge=0.0)
    delay_ms: float = Field(default=1.0, ge=0.0, le=1000.0)
    inhibitory: bool = False


class GraphQuery(StrictModel):
    """Limits and provider selection for a graph request."""

    region: Region = Region.OPTIC_LOBES
    source: Literal["auto", "flywire"] = "auto"
    max_neurons: int = Field(default=240, ge=1, le=5000)
    max_synapses: int = Field(default=1200, ge=1, le=50_000)
    strict: bool = False

    @field_validator("region", mode="before")
    @classmethod
    def validate_region(cls, value: str | Region) -> Region:
        return normalize_region(value)


class Network(StrictModel):
    """Normalized graph schema returned to clients.

    The same shape is emitted by the local fallback and the optional remote
    adapters. This prevents the frontend from depending on provider quirks.
    """

    schema_version: Literal["1.0"] = "1.0"
    region: str
    source: str
    coordinate_space: str
    units: str
    neurons: list[Neuron]
    synapses: list[Synapse]
    truncated: bool = False
    fallback: bool = False
    fallback_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NetworkSummary(StrictModel):
    """Small network descriptor used in simulation responses."""

    region: str
    source: str
    coordinate_space: str
    neuron_count: int
    synapse_count: int
    truncated: bool = False
    fallback: bool = False


class Stimulus(StrictModel):
    """External current pulse injected into selected neurons."""

    neuron_ids: list[str] = Field(default_factory=list, max_length=256)
    intensity: float = Field(default=1.5, ge=0.0, le=50.0)
    duration_ms: float = Field(default=100.0, gt=0.0, le=5000.0)
    role: str | None = None


class SimulationConfig(StrictModel):
    """Numerical parameters for the leaky integrate-and-fire model."""

    dt_ms: float = Field(default=5.0, ge=1.0, le=100.0)
    duration_ms: float = Field(default=500.0, gt=0.0, le=30_000.0)
    tau_ms: float = Field(default=20.0, gt=0.0, le=10_000.0)
    threshold: float = Field(default=1.0, gt=0.0)
    reset_potential: float = Field(default=0.0)
    resting_potential: float = Field(default=0.0)
    frame_interval_ms: float = Field(default=10.0, gt=0.0, le=1000.0)
    max_spikes_per_frame: int = Field(default=2000, ge=1, le=100_000)
    max_frames: int = Field(default=2000, ge=1, le=10_000)

    @field_validator("duration_ms")
    @classmethod
    def validate_duration(cls, value: float) -> float:
        # Avoid an accidental million-step request from a malformed client.
        if value > 30_000:
            raise ValueError("duration_ms must be <= 30000")
        return value


class SimulationRequest(StrictModel):
    """HTTP simulation request."""

    graph: GraphQuery = Field(default_factory=GraphQuery)
    config: SimulationConfig = Field(default_factory=SimulationConfig)
    stimulus: Stimulus = Field(default_factory=Stimulus)
    engine: Literal["lif", "axobug"] = "lif"
    include_voltage: bool = False


class SpikeFrame(StrictModel):
    """One display frame emitted by the simulator."""

    t_ms: float
    spikes: list[str]
    spike_indices: list[int]
    total_spikes: int
    active_neurons: int
    membrane_potential: list[float] | None = None
    channels: dict[str, float] | None = None


class SimulationStats(StrictModel):
    """Summary counters for a completed run."""

    steps: int
    total_spikes: int
    responding_neurons: int
    peak_active_neurons: int
    elapsed_simulated_ms: float
    truncated_frames: bool = False


class SimulationResult(StrictModel):
    """HTTP result for a completed LIF or Axobug-backed run."""

    engine_requested: Literal["lif", "axobug"]
    engine_used: Literal["lif", "axobug"]
    fallback: bool = False
    fallback_reason: str | None = None
    network: NetworkSummary
    frames: list[SpikeFrame]
    stats: SimulationStats
    metadata: dict[str, Any] = Field(default_factory=dict)


class AxobugRunRequest(StrictModel):
    """Small proxy request for the public Axobug Neuro API."""

    stimulus: str = "loom"
    intensity: float = Field(default=1.0, ge=0.0, le=2.0)
    duration_ms: int = Field(default=100, ge=50, le=200)
    seed: int = Field(default=42, ge=0, le=4_294_967_295)
    view: Literal["full", "drive"] = "full"

    @field_validator("duration_ms")
    @classmethod
    def validate_axobug_duration(cls, value: int) -> int:
        if value not in {50, 100, 150, 200}:
            raise ValueError("Axobug duration_ms must be one of 50, 100, 150, 200")
        return value


class HealthResponse(StrictModel):
    status: Literal["ok"]
    service: str
    version: str
    default_region: str
    mock_fallback: bool = False
