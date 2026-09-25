"""Optional adapter for FlyWire/Codex-compatible JSON graph exports.

FlyWire Codex is a signed-in web application and does not promise one stable,
anonymous REST endpoint for raw connectome data. This adapter therefore
supports an explicitly configured JSON export or REST proxy rather than
inventing private Codex routes. The accepted input is deliberately permissive:
common ``neurons``/``cells`` and ``synapses``/``connections`` field names are
normalized into the backend schema.

No credentials are required for a local JSON export. If a FlyWire endpoint is
configured, use a short-lived token through ``FLYWIRE_API_TOKEN`` and never
commit it to source control.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

import httpx

from app.providers.base import ProviderError, limit_graph
from app.schemas import Network, Neuron, Region, Synapse


class FlyWireProvider:
    """Fetch a bounded graph from a user-configured JSON source."""

    name = "flywire"

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        graph_url: str | None = None,
        api_token: str | None = None,
        data_file: str | None = None,
        timeout_seconds: float = 20.0,
        max_remote_bytes: int = 12_000_000,
    ) -> None:
        self._client = client
        self.graph_url = graph_url.rstrip() if graph_url else None
        self.api_token = api_token
        self.data_file = data_file
        self.timeout_seconds = timeout_seconds
        self.max_remote_bytes = max_remote_bytes

    @property
    def configured(self) -> bool:
        """Whether at least one external graph source is configured."""

        return bool(self.graph_url or self.data_file)

    async def fetch_network(
        self,
        region: Region,
        *,
        max_neurons: int,
        max_synapses: int,
    ) -> Network:
        """Fetch and normalize a graph, enforcing hard memory limits."""

        payload = await self._load_payload()
        neurons = self._parse_neurons(payload, region, max_neurons)
        if not neurons:
            raise ProviderError("FlyWire graph contained no neurons for the requested region")
        id_map = {neuron.id: neuron for neuron in neurons}
        synapses = self._parse_synapses(payload, id_map, max_synapses)
        source_metadata = payload.get("metadata") if isinstance(payload, dict) else None
        metadata = dict(source_metadata) if isinstance(source_metadata, dict) else {}
        metadata.update(
            {
                "remote": bool(self.graph_url and not self.data_file),
                "local_file": bool(self.data_file),
                "adapter": "flywire-json",
                "description": "Normalized from the configured FlyWire/Codex-compatible JSON source.",
            }
        )
        if isinstance(payload, dict):
            source_region = payload.get("region")
            if isinstance(source_region, str) and source_region:
                metadata["source_region"] = source_region
            coordinate_space = payload.get("coordinate_space")
            units = payload.get("units")
        else:
            coordinate_space = None
            units = None
        graph = Network(
            region=region.value,
            source=self.name,
            coordinate_space=str(coordinate_space or "provider"),
            units=str(units or "provider"),
            neurons=neurons,
            synapses=synapses,
            metadata=metadata,
        )
        return limit_graph(graph, max_neurons=max_neurons, max_synapses=max_synapses)

    async def _load_payload(self) -> Any:
        if self.data_file:
            return self._read_file(Path(self.data_file))
        if not self.graph_url:
            raise ProviderError("FLYWIRE_GRAPH_URL or FLYWIRE_DATA_FILE is not configured")
        headers = {"Accept": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        try:
            # Stream the response so a surprisingly large export cannot
            # silently consume the whole process memory.
            async with self._client.stream(
                "GET",
                self.graph_url,
                headers=headers,
                timeout=self.timeout_seconds,
            ) as response:
                if response.status_code >= 400:
                    raise ProviderError(f"FlyWire endpoint returned HTTP {response.status_code}")
                declared_length = response.headers.get("content-length")
                if declared_length and int(declared_length) > self.max_remote_bytes:
                    raise ProviderError("FlyWire response exceeds MAX_REMOTE_BYTES")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self.max_remote_bytes:
                        raise ProviderError("FlyWire response exceeds MAX_REMOTE_BYTES")
        except ProviderError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(f"could not fetch FlyWire graph: {exc}") from exc
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError("FlyWire response is not valid UTF-8 JSON") from exc

    def _read_file(self, path: Path) -> Any:
        try:
            size = path.stat().st_size
            if size > self.max_remote_bytes:
                raise ProviderError("FlyWire data file exceeds MAX_REMOTE_BYTES")
            raw = path.read_bytes()
            return json.loads(raw.decode("utf-8"))
        except ProviderError:
            raise
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError(f"could not read FlyWire data file: {exc}") from exc

    def _parse_neurons(
        self,
        payload: Any,
        requested_region: Region,
        max_neurons: int,
    ) -> list[Neuron]:
        records = _records(_first_value(payload, "neurons", "cells", "neuron_data"))
        parsed: list[Neuron] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            neuron_id = _first_value(record, "id", "neuron_id", "cell_id", "name")
            if isinstance(neuron_id, dict):
                neuron_id = _first_value(neuron_id, "id", "value", "name")
            if neuron_id is None:
                continue
            region_value = _first_value(
                record, "region", "neuropil", "brain_region", "division", "compartment"
            )
            if requested_region is not Region.ALL and region_value is not None:
                if not _matches_region(str(region_value), requested_region):
                    continue
            position = _position(record)
            if position is None:
                continue
            x, y, z = position
            cell_type = _first_value(record, "cell_type", "cellType", "type", "label")
            additional_types = _first_value(
                record, "additional_cell_types", "additional_type(s)", "additional_types"
            )
            group = _first_value(record, "group", "division", "compartment")
            neuropil = _first_value(record, "neuropil", "region", "group")
            nt_type = _first_value(record, "nt_type", "neurotransmitter", "transmitter")
            role = _first_value(record, "role", "class", "cell_class") or "interneuron"
            identifier = str(neuron_id)
            parsed.append(
                Neuron(
                    id=identifier,
                    label=str(
                        _first_value(record, "label", "name", "display_name")
                        or cell_type
                        or identifier
                    ),
                    region=str(region_value or requested_region.value),
                    x=x,
                    y=y,
                    z=z,
                    role=str(role),
                    cell_type=str(cell_type) if cell_type is not None else None,
                    additional_cell_types=(
                        str(additional_types) if additional_types not in (None, "") else None
                    ),
                    group=str(group) if group is not None else None,
                    neuropil=str(neuropil) if neuropil is not None else None,
                    nt_type=str(nt_type) if nt_type not in (None, "") else None,
                )
            )
            if len(parsed) >= max_neurons:
                break
        return parsed

    def _parse_synapses(
        self,
        payload: Any,
        neurons: dict[str, Neuron],
        max_synapses: int,
    ) -> list[Synapse]:
        records = _records(
            _first_value(payload, "synapses", "connections", "edges", "connectome")
        )
        parsed: list[Synapse] = []
        for record in records:
            if not isinstance(record, dict) or len(parsed) >= max_synapses:
                break
            source = _endpoint(record, "source", "pre", "from", "presynaptic", "source_id")
            target = _endpoint(record, "target", "post", "to", "postsynaptic", "target_id")
            if source is None or target is None:
                continue
            source = str(source)
            target = str(target)
            if source not in neurons or target not in neurons or source == target:
                continue
            synapse_count_value = _first_value(record, "synapse_count", "syn_count")
            synapse_count: float | None
            try:
                synapse_count = (
                    float(synapse_count_value)
                    if synapse_count_value is not None
                    else None
                )
            except (TypeError, ValueError):
                synapse_count = None
            if synapse_count is not None:
                synapse_count = max(0.0, synapse_count)
            weight_value = _first_value(record, "weight", "strength", "synapse_count", "count")
            try:
                weight = float(weight_value if weight_value is not None else 0.5)
            except (TypeError, ValueError):
                weight = 0.5
            weight = max(0.0, min(10.0, weight))
            delay_value = _first_value(record, "delay_ms", "delay", "latency_ms")
            try:
                delay = float(delay_value if delay_value is not None else 1.0)
            except (TypeError, ValueError):
                delay = 1.0
            inhibitory_value = _first_value(record, "inhibitory", "is_inhibitory")
            nt_type_value = _first_value(record, "nt_type", "neurotransmitter", "transmitter")
            nt_type = str(nt_type_value) if nt_type_value not in (None, "") else None
            neuropil_value = _first_value(record, "neuropil", "region")
            if isinstance(inhibitory_value, str):
                inhibitory = inhibitory_value.lower() in {"1", "true", "yes", "gaba", "gly", "glicina"}
            elif inhibitory_value is not None:
                inhibitory = bool(inhibitory_value)
            else:
                inhibitory = bool(nt_type and nt_type.upper() in {"GABA", "GLY"})
            parsed.append(
                Synapse(
                    source=source,
                    target=target,
                    weight=weight,
                    delay_ms=max(0.0, min(1000.0, delay)),
                    inhibitory=inhibitory,
                    synapse_count=synapse_count,
                    neuropil=str(neuropil_value) if neuropil_value is not None else None,
                    nt_type=nt_type,
                )
            )
        return parsed


def _first_value(data: Any, *keys: str) -> Any:
    """Return the first present key, supporting one nested ``data`` object."""

    if not isinstance(data, dict):
        return None
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    nested = data.get("data")
    if isinstance(nested, dict):
        return _first_value(nested, *keys)
    return None


def _records(value: Any) -> Iterable[Any]:
    """Normalize list and ID-to-object JSON containers into records."""

    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        # Some exports use {"12345": {"x": ...}} rather than a list.
        if any(key in value for key in ("id", "neuron_id", "cell_id", "x", "position")):
            return [value]
        if all(isinstance(item, dict) for item in value.values()):
            return [dict(item, id=key) for key, item in value.items()]
        return []
    return []


def _position(record: dict[str, Any]) -> tuple[float, float, float] | None:
    """Read common position representations from a neuron record."""

    for key in ("position", "xyz", "coordinates", "coord", "soma_position"):
        value = record.get(key)
        if isinstance(value, dict):
            value = [value.get("x"), value.get("y"), value.get("z")]
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            try:
                parsed = (float(value[0]), float(value[1]), float(value[2]))
                if all(math.isfinite(item) for item in parsed):
                    return parsed
            except (TypeError, ValueError):
                pass
    try:
        parsed = (float(record["x"]), float(record["y"]), float(record["z"]))
        return parsed if all(math.isfinite(item) for item in parsed) else None
    except (KeyError, TypeError, ValueError):
        return None


def _endpoint(record: dict[str, Any], *keys: str) -> Any:
    value = _first_value(record, *keys)
    if isinstance(value, dict):
        return _first_value(value, "id", "value", "name")
    return value


def _matches_region(value: str, requested: Region) -> bool:
    normalized = value.lower().replace("-", "_").replace(" ", "_")
    if requested is Region.OPTIC_LOBES:
        return any(token in normalized for token in ("optic", "visual", "lobula", "medulla", "lamina"))
    if requested is Region.DESCENDING:
        return "descend" in normalized or normalized in {"motor", "motors"}
    if requested is Region.MOTOR:
        return "motor" in normalized or "descend" in normalized
    if requested is Region.MUSHROOM_BODY:
        return any(token in normalized for token in ("mushroom", "kenyon", "memory", "mb"))
    return True
