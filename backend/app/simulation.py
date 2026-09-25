"""Motor pequeno e determinístico de integração e vazamento (LIF).

O motor guarda uma estrutura de adjacência compacta no estilo CSR e um buffer
circular curto para correntes sinápticas pendentes. Não cria uma matriz densa
N x N; assim, a memória cresce com as arestas e o maior atraso, e não com o
quadrado do número de neurônios.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.schemas import Network, SimulationConfig, SimulationRequest, SimulationResult, SimulationStats, SpikeFrame, Stimulus


MAX_RING_SLOTS = 512
MAX_PENDING_ELEMENTS = 1_000_000


@dataclass(slots=True)
class StepResult:
    """Resultado de avançar o modelo LIF em um passo de tempo."""

    t_ms: float
    spikes: np.ndarray
    voltages: np.ndarray
    total_spikes: int


class LIFSimulator:
    """Estado LIF orientado a eventos para uma rede."""

    def __init__(self, network: Network, config: SimulationConfig) -> None:
        if not network.neurons:
            raise ValueError("cannot simulate an empty network")
        self.network = network
        self.config = config
        self.neuron_ids = [neuron.id for neuron in network.neurons]
        self.index_by_id = {neuron_id: index for index, neuron_id in enumerate(self.neuron_ids)}
        self.neuron_count = len(self.neuron_ids)
        self.voltage = np.full(self.neuron_count, config.resting_potential, dtype=np.float32)
        self.responding = np.zeros(self.neuron_count, dtype=bool)
        self.total_spikes = 0
        self._step_index = 0
        self._decay = math.exp(-config.dt_ms / config.tau_ms)
        self._build_adjacency()
        max_delay = float(self._edge_delays.max()) if self._edge_delays.size else 1.0
        max_delay_steps = max(1, int(math.ceil(max_delay / config.dt_ms)))
        pending_elements = (max_delay_steps + 1) * self.neuron_count
        if max_delay_steps > MAX_RING_SLOTS or pending_elements > MAX_PENDING_ELEMENTS:
            raise ValueError(
                "simulation topology exceeds the bounded delay buffer; "
                "increase dt_ms or reduce graph size"
            )
        # Uma posição extra impede que um evento atrasado seja sobrescrito por outro
        # evento com o mesmo resto de divisão.
        self._ring_size = max_delay_steps + 1
        self._pending = np.zeros((self._ring_size, self.neuron_count), dtype=np.float32)
        self._zero_input = np.zeros(self.neuron_count, dtype=np.float32)

    def _build_adjacency(self) -> None:
        """Agrupa arestas de saída por origem e atraso para atualizar vetores rapidamente."""

        source_indices: list[int] = []
        target_indices: list[int] = []
        signed_weights: list[float] = []
        delays: list[float] = []
        for synapse in self.network.synapses:
            source = self.index_by_id.get(synapse.source)
            target = self.index_by_id.get(synapse.target)
            if source is None or target is None or source == target:
                continue
            source_indices.append(source)
            target_indices.append(target)
            signed_weights.append(-synapse.weight if synapse.inhibitory else synapse.weight)
            delays.append(synapse.delay_ms)
        # Os vetores reais são mantidos compactos, com inteiros e decimais.
        self._edge_sources = np.asarray(source_indices, dtype=np.int32)
        self._edge_targets = np.asarray(target_indices, dtype=np.int32)
        self._edge_weights = np.asarray(signed_weights, dtype=np.float32)
        self._edge_delays = np.asarray(delays, dtype=np.float32)
        self._delay_buckets: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        for delay in sorted(set(float(value) for value in delays)):
            # ``round`` é estável para os pequenos atrasos usados nos testes e grafos
            # limitados, e mantém uma janela de entrega de um passo para atrasos
            # menores que 1 ms.
            delay_steps = max(1, int(round(delay / self.config.dt_ms)))
            mask = np.isclose(self._edge_delays, delay)
            if not np.any(mask):
                continue
            if delay_steps in self._delay_buckets:
                old_sources, old_targets, old_weights = self._delay_buckets[delay_steps]
                self._delay_buckets[delay_steps] = (
                    np.concatenate((old_sources, self._edge_sources[mask])),
                    np.concatenate((old_targets, self._edge_targets[mask])),
                    np.concatenate((old_weights, self._edge_weights[mask])),
                )
            else:
                self._delay_buckets[delay_steps] = (
                    self._edge_sources[mask],
                    self._edge_targets[mask],
                    self._edge_weights[mask],
                )

    def reset(self) -> None:
        """Reinicia potenciais e eventos pendentes sem reconstruir a topologia."""

        self.voltage.fill(self.config.resting_potential)
        self.responding.fill(False)
        self.total_spikes = 0
        self._step_index = 0
        self._pending.fill(0.0)

    def stimulus_vector(
        self,
        stimulus: Stimulus,
        *,
        region: str | None = None,
    ) -> np.ndarray:
        """Cria um vetor de corrente para IDs explícitos ou uma função de entrada adequada."""

        vector = np.zeros(self.neuron_count, dtype=np.float32)
        selected: list[int] = []
        if stimulus.neuron_ids:
            for neuron_id in stimulus.neuron_ids:
                index = self.index_by_id.get(neuron_id)
                if index is not None:
                    selected.append(index)
        if not selected and stimulus.role:
            selected = [
                index
                for index, neuron in enumerate(self.network.neurons)
                if neuron.role.lower() == stimulus.role.lower()
            ]
        if not selected:
            preferred_roles = {
                "optic_lobes": ("visual_input", "sensory"),
                "visual": ("visual_input", "sensory"),
                "descending": ("sensory", "interneuron"),
                "motor": ("interneuron", "descending"),
                "mushroom_body": ("sensory", "interneuron"),
                "all": ("visual_input", "sensory"),
            }
            roles = preferred_roles.get(region or self.network.region, ("sensory", "interneuron"))
            for role in roles:
                selected = [
                    index
                    for index, neuron in enumerate(self.network.neurons)
                    if neuron.role.lower() == role
                ]
                if selected:
                    break
        if not selected:
            # A pessoa usuária pode pedir um grafo com nomes de função próprios.
            # Injetar nos primeiros nós é uma última opção determinística.
            selected = list(range(min(4, self.neuron_count)))
        if selected:
            vector[np.asarray(sorted(set(selected)), dtype=np.int32)] = stimulus.intensity
        return vector

    def step(self, external_input: np.ndarray | None = None) -> StepResult:
        """Avança um passo e devolve picos e potenciais de membrana."""

        if external_input is None:
            external_input = self._zero_input
        if external_input.shape != (self.neuron_count,):
            raise ValueError("external input has the wrong shape")

        current_slot = self._step_index % self._ring_size
        # Copia antes de limpar: o corte básico do NumPy devolve uma visão.
        pending_input = self._pending[current_slot].copy()
        self._pending[current_slot].fill(0.0)

        # Atualização LIF: v[t] = v_rest + (v[t-1] - v_rest) * exp(-dt/tau) + I.
        # Subtrair e restaurar o nível de repouso é importante quando quem
        # chama escolhe um potencial de repouso diferente de zero.
        self.voltage -= self.config.resting_potential
        self.voltage *= self._decay
        self.voltage += self.config.resting_potential
        self.voltage += pending_input
        self.voltage += external_input
        # Limitar a tensão evita que pesos remotos malformados gerem valores
        # exponenciais ou muito grandes e mantém a demonstração estável.
        upper_bound = max(self.config.threshold * 8.0, 8.0)
        np.clip(self.voltage, min=self.config.reset_potential - 2.0, max=upper_bound, out=self.voltage)

        spikes = np.flatnonzero(self.voltage >= self.config.threshold).astype(np.int32, copy=False)
        if spikes.size:
            self.voltage[spikes] = self.config.reset_potential
            self.responding[spikes] = True
            self.total_spikes += int(spikes.size)
            self._schedule_synapses(spikes)

        t_ms = (self._step_index + 1) * self.config.dt_ms
        self._step_index += 1
        return StepResult(
            t_ms=t_ms,
            spikes=spikes,
            voltages=self.voltage.copy(),
            total_spikes=self.total_spikes,
        )

    def _schedule_synapses(self, spikes: np.ndarray) -> None:
        """Coloca correntes de saída em posições futuras do buffer circular."""

        if self._edge_sources.size == 0:
            return
        for delay_steps, (sources, targets, weights) in self._delay_buckets.items():
            outgoing_mask = np.isin(sources, spikes)
            if not np.any(outgoing_mask):
                continue
            active_sources = sources[outgoing_mask]
            active_targets = targets[outgoing_mask]
            active_weights = weights[outgoing_mask]
            destination = (self._step_index + delay_steps) % self._ring_size
            # add.at soma corretamente correntes que chegam de várias origens.
            np.add.at(self._pending[destination], active_targets, active_weights)


def _frame_from_step(
    simulator: LIFSimulator,
    result: StepResult,
    *,
    max_spikes: int,
    include_voltage: bool,
) -> SpikeFrame:
    """Converte o resultado de um passo NumPy em um quadro compacto para a API."""

    visible = result.spikes[:max_spikes]
    visible_ids = [simulator.neuron_ids[int(index)] for index in visible]
    voltage = None
    if include_voltage:
        voltage = [round(float(value), 4) for value in result.voltages]
    return SpikeFrame(
        t_ms=round(result.t_ms, 3),
        spikes=visible_ids,
        spike_indices=[int(index) for index in visible],
        total_spikes=result.total_spikes,
        active_neurons=int(result.spikes.size),
        membrane_potential=voltage,
    )


def _run_local_sync(
    network: Network,
    request: SimulationRequest,
    *,
    max_steps: int = 200_000,
) -> tuple[list[SpikeFrame], SimulationStats, dict[str, Any]]:
    """Núcleo síncrono, seguro para executar em uma linha de execução."""

    config = request.config
    simulation_network = network
    overrides = {
        (override.source, override.target): override
        for override in request.excitatory_edge_overrides
    }
    if request.ablate_inhibitory or overrides:
        adjusted_synapses = []
        for synapse in network.synapses:
            key = (synapse.source, synapse.target)
            if request.ablate_inhibitory and synapse.inhibitory:
                adjusted_synapses.append(synapse.model_copy(update={"inhibitory": False, "weight": 0.0}))
                continue
            override = overrides.get(key)
            if override is not None:
                adjusted_synapses.append(
                    synapse.model_copy(
                        update={
                            "inhibitory": False,
                            "weight": override.weight if override.weight is not None else max(1.0, synapse.weight),
                        }
                    )
                )
                continue
            adjusted_synapses.append(synapse)
        simulation_network = network.model_copy(update={"synapses": adjusted_synapses})
    simulator = LIFSimulator(simulation_network, config)
    stimulus = simulator.stimulus_vector(request.stimulus, region=network.region)
    zero = np.zeros(simulator.neuron_count, dtype=np.float32)
    requested_steps = max(1, int(round(config.duration_ms / config.dt_ms)))
    steps = min(requested_steps, max_steps)
    requested_frame_stride = max(1, int(round(config.frame_interval_ms / config.dt_ms)))
    # Preserva o ritmo pedido quando possível, mas não deixa que uma combinação
    # de dt pequeno e duração grande crie uma resposta sem limite.
    frame_stride = max(requested_frame_stride, int(math.ceil(steps / config.max_frames)))
    frames: list[SpikeFrame] = []
    peak_active = 0
    for step_number in range(1, steps + 1):
        elapsed_before = (step_number - 1) * config.dt_ms
        active_input = stimulus if elapsed_before < request.stimulus.duration_ms else zero
        step_result = simulator.step(active_input)
        peak_active = max(peak_active, int(step_result.spikes.size))
        if step_number % frame_stride == 0 or step_number == steps:
            frames.append(
                _frame_from_step(
                    simulator,
                    step_result,
                    max_spikes=config.max_spikes_per_frame,
                    include_voltage=request.include_voltage,
                )
            )
    stats = SimulationStats(
        steps=steps,
        total_spikes=simulator.total_spikes,
        responding_neurons=int(np.count_nonzero(simulator.responding)),
        peak_active_neurons=peak_active,
        elapsed_simulated_ms=round(steps * config.dt_ms, 3),
        truncated_frames=steps < requested_steps or frame_stride > requested_frame_stride,
    )
    metadata = {
        "model": "leaky-integrate-and-fire",
        "dt_ms": config.dt_ms,
        "frame_stride_steps": frame_stride,
        "ring_buffer_slots": simulator._ring_size,
        "input_neuron_count": int(np.count_nonzero(stimulus)),
        "ablate_inhibitory": request.ablate_inhibitory,
        "excitatory_edge_overrides": [override.model_dump() for override in request.excitatory_edge_overrides],
    }
    return frames, stats, metadata


async def run_local(network: Network, request: SimulationRequest) -> SimulationResult:
    """Executa o motor LIF sem bloquear o loop de eventos do asyncio."""

    frames, stats, metadata = await asyncio.to_thread(_run_local_sync, network, request)
    return SimulationResult(
        engine_requested="lif",
        engine_used="lif",
        network=_network_summary(network),
        frames=frames,
        stats=stats,
        metadata=metadata,
    )


def _network_summary(network: Network) -> Any:
    """Evita importar o módulo de rotas e devolve um resumo compatível com o esquema."""

    from app.schemas import NetworkSummary

    return NetworkSummary(
        region=network.region,
        source=network.source,
        coordinate_space=network.coordinate_space,
        neuron_count=len(network.neurons),
        synapse_count=len(network.synapses),
        truncated=network.truncated,
        fallback=network.fallback,
    )


def make_step_input(simulator: LIFSimulator, vector: np.ndarray) -> np.ndarray:
    """Devolve um vetor de entrada sem expor detalhes mutáveis do simulador."""

    return vector if vector.shape == (simulator.neuron_count,) else np.zeros(simulator.neuron_count, dtype=np.float32)
