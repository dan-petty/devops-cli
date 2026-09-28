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


# ── Provider VRAM Service Aliases ─────────────────────────────────────────────
# Standardized Kubernetes Service DNS names representing provider and VRAM capacity (<llm_provider>-<vram_gib>).
PROVIDER_SERVICE_ALIASES: Final[dict[str, dict[str, Any]]] = {
    "ollama-16gib": {
        "service_name": "ollama-16gib",
        "provider": "ollama",
        "vram_gib": 16,
        "ports": {"ollama": 11434},
        "default_model": "qwen2.5-coder:7b",
        "virtual_model": "devops-chat",
        "description": "Ollama 16GiB VRAM service (7B chat and embeddings)",
    },
    "ollama-24gib": {
        "service_name": "ollama-24gib",
        "provider": "ollama",
        "vram_gib": 24,
        "ports": {"ollama": 11434},
        "default_model": "qwen2.5-coder:14b",
        "virtual_model": "devops-coder",
        "description": "Ollama 24GiB VRAM service (14B coding)",
    },
    "ollama-32gib": {
        "service_name": "ollama-32gib",
        "provider": "ollama",
        "vram_gib": 32,
        "ports": {"ollama": 11434},
        "default_model": "qwen3-coder:30b",
        "virtual_model": "devops-reasoning",
        "description": "Ollama 32GiB VRAM service (30B reasoning & code review)",
    },
    "ollama-48gib": {
        "service_name": "ollama-48gib",
        "provider": "ollama",
        "vram_gib": 48,
        "ports": {"ollama": 11434},
        "default_model": "cogito-v2:70b",
        "virtual_model": "devops-flagship",
        "description": "Ollama 48GiB VRAM service (70B deep reasoning)",
    },
    "ollama-64gib": {
        "service_name": "ollama-64gib",
        "provider": "ollama",
        "vram_gib": 64,
        "ports": {"ollama": 11434},
        "default_model": "cogito-v2:70b",
        "virtual_model": "devops-flagship",
        "description": "Ollama 64GiB VRAM service (70B extended context)",
    },
    "ollama-72gib": {
        "service_name": "ollama-72gib",
        "provider": "ollama",
        "vram_gib": 72,
        "ports": {"ollama": 11434},
        "default_model": "cogito-v2:70b",
        "virtual_model": "devops-flagship",
        "description": "Ollama 72GiB VRAM service (70B pipeline parallel)",
    },
    "ollama-96gib": {
        "service_name": "ollama-96gib",
        "provider": "ollama",
        "vram_gib": 96,
        "ports": {"ollama": 11434},
        "default_model": "cogito-v2:70b",
        "virtual_model": "devops-flagship",
        "description": "Ollama 96GiB VRAM service (70B Q8 high precision)",
    },
    "ollama-128gib": {
        "service_name": "ollama-128gib",
        "provider": "ollama",
        "vram_gib": 128,
        "ports": {"ollama": 11434},
        "default_model": "cogito-v2:70b",
        "virtual_model": "devops-flagship",
        "description": "Ollama 128GiB VRAM service (70B Q8 128K context)",
    },
    "vllm-16gib": {
        "service_name": "vllm-16gib",
        "provider": "vllm",
        "vram_gib": 16,
        "ports": {"vllm": 8000},
        "default_model": "qwen2.5-coder-14b-instruct",
        "virtual_model": "devops-coder",
        "description": "vLLM 16GiB VRAM service (14B AWQ completions)",
    },
    "vllm-24gib": {
        "service_name": "vllm-24gib",
        "provider": "vllm",
        "vram_gib": 24,
        "ports": {"vllm": 8000},
        "default_model": "qwen2.5-coder-14b-instruct",
        "virtual_model": "devops-coder",
        "description": "vLLM 24GiB VRAM service (14B AWQ batching)",
    },
    "vllm-32gib": {
        "service_name": "vllm-32gib",
        "provider": "vllm",
        "vram_gib": 32,
        "ports": {"vllm": 8000},
        "default_model": "qwen3-coder:30b",
        "virtual_model": "devops-reasoning",
        "description": "vLLM 32GiB VRAM service (30B AWQ reasoning)",
    },
    "vllm-48gib": {
        "service_name": "vllm-48gib",
        "provider": "vllm",
        "vram_gib": 48,
        "ports": {"vllm": 8000},
        "default_model": "qwen3-coder:30b",
        "virtual_model": "devops-reasoning",
        "description": "vLLM 48GiB VRAM service (30B AWQ 64K context batching)",
    },
    "vllm-64gib": {
        "service_name": "vllm-64gib",
        "provider": "vllm",
        "vram_gib": 64,
        "ports": {"vllm": 8000},
        "default_model": "cogito-v2:70b",
        "virtual_model": "devops-flagship",
        "description": "vLLM 64GiB VRAM service (70B AWQ flagship)",
    },
    "vllm-72gib": {
        "service_name": "vllm-72gib",
        "provider": "vllm",
        "vram_gib": 72,
        "ports": {"vllm": 8000},
        "default_model": "cogito-v2:70b",
        "virtual_model": "devops-flagship",
        "description": "vLLM 72GiB VRAM service (70B AWQ pipeline parallel)",
    },
    "vllm-96gib": {
        "service_name": "vllm-96gib",
        "provider": "vllm",
        "vram_gib": 96,
        "ports": {"vllm": 8000},
        "default_model": "cogito-v2:70b",
        "virtual_model": "devops-flagship",
        "description": "vLLM 96GiB VRAM service (70B AWQ 64K context)",
    },
    "vllm-128gib": {
        "service_name": "vllm-128gib",
        "provider": "vllm",
        "vram_gib": 128,
        "ports": {"vllm": 8000},
        "default_model": "cogito-v2:70b",
        "virtual_model": "devops-flagship",
        "description": "vLLM 128GiB VRAM service (70B FP8/BF16 flagship)",
    },
}

MODEL_SERVICE_ALIASES: Final[dict[str, dict[str, Any]]] = PROVIDER_SERVICE_ALIASES

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
        "service_alias": "ollama-16gib",
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
        "service_alias": "vllm-16gib",
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
        "service_alias": "ollama-24gib",
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
        "service_alias": "vllm-24gib",
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
        "service_alias": "ollama-32gib",
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
        "service_alias": "vllm-32gib",
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
        "service_alias": "ollama-32gib",
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
        "service_alias": "vllm-32gib",
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
        "service_alias": "ollama-48gib",
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
        "service_alias": "vllm-48gib",
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
        "service_alias": "ollama-64gib",
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
        "service_alias": "vllm-64gib",
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
        "service_alias": "ollama-48gib",
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
        "service_alias": "vllm-48gib",
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
        "service_alias": "ollama-72gib",
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
        "service_alias": "vllm-72gib",
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
        "service_alias": "ollama-96gib",
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
        "service_alias": "vllm-96gib",
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
        "service_alias": "ollama-64gib",
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
        "service_alias": "vllm-64gib",
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
        "service_alias": "ollama-96gib",
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
        "service_alias": "vllm-96gib",
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
        "service_alias": "ollama-128gib",
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
        "service_alias": "vllm-128gib",
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
    """Return all standardized Kubernetes provider-vram service aliases (<llm_provider>-<vram_gib>)."""
    return dict(PROVIDER_SERVICE_ALIASES)


def get_gateway_routing_entries() -> list[dict[str, Any]]:
    """Generate LiteLLM gateway routing model_list entries targeting service aliases."""
    return [
        {
            "model_name": "devops-chat",
            "litellm_params": {
                "model": "ollama_chat/qwen2.5-coder:7b",
                "api_base": "http://ollama-16gib.llm.svc.cluster.local:11434",
            },
        },
        {
            "model_name": "devops-coder",
            "litellm_params": {
                "model": "openai/qwen2.5-coder-14b-instruct",
                "api_base": "http://vllm-16gib.llm.svc.cluster.local:8000/v1",
                "api_key": "none",
            },
        },
        {
            "model_name": "devops-reasoning",
            "litellm_params": {
                "model": "openai/qwen3-coder:30b",
                "api_base": "http://vllm-48gib.llm.svc.cluster.local:8000/v1",
                "api_key": "none",
            },
        },
        {
            "model_name": "devops-flagship",
            "litellm_params": {
                "model": "openai/cogito-v2:70b",
                "api_base": "http://vllm-64gib.llm.svc.cluster.local:8000/v1",
                "api_key": "none",
            },
        },
        {
            "model_name": "devops-embedding",
            "litellm_params": {
                "model": "ollama/bge-m3",
                "api_base": "http://ollama-16gib.llm.svc.cluster.local:11434",
            },
        },
    ]
