"""How busy each backend in the LLM pool was over a window, from Prometheus (#546).

#545's imbalance was measured by sampling `nvidia-smi` and the vLLM queues by hand. With the
gateway's, the vLLM servers' and the GPUs' metrics in Prometheus, the same picture comes from one
set of queries over any window:
- the gateway's requests, failures and mean calls in flight per deployment, covering the Ollama
  nodes, which export no metrics;
- each vLLM server's share of the window with a request running, and its queue;
- each GPU's utilisation and peak memory.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable

import httpx2
from pydantic import BaseModel, Field

from devops_cli.ai.gateway_tune import backend_label
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.models.prometheus import PrometheusQueryResult

# A PromQL instant query's result: each series' labels and value.
Query = Callable[[str], list[tuple[dict[str, str], float]]]

_WINDOW = re.compile(r"^([1-9]\d*)([smhd])$")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
# Each LiteLLM deployment is identified by model_id; this attaches its api_base.
_DEPLOYMENT = (
    "on (model_id) group_left (api_base) "
    "group by (model_id, api_base) (litellm_deployment_total_requests_total)"
)


class PoolLoadError(DevOpsCLIError):
    """Prometheus could not answer a pool load query."""


def prometheus_query(base_url: str, timeout: float) -> Query:
    """Instant queries against a Prometheus server; series without a number are left out."""

    def query(expr: str) -> list[tuple[dict[str, str], float]]:
        try:
            with httpx2.Client() as client:
                response = client.get(
                    f"{base_url}/api/v1/query", params={"query": expr}, timeout=timeout
                )
                response.raise_for_status()
        except httpx2.HTTPError as exc:
            raise PoolLoadError(f"Prometheus at {base_url} did not answer: {exc}") from exc
        result = PrometheusQueryResult.from_instant_response(response.json())
        if result.status != "success":
            raise PoolLoadError(f"Prometheus rejected a query: {result.error or 'unknown'}")
        values = [(series.labels, float(series.value or "nan")) for series in result.series]
        return [(labels, value) for labels, value in values if not math.isnan(value)]

    return query


def window_seconds(window: str) -> int:
    """A PromQL duration such as `30m` or `2h`, in seconds."""
    match = _WINDOW.match(window)
    if not match:
        raise ValueError(f"window {window!r} is not a duration such as 30m, 2h or 1d")
    return int(match.group(1)) * _UNIT_SECONDS[match.group(2)]


class BackendLoad(BaseModel):
    """One backend's load over the window."""

    backend: str
    requests: float = 0.0
    failures: float = 0.0
    # Call seconds per second: the calls the gateway had on it at once, on average.
    mean_in_flight: float = 0.0
    # vLLM servers only: the share of the window with a request running, and the queue.
    busy_share: float | None = None
    mean_waiting: float | None = None
    max_waiting: float | None = None


class GpuLoad(BaseModel):
    """One GPU's load over the window."""

    host: str
    gpu: str
    model: str
    mean_utilisation: float = 0.0
    peak_memory_mib: float = 0.0


class PoolLoad(BaseModel):
    """The pool's load over a window."""

    window: str
    backends: list[BackendLoad] = Field(default_factory=list)
    gpus: list[GpuLoad] = Field(default_factory=list)


def _by_backend(query: Query, expr: str, label: str) -> dict[str, float]:
    """A query's values keyed by backend, named from an api_base or a vLLM job."""
    values: dict[str, float] = {}
    for labels, value in query(expr):
        raw = labels.get(label, "")
        name = backend_label(raw) if label == "api_base" else raw
        if name:
            values[name] = values.get(name, 0.0) + value
    return values


def _backends(query: Query, window: str) -> list[BackendLoad]:
    seconds = window_seconds(window)
    gateway = {
        "requests": _by_backend(
            query,
            f"sum by (api_base) (increase(litellm_deployment_total_requests_total[{window}]))",
            "api_base",
        ),
        "failures": _by_backend(
            query,
            f"sum by (api_base) (increase(litellm_deployment_failure_responses_total[{window}]))",
            "api_base",
        ),
        "mean_in_flight": _by_backend(
            query,
            f"sum by (api_base) (increase(litellm_llm_api_latency_metric_sum[{window}]) "
            f"* {_DEPLOYMENT}) / {seconds}",
            "api_base",
        ),
    }
    running = "sum by (job) (vllm:num_requests_running)"
    waiting = "sum by (job) (vllm:num_requests_waiting)"
    vllm = {
        "busy_share": _by_backend(
            query, f"avg_over_time(({running} > bool 0)[{window}:15s])", "job"
        ),
        "mean_waiting": _by_backend(query, f"avg_over_time({waiting}[{window}:15s])", "job"),
        "max_waiting": _by_backend(query, f"max_over_time({waiting}[{window}:15s])", "job"),
    }
    names = sorted({name for values in (*gateway.values(), *vllm.values()) for name in values})
    return [
        BackendLoad(
            backend=name,
            **{field: values.get(name, 0.0) for field, values in gateway.items()},
            **{field: values.get(name) for field, values in vllm.items()},
        )
        for name in names
    ]


def _gpus(query: Query, window: str) -> list[GpuLoad]:
    by = "by (Hostname, gpu, modelName)"
    utilisation = query(f"avg {by} (avg_over_time(DCGM_FI_DEV_GPU_UTIL[{window}]))")
    memory = {
        (labels.get("Hostname", ""), labels.get("gpu", "")): value
        for labels, value in query(f"max {by} (max_over_time(DCGM_FI_DEV_FB_USED[{window}]))")
    }
    gpus = [
        GpuLoad(
            host=labels.get("Hostname", ""),
            gpu=labels.get("gpu", ""),
            model=labels.get("modelName", ""),
            mean_utilisation=value,
            peak_memory_mib=memory.get((labels.get("Hostname", ""), labels.get("gpu", "")), 0.0),
        )
        for labels, value in utilisation
    ]
    return sorted(gpus, key=lambda g: (g.host, g.gpu))


def pool_load(query: Query, window: str) -> PoolLoad:
    """Each backend's and GPU's load over the window, e.g. `1h`."""
    window_seconds(window)
    return PoolLoad(window=window, backends=_backends(query, window), gpus=_gpus(query, window))


__all__ = [
    "BackendLoad",
    "GpuLoad",
    "PoolLoad",
    "PoolLoadError",
    "Query",
    "pool_load",
    "prometheus_query",
    "window_seconds",
]
