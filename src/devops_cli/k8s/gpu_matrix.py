"""Traditional Homelab GPU Configuration Matrix and Service Alias Mapping.

Maps GPU counts (1, 2, 3, 4) and per-GPU VRAM sizes (16GiB, 24GiB, 32GiB) across
inference backend (Ollama) to optimal model assignments and Kubernetes service aliases.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

GpuCount = Literal[1, 2, 3, 4]
VramSizeGib = Literal[16, 24, 32]
BackendType = Literal["ollama"]

VALID_GPU_COUNTS: Final[tuple[int, ...]] = (1, 2, 3, 4)
VALID_VRAM_SIZES: Final[tuple[int, ...]] = (16, 24, 32)
VALID_BACKENDS: Final[tuple[str, ...]] = ("ollama",)

_MATRIX_JSON_PATH: Final[Path] = Path(__file__).resolve().parent / "gpu_matrix.json"


class GpuProfile(BaseModel):
    """Specification of an inference workload optimized for specific GPU hardware."""

    model_config = ConfigDict(frozen=True)

    gpu_count: GpuCount
    vram_per_gpu_gib: VramSizeGib
    total_vram_gib: int
    backend: BackendType
    model_id: str
    model_alias: str
    service_alias: str
    service_port: int
    max_model_len: int
    tensor_parallel_size: int
    quantization: str
    virtual_gateway_model: str
    description: str = Field(default="")


@functools.cache
def _load_matrix_data() -> dict[str, Any]:
    """Load hardware profiles, service aliases, and gateway routes from JSON asset."""
    return cast(dict[str, Any], json.loads(_MATRIX_JSON_PATH.read_text(encoding="utf-8")))


def _build_profile_lookup() -> dict[tuple[int, int, str], GpuProfile]:
    """Construct keyed lookup map for all hardware matrix entries."""
    data = _load_matrix_data()
    return {
        (p["gpu_count"], p["vram_per_gpu_gib"], p["backend"]): GpuProfile(**p)
        for p in data["profiles"]
    }


_GPU_PROFILE_MAP: Final[dict[tuple[int, int, str], GpuProfile]] = _build_profile_lookup()

# Module-level aliases loaded from JSON asset
PROVIDER_SERVICE_ALIASES: Final[dict[str, dict[str, Any]]] = _load_matrix_data()[
    "provider_service_aliases"
]
MODEL_SERVICE_ALIASES: Final[dict[str, dict[str, Any]]] = PROVIDER_SERVICE_ALIASES
SPEED_TIER_SERVICE_ALIASES: Final[dict[str, dict[str, Any]]] = _load_matrix_data()[
    "speed_tier_service_aliases"
]


def get_gpu_profile(gpu_count: int, vram_per_gpu_gib: int, backend: str = "ollama") -> GpuProfile:
    """Retrieve optimal model and deployment profile for given GPU hardware specification."""
    normalized_backend = backend.lower().strip()
    key = (gpu_count, vram_per_gpu_gib, normalized_backend)
    if key not in _GPU_PROFILE_MAP:
        valid_combos = [f"{g}x{v}GiB ({b})" for g, v, b in _GPU_PROFILE_MAP]
        raise ValueError(
            f"Unsupported GPU configuration: {gpu_count}x{vram_per_gpu_gib}GiB on '{backend}'. "
            f"Allowed combinations: {', '.join(valid_combos[:6])}..."
        )
    return _GPU_PROFILE_MAP[key]


def list_gpu_profiles(
    gpu_count: int | None = None,
    vram_per_gpu_gib: int | None = None,
    backend: str | None = None,
) -> list[GpuProfile]:
    """Filter and return hardware profiles matching given constraints."""
    profiles = list(_GPU_PROFILE_MAP.values())
    if gpu_count is not None:
        profiles = [p for p in profiles if p.gpu_count == gpu_count]
    if vram_per_gpu_gib is not None:
        profiles = [p for p in profiles if p.vram_per_gpu_gib == vram_per_gpu_gib]
    if backend is not None:
        norm_b = backend.lower().strip()
        profiles = [p for p in profiles if p.backend == norm_b]
    return sorted(profiles, key=lambda p: (p.gpu_count, p.vram_per_gpu_gib, p.backend))


def get_service_aliases() -> dict[str, dict[str, Any]]:
    """Return all standardized Kubernetes provider-vram service aliases (<llm_provider>-<vram_gib>)."""
    return dict(PROVIDER_SERVICE_ALIASES)


def get_speed_tier_service_aliases() -> dict[str, dict[str, Any]]:
    """Return all standardized Kubernetes speed tier service aliases (<llm_provider>-<vram_gib>-<speed_tier>)."""
    return dict(SPEED_TIER_SERVICE_ALIASES)


def get_gateway_routing_entries() -> list[dict[str, Any]]:
    """Generate LiteLLM gateway routing model_list entries targeting service aliases."""
    return list(_load_matrix_data()["gateway_routes"])


__all__ = [
    "MODEL_SERVICE_ALIASES",
    "PROVIDER_SERVICE_ALIASES",
    "SPEED_TIER_SERVICE_ALIASES",
    "VALID_BACKENDS",
    "VALID_GPU_COUNTS",
    "VALID_VRAM_SIZES",
    "BackendType",
    "GpuCount",
    "GpuProfile",
    "VramSizeGib",
    "get_gateway_routing_entries",
    "get_gpu_profile",
    "get_service_aliases",
    "get_speed_tier_service_aliases",
    "list_gpu_profiles",
]
