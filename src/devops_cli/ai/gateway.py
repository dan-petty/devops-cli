"""High-throughput LLM Gateway & Distributed Inference Router.

Fronts heterogeneous Ollama cluster nodes and dedicated vLLM Tensor-Parallel (TP=2)
serving instances with virtual model tiering, least-latency routing, and circuit-breaking.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Final

import httpx2
from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.router import TaskComplexity
from devops_cli.config.constants import (
    CONST_AI_BACKEND_LIGHTLLM,
    CONST_AI_BACKENDS,
    CONST_AI_GATEWAY_PROVIDER,
    CONST_AI_GATEWAY_PROVIDER_LITELLM,
    CONST_AI_GATEWAY_PROVIDER_PORTKEY,
    CONST_AI_GATEWAY_PROVIDERS,
    CONST_AI_GATEWAY_VIRTUAL_MODELS,
    CONST_TASK_TAXONOMY_CODER,
    CONST_TASK_TAXONOMY_EMBEDDING,
    CONST_TASK_TAXONOMY_REASONING,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_GATEWAY_HEALTH_TIMEOUT_SECONDS,
    DEFAULT_AI_GATEWAY_URL,
    DEFAULT_PORTKEY_GATEWAY_URL,
)
from devops_cli.config.settings import AIConfig, load_settings
from devops_cli.core.validation import validate_url_egress
from devops_cli.exceptions import ValidationError
from devops_cli.telemetry import record_metric, trace_span

logger = logging.getLogger(__name__)

DEFAULT_GATEWAY_ROUTES: Final[tuple[dict[str, str], ...]] = (
    {
        "virtual_model": "devops-chat",
        "target_model": "qwen2.5-coder:7b",
        "backend_type": "ollama",
        "backend_url": "http://ollama.llm.svc.cluster.local:11434",
    },
    {
        "virtual_model": "devops-coder",
        "target_model": "qwen2.5-coder:14b",
        "backend_type": "ollama",
        "backend_url": "http://ollama.llm.svc.cluster.local:11434",
    },
    {
        "virtual_model": "devops-reasoning",
        "target_model": "llama-3.3-70b-instruct",
        "backend_type": "vllm",
        "backend_url": "http://vllm.llm.svc.cluster.local:8000/v1",
    },
    {
        "virtual_model": "devops-embedding",
        "target_model": "bge-m3",
        "backend_type": "ollama",
        "backend_url": "http://ollama.llm.svc.cluster.local:11434",
    },
)

DEFAULT_PORTKEY_ROUTES: Final[tuple[dict[str, str], ...]] = (
    {
        "virtual_model": "devops-chat",
        "target_model": "qwen2.5-coder:7b",
        "backend_type": "ollama",
        "backend_url": "http://ollama.llm.svc.cluster.local:11434",
    },
    {
        "virtual_model": "devops-coder",
        "target_model": "qwen2.5-coder:14b",
        "backend_type": "lightllm",
        "backend_url": "http://lightllm.llm.svc.cluster.local:8000/v1",
    },
    {
        "virtual_model": "devops-reasoning",
        "target_model": "llama-3.3-70b-instruct",
        "backend_type": "vllm",
        "backend_url": "http://vllm.llm.svc.cluster.local:8000/v1",
    },
    {
        "virtual_model": "devops-embedding",
        "target_model": "bge-m3",
        "backend_type": "ollama",
        "backend_url": "http://ollama.llm.svc.cluster.local:11434",
    },
)

MODEL_FAILOVER_PAIRS: Final[dict[str, str]] = {
    "devops-reasoning": "devops-coder",
    "devops-coder": "devops-chat",
    "devops-chat": "direct-ollama",
    "devops-embedding": "direct-ollama",
}


class GatewayRoute(BaseModel):
    """Registered route from virtual model alias to physical inference engine backend."""

    model_config = ConfigDict(frozen=True)

    virtual_model: str
    target_model: str
    backend_type: str  # ollama | vllm | cloud | failover:*
    backend_url: str
    healthy: bool = True
    latency_ms: float = 0.0


class GatewayStatus(BaseModel):
    """Aggregate health status, active routes, and circuit breaker metrics."""

    model_config = ConfigDict(frozen=True)

    healthy: bool
    gateway_url: str
    active_routes: list[GatewayRoute] = Field(default_factory=list)
    circuit_breaker_tripped: bool = False
    backend_counts: dict[str, int] = Field(default_factory=dict)
    details: dict[str, Any] = Field(default_factory=dict)


def _build_default_routes(
    provider: str = CONST_AI_GATEWAY_PROVIDER_LITELLM,
) -> list[GatewayRoute]:
    """Construct default virtual model routes based on provider specification."""
    routes_tuple = (
        DEFAULT_PORTKEY_ROUTES
        if provider == CONST_AI_GATEWAY_PROVIDER_PORTKEY
        else DEFAULT_GATEWAY_ROUTES
    )
    return [GatewayRoute(**route) for route in routes_tuple]


def _count_backends(routes: list[GatewayRoute]) -> dict[str, int]:
    """Tally route counts by backend type."""
    counts: dict[str, int] = {}
    for route in routes:
        b_type = route.backend_type.split(":", 1)[-1]
        counts[b_type] = counts.get(b_type, 0) + 1
    return counts


def _resolve_state_file(data_dir: Path | str | None = None) -> Path:
    """Resolve persistent gateway state file path under agent directory."""
    from devops_cli.core.paths import is_forbidden_system_path, validate_no_path_traversal
    from devops_cli.exceptions import SecurityError

    if data_dir:
        validate_no_path_traversal(data_dir, label="Gateway data_dir")
        base = Path(data_dir).resolve()
    else:
        base = load_settings().data.dir.resolve()

    if is_forbidden_system_path(base):
        raise SecurityError(f"Gateway data_dir resolves to forbidden system path: {base}")

    target = base / "agent" / "gateway_state.json"
    if not target.resolve().is_relative_to(base):
        raise SecurityError(f"Gateway state file escapes base directory: {target}")
    return target


def _load_gateway_state(state_file: Path) -> tuple[bool, list[GatewayRoute] | None]:
    """Load circuit breaker and active route state from persistent storage."""
    if not state_file.is_file():
        return False, None
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        cb_active = bool(data.get("circuit_breaker_active", False))
        raw_routes = data.get("routes", [])
        if isinstance(raw_routes, list) and raw_routes:
            return cb_active, [GatewayRoute.model_validate(r) for r in raw_routes]
        return cb_active, None
    except Exception as exc:
        logger.warning("Failed loading gateway state from '%s': %s", state_file, exc)
        return False, None


def _save_gateway_state(
    state_file: Path, circuit_breaker_active: bool, routes: list[GatewayRoute]
) -> None:
    """Atomically persist gateway circuit breaker and routes to disk."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "circuit_breaker_active": circuit_breaker_active,
        "routes": [r.model_dump() for r in routes],
    }
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=state_file.parent,
            delete=False,
            prefix="gateway_state_",
            suffix=".tmp",
        ) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(json.dumps(payload, indent=2))
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, state_file)
    except Exception as exc:
        logger.warning("Failed saving gateway state to '%s': %s", state_file, exc)
        if tmp_path and tmp_path.is_file():
            tmp_path.unlink(missing_ok=True)


def _resolve_fallback_physical_route(
    fallback_target: str, active_routes: list[GatewayRoute]
) -> tuple[str, str, str]:
    """Resolve virtual alias to its physical target model, backend type, and URL."""
    target_r = next((r for r in active_routes if r.virtual_model == fallback_target), None)
    if target_r is not None:
        return target_r.target_model, target_r.backend_type, target_r.backend_url
    return "qwen2.5-coder:7b", "ollama", "http://ollama.llm.svc.cluster.local:11434"


def _parse_remote_model_items(data: list[dict[str, Any]], clean_url: str) -> list[GatewayRoute]:
    """Parse list of remote model objects into GatewayRoutes."""
    routes: list[GatewayRoute] = []
    for item in data:
        m_name = item.get("model_name") or item.get("id") or "unknown"
        params = item.get("litellm_params", {})
        routes.append(
            GatewayRoute(
                virtual_model=m_name,
                target_model=params.get("model", m_name),
                backend_type="remote",
                backend_url=params.get("api_base", clean_url),
                healthy=True,
            )
        )
    return routes


def _fetch_remote_routes(gateway_url: str, allow_private: bool) -> list[GatewayRoute] | None:
    """Attempt live query against LiteLLM models API to discover runtime routes."""
    try:
        validate_url_egress(gateway_url, purpose="AI gateway", allow_private=allow_private)
        clean_url = gateway_url.rstrip("/")
        with httpx2.Client(timeout=2.0) as client:
            resp = client.get(f"{clean_url}/model/info")
            if resp.status_code != 200:
                resp = client.get(f"{clean_url}/models")
            if resp.status_code >= 400:
                return None
            data = resp.json().get("data", [])
            if not isinstance(data, list) or not data:
                return None
            routes = _parse_remote_model_items(data, clean_url)
            return routes or None
    except Exception as exc:
        logger.debug("Failed to query live models API at %s: %s", gateway_url, exc)
        return None


def _probe_gateway_http(
    client: httpx2.Client, probe_base: str, provider: str
) -> tuple[bool, int, str | None]:
    """Execute HTTP health check against gateway provider endpoints."""
    try:
        if provider == CONST_AI_GATEWAY_PROVIDER_PORTKEY:
            resp = client.get(f"{probe_base}/health")
            if resp.status_code != 200:
                resp = client.get(f"{probe_base}/v1/health")
        else:
            resp = client.get(f"{probe_base}/health/readiness")
            if resp.status_code != 200:
                resp = client.get(f"{probe_base}/health")
        code = resp.status_code
        return (code < 400, code, None)
    except (httpx2.HTTPError, OSError) as exc:
        return (False, 0, str(exc)[:256])


def _execute_kubectl_scale(
    deployment: str, replicas: int, namespace: str
) -> tuple[str, dict[str, Any]]:
    """Execute kubectl scale deployment command with bounded timeout."""
    cmd = [
        "kubectl",
        "scale",
        "deployment",
        deployment,
        f"--namespace={namespace}",
        f"--replicas={replicas}",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0, check=False)
        if proc.returncode == 0:
            return "scaled", {"output": proc.stdout.strip()[:256]}
        return "error", {"error": (proc.stderr.strip() or proc.stdout.strip())[:256]}
    except (subprocess.SubprocessError, OSError) as exc:
        return "error", {"error": str(exc)[:256]}


class GatewayRouter:
    """Manages OpenAI-compatible AI Gateway routing, health probing, and failovers."""

    def __init__(
        self,
        config: AIConfig | None = None,
        state_file: Path | str | None = None,
        provider: str | None = None,
    ) -> None:
        self.config = config or AIConfig()
        self.provider: str = provider or self.config.gateway_provider
        self.state_file = Path(state_file) if state_file else _resolve_state_file()
        cb_active, loaded_routes = _load_gateway_state(self.state_file)
        self._circuit_breaker_active: bool = cb_active
        self._active_routes: list[GatewayRoute] = loaded_routes or _build_default_routes(
            self.provider
        )

    @property
    def gateway_url(self) -> str:
        """Resolve effective gateway base URL based on active provider."""
        if self.provider == CONST_AI_GATEWAY_PROVIDER_PORTKEY:
            return self.config.portkey_url or DEFAULT_PORTKEY_GATEWAY_URL
        return self.config.gateway_url or DEFAULT_AI_GATEWAY_URL

    def list_routes(self, gateway_url: str | None = None) -> list[GatewayRoute]:
        """Return configured or live queried virtual model routes."""
        if gateway_url:
            remote = _fetch_remote_routes(gateway_url, self.config.allow_private_network)
            if remote is not None:
                return remote
        return list(self._active_routes)

    def probe_gateway(
        self,
        gateway_url: str | None = None,
        timeout: float = DEFAULT_AI_GATEWAY_HEALTH_TIMEOUT_SECONDS,
        provider: str | None = None,
    ) -> GatewayStatus:
        """Probe gateway health endpoint and latency with OpenTelemetry tracing."""
        if provider and provider in CONST_AI_GATEWAY_PROVIDERS:
            self.provider = provider
        raw_url = (gateway_url or self.gateway_url).rstrip("/")
        validate_url_egress(
            raw_url, purpose="AI gateway", allow_private=self.config.allow_private_network
        )
        probe_base = raw_url[:-3] if raw_url.endswith("/v1") else raw_url

        with trace_span(
            "ai.gateway.probe", {"gateway.url": raw_url, "gateway.provider": self.provider}
        ) as span_h:
            start = time.perf_counter()
            with httpx2.Client(timeout=timeout) as client:
                is_ok, status_code, err_msg = _probe_gateway_http(client, probe_base, self.provider)

            latency = round((time.perf_counter() - start) * 1000, 2)
            self._circuit_breaker_active = not is_ok
            self._active_routes = [
                GatewayRoute(
                    virtual_model=r.virtual_model,
                    target_model=r.target_model,
                    backend_type=r.backend_type,
                    backend_url=r.backend_url,
                    healthy=is_ok,
                    latency_ms=latency if is_ok else 0.0,
                )
                for r in self._active_routes
            ]
            _save_gateway_state(self.state_file, self._circuit_breaker_active, self._active_routes)

            record_metric("ai.gateway.latency_ms", latency)
            record_metric("ai.gateway.healthy", 1 if is_ok else 0)
            span_h.set_attribute("ai.gateway.healthy", is_ok)
            span_h.set_attribute("ai.gateway.latency_ms", latency)

            details: dict[str, Any] = {"latency_ms": latency}
            if err_msg is not None:
                details["error"] = err_msg
            else:
                details["status_code"] = status_code

            return GatewayStatus(
                healthy=is_ok,
                gateway_url=raw_url,
                active_routes=list(self._active_routes),
                circuit_breaker_tripped=self._circuit_breaker_active,
                backend_counts=_count_backends(self._active_routes),
                details=details,
            )

    def resolve_model(
        self,
        task_name: str,
        token_count: int = 0,
        complexity: TaskComplexity | str = TaskComplexity.LOW,
    ) -> tuple[str, str]:
        """Resolve virtual model alias based on context tokens and task profile."""
        norm_complexity = (
            TaskComplexity(complexity)
            if isinstance(complexity, str) and complexity in TaskComplexity
            else TaskComplexity.LOW
        )

        if task_name in CONST_TASK_TAXONOMY_EMBEDDING:
            return (CONST_AI_GATEWAY_PROVIDER, "devops-embedding")

        is_reasoning_task = (
            token_count >= 32768
            or norm_complexity in (TaskComplexity.HIGH, TaskComplexity.FRONTIER)
            or task_name in CONST_TASK_TAXONOMY_REASONING
        )
        if is_reasoning_task:
            return (CONST_AI_GATEWAY_PROVIDER, "devops-reasoning")

        is_coder_task = (
            norm_complexity == TaskComplexity.MEDIUM
            or task_name in CONST_TASK_TAXONOMY_CODER
            or token_count > 4000
        )
        if is_coder_task:
            return (CONST_AI_GATEWAY_PROVIDER, "devops-coder")

        return (CONST_AI_GATEWAY_PROVIDER, "devops-chat")

    def trigger_failover(
        self,
        virtual_model: str,
        simulate: bool = False,
    ) -> dict[str, Any]:
        """Trigger or simulate failover of a model alias to its secondary fallback."""
        if virtual_model not in CONST_AI_GATEWAY_VIRTUAL_MODELS:
            raise ValidationError(
                f"Unknown virtual model '{virtual_model}'. Expected one of {CONST_AI_GATEWAY_VIRTUAL_MODELS}.",
                field="virtual_model",
            )

        with trace_span(
            "ai.gateway.failover", {"virtual_model": virtual_model, "simulate": simulate}
        ):
            record_metric("ai.gateway.failover_events", 1)
            fallback_target = MODEL_FAILOVER_PAIRS.get(virtual_model, "direct-ollama")
            target_m, b_type, b_url = _resolve_fallback_physical_route(
                fallback_target, self._active_routes
            )

            if not simulate:
                self._circuit_breaker_active = True
                self._active_routes = [
                    GatewayRoute(
                        virtual_model=r.virtual_model,
                        target_model=target_m
                        if r.virtual_model == virtual_model
                        else r.target_model,
                        backend_type=f"failover:{b_type}"
                        if r.virtual_model == virtual_model
                        else r.backend_type,
                        backend_url=b_url if r.virtual_model == virtual_model else r.backend_url,
                        healthy=True,
                        latency_ms=r.latency_ms,
                    )
                    for r in self._active_routes
                ]
                _save_gateway_state(
                    self.state_file, self._circuit_breaker_active, self._active_routes
                )

            return {
                "virtual_model": virtual_model,
                "fallback_target": fallback_target,
                "target_model": target_m,
                "circuit_breaker_tripped": self._circuit_breaker_active,
                "simulated": simulate,
                "status": "failover_active" if not simulate else "simulated",
            }

    def scale_vllm(
        self,
        replicas: int | None = None,
        tensor_parallel_size: int | None = None,
        apply: bool = False,
        namespace: str = "llm",
    ) -> dict[str, Any]:
        """Inspect or scale vLLM Tensor Parallel serving parameters."""
        effective_replicas = replicas if replicas is not None else 1
        effective_tp = tensor_parallel_size if tensor_parallel_size is not None else 2
        total_vram_gb = effective_replicas * effective_tp * 24

        with trace_span(
            "ai.gateway.scale_vllm",
            {
                "replicas": effective_replicas,
                "tensor_parallel_size": effective_tp,
                "apply": apply,
            },
        ):
            record_metric("ai.gateway.vllm_replicas", effective_replicas)
            if replicas is not None and apply:
                status, details = _execute_kubectl_scale("vllm", effective_replicas, namespace)
            else:
                status = "inspected" if replicas is None else "simulated"
                details = {}

            return {
                "backend": "vllm",
                "model": "casperhansen/llama-3.3-70b-instruct-awq",
                "served_model_name": "llama-3.3-70b-instruct",
                "replicas": effective_replicas,
                "tensor_parallel_size": effective_tp,
                "vram_per_gpu_gb": 24,
                "vram_per_replica_gb": effective_tp * 24,
                "total_vram_gb": total_vram_gb,
                "status": status,
                "details": details,
            }

    def scale_lightllm(
        self,
        replicas: int | None = None,
        tensor_parallel_size: int | None = None,
        max_model_len: int | None = None,
        apply: bool = False,
        namespace: str = "llm",
    ) -> dict[str, Any]:
        """Inspect or scale LightLLM high-throughput serving parameters."""
        effective_replicas = replicas if replicas is not None else 1
        effective_tp = tensor_parallel_size if tensor_parallel_size is not None else 1
        effective_max_len = max_model_len if max_model_len is not None else 8192
        vram_per_replica = effective_tp * 24
        total_vram_gb = effective_replicas * vram_per_replica

        with trace_span(
            "ai.gateway.scale_lightllm",
            {
                "replicas": effective_replicas,
                "tensor_parallel_size": effective_tp,
                "apply": apply,
            },
        ):
            record_metric("ai.gateway.lightllm_replicas", effective_replicas)
            if replicas is not None and apply:
                status, details = _execute_kubectl_scale("lightllm", effective_replicas, namespace)
            else:
                status = "inspected" if replicas is None else "simulated"
                details = {}

            return {
                "backend": "lightllm",
                "model": "casperhansen/llama-3.3-70b-instruct-awq",
                "served_model_name": "llama-3.3-70b-instruct",
                "replicas": effective_replicas,
                "tensor_parallel_size": effective_tp,
                "max_model_len": effective_max_len,
                "vram_per_replica_gb": vram_per_replica,
                "total_vram_gb": total_vram_gb,
                "status": status,
                "details": details,
            }

    def probe_backend(
        self,
        backend_type: str,
        backend_url: str | None = None,
        timeout: float = DEFAULT_AI_GATEWAY_HEALTH_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        """Probe an individual inference backend (vllm, lightllm, ollama) directly."""
        clean_type = backend_type.lower()
        if clean_type not in CONST_AI_BACKENDS:
            raise ValidationError(
                f"Unknown backend type '{backend_type}'. Expected one of {CONST_AI_BACKENDS}.",
                field="backend_type",
            )

        resolved_url = _resolve_backend_url(self.config, clean_type, backend_url)
        raw_url = resolved_url.rstrip("/")
        validate_url_egress(
            raw_url,
            purpose=f"AI backend {clean_type}",
            allow_private=self.config.allow_private_network,
        )
        probe_base = raw_url[:-3] if raw_url.endswith("/v1") else raw_url

        start = time.perf_counter()
        is_ok, status_code, err_msg, models = _probe_backend_http(probe_base, clean_type, timeout)
        latency = round((time.perf_counter() - start) * 1000, 2)

        return {
            "backend": clean_type,
            "backend_type": clean_type,
            "url": raw_url,
            "healthy": is_ok,
            "latency_ms": latency if is_ok else 0.0,
            "status_code": status_code,
            "error": err_msg,
            "model_count": len(models),
            "models": models,
        }

    def build_pydantic_cascade_model(
        self,
        virtual_model: str = "devops-chat",
        settings: Any = None,
        model_concurrency: Any = None,
    ) -> Any:
        """Construct a PydanticAI FallbackModel chaining the primary route to its failover target."""
        from devops_cli.ai.pydantic_ai_bridge import build_fallback_cascade_model

        fallback_target = MODEL_FAILOVER_PAIRS.get(virtual_model, "devops-chat")
        return build_fallback_cascade_model(
            [virtual_model, fallback_target, "ollama"],
            settings=settings,
            model_concurrency=model_concurrency,
        )


def _resolve_backend_url(config: AIConfig, clean_type: str, backend_url: str | None) -> str:
    """Resolve backend target URL from override or AIConfig defaults."""
    if backend_url:
        return backend_url
    if clean_type == CONST_AI_BACKEND_LIGHTLLM:
        return config.lightllm_url
    if clean_type == "ollama":
        return config.get_ollama_urls[0]
    return config.vllm_url


def _probe_backend_http(
    probe_base: str, clean_type: str, timeout: float
) -> tuple[bool, int, str | None, list[str]]:
    """Execute HTTP health and model queries against an inference backend."""
    status_code = 0
    err_msg: str | None = None
    models: list[str] = []
    try:
        with httpx2.Client(timeout=timeout) as client:
            resp = client.get(f"{probe_base}/health")
            if resp.status_code != 200:
                resp = client.get(f"{probe_base}/v1/models")
            status_code = resp.status_code
            is_ok = status_code < 400
            if is_ok:
                models = _fetch_backend_models(client, probe_base, clean_type)
            return is_ok, status_code, None, models
    except (httpx2.HTTPError, OSError) as exc:
        err_msg = str(exc)[:256]
        return False, status_code, err_msg, []


def _fetch_backend_models(client: httpx2.Client, probe_base: str, backend_type: str) -> list[str]:
    """Fetch registered models from inference backend endpoint."""
    url = f"{probe_base}/api/tags" if backend_type == "ollama" else f"{probe_base}/v1/models"
    try:
        resp = client.get(url)
        if resp.status_code >= 400:
            return []
        data = resp.json()
        if "data" in data and isinstance(data["data"], list):
            return [m.get("id", "") for m in data["data"] if isinstance(m, dict) and "id" in m]
        if "models" in data and isinstance(data["models"], list):
            return [
                m.get("name", "") for m in data["models"] if isinstance(m, dict) and "name" in m
            ]
    except httpx2.HTTPError, OSError, ValueError:
        return []
    return []
