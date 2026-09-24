"""Graph retrieval for the future authenticated FlyWire data phase.

The mock graph was intentionally removed. Until a real FlyWire export or
authenticated proxy is configured, graph endpoints fail explicitly instead of
showing fabricated neurons.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from typing import Any

from app.providers.base import ProviderError
from app.providers.flywire import FlyWireProvider
from app.schemas import GraphQuery, Network, Region


class NetworkUnavailable(RuntimeError):
    """Raised when real FlyWire graph data is not configured or unavailable."""


class NetworkService:
    """Fetch bounded real FlyWire graphs and cache successful results only."""

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
        """Return real FlyWire data or raise; never fall back to fake neurons."""

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
        return {
            "entries": len(self._cache),
            "max_entries": self.cache_size,
            "max_graph_neurons": self.max_graph_neurons,
            "max_graph_synapses": self.max_graph_synapses,
            "flywire_configured": self.flywire.configured,
            "mock_enabled": False,
        }

    def clear_cache(self) -> None:
        self._cache.clear()


def normalize_query_region(value: Any) -> Region:
    from app.schemas import normalize_region

    return normalize_region(value)
