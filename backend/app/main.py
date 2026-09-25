"""FastAPI application exposing graph, simulation and realtime endpoints."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import Settings
from app.legacy import LegacyRuntime
from app.providers.axobug import AxobugClient, AxobugError
from app.providers.flywire import FlyWireProvider
from app.realtime import RealtimeSession
from app.schemas import (
    AxobugRunRequest,
    GraphQuery,
    HealthResponse,
    Network,
    Region,
    SimulationConfig,
    SimulationRequest,
    Stimulus,
    normalize_region,
)
from app.services.network import NetworkService, NetworkUnavailable
from app.services.simulation import SimulationService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create one shared HTTP client and bounded service graph per process."""

    settings = Settings.from_env()
    headers = {
        "User-Agent": f"drosophila-neuro-sim/{__version__}",
        "Accept": "application/json",
    }
    http_client = httpx.AsyncClient(headers=headers, follow_redirects=True)
    axobug = AxobugClient(
        http_client,
        base_url=settings.axobug_base_url,
        api_token=settings.axobug_api_token,
        timeout_seconds=settings.axobug_timeout_seconds,
    )
    flywire = FlyWireProvider(
        http_client,
        graph_url=settings.flywire_graph_url,
        api_token=settings.flywire_api_token,
        data_file=settings.flywire_data_file,
        timeout_seconds=settings.flywire_timeout_seconds,
        max_remote_bytes=settings.max_remote_bytes,
    )
    app.state.settings = settings
    app.state.http_client = http_client
    app.state.axobug = axobug
    app.state.flywire = flywire
    app.state.networks = NetworkService(
        flywire=flywire,
        cache_size=settings.cache_size,
        max_graph_neurons=settings.max_graph_neurons,
        max_graph_synapses=settings.max_graph_synapses,
    )
    app.state.simulations = SimulationService(axobug)
    # One optional compatibility runtime for the original single-file demo
    # endpoints. The primary WebSocket still creates isolated sessions.
    app.state.legacy_runtime = None
    app.state.legacy_region = None
    app.state.legacy_source = None
    app.state.realtime_sessions = set()
    try:
        yield
    finally:
        await http_client.aclose()


def create_app() -> FastAPI:
    """Application factory, useful for tests and alternative ASGI servers."""

    app = FastAPI(
        title="Drosophila Neuro Simulator",
        version=__version__,
        description=(
            "Bounded 3D neural subnetwork API with optional real FlyWire graph data, "
            "LIF simulation and WebSocket spike streaming."
        ),
        lifespan=lifespan,
    )
    # Settings are needed while constructing middleware. Environment parsing is
    # cheap and keeps the factory independent from the lifespan state.
    settings = Settings.from_env()
    allow_credentials = "*" not in settings.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/", tags=["system"])
    async def root() -> dict[str, str]:
        return {
            "name": "Drosophila Neuro Simulator",
            "docs": "/docs",
            "health": "/api/health",
            "network": "/api/network?region=optic_lobes",
            "websocket": "/ws/simulation?region=optic_lobes",
        }

    @app.get("/api/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="drosophila-neuro-sim",
            version=__version__,
            default_region=Region.OPTIC_LOBES.value,
            mock_fallback=False,
        )

    @app.get("/api/cache", tags=["system"])
    async def cache_info(request: Request) -> dict[str, Any]:
        service: NetworkService = request.app.state.networks
        return service.cache_info()

    # Backward-compatible aliases for the prototype API. They intentionally
    # delegate to the same bounded provider service instead of duplicating
    # network-fetching logic.
    @app.get("/health", tags=["compatibility"])
    async def legacy_health() -> dict[str, str]:
        return {"status": "ok", "service": "drosophila-neuro-sim", "version": __version__}

    @app.get("/neurons", tags=["compatibility"])
    async def legacy_neurons(
        request: Request,
        region: str = Query("optic_lobe"),
        source: str = Query("auto"),
    ) -> dict[str, Any]:
        runtime = await _get_legacy_runtime(request, region, source)
        neurons = runtime.neuron_payload()
        return {"neurons": neurons, "count": len(neurons)}

    @app.get("/synapses", tags=["compatibility"])
    async def legacy_synapses(
        request: Request,
        region: str = Query("optic_lobe"),
        source: str = Query("auto"),
    ) -> dict[str, Any]:
        query = _graph_query(region, source, 240, 1200, False)
        network = await _network_for_request(request, query)
        synapses = [
            {
                "pre_id": synapse.source,
                "post_id": synapse.target,
                "source": synapse.source,
                "target": synapse.target,
                "weight": round(synapse.weight, 4),
                "delay_ms": synapse.delay_ms,
                "inhibitory": synapse.inhibitory,
            }
            for synapse in network.synapses
        ]
        return {"synapses": synapses, "count": len(synapses)}

    @app.post("/inject-stimulus", tags=["compatibility"])
    async def legacy_inject(
        request: Request,
        neuron_id: str | None = Query(None),
        current: float = Query(10.0, ge=0.0, le=50.0),
        region: str = Query("optic_lobe"),
        source: str = Query("auto"),
    ) -> dict[str, Any]:
        # Also accept {"neuron_id": ..., "current": ...} for JSON clients.
        if neuron_id is None:
            try:
                body = await request.json()
            except Exception:
                body = {}
            if isinstance(body, dict):
                neuron_id = str(body.get("neuron_id") or body.get("id") or "") or None
                if "current" in body:
                    try:
                        current = float(body["current"])
                    except (TypeError, ValueError) as exc:
                        raise HTTPException(status_code=422, detail="current must be numeric") from exc
                    if not 0.0 <= current <= 50.0:
                        raise HTTPException(status_code=422, detail="current must be between 0 and 50")
        if not neuron_id:
            raise HTTPException(status_code=422, detail="neuron_id is required")
        runtime = await _get_legacy_runtime(request, region, source)
        if not runtime.inject(neuron_id, current):
            raise HTTPException(status_code=404, detail=f"neuron '{neuron_id}' not found")
        # Preserve the behavior documented by the original prototype: an HTTP
        # injection also reaches already-connected visualization sessions.
        pulse = Stimulus(neuron_ids=[neuron_id], intensity=current, duration_ms=100.0)
        for session in tuple(request.app.state.realtime_sessions):
            if session.network.region == runtime.network.region:
                session.inject(pulse)
        return {"message": f"Stimulus injected into {neuron_id}", "current": current}

    @app.get("/api/regions", tags=["network"])
    async def regions() -> list[dict[str, str]]:
        return [
            {
                "id": Region.OPTIC_LOBES.value,
                "label": "Lobos ópticos / visão",
                "default_input_role": "visual_input",
            },
            {
                "id": Region.DESCENDING.value,
                "label": "Neurônios descendentes",
                "default_input_role": "sensory",
            },
            {
                "id": Region.MOTOR.value,
                "label": "Neurônios motores",
                "default_input_role": "interneuron",
            },
            {
                "id": Region.MUSHROOM_BODY.value,
                "label": "Corpos cogumelo / memória",
                "default_input_role": "sensory",
            },
            {
                "id": Region.ALL.value,
                "label": "Sub-rede completa",
                "default_input_role": "visual_input",
            },
        ]

    @app.get("/api/providers", tags=["system"])
    async def providers(request: Request) -> dict[str, Any]:
        settings: Settings = request.app.state.settings
        flywire: FlyWireProvider = request.app.state.flywire
        return {
            "mock": {
                "available": False,
                "role": "desativado nesta fase",
                "reason": "O projeto usa somente dados reais; configure FlyWire para o grafo.",
            },
            "flywire": {
                "available": flywire.configured,
                "role": "fonte real de neurônios e conexões",
                "coordinates": "normalized provider coordinates",
                "configured_url": bool(settings.flywire_graph_url),
                "configured_file": bool(settings.flywire_data_file),
            },
            "axobug": {
                "available": True,
                "role": "fonte real de simulação e comportamento",
                "graph_endpoint": False,
                "note": "Axobug retorna simulação/comportamento; o grafo local é servido pelo FlyWire.",
            },
        }

    @app.get("/api/network", response_model=Network, tags=["network"])
    async def get_network(
        request: Request,
        region: str = Query(Region.OPTIC_LOBES.value),
        source: str = Query("auto"),
        max_neurons: int = Query(240, ge=1, le=5000),
        max_synapses: int = Query(1200, ge=1, le=50_000),
        strict: bool = Query(False),
    ) -> Network:
        query = _graph_query(region, source, max_neurons, max_synapses, strict)
        return await _network_for_request(request, query)

    @app.post("/api/network", response_model=Network, tags=["network"])
    async def post_network(request: Request, query: GraphQuery) -> Network:
        return await _network_for_request(request, query)

    @app.get("/api/axobug/model", tags=["axobug"])
    async def axobug_model(request: Request) -> dict[str, Any]:
        client: AxobugClient = request.app.state.axobug
        try:
            return {"available": True, "model": await client.model_info()}
        except AxobugError as exc:
            # Capability probing should be non-fatal for local development.
            return {"available": False, "error": str(exc), "fallback": None}

    @app.post("/api/axobug/run", tags=["axobug"])
    async def axobug_run(
        request: Request,
        payload: AxobugRunRequest,
        view: Literal["full", "drive"] | None = Query(None),
    ) -> dict[str, Any]:
        client: AxobugClient = request.app.state.axobug
        selected_view = view or payload.view
        try:
            return await client.run(
                stimulus=payload.stimulus,
                intensity=payload.intensity,
                duration_ms=payload.duration_ms,
                seed=payload.seed,
                view=selected_view,
            )
        except AxobugError as exc:
            raise HTTPException(status_code=503, detail={"error": str(exc), "fallback": "Use /api/simulate with engine=lif"}) from exc

    @app.post("/api/simulate", tags=["simulation"])
    async def simulate(request: Request, payload: SimulationRequest) -> dict[str, Any]:
        network = await _network_for_request(request, payload.graph)
        service: SimulationService = request.app.state.simulations
        return (await service.run(network, payload)).model_dump(mode="json")

    @app.websocket("/ws/simulation")
    @app.websocket("/ws/simulate")
    async def simulation_socket(
        websocket: WebSocket,
        region: str = Query(Region.OPTIC_LOBES.value),
        source: str = Query("auto"),
        max_neurons: int = Query(240, ge=1, le=5000),
        max_synapses: int = Query(1200, ge=1, le=50_000),
        include_voltage: bool = Query(False),
        dt_ms: float = Query(5.0, ge=1.0, le=100.0),
        frame_interval_ms: float = Query(16.0, gt=0.0, le=1000.0),
    ) -> None:
        await websocket.accept()
        try:
            query = _graph_query(region, source, max_neurons, max_synapses, False)
            config = SimulationConfig(
                dt_ms=dt_ms,
                frame_interval_ms=frame_interval_ms,
            )
            network = await _network_for_request(websocket, query)
            session = RealtimeSession(
                websocket,
                network,
                config=config,
                include_voltage=include_voltage,
                legacy_payload=websocket.url.path.endswith("/simulate"),
            )
            sessions = websocket.app.state.realtime_sessions
            sessions.add(session)
            try:
                await session.run()
            finally:
                sessions.discard(session)
        except WebSocketDisconnect:
            return
        except (ValueError, NetworkUnavailable, HTTPException) as exc:
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            await websocket.send_json({"type": "error", "message": str(detail)})
            await websocket.close(code=1011)

    return app


async def _network_for_request(request: Request | WebSocket, query: GraphQuery) -> Network:
    service: NetworkService = request.app.state.networks
    try:
        return await service.get_network(query)
    except NetworkUnavailable as exc:
        raise HTTPException(status_code=503, detail={"error": str(exc)}) from exc


async def _get_legacy_runtime(request: Request, region: str, source: str) -> LegacyRuntime:
    """Return the one compatibility runtime, rebuilding it when region changes."""

    try:
        normalized = normalize_region(region)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    runtime: LegacyRuntime | None = request.app.state.legacy_runtime
    if (
        runtime is not None
        and request.app.state.legacy_region == normalized.value
        and request.app.state.legacy_source == source
    ):
        return runtime
    network = await _network_for_request(
        request,
        _graph_query(normalized.value, source, 240, 1200, False),
    )
    runtime = LegacyRuntime(network)
    request.app.state.legacy_runtime = runtime
    request.app.state.legacy_region = normalized.value
    request.app.state.legacy_source = source
    return runtime


def _graph_query(region: str, source: str, max_neurons: int, max_synapses: int, strict: bool) -> GraphQuery:
    """Convert query-string values into a validated schema object."""

    try:
        return GraphQuery(
            region=normalize_region(region),
            source=source,
            max_neurons=max_neurons,
            max_synapses=max_synapses,
            strict=strict,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


app = create_app()
