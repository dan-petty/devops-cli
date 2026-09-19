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
    CONST_AI_GATEWAY_PROVIDER,
    CONST_AI_GATEWAY_VIRTUAL_MODELS,
    CONST_TASK_TAXONOMY_CODER,
    CONST_TASK_TAXONOMY_EMBEDDING,
    CONST_TASK_TAXONOMY_REASONING,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_GATEWAY_HEALTH_TIMEOUT_SECONDS,
    DEFAULT_AI_GATEWAY_URL,
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


def _build_default_routes() -> list[GatewayRoute]:
    """Construct default virtual model routes based on cluster specification."""
    return [GatewayRoute(**route) for route in DEFAULT_GATEWAY_ROUTES]


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
            return routes or None
    except Exception as exc:
        logger.debug("Failed to query live models API at %s: %s", gateway_url, exc)
        return None


def _execute_kubectl_scale(replicas: int, namespace: str) -> tuple[str, dict[str, Any]]:
    """Execute kubectl scale deployment command with bounded timeout."""
    cmd = [
        "kubectl",
        "scale",
        "deployment",
        "vllm",
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
    """Manages OpenAI-compatible LiteLLM Gateway routing, health probing, and failovers."""

    def __init__(
        self, config: AIConfig | None = None, state_file: Path | str | None = None
    ) -> None:
        self.config = config or AIConfig()
        self.state_file = Path(state_file) if state_file else _resolve_state_file()
        cb_active, loaded_routes = _load_gateway_state(self.state_file)
        self._circuit_breaker_active: bool = cb_active
        self._active_routes: list[GatewayRoute] = loaded_routes or _build_default_routes()

    @property
    def gateway_url(self) -> str:
        """Resolve effective gateway base URL."""
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
    ) -> GatewayStatus:
        """Probe gateway health endpoint and latency with OpenTelemetry tracing."""
        raw_url = (gateway_url or self.gateway_url).rstrip("/")
        validate_url_egress(
            raw_url, purpose="AI gateway", allow_private=self.config.allow_private_network
        )
        probe_base = raw_url[:-3] if raw_url.endswith("/v1") else raw_url

        with trace_span("ai.gateway.probe", {"gateway.url": raw_url}) as span_h:
            start = time.perf_counter()
            is_ok = False
            status_code = 0
            err_msg: str | None = None
            try:
                with httpx2.Client(timeout=timeout) as client:
                    resp = client.get(f"{probe_base}/health/readiness")
                    if resp.status_code != 200:
                        resp = client.get(f"{probe_base}/health")
                    status_code = resp.status_code
                    is_ok = status_code < 400
            except (httpx2.HTTPError, OSError) as exc:
                err_msg = str(exc)[:256]

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
                status, details = _execute_kubectl_scale(effective_replicas, namespace)
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
