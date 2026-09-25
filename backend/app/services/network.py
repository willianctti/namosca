"""Obtenção de grafos para a próxima fase autenticada de dados FlyWire.

O grafo simulado foi removido de propósito. Enquanto não houver uma
exportação real do FlyWire ou um proxy autenticado, as rotas de grafo
falham explicitamente em vez de mostrar neurônios fabricados.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from typing import Any

from app.providers.base import ProviderError
from app.providers.flywire import FlyWireProvider
from app.schemas import GraphQuery, Network, Region


class NetworkUnavailable(RuntimeError):
    """Erro levantado quando os dados reais do grafo FlyWire não estão configurados ou disponíveis."""


class NetworkService:
    """Obtém grafos reais do FlyWire com limites e guarda apenas resultados bem-sucedidos."""

    def __init__(
        self,
        *,
        flywire: FlyWireProvider,
        cache_size: int = 4,
        max_graph_neurons: int = 1200,
        max_graph_synapses: int = 6000,
    ) -> None:
        self.flywire = flywire
        self.cache_size = max(1, cache_size)
        self.max_graph_neurons = max(1, max_graph_neurons)
        self.max_graph_synapses = max(1, max_graph_synapses)
        self._cache: OrderedDict[tuple[str, str, int, int], Network] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get_network(self, query: GraphQuery) -> Network:
        """Obtém dados reais do FlyWire ou lança erro; nunca usa neurônios falsos."""

        region = normalize_query_region(query.region)
        max_neurons = min(query.max_neurons, self.max_graph_neurons)
        max_synapses = min(query.max_synapses, self.max_graph_synapses)
        key = (region.value, query.source, max_neurons, max_synapses)
        async with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                return cached

        if not self.flywire.configured:
            raise NetworkUnavailable(
                "FlyWire graph data is not configured. Set FLYWIRE_GRAPH_URL or "
                "FLYWIRE_DATA_FILE; mock neuron data is disabled."
            )

        try:
            graph = await self.flywire.fetch_network(
                region,
                max_neurons=max_neurons,
                max_synapses=max_synapses,
            )
        except (ProviderError, OSError, ValueError) as exc:
            raise NetworkUnavailable(str(exc)) from exc

        if max_neurons < query.max_neurons or max_synapses < query.max_synapses:
            metadata = dict(graph.metadata)
            metadata.update(
                {
                    "server_limit_applied": True,
                    "requested_max_neurons": query.max_neurons,
                    "requested_max_synapses": query.max_synapses,
                }
            )
            graph = graph.model_copy(update={"truncated": True, "metadata": metadata})

        async with self._lock:
            self._cache[key] = graph
            self._cache.move_to_end(key)
            while len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
        return graph

    def cache_info(self) -> dict[str, Any]:
        """Devolve informações sobre o cache e os limites configurados."""

        return {
            "entries": len(self._cache),
            "max_entries": self.cache_size,
            "max_graph_neurons": self.max_graph_neurons,
            "max_graph_synapses": self.max_graph_synapses,
            "flywire_configured": self.flywire.configured,
            "mock_enabled": False,
        }

    def clear_cache(self) -> None:
        """Limpa todos os grafos guardados no cache."""

        self._cache.clear()


def normalize_query_region(value: Any) -> Region:
    """Normaliza a região de uma consulta usando o esquema comum."""

    from app.schemas import normalize_region

    return normalize_region(value)
