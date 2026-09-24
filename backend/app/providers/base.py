"""Provider interfaces and normalized graph helpers."""

from __future__ import annotations

from typing import Protocol

from app.schemas import Network, Region


class ProviderError(RuntimeError):
    """A recoverable data-provider failure.

    The API layer converts this into a structured fallback or a 503 response,
    depending on the request's ``strict`` flag.
    """


class NetworkProvider(Protocol):
    """Minimal asynchronous contract for graph providers."""

    name: str

    async def fetch_network(
        self,
        region: Region,
        *,
        max_neurons: int,
        max_synapses: int,
    ) -> Network:
        """Return a normalized, bounded network graph."""


def limit_graph(graph: Network, *, max_neurons: int, max_synapses: int) -> Network:
    """Apply deterministic limits while preserving valid endpoint references."""

    if len(graph.neurons) <= max_neurons and len(graph.synapses) <= max_synapses:
        return graph

    neurons = graph.neurons[:max_neurons]
    allowed = {neuron.id for neuron in neurons}
    synapses = [
        synapse
        for synapse in graph.synapses
        if synapse.source in allowed and synapse.target in allowed
    ][:max_synapses]
    return graph.model_copy(
        update={
            "neurons": neurons,
            "synapses": synapses,
            "truncated": True,
        }
    )
