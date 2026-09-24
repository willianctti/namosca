"""Application configuration loaded from environment variables.

Using a small dataclass instead of a settings library keeps the runtime
lightweight and makes the deployment contract obvious.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:  # Optional at import time; uvicorn[standard] installs it in normal setups.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - environment without python-dotenv
    pass


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    """Read a positive integer environment variable safely."""

    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _env_float(name: str, default: float, *, minimum: float = 0.0) -> float:
    """Read a non-negative float environment variable safely."""

    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _env_list(name: str, default: str) -> list[str]:
    """Parse a comma-separated environment variable."""

    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings for the API and remote providers."""

    axobug_base_url: str = "https://axobug.com"
    axobug_api_token: str | None = None
    axobug_timeout_seconds: float = 20.0
    flywire_graph_url: str | None = None
    flywire_api_token: str | None = None
    flywire_timeout_seconds: float = 20.0
    flywire_data_file: str | None = None
    max_graph_neurons: int = 1200
    max_graph_synapses: int = 6000
    max_remote_bytes: int = 12_000_000
    cache_size: int = 4
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    )

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from process environment variables."""

        flywire_url = os.getenv("FLYWIRE_GRAPH_URL", "").strip() or None
        flywire_file = os.getenv("FLYWIRE_DATA_FILE", "").strip() or None
        origins = tuple(
            _env_list(
                "CORS_ORIGINS",
                "http://localhost:5173,http://localhost:8000,http://127.0.0.1:5173,http://127.0.0.1:8000,http://localhost:8080,http://127.0.0.1:8080",
            )
        )
        return cls(
            axobug_base_url=os.getenv("AXOBUG_BASE_URL", "https://axobug.com").rstrip("/"),
            axobug_api_token=os.getenv("AXOBUG_API_TOKEN", "").strip() or None,
            axobug_timeout_seconds=_env_float("AXOBUG_TIMEOUT_SECONDS", 20.0, minimum=0.1),
            flywire_graph_url=flywire_url,
            flywire_api_token=os.getenv("FLYWIRE_API_TOKEN", "").strip() or None,
            flywire_timeout_seconds=_env_float("FLYWIRE_TIMEOUT_SECONDS", 20.0, minimum=0.1),
            flywire_data_file=flywire_file,
            max_graph_neurons=_env_int("MAX_GRAPH_NEURONS", 1200),
            max_graph_synapses=_env_int("MAX_GRAPH_SYNAPSES", 6000),
            max_remote_bytes=_env_int("MAX_REMOTE_BYTES", 12_000_000),
            cache_size=_env_int("CACHE_SIZE", 4),
            cors_origins=origins,
        )
