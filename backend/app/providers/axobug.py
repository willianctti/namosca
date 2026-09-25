"""Cliente da API pública Axobug Neuro.

A versão alpha pública do Axobug oferece respostas de simulação
(``/api/v1/run``), mas não uma exportação bruta de neurônios e conexões.
Por isso, este cliente é um motor de simulação opcional; o grafo normalizado
local continua sendo a fonte, a menos que outra rota JSON compatível com
FlyWire seja configurado.

Referência: https://docs.axobug.com/api-reference
"""

from __future__ import annotations

from typing import Any

import httpx

from app.providers.base import ProviderError


class AxobugError(ProviderError):
    """Erro levantado quando a API remota do Axobug está indisponível ou inválida."""


class AxobugClient:
    """Adaptador HTTP pequeno e cancelável para as rotas documentadas do Axobug."""

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
        """Devolve os metadados do modelo usados para informar as capacidades."""

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
        """Executa um experimento isolado no Axobug.

        O Axobug aceita atualmente durações de 50, 100, 150 ou 200 ms. Quem chama
        este método deve normalizar o valor antes.
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
        """Extrai uma mensagem curta de erro sem devolver um corpo enorme."""

        try:
            payload = response.json()
        except ValueError:
            return response.text[:200]
        if isinstance(payload, dict):
            detail = payload.get("error") or payload.get("detail") or payload.get("message")
            if detail:
                return str(detail)[:200]
        return response.text[:200]
