"""Client for the public Axobug Neuro API.

The public Axobug alpha exposes simulation responses (``/api/v1/run``), not a
raw neuron/connectome export. Consequently this client is used as an optional
simulation engine; the local normalized graph remains the graph source unless
a separate FlyWire-compatible JSON endpoint is configured.

Reference: https://docs.axobug.com/api-reference
"""

from __future__ import annotations

from typing import Any

import httpx

from app.providers.base import ProviderError


class AxobugError(ProviderError):
    """Raised when the remote Axobug API is unavailable or invalid."""


class AxobugClient:
    """Small, cancellable HTTP adapter for Axobug's documented endpoints."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        base_url: str,
        timeout_seconds: float,
        api_token: str | None = None,
    ) -> None:
        self._client = client
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.api_token = api_token

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    async def model_info(self) -> dict[str, Any]:
        """Return model metadata used for capability reporting."""

        url = f"{self.base_url}/api/v1/model"
        try:
            response = await self._client.get(
                url,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise AxobugError(f"could not reach Axobug: {exc}") from exc
        if response.status_code >= 400:
            raise AxobugError(f"Axobug returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise AxobugError("Axobug returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise AxobugError("Axobug model response must be an object")
        return payload

    async def run(
        self,
        *,
        stimulus: str,
        intensity: float,
        duration_ms: int,
        seed: int,
        view: str = "full",
    ) -> dict[str, Any]:
        """Run one isolated Axobug experiment.

        Axobug currently accepts durations 50, 100, 150, or 200 ms. The caller
        is responsible for normalizing the value before calling this method.
        """

        url = f"{self.base_url}/api/v1/run"
        body = {
            "stimulus": stimulus,
            "intensity": intensity,
            "duration_ms": duration_ms,
            "seed": seed,
        }
        try:
            response = await self._client.post(
                url,
                params={"view": view},
                json=body,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise AxobugError(f"could not reach Axobug: {exc}") from exc
        if response.status_code >= 400:
            detail = self._error_detail(response)
            raise AxobugError(f"Axobug returned HTTP {response.status_code}: {detail}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise AxobugError("Axobug returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise AxobugError("Axobug run response must be an object")
        if not isinstance(payload.get("frames", []), list):
            raise AxobugError("Axobug response has no valid frames array")
        return payload

    @staticmethod
    def _error_detail(response: httpx.Response) -> str:
        """Extract a short error message without returning a huge body."""

        try:
            payload = response.json()
        except ValueError:
            return response.text[:200]
        if isinstance(payload, dict):
            detail = payload.get("error") or payload.get("detail") or payload.get("message")
            if detail:
                return str(detail)[:200]
        return response.text[:200]
