"""Traditional Homelab GPU Configuration Matrix and Service Alias Mapping.

Maps GPU counts (1, 2, 3, 4) and per-GPU VRAM sizes (16GiB, 24GiB, 32GiB) across
inference backends (Ollama, vLLM) to optimal model assignments and Kubernetes service aliases.
"""

from __future__ import annotations

from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

GpuCount = Literal[1, 2, 3, 4]
VramSizeGib = Literal[16, 24, 32]
BackendType = Literal["ollama", "vllm"]

VALID_GPU_COUNTS: Final[tuple[int, ...]] = (1, 2, 3, 4)
VALID_VRAM_SIZES: Final[tuple[int, ...]] = (16, 24, 32)
VALID_BACKENDS: Final[tuple[str, ...]] = ("ollama", "vllm")


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


# ── Model Service Aliases ─────────────────────────────────────────────────────
# Standardized Kubernetes Service DNS names representing model classes.
MODEL_SERVICE_ALIASES: Final[dict[str, dict[str, Any]]] = {
    "qwen2.5-coder-7b": {
        "service_name": "model-qwen2-5-coder-7b",
        "model_id": "qwen2.5-coder:7b",
        "virtual_model": "devops-chat",
        "ports": {"ollama": 11434, "vllm": 8000},
        "description": "Code and chat generation (7B class)",
    },
    "qwen2.5-coder-14b": {
        "service_name": "model-qwen2-5-coder-14b",
        "model_id": "qwen2.5-coder-14b-instruct",
        "virtual_model": "devops-coder",
        "ports": {"ollama": 11434, "vllm": 8000},
        "description": "High-throughput coding and reasoning (14B class)",
    },
    "qwen3-coder-30b": {
        "service_name": "model-qwen3-coder-30b",
        "model_id": "qwen3-coder:30b",
        "virtual_model": "devops-reasoning",
        "ports": {"ollama": 11434, "vllm": 8000},
        "description": "Complex reasoning and multi-file code review (30B class)",
    },
    "cogito-v2-70b": {
        "service_name": "model-cogito-v2-70b",
        "model_id": "cogito-v2:70b",
        "virtual_model": "devops-flagship",
        "ports": {"ollama": 11434, "vllm": 8000},
        "description": "Flagship deep reasoning and architectural synthesis (70B class)",
    },
    "bge-m3": {
        "service_name": "model-bge-m3",
        "model_id": "bge-m3:latest",
        "virtual_model": "devops-embedding",
        "ports": {"ollama": 11434},
        "description": "Dense semantic embedding generation",
    },
}

# ── 24 Hardware Configurations Matrix ─────────────────────────────────────────
# Structured mapping table covering counts [1,2,3,4] x VRAM [16,24,32] x backends [ollama, vllm].
_MATRIX_ENTRIES: Final[tuple[dict[str, Any], ...]] = (
    # ── 1 GPU Profiles ────────────────────────────────────────────────────────
    {
        "gpu_count": 1,
        "vram_per_gpu_gib": 16,
        "backend": "ollama",
        "model_id": "qwen2.5-coder:7b",
        "model_alias": "qwen2.5-coder-7b",
        "service_alias": "model-qwen2-5-coder-7b",
        "service_port": 11434,
        "max_model_len": 32768,
        "tensor_parallel_size": 1,
        "quantization": "Q4_K_M",
        "virtual_gateway_model": "devops-chat",
        "description": "Single 16GB GPU (RTX 4080 / T4) serving 7B code chat with generous context headroom.",
    },
    {
        "gpu_count": 1,
        "vram_per_gpu_gib": 16,
        "backend": "vllm",
        "model_id": "qwen2.5-coder-14b-instruct",
        "model_alias": "qwen2.5-coder-14b",
        "service_alias": "model-qwen2-5-coder-14b",
        "service_port": 8000,
        "max_model_len": 16384,
        "tensor_parallel_size": 1,
        "quantization": "AWQ",
        "virtual_gateway_model": "devops-coder",
        "description": "Single 16GB GPU running 14B AWQ with FP8 KV cache for low-latency coding completions.",
    },
    {
        "gpu_count": 1,
        "vram_per_gpu_gib": 24,
        "backend": "ollama",
        "model_id": "qwen2.5-coder:14b",
        "model_alias": "qwen2.5-coder-14b",
        "service_alias": "model-qwen2-5-coder-14b",
        "service_port": 11434,
        "max_model_len": 32768,
        "tensor_parallel_size": 1,
        "quantization": "Q8_0",
        "virtual_gateway_model": "devops-coder",
        "description": "Single 24GB GPU (RTX 3090/4090) serving high-precision Q8 14B model with 32K context.",
    },
    {
        "gpu_count": 1,
        "vram_per_gpu_gib": 24,
        "backend": "vllm",
        "model_id": "qwen2.5-coder-14b-instruct",
        "model_alias": "qwen2.5-coder-14b",
        "service_alias": "model-qwen2-5-coder-14b",
        "service_port": 8000,
        "max_model_len": 32768,
        "tensor_parallel_size": 1,
        "quantization": "AWQ",
        "virtual_gateway_model": "devops-coder",
        "description": "Single 24GB GPU serving 14B AWQ continuous batching with large 32K KV cache.",
    },
    {
        "gpu_count": 1,
        "vram_per_gpu_gib": 32,
        "backend": "ollama",
        "model_id": "qwen3-coder:30b",
        "model_alias": "qwen3-coder-30b",
        "service_alias": "model-qwen3-coder-30b",
        "service_port": 11434,
        "max_model_len": 48000,
        "tensor_parallel_size": 1,
        "quantization": "Q4_K_M",
        "virtual_gateway_model": "devops-reasoning",
        "description": "Single 32GB GPU (Tesla V100 32GB) serving 30B MoE with 48K context window.",
    },
    {
        "gpu_count": 1,
        "vram_per_gpu_gib": 32,
        "backend": "vllm",
        "model_id": "qwen3-coder:30b",
        "model_alias": "qwen3-coder-30b",
        "service_alias": "model-qwen3-coder-30b",
        "service_port": 8000,
        "max_model_len": 32768,
        "tensor_parallel_size": 1,
        "quantization": "AWQ",
        "virtual_gateway_model": "devops-reasoning",
        "description": "Single 32GB GPU running 30B AWQ with 32K context for multi-persona review.",
    },
    # ── 2 GPU Profiles ────────────────────────────────────────────────────────
    {
        "gpu_count": 2,
        "vram_per_gpu_gib": 16,
        "backend": "ollama",
        "model_id": "qwen3-coder:30b",
        "model_alias": "qwen3-coder-30b",
        "service_alias": "model-qwen3-coder-30b",
        "service_port": 11434,
        "max_model_len": 32768,
        "tensor_parallel_size": 2,
        "quantization": "Q4_K_M",
        "virtual_gateway_model": "devops-reasoning",
        "description": "Dual 16GB GPUs (32GB total) split-loading 30B MoE across both cards.",
    },
    {
        "gpu_count": 2,
        "vram_per_gpu_gib": 16,
        "backend": "vllm",
        "model_id": "qwen3-coder:30b",
        "model_alias": "qwen3-coder-30b",
        "service_alias": "model-qwen3-coder-30b",
        "service_port": 8000,
        "max_model_len": 32768,
        "tensor_parallel_size": 2,
        "quantization": "AWQ",
        "virtual_gateway_model": "devops-reasoning",
        "description": "Dual 16GB GPUs with TP=2 continuous batching serving 30B AWQ.",
    },
    {
        "gpu_count": 2,
        "vram_per_gpu_gib": 24,
        "backend": "ollama",
        "model_id": "cogito-v2:70b",
        "model_alias": "cogito-v2-70b",
        "service_alias": "model-cogito-v2-70b",
        "service_port": 11434,
        "max_model_len": 32768,
        "tensor_parallel_size": 2,
        "quantization": "Q4_K_M",
        "virtual_gateway_model": "devops-flagship",
        "description": "Dual 24GB GPUs (48GB total, 2x RTX 3090/4090) serving 70B flagship model.",
    },
    {
        "gpu_count": 2,
        "vram_per_gpu_gib": 24,
        "backend": "vllm",
        "model_id": "qwen3-coder:30b",
        "model_alias": "qwen3-coder-30b",
        "service_alias": "model-qwen3-coder-30b",
        "service_port": 8000,
        "max_model_len": 65536,
        "tensor_parallel_size": 2,
        "quantization": "AWQ",
        "virtual_gateway_model": "devops-reasoning",
        "description": "Dual 24GB GPUs with TP=2 serving 30B AWQ with maximal 64K context and 64 max-seqs.",
    },
    {
        "gpu_count": 2,
        "vram_per_gpu_gib": 32,
        "backend": "ollama",
        "model_id": "cogito-v2:70b",
        "model_alias": "cogito-v2-70b",
        "service_alias": "model-cogito-v2-70b",
        "service_port": 11434,
        "max_model_len": 65536,
        "tensor_parallel_size": 2,
        "quantization": "Q4_K_M",
        "virtual_gateway_model": "devops-flagship",
        "description": "Dual 32GB GPUs (64GB total) serving 70B flagship with expanded 64K context.",
    },
    {
        "gpu_count": 2,
        "vram_per_gpu_gib": 32,
        "backend": "vllm",
        "model_id": "cogito-v2:70b",
        "model_alias": "cogito-v2-70b",
        "service_alias": "model-cogito-v2-70b",
        "service_port": 8000,
        "max_model_len": 32768,
        "tensor_parallel_size": 2,
        "quantization": "AWQ",
        "virtual_gateway_model": "devops-flagship",
        "description": "Dual 32GB GPUs with TP=2 continuous batching serving 70B AWQ flagship.",
    },
    # ── 3 GPU Profiles ────────────────────────────────────────────────────────
    {
        "gpu_count": 3,
        "vram_per_gpu_gib": 16,
        "backend": "ollama",
        "model_id": "cogito-v2:70b",
        "model_alias": "cogito-v2-70b",
        "service_alias": "model-cogito-v2-70b",
        "service_port": 11434,
        "max_model_len": 32768,
        "tensor_parallel_size": 3,
        "quantization": "Q4_K_M",
        "virtual_gateway_model": "devops-flagship",
        "description": "Triple 16GB GPUs (48GB total) offloading 70B model layers evenly across 3 devices.",
    },
    {
        "gpu_count": 3,
        "vram_per_gpu_gib": 16,
        "backend": "vllm",
        "model_id": "qwen3-coder:30b",
        "model_alias": "qwen3-coder-30b",
        "service_alias": "model-qwen3-coder-30b",
        "service_port": 8000,
        "max_model_len": 32768,
        "tensor_parallel_size": 2,
        "quantization": "AWQ",
        "virtual_gateway_model": "devops-reasoning",
        "description": "Triple 16GB GPUs deploying TP=2 continuous batching with dedicated overflow worker.",
    },
    {
        "gpu_count": 3,
        "vram_per_gpu_gib": 24,
        "backend": "ollama",
        "model_id": "cogito-v2:70b",
        "model_alias": "cogito-v2-70b",
        "service_alias": "model-cogito-v2-70b",
        "service_port": 11434,
        "max_model_len": 65536,
        "tensor_parallel_size": 3,
        "quantization": "Q4_K_M",
        "virtual_gateway_model": "devops-flagship",
        "description": "Triple 24GB GPUs (72GB total) serving 70B flagship with deep 64K context.",
    },
    {
        "gpu_count": 3,
        "vram_per_gpu_gib": 24,
        "backend": "vllm",
        "model_id": "cogito-v2:70b",
        "model_alias": "cogito-v2-70b",
        "service_alias": "model-cogito-v2-70b",
        "service_port": 8000,
        "max_model_len": 32768,
        "tensor_parallel_size": 2,
        "quantization": "AWQ",
        "virtual_gateway_model": "devops-flagship",
        "description": "Triple 24GB GPUs with hybrid pipeline-tensor parallelism serving 70B flagship.",
    },
    {
        "gpu_count": 3,
        "vram_per_gpu_gib": 32,
        "backend": "ollama",
        "model_id": "cogito-v2:70b",
        "model_alias": "cogito-v2-70b",
        "service_alias": "model-cogito-v2-70b",
        "service_port": 11434,
        "max_model_len": 131072,
        "tensor_parallel_size": 3,
        "quantization": "Q8_0",
        "virtual_gateway_model": "devops-flagship",
        "description": "Triple 32GB GPUs (96GB total) serving high-fidelity Q8 70B with full 128K context.",
    },
    {
        "gpu_count": 3,
        "vram_per_gpu_gib": 32,
        "backend": "vllm",
        "model_id": "cogito-v2:70b",
        "model_alias": "cogito-v2-70b",
        "service_alias": "model-cogito-v2-70b",
        "service_port": 8000,
        "max_model_len": 65536,
        "tensor_parallel_size": 2,
        "quantization": "AWQ",
        "virtual_gateway_model": "devops-flagship",
        "description": "Triple 32GB GPUs serving 70B flagship with 64K context and high concurrency.",
    },
    # ── 4 GPU Profiles ────────────────────────────────────────────────────────
    {
        "gpu_count": 4,
        "vram_per_gpu_gib": 16,
        "backend": "ollama",
        "model_id": "cogito-v2:70b",
        "model_alias": "cogito-v2-70b",
        "service_alias": "model-cogito-v2-70b",
        "service_port": 11434,
        "max_model_len": 65536,
        "tensor_parallel_size": 4,
        "quantization": "Q4_K_M",
        "virtual_gateway_model": "devops-flagship",
        "description": "Quad 16GB GPUs (64GB total) balanced across 4 cards serving 70B flagship.",
    },
    {
        "gpu_count": 4,
        "vram_per_gpu_gib": 16,
        "backend": "vllm",
        "model_id": "cogito-v2:70b",
        "model_alias": "cogito-v2-70b",
        "service_alias": "model-cogito-v2-70b",
        "service_port": 8000,
        "max_model_len": 32768,
        "tensor_parallel_size": 4,
        "quantization": "AWQ",
        "virtual_gateway_model": "devops-flagship",
        "description": "Quad 16GB GPUs with TP=4 continuous batching serving 70B AWQ.",
    },
    {
        "gpu_count": 4,
        "vram_per_gpu_gib": 24,
        "backend": "ollama",
        "model_id": "cogito-v2:70b",
        "model_alias": "cogito-v2-70b",
        "service_alias": "model-cogito-v2-70b",
        "service_port": 11434,
        "max_model_len": 131072,
        "tensor_parallel_size": 4,
        "quantization": "Q8_0",
        "virtual_gateway_model": "devops-flagship",
        "description": "Quad 24GB GPUs (96GB total) serving uncompromised Q8 70B with full 128K context.",
    },
    {
        "gpu_count": 4,
        "vram_per_gpu_gib": 24,
        "backend": "vllm",
        "model_id": "cogito-v2:70b",
        "model_alias": "cogito-v2-70b",
        "service_alias": "model-cogito-v2-70b",
        "service_port": 8000,
        "max_model_len": 65536,
        "tensor_parallel_size": 4,
        "quantization": "AWQ",
        "virtual_gateway_model": "devops-flagship",
        "description": "Quad 24GB GPUs with TP=4 continuous batching serving 70B AWQ with 64K context.",
    },
    {
        "gpu_count": 4,
        "vram_per_gpu_gib": 32,
        "backend": "ollama",
        "model_id": "cogito-v2:70b",
        "model_alias": "cogito-v2-70b",
        "service_alias": "model-cogito-v2-70b",
        "service_port": 11434,
        "max_model_len": 131072,
        "tensor_parallel_size": 4,
        "quantization": "Q8_0",
        "virtual_gateway_model": "devops-flagship",
        "description": "Quad 32GB GPUs (128GB total) providing maximum capacity for 70B model with full context.",
    },
    {
        "gpu_count": 4,
        "vram_per_gpu_gib": 32,
        "backend": "vllm",
        "model_id": "cogito-v2:70b",
        "model_alias": "cogito-v2-70b",
        "service_alias": "model-cogito-v2-70b",
        "service_port": 8000,
        "max_model_len": 65536,
        "tensor_parallel_size": 4,
        "quantization": "FP8",
        "virtual_gateway_model": "devops-flagship",
        "description": "Quad 32GB GPUs with TP=4 serving high-throughput FP8 70B flagship.",
    },
)


def _build_profile_lookup() -> dict[tuple[int, int, str], GpuProfile]:
    """Construct keyed lookup map for all hardware matrix entries."""
    lookup: dict[tuple[int, int, str], GpuProfile] = {}
    for entry in _MATRIX_ENTRIES:
        total_vram = entry["gpu_count"] * entry["vram_per_gpu_gib"]
        profile = GpuProfile(
            total_vram_gib=total_vram,
            **entry,
        )
        lookup[(profile.gpu_count, profile.vram_per_gpu_gib, profile.backend)] = profile
    return lookup


_GPU_PROFILE_MAP: Final[dict[tuple[int, int, str], GpuProfile]] = _build_profile_lookup()


def get_gpu_profile(gpu_count: int, vram_per_gpu_gib: int, backend: str) -> GpuProfile:
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
    """Return all standardized Kubernetes model service aliases."""
    return dict(MODEL_SERVICE_ALIASES)


def get_gateway_routing_entries() -> list[dict[str, Any]]:
    """Generate LiteLLM gateway routing model_list entries targeting service aliases."""
    entries: list[dict[str, Any]] = []
    seen_virtual: set[str] = set()

    for alias_info in MODEL_SERVICE_ALIASES.values():
        virtual_name = alias_info["virtual_model"]
        if virtual_name in seen_virtual:
            continue
        seen_virtual.add(virtual_name)

        service_name = alias_info["service_name"]
        model_id = alias_info["model_id"]
        ports = alias_info["ports"]

        if "vllm" in ports:
            entries.append(
                {
                    "model_name": virtual_name,
                    "litellm_params": {
                        "model": f"openai/{model_id}",
                        "api_base": f"http://{service_name}.llm.svc.cluster.local:{ports['vllm']}/v1",
                        "api_key": "none",
                    },
                }
            )
        elif "ollama" in ports:
            prefix = "ollama" if virtual_name == "devops-embedding" else "ollama_chat"
            entries.append(
                {
                    "model_name": virtual_name,
                    "litellm_params": {
                        "model": f"{prefix}/{model_id}",
                        "api_base": f"http://{service_name}.llm.svc.cluster.local:{ports['ollama']}",
                    },
                }
            )

    return entries
