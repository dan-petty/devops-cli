"""High-throughput LLM Gateway & Distributed Inference Router.

Fronts heterogeneous Ollama cluster nodes with virtual model tiering, least-latency routing,
and circuit-breaking.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Final

import httpx2
from pydantic import BaseModel, ConfigDict, Field

from devops_cli.ai.capability import validate_failover_capability
from devops_cli.ai.client.models import credentials_error
from devops_cli.config.constants import (
    CONST_AI_BACKENDS,
    CONST_AI_GATEWAY_DEFAULT_ROUTE,
    CONST_AI_GATEWAY_PROVIDER_PORTKEY,
    CONST_AI_GATEWAY_PROVIDERS,
    CONST_AI_GATEWAY_VIRTUAL_MODELS,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_GATEWAY_HEALTH_TIMEOUT_SECONDS,
    DEFAULT_OLLAMA_CLUSTER_URL,
)
from devops_cli.config.settings import AIConfig, load_settings
from devops_cli.core.validation import validate_url_egress
from devops_cli.exceptions import ConfigurationError, ValidationError
from devops_cli.telemetry import record_metric, trace_span

logger = logging.getLogger(__name__)

# The route of each virtual model: the model that the gateway config (k8s/llm/gateway/config.yaml)
# sends to the tier of the default Ollama Service. The wheel and the service image hold only
# src/devops_cli, so the CLI cannot read that config. tests/test_k8s_llm_gateway.py fails when a
# route, or the route that a failover records, names a model that the config does not send to the
# route's tier (#1969).
DEFAULT_GATEWAY_ROUTES: Final[tuple[dict[str, str], ...]] = (
    {
        "virtual_model": "devops-chat",
        "target_model": "qwen3.8:27b",
        "backend_type": "ollama",
        "backend_url": DEFAULT_OLLAMA_CLUSTER_URL,
    },
    {
        "virtual_model": "devops-coder",
        "target_model": "qwen3-coder:30b",
        "backend_type": "ollama",
        "backend_url": DEFAULT_OLLAMA_CLUSTER_URL,
    },
    {
        "virtual_model": "devops-reasoning",
        "target_model": "qwen3-coder:30b",
        "backend_type": "ollama",
        "backend_url": DEFAULT_OLLAMA_CLUSTER_URL,
    },
    {
        "virtual_model": "devops-embedding",
        "target_model": "qwen3-embedding:0.6b",
        "backend_type": "ollama",
        "backend_url": DEFAULT_OLLAMA_CLUSTER_URL,
    },
)

# The backend type of a route that a failover records starts with this prefix, then names the
# backend type of the fallback route, e.g. `failover:ollama`.
_FAILOVER_BACKEND_PREFIX: Final[str] = "failover:"

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
    backend_type: str  # ollama | cloud | failover:*
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
    failover_routes: list[str] = Field(default_factory=list)
    backend_counts: dict[str, int] = Field(default_factory=dict)
    details: dict[str, Any] = Field(default_factory=dict)


def _build_default_routes() -> list[GatewayRoute]:
    """Construct default virtual model routes."""
    return [GatewayRoute(**route) for route in DEFAULT_GATEWAY_ROUTES]


def _failover_virtual_models(routes: list[GatewayRoute]) -> list[str]:
    """Name the virtual models whose route is a route that a failover recorded."""
    return [r.virtual_model for r in routes if r.backend_type.startswith(_FAILOVER_BACKEND_PREFIX)]


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
    virtual_model: str, fallback_target: str, active_routes: list[GatewayRoute]
) -> tuple[str, str, str]:
    """Resolve the failover of `virtual_model` to its target model, backend type and URL.

    A fallback to another virtual model takes the route of that model. `direct-ollama` names no
    route: the virtual model keeps the target model of its default route, which calls the default
    Ollama tier without the gateway.
    """
    route = next(
        (r for r in active_routes if r.virtual_model == fallback_target),
        next(r for r in _build_default_routes() if r.virtual_model == virtual_model),
    )
    return route.target_model, route.backend_type, route.backend_url


def _wildcard_pattern(items: list[dict[str, Any]]) -> str:
    """Name a wildcard deployment from the models it expanded into, e.g. `ollama/*`."""
    prefix = os.path.commonprefix([str(i.get("model_name") or "") for i in items])
    return f"{prefix[: prefix.rfind('/') + 1]}*"


def _parse_remote_model_items(data: list[dict[str, Any]], clean_url: str) -> list[GatewayRoute]:
    """Parse remote model objects into GatewayRoutes, one per gateway deployment.

    LiteLLM lists a wildcard deployment once for every model it can serve, all under the
    wildcard's own deployment id; those entries collapse back into one `<provider>/*` route.
    """
    by_deployment: dict[str, list[dict[str, Any]]] = {}
    for item in data:
        deployment_id = (item.get("model_info") or {}).get("id") or f"item-{id(item)}"
        by_deployment.setdefault(str(deployment_id), []).append(item)

    routes: list[GatewayRoute] = []
    for items in by_deployment.values():
        params = items[0].get("litellm_params", {})
        m_name = items[0].get("model_name") or items[0].get("id") or "unknown"
        target = params.get("model", m_name)
        if len(items) > 1:
            m_name = target = _wildcard_pattern(items)
        routes.append(
            GatewayRoute(
                virtual_model=m_name,
                target_model=target,
                backend_type="remote",
                backend_url=params.get("api_base", clean_url),
                healthy=True,
            )
        )
    return routes


def _sanitize_api_key_header(api_key: str | None) -> dict[str, str]:
    """Sanitize API key header against CRLF injection and invalid characters."""
    if not api_key or not isinstance(api_key, str):
        return {}
    clean = api_key.strip()
    if any(c in clean for c in ("\r", "\n")) or not clean.isascii():
        return {}
    return {"Authorization": f"Bearer {clean}"}


def _fetch_endpoint_resp(
    http_client: httpx2.Client, gateway_url: str, headers: dict[str, str]
) -> httpx2.Response:
    resp = http_client.get(f"{gateway_url}/model/info", headers=headers)
    if resp.status_code not in (200, 401, 403):
        resp = http_client.get(f"{gateway_url}/models", headers=headers)
    return resp


def _query_model_info(
    gateway_url: str,
    allow_private: bool,
    api_key: str | None,
    client: httpx2.Client | None = None,
) -> Any:
    """GET the gateway's /model/info (falling back to /models); None when unreachable."""
    headers = _sanitize_api_key_header(api_key)
    try:
        validate_url_egress(gateway_url, purpose="AI gateway", allow_private=allow_private)
        if client is not None:
            return _fetch_endpoint_resp(client, gateway_url, headers)
        with httpx2.Client(timeout=2.0) as ephemeral_client:
            return _fetch_endpoint_resp(ephemeral_client, gateway_url, headers)
    except Exception as exc:
        logger.debug("Failed to query live models API at %s: %s", gateway_url, exc)
        return None


def fetch_model_info(
    gateway_url: str,
    allow_private: bool,
    api_key: str | None = None,
    client: httpx2.Client | None = None,
) -> list[dict[str, Any]] | None:
    """Return the gateway's `/model/info` entries; None when it is unreachable or lists nothing.

    Raises AICredentialsError when the gateway rejects the request, rather than letting the
    caller fall back to defaults that do not describe the gateway.
    """
    resp = _query_model_info(gateway_url.rstrip("/"), allow_private, api_key, client=client)
    if resp is None:
        return None
    if resp.status_code in (401, 403):
        raise credentials_error("The LLM gateway", has_key=bool(api_key), status=resp.status_code)
    if resp.status_code >= 400:
        return None
    try:
        data = resp.json().get("data", [])
    except ValueError:
        return None
    return data if isinstance(data, list) and data else None


_GATEWAY_REASONING_CACHE: dict[tuple[str, str | None], dict[str, bool]] = {}


def clear_gateway_reasoning_cache() -> None:
    """Clear cached gateway reasoning capabilities."""
    _GATEWAY_REASONING_CACHE.clear()


def parse_gateway_reasoning_models(data: list[dict[str, Any]] | None) -> dict[str, bool]:
    """Derive reasoning capability by model name from /model/info data items.

    A model group gets reasoning capability only when every deployment in it declares
    supports_reasoning: true. A mixed or undeclared group evaluates to False.
    """
    if not data or not isinstance(data, list):
        return {}
    deployments: dict[str, list[dict[str, Any]]] = {}
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("model_name"), str):
            deployments.setdefault(item["model_name"], []).append(item)

    return {
        m_name: (
            bool(deps)
            and all(
                isinstance(d.get("model_info"), dict)
                and bool(d["model_info"].get("supports_reasoning"))
                for d in deps
            )
        )
        for m_name, deps in deployments.items()
    }


def resolve_gateway_reasoning_models(
    gateway_url: str,
    allow_private: bool,
    api_key: str | None = None,
    *,
    data: list[dict[str, Any]] | None = None,
    client: httpx2.Client | None = None,
) -> dict[str, bool]:
    """Return model_name -> supports_reasoning map for gateway, cached per process."""
    if data is not None:
        return parse_gateway_reasoning_models(data)
    key = (gateway_url.rstrip("/"), api_key)
    if key in _GATEWAY_REASONING_CACHE:
        return _GATEWAY_REASONING_CACHE[key]
    raw_data = fetch_model_info(gateway_url, allow_private, api_key, client=client)
    result = parse_gateway_reasoning_models(raw_data)
    _GATEWAY_REASONING_CACHE[key] = result
    return result


def is_gateway_model_reasoning(
    model_name: str,
    gateway_url: str,
    allow_private: bool,
    api_key: str | None = None,
    *,
    data: list[dict[str, Any]] | None = None,
    client: httpx2.Client | None = None,
) -> bool:
    """Check if model_name is declared with supports_reasoning in gateway deployments."""
    caps = resolve_gateway_reasoning_models(
        gateway_url, allow_private, api_key, data=data, client=client
    )
    return caps.get(model_name, False)


def _fetch_remote_routes(
    gateway_url: str, allow_private: bool, api_key: str | None = None
) -> list[GatewayRoute] | None:
    """Query the gateway's deployments as routes; None when it is unreachable or lists nothing."""
    data = fetch_model_info(gateway_url, allow_private, api_key)
    return _parse_remote_model_items(data, gateway_url.rstrip("/")) or None if data else None


def _probe_gateway_http(
    client: httpx2.Client, probe_base: str, provider: str
) -> tuple[bool, int, str | None]:
    """Execute HTTP health check against gateway provider endpoints."""
    try:
        if provider == CONST_AI_GATEWAY_PROVIDER_PORTKEY:
            resp = client.get(f"{probe_base}/")
            if resp.status_code != 200:
                resp = client.get(f"{probe_base}/health")
        else:
            resp = client.get(f"{probe_base}/health/readiness")
            if resp.status_code != 200:
                resp = client.get(f"{probe_base}/health")
        code = resp.status_code
        return (code < 400, code, None)
    except (httpx2.HTTPError, OSError) as exc:
        return (False, 0, str(exc)[:256])


class GatewayRouter:
    """Manages OpenAI-compatible AI Gateway routing, health probing, and failovers."""

    def __init__(
        self,
        config: AIConfig | None = None,
        state_file: Path | str | None = None,
        provider: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.config = config or AIConfig()
        self._api_key = api_key
        self.provider: str = provider or self.config.gateway_provider
        self.state_file = Path(state_file) if state_file else _resolve_state_file()
        cb_active, loaded_routes = _load_gateway_state(self.state_file)
        self._circuit_breaker_active: bool = cb_active
        self._active_routes: list[GatewayRoute] = loaded_routes or _build_default_routes()

    @property
    def gateway_url(self) -> str:
        """Resolve effective gateway base URL based on active provider."""
        if self.provider == CONST_AI_GATEWAY_PROVIDER_PORTKEY:
            if not self.config.portkey_url:
                raise ConfigurationError(
                    "No Portkey gateway URL configured. Run: devops config set ai.portkey_url <url>",
                    key="ai.portkey_url",
                )
            return self.config.portkey_url
        if not self.config.gateway_url:
            raise ConfigurationError(
                "No AI gateway URL configured. Run: devops config set ai.gateway_url <url>",
                key="ai.gateway_url",
            )
        return self.config.gateway_url

    def list_routes(self, gateway_url: str | None = None) -> list[GatewayRoute]:
        """Return configured or live queried virtual model routes."""
        if gateway_url:
            remote = _fetch_remote_routes(
                gateway_url, self.config.allow_private_network, self._api_key
            )
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
            # A healthy probe keeps a failover route: LiteLLM, not this route table, moves the
            # live traffic, so only a reset restores the default route (#1986).
            failover = _failover_virtual_models(self._active_routes)
            self._circuit_breaker_active = not is_ok or bool(failover)
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
                failover_routes=failover,
                backend_counts=_count_backends(self._active_routes),
                details=details,
            )

    def trigger_failover(
        self,
        virtual_model: str,
        simulate: bool = False,
        force: bool = False,
    ) -> dict[str, Any]:
        """Trigger or simulate failover of a model alias to its secondary fallback."""
        if virtual_model not in CONST_AI_GATEWAY_VIRTUAL_MODELS:
            raise ValidationError(
                f"Unknown virtual model '{virtual_model}'. Expected one of {CONST_AI_GATEWAY_VIRTUAL_MODELS}.",
                field="virtual_model",
            )

        with trace_span(
            "ai.gateway.failover",
            {"virtual_model": virtual_model, "simulate": simulate, "force": force},
        ):
            record_metric("ai.gateway.failover_events", 1)
            fallback_target = MODEL_FAILOVER_PAIRS.get(virtual_model, "direct-ollama")
            target_m, b_type, b_url = _resolve_fallback_physical_route(
                virtual_model, fallback_target, self._active_routes
            )
            validate_failover_capability(virtual_model, target_m, b_type, force=force)

            if not simulate:
                self._circuit_breaker_active = True
                self._active_routes = [
                    GatewayRoute(
                        virtual_model=r.virtual_model,
                        target_model=target_m
                        if r.virtual_model == virtual_model
                        else r.target_model,
                        backend_type=f"{_FAILOVER_BACKEND_PREFIX}{b_type}"
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

    def reset_failover(self) -> dict[str, Any]:
        """Restore the default route of every virtual model and clear the circuit breaker."""
        restored = _failover_virtual_models(self._active_routes)
        with trace_span("ai.gateway.failover_reset", {"restored_routes": len(restored)}):
            self._circuit_breaker_active = False
            self._active_routes = _build_default_routes()
            _save_gateway_state(self.state_file, self._circuit_breaker_active, self._active_routes)
        return {
            "status": "reset",
            "restored_routes": restored,
            "circuit_breaker_tripped": self._circuit_breaker_active,
        }

    def probe_backend(
        self,
        backend_type: str,
        backend_url: str | None = None,
        timeout: float = DEFAULT_AI_GATEWAY_HEALTH_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        """Probe an individual inference backend (e.g. ollama) directly."""
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
        virtual_model: str = CONST_AI_GATEWAY_DEFAULT_ROUTE,
        settings: Any = None,
        model_concurrency: Any = None,
    ) -> Any:
        """Construct a PydanticAI FallbackModel: the route and its failover route on this
        router's gateway, then `ai.model` on Ollama itself, which `direct-ollama` names."""
        from devops_cli.ai.pydantic_ai_bridge import build_fallback_cascade_model

        fallback_target = MODEL_FAILOVER_PAIRS.get(virtual_model, CONST_AI_GATEWAY_DEFAULT_ROUTE)
        routes = [r for r in (virtual_model, fallback_target) if r != "direct-ollama"]
        return build_fallback_cascade_model(
            [*(f"{self.provider}:{route}" for route in routes), "ollama"],
            settings=settings,
            model_concurrency=model_concurrency,
        )


def _resolve_backend_url(config: AIConfig, clean_type: str, backend_url: str | None) -> str:
    """Resolve backend target URL from override or AIConfig defaults."""
    if backend_url:
        return backend_url
    if clean_type == "ollama":
        return config.get_ollama_urls[0]
    raise ValidationError(
        f"No default URL configured for backend '{clean_type}'", field="backend_type"
    )


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
