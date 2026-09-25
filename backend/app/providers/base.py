"""Interfaces de provedores e utilitários para normalizar grafos."""

from __future__ import annotations

from typing import Protocol

from app.schemas import Network, Region


class ProviderError(RuntimeError):
    """Falha recuperável de um provedor de dados.

    A camada da API transforma este erro em uma alternativa estruturada ou em
    uma resposta 503, conforme a opção ``strict`` da solicitação.
    """


class NetworkProvider(Protocol):
    """Contrato assíncrono mínimo para provedores de grafos."""

    name: str

    async def fetch_network(
        self,
        region: Region,
        *,
        max_neurons: int,
        max_synapses: int,
    ) -> Network:
        """Devolve um grafo de rede normalizado e limitado."""


def limit_graph(graph: Network, *, max_neurons: int, max_synapses: int) -> Network:
    """Aplica limites determinísticos e preserva referências válidas entre neurônios."""

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
