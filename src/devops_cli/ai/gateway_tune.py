"""Measure each deployment of a gateway model group and recommend routing weights.

The gateway spreads a model group over its deployments by weight (`simple-shuffle`), and those
weights only help if they track what each backend can actually serve. This measures every
deployment on its own and recommends weights in proportion to its best request rate.

The inference backends admit traffic only from the gateway, so the sweep
(`devops_cli.ai.gateway_bench`) runs in an ephemeral container attached to the gateway pod
(`kubectl debug`). It shares the pod's network identity, so it takes the same path as the gateway's
own requests, and it runs this project's Python rather than whatever the gateway image ships.
Nothing is reconfigured; the result is a recommendation. An exited ephemeral container stays
listed on the pod until the pod is replaced.
"""

from __future__ import annotations

import inspect
import json
import subprocess
import time
import uuid
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from devops_cli.ai import gateway, gateway_bench
from devops_cli.ai.gateway import fetch_model_info
from devops_cli.config.constants import (
    CONST_CONTINUOUS_BATCHING_ENGINES,
    CONST_DEFAULT_CONTINUOUS_CONCURRENCY,
    CONST_DEFAULT_SERIAL_CONCURRENCY,
    CONST_ENGINE_MULTIPLIER_CONTINUOUS_BATCHING,
    CONST_ENGINE_MULTIPLIER_SERIAL,
    CONST_GPU_MEMORY_BANDWIDTH_GBPS,
    CONST_REVIEW_CHARS_PER_TOKEN,
)
from devops_cli.config.defaults import DEFAULT_GATEWAY_TUNE_IMAGE
from devops_cli.exceptions import DevOpsCLIError

_INSTRUCTION = "List up to five concrete defects in this code, one line each.\n\n"
# Share of a deployment's max_input_tokens a measurement prompt may fill.
_INPUT_MARGIN = 0.9


class GatewayTuneError(DevOpsCLIError):
    """Raised when the gateway's deployments cannot be discovered or measured."""


class LevelResult(BaseModel):
    """One concurrency level of one deployment's sweep."""

    concurrency: int
    requests: int
    errors: int
    wall_seconds: float
    requests_per_second: float
    p50_latency_seconds: float | None = None
    completion_tokens: int = 0
    last_error: str | None = None

    @property
    def tokens_per_second(self) -> float:
        return self.completion_tokens / self.wall_seconds if self.wall_seconds > 0 else 0.0

    @property
    def tokens_per_request(self) -> float | None:
        served = self.requests - self.errors
        return self.completion_tokens / served if served > 0 else None


class GpuInfo(BaseModel):
    """A GPU visible to a backend pod."""

    name: str
    memory_mib: int
    bandwidth_gbps: float | None = None


class DeploymentTune(BaseModel):
    """A deployment's hardware, measurements and recommended weight.

    ``requests_per_second`` is capacity (fixed-length tokens per second at the best concurrency)
    divided by cost (tokens the model writes per request when left to stop on its own).
    """

    deployment_id: str
    backend: str
    model: str
    api_base: str
    current_weight: float | None = None
    prompt_tokens: int = 0
    engine: str = "unknown"
    kv_cache_tokens: int | None = None
    gpus: list[GpuInfo] = Field(default_factory=list)
    capacity: list[LevelResult] = Field(default_factory=list)
    cost: LevelResult | None = None
    best_concurrency: int | None = None
    capacity_tokens_per_second: float = 0.0
    cost_tokens_per_request: float | None = None
    requests_per_second: float = 0.0
    recommended_weight: int = 0
    recommended_concurrency: int | None = None


class TuneReport(BaseModel):
    """Measurements and recommended weights for one model group."""

    model_group: str
    prompt_tokens: int
    max_tokens: int
    deployments: list[DeploymentTune]


def discover_pool(model_info: list[dict[str, Any]], model_group: str) -> list[dict[str, Any]]:
    """Return the model group's deployments from the gateway's `/model/info` entries."""
    pool: list[dict[str, Any]] = []
    for item in model_info:
        if item.get("model_name") != model_group:
            continue
        params = item.get("litellm_params") or {}
        pool.append(
            {
                "deployment_id": str((item.get("model_info") or {}).get("id") or ""),
                "model": str(params.get("model") or ""),
                "api_base": str(params.get("api_base") or ""),
                "weight": params.get("weight"),
                "max_input_tokens": (item.get("model_info") or {}).get("max_input_tokens"),
            }
        )
    return pool


def _dep_field(dep: Any, field: str, default: Any = "") -> Any:
    """Extract a deployment field whether it is an object or a dictionary."""
    if isinstance(dep, dict):
        return dep.get(field, default)
    return getattr(dep, field, default)


def _resolve_override(
    dep_id: str,
    backend: str,
    overrides: dict[str, int] | None,
) -> int | None:
    """Resolve an override by deployment_id first, then by backend label."""
    if not overrides:
        return None
    val = overrides.get(dep_id)
    if val is not None:
        return val
    return overrides.get(backend) if backend else None


def _deployment_backend_map(deployments: list[Any] | None) -> dict[str, str]:
    """Map deployment_id to backend label for all deployments."""
    if not deployments:
        return {}
    return {
        str(_dep_field(d, "deployment_id", "")): str(_dep_field(d, "backend", ""))
        for d in deployments
        if _dep_field(d, "deployment_id", "")
    }


def recommend_weights(
    best_rates: dict[str, float],
    overrides: dict[str, int] | None = None,
    deployments: list[Any] | None = None,
) -> dict[str, int]:
    """Weight each deployment by its best request rate relative to the slowest one.

    The slowest measured deployment gets 1. A deployment that served nothing gets 0, which
    keeps the gateway from routing to it. Custom overrides take precedence when configured,
    matched by deployment ID or backend label.
    """
    measured = [rate for rate in best_rates.values() if rate > 0]
    floor = min(measured) if measured else 1.0
    weights = {
        dep: max(1, round(rate / floor)) if rate > 0 else 0 for dep, rate in best_rates.items()
    }
    if not overrides:
        return weights
    backend_map = _deployment_backend_map(deployments)
    for dep in weights:
        override = _resolve_override(dep, backend_map.get(dep, ""), overrides)
        if override is not None:
            weights[dep] = override
    return weights


def _is_continuous_engine(engine: str, backend: str) -> bool:
    """Check if engine or backend supports continuous batching."""
    target = f"{engine} {backend}".lower()
    return any(e in target for e in CONST_CONTINUOUS_BATCHING_ENGINES)


def _deployment_bandwidth_sum(dep: Any) -> float:
    """Sum GPU memory bandwidths across GPUs assigned to a deployment."""
    gpus = _dep_field(dep, "gpus", [])
    total = 0.0
    for g in gpus:
        bw = getattr(g, "bandwidth_gbps", None) or (
            g.get("bandwidth_gbps") if isinstance(g, dict) else None
        )
        total += float(bw) if bw else 500.0
    return total


def _deployment_hardware_score(dep: Any) -> float:
    """Compute relative throughput capacity score from GPUs and engine type."""
    backend = str(_dep_field(dep, "backend", ""))
    engine = str(_dep_field(dep, "engine", ""))
    is_continuous = _is_continuous_engine(engine, backend)

    bw_sum = _deployment_bandwidth_sum(dep)
    if not bw_sum:
        bw_sum = 1000.0 if is_continuous else 500.0

    multiplier = (
        CONST_ENGINE_MULTIPLIER_CONTINUOUS_BATCHING
        if is_continuous
        else CONST_ENGINE_MULTIPLIER_SERIAL
    )
    return bw_sum * multiplier


def calculate_hardware_weights(
    deployments: list[Any],
    overrides: dict[str, int] | None = None,
) -> dict[str, int]:
    """Dynamically calculate recommended routing weights from discovered hardware properties.

    Evaluates total GPU memory bandwidth and engine execution model (continuous batching vs
    serial execution). Custom overrides take precedence when configured.
    """
    scores = {
        str(_dep_field(dep, "deployment_id")): _deployment_hardware_score(dep)
        for dep in deployments
        if _dep_field(dep, "deployment_id")
    }
    valid_scores = [s for s in scores.values() if s > 0]
    min_score = min(valid_scores) if valid_scores else 1.0
    weights = {
        dep_id: max(1, round(score / min_score)) if score > 0 else 0
        for dep_id, score in scores.items()
    }
    if not overrides:
        return weights
    for dep in deployments:
        dep_id = str(_dep_field(dep, "deployment_id", ""))
        backend = str(_dep_field(dep, "backend", ""))
        override = _resolve_override(dep_id, backend, overrides)
        if override is not None and dep_id:
            weights[dep_id] = override
    return weights


def calculate_hardware_concurrency(
    deployments: list[Any],
    overrides: dict[str, int] | None = None,
) -> dict[str, int]:
    """Compute concurrency limits from engine capabilities with config overrides."""
    limits: dict[str, int] = {}
    for dep in deployments:
        dep_id = str(_dep_field(dep, "deployment_id", ""))
        if not dep_id:
            continue
        backend = str(_dep_field(dep, "backend", ""))
        engine = str(_dep_field(dep, "engine", ""))
        is_continuous = _is_continuous_engine(engine, backend)
        default_limit = (
            CONST_DEFAULT_CONTINUOUS_CONCURRENCY
            if is_continuous
            else CONST_DEFAULT_SERIAL_CONCURRENCY
        )
        override = _resolve_override(dep_id, backend, overrides)
        limits[dep_id] = override if override is not None else default_limit
    return limits


def gpu_bandwidth_gbps(name: str) -> float | None:
    """Look up a GPU's memory bandwidth from its `nvidia-smi` name; None when unknown."""
    lowered = name.lower()
    for key in sorted(CONST_GPU_MEMORY_BANDWIDTH_GBPS, key=len, reverse=True):
        if key in lowered:
            return CONST_GPU_MEMORY_BANDWIDTH_GBPS[key]
    return None


def backend_pods(api_base: str, context: str | None) -> tuple[str | None, list[str]]:
    """Resolve a backend's cluster address to its namespace and pods.

    `<pod>.<service>.<namespace>.svc...` names one pod through a headless Service;
    `<service>.<namespace>.svc...` resolves through the Service's selector to its running pods.
    Any other address is outside the cluster and has no pods to inspect.
    """
    labels = (urlparse(api_base).hostname or "").split(".")
    if "svc" not in labels:
        return None, []
    parts = labels[: labels.index("svc")]
    if len(parts) == 3:
        return parts[2], [parts[0]]
    if len(parts) != 2:
        return None, []
    service, namespace = parts
    found = _kubectl(["get", "svc", service, "-n", namespace, "-o", "json"], context=context)
    if found.returncode != 0:
        return namespace, []
    selector = json.loads(found.stdout).get("spec", {}).get("selector") or {}
    pods = _kubectl(
        [
            "get",
            "pods",
            "-n",
            namespace,
            "-l",
            ",".join(f"{k}={v}" for k, v in selector.items()),
            "--field-selector=status.phase=Running",
            "-o",
            "jsonpath={.items[*].metadata.name}",
        ],
        context=context,
    )
    return namespace, pods.stdout.split() if pods.returncode == 0 else []


def gpu_inventory(namespace: str, pod: str, context: str | None) -> list[GpuInfo]:
    """List the GPUs a backend pod sees, from `nvidia-smi` inside it."""
    query = _kubectl(
        [
            "exec",
            "-n",
            namespace,
            pod,
            "--",
            "nvidia-smi",
            "--query-gpu=name,memory.total",
            "--format=csv,noheader,nounits",
        ],
        context=context,
    )
    if query.returncode != 0:
        raise GatewayTuneError(f"Cannot read GPUs in {namespace}/{pod}: {_detail(query)}")
    gpus: list[GpuInfo] = []
    for line in query.stdout.splitlines():
        name, _, memory = line.rpartition(",")
        if name.strip() and memory.strip().isdigit():
            gpus.append(
                GpuInfo(
                    name=name.strip(),
                    memory_mib=int(memory),
                    bandwidth_gbps=gpu_bandwidth_gbps(name),
                )
            )
    return gpus


def deployment_gpus(api_base: str, context: str | None) -> list[GpuInfo]:
    """GPUs behind a deployment's backend; empty when they cannot be inspected."""
    namespace, pods = backend_pods(api_base, context)
    if namespace is None or not pods:
        return []
    try:
        return gpu_inventory(namespace, pods[0], context)
    except GatewayTuneError:
        return []


def backend_label(api_base: str) -> str:
    """Name a deployment by its backend host's first label, e.g. `vllm` or `ollama-0`."""
    host = urlparse(api_base).hostname or api_base
    return host.split(".", 1)[0]


def review_page_tokens(context_window: int) -> int:
    """Tokens in one review page for a context window, as `devops ai review` sizes its pages."""
    from devops_cli.ai.review.chunker import review_page_chars

    return int(review_page_chars(context_window) / CONST_REVIEW_CHARS_PER_TOKEN)


def deployment_prompt_tokens(prompt_tokens: int, max_input_tokens: int | None) -> int:
    """Cap the prompt below a deployment's input limit.

    The gateway's pre-call checks never send a page too large for a deployment to it, so it is
    measured on the largest page it would be given. The margin absorbs the estimate's error.
    """
    if not max_input_tokens:
        return prompt_tokens
    return min(prompt_tokens, int(max_input_tokens * _INPUT_MARGIN))


def review_prompt(prompt_tokens: int) -> str:
    """Build a review-style prompt of roughly ``prompt_tokens`` tokens from this project's code."""
    source = inspect.getsource(gateway)
    chars = int(prompt_tokens * CONST_REVIEW_CHARS_PER_TOKEN)
    code = (source * (chars // len(source) + 1))[:chars]
    return f"{_INSTRUCTION}{code}"


def bench_script(spec: dict[str, Any]) -> str:
    """Return the sweep module's source followed by a call that runs it on ``spec``."""
    return f"{inspect.getsource(gateway_bench)}\n\nmain({json.dumps(spec)!r})\n"


_IMAGE_PULL_FAILURES = frozenset({"ErrImagePull", "ImagePullBackOff", "InvalidImageName"})


# kubectl's message when it never reached the API server, e.g. a transient DNS failure. The
# request was not delivered, so retrying cannot repeat it.
_UNREACHABLE = "Unable to connect to the server"
_KUBECTL_ATTEMPTS = 3


def _kubectl(
    args: list[str],
    *,
    context: str | None,
    timeout: float | None = 60.0,
    input_data: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run kubectl, retrying when the API server was unreachable.

    The context flag goes first so it never lands after a `--` separator. A sweep makes dozens
    of calls, so one transient connection failure would otherwise abort it.
    """
    cmd = ["kubectl", *(["--context", context] if context else []), *args]
    for attempt in range(1, _KUBECTL_ATTEMPTS + 1):
        try:
            proc = subprocess.run(  # noqa: S603  # nosec B603 - fixed kubectl argv, no shell
                cmd,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            raise GatewayTuneError(f"kubectl {args[0]} failed: {exc}") from exc
        if proc.returncode == 0 or _UNREACHABLE not in (proc.stderr or ""):
            return proc
        if attempt < _KUBECTL_ATTEMPTS:
            time.sleep(attempt)
    return proc


def _detail(proc: subprocess.CompletedProcess[str]) -> str:
    return (proc.stderr or proc.stdout or "").strip()[-500:]


def _gateway_pod(namespace: str, deployment: str, context: str | None) -> str:
    """Return a running pod of the gateway deployment, found through its label selector."""
    selector = _kubectl(
        ["get", "deployment", deployment, "-n", namespace, "-o", "json"], context=context
    )
    if selector.returncode != 0:
        raise GatewayTuneError(
            f"Cannot read the gateway deployment {namespace}/{deployment}: {_detail(selector)}"
        )
    labels = json.loads(selector.stdout)["spec"]["selector"].get("matchLabels") or {}
    pods = _kubectl(
        [
            "get",
            "pods",
            "-n",
            namespace,
            "-l",
            ",".join(f"{k}={v}" for k, v in labels.items()),
            "--field-selector=status.phase=Running",
            "-o",
            "jsonpath={.items[0].metadata.name}",
        ],
        context=context,
    )
    if pods.returncode != 0 or not pods.stdout.strip():
        raise GatewayTuneError(
            f"The gateway deployment {namespace}/{deployment} has no running pod."
        )
    return pods.stdout.strip()


def _container_state(
    pod: str, container: str, namespace: str, context: str | None
) -> dict[str, Any]:
    proc = _kubectl(["get", "pod", pod, "-n", namespace, "-o", "json"], context=context)
    if proc.returncode != 0:
        return {}
    statuses = json.loads(proc.stdout).get("status", {}).get("ephemeralContainerStatuses") or []
    return next((s.get("state") or {} for s in statuses if s.get("name") == container), {})


def _wait_for_running(
    pod: str, container: str, namespace: str, context: str | None, timeout: float, poll: float
) -> None:
    """Poll the ephemeral container until it is running."""
    deadline = time.monotonic() + timeout
    while True:
        state = _container_state(pod, container, namespace, context)
        if "running" in state:
            return
        if "terminated" in state:
            raise GatewayTuneError(
                f"The sweep container {container} in {namespace}/{pod} terminated prematurely."
            )
        waiting = state.get("waiting") or {}
        if waiting.get("reason") in _IMAGE_PULL_FAILURES:
            raise GatewayTuneError(f"Cannot start the sweep container: {waiting.get('message')}")
        if time.monotonic() > deadline:
            raise GatewayTuneError(
                f"The sweep container in {namespace}/{pod} did not start in {timeout:.0f} s."
            )
        time.sleep(poll)


def _ensure_sweep_container(
    pod: str,
    namespace: str,
    *,
    container: str,
    image: str,
    context: str | None,
    timeout: float,
    poll: float,
) -> str:
    """Ensure an ephemeral debug container is running in the pod, creating one if needed."""
    state = _container_state(pod, container, namespace, context)
    if "running" in state:
        return container
    active_container = container
    if "terminated" in state:
        active_container = f"{container}-{uuid.uuid4().hex[:6]}"

    started = _kubectl(
        [
            "debug",
            f"pod/{pod}",
            "-n",
            namespace,
            "--profile=restricted",
            f"--image={image}",
            f"--container={active_container}",
            "--",
            "sleep",
            "3600",
        ],
        context=context,
    )
    if started.returncode != 0:
        raise GatewayTuneError(
            f"Cannot attach the sweep container to {namespace}/{pod}: {_detail(started)}"
        )
    _wait_for_running(pod, active_container, namespace, context, timeout, poll)
    return active_container


def measure_in_gateway_pod(
    spec: dict[str, Any],
    *,
    namespace: str,
    deployment: str,
    context: str | None = None,
    timeout: float | None = None,
    image: str = DEFAULT_GATEWAY_TUNE_IMAGE,
    poll_seconds: float = 2.0,
    container: str = "gateway-tune-runner",
) -> list[dict[str, Any]]:
    """Run the sweep in an ephemeral container attached to a gateway pod; return its results.

    Reuses an active debug container running ``sleep`` and pipes the sweep script via stdin
    to avoid argv character length limits on large prompts.
    """
    pod = _gateway_pod(namespace, deployment, context)
    active_container = _ensure_sweep_container(
        pod,
        namespace,
        container=container,
        image=image,
        context=context,
        timeout=timeout or 600.0,
        poll=poll_seconds,
    )
    script = bench_script(spec)
    exec_res = _kubectl(
        [
            "exec",
            "-i",
            pod,
            "-n",
            namespace,
            "-c",
            active_container,
            "--",
            "python",
            "-",
        ],
        context=context,
        timeout=timeout or 600.0,
        input_data=script,
    )
    if exec_res.returncode != 0:
        raise GatewayTuneError(f"The sweep failed in {namespace}/{pod}: {_detail(exec_res)}")
    lines = exec_res.stdout.strip().splitlines()
    try:
        results: list[dict[str, Any]] = json.loads(lines[-1])
    except (IndexError, ValueError) as exc:
        raise GatewayTuneError(f"The sweep in {namespace}/{pod} returned no results.") from exc
    return results


def _tuned(dep: dict[str, Any], result: dict[str, Any], gpus: list[GpuInfo]) -> DeploymentTune:
    capacity = [LevelResult(**lvl) for lvl in result.get("capacity") or []]
    cost = LevelResult(**result["cost"]) if result.get("cost") else None
    best = max(
        (lvl for lvl in capacity if lvl.tokens_per_second > 0),
        key=lambda lvl: lvl.tokens_per_second,
        default=None,
    )
    tokens_per_request = cost.tokens_per_request if cost else None
    capacity_tps = best.tokens_per_second if best else 0.0
    engine = result.get("engine") or {}
    return DeploymentTune(
        deployment_id=dep["deployment_id"],
        backend=backend_label(dep["api_base"]),
        model=dep["model"],
        api_base=dep["api_base"],
        current_weight=dep["weight"],
        engine=engine.get("engine", "unknown"),
        kv_cache_tokens=engine.get("kv_cache_tokens"),
        gpus=gpus,
        capacity=capacity,
        cost=cost,
        best_concurrency=best.concurrency if best else None,
        capacity_tokens_per_second=round(capacity_tps, 2),
        cost_tokens_per_request=round(tokens_per_request, 2) if tokens_per_request else None,
        requests_per_second=(
            round(capacity_tps / tokens_per_request, 4) if tokens_per_request else 0.0
        ),
    )


def tune_pool(
    *,
    gateway_url: str,
    allow_private: bool,
    api_key: str | None,
    model_group: str,
    levels: list[int],
    rounds: int,
    prompt_tokens: int,
    max_tokens: int,
    request_timeout: float,
    namespace: str,
    deployment: str,
    context: str | None = None,
    image: str = DEFAULT_GATEWAY_TUNE_IMAGE,
    on_deployment: Callable[[dict[str, Any]], None] | None = None,
    overrides: dict[str, int] | None = None,
    concurrency_overrides: dict[str, int] | None = None,
) -> TuneReport:
    """Measure each deployment of ``model_group``, one at a time, and recommend weights."""
    model_info = fetch_model_info(gateway_url, allow_private, api_key)
    if not model_info:
        raise GatewayTuneError(f"The gateway at {gateway_url} listed no deployments.")
    pool = discover_pool(model_info, model_group)
    if not pool:
        raise GatewayTuneError(f"The gateway has no deployments for '{model_group}'.")

    # Each capacity level's workers, and then the cost pass, send `rounds` requests in turn.
    exec_timeout = request_timeout * rounds * (len(levels) + 1) + 60
    tuned: list[DeploymentTune] = []
    for dep in pool:
        if on_deployment:
            on_deployment(dep)
        tokens = deployment_prompt_tokens(prompt_tokens, dep["max_input_tokens"])
        spec = {
            "deployments": [{k: dep[k] for k in ("deployment_id", "model", "api_base")}],
            "levels": levels,
            "rounds": rounds,
            "prompt": review_prompt(tokens),
            "max_tokens": max_tokens,
            "timeout": request_timeout,
        }
        result = measure_in_gateway_pod(
            spec,
            namespace=namespace,
            deployment=deployment,
            context=context,
            timeout=exec_timeout,
            image=image,
        )
        tuned.append(
            _tuned(dep, result[0], deployment_gpus(dep["api_base"], context)).model_copy(
                update={"prompt_tokens": tokens}
            )
        )

    measured_rates = {t.deployment_id: t.requests_per_second for t in tuned}
    if any(rate > 0 for rate in measured_rates.values()):
        weights = recommend_weights(measured_rates, overrides=overrides, deployments=tuned)
    else:
        weights = calculate_hardware_weights(tuned, overrides=overrides)
    concurrencies = calculate_hardware_concurrency(tuned, overrides=concurrency_overrides)
    return TuneReport(
        model_group=model_group,
        prompt_tokens=prompt_tokens,
        max_tokens=max_tokens,
        deployments=[
            t.model_copy(
                update={
                    "recommended_weight": weights[t.deployment_id],
                    "recommended_concurrency": concurrencies.get(t.deployment_id),
                }
            )
            for t in tuned
        ],
    )


__all__ = [
    "DeploymentTune",
    "GatewayTuneError",
    "GpuInfo",
    "LevelResult",
    "TuneReport",
    "backend_label",
    "backend_pods",
    "bench_script",
    "calculate_hardware_concurrency",
    "calculate_hardware_weights",
    "deployment_gpus",
    "deployment_prompt_tokens",
    "discover_pool",
    "gpu_bandwidth_gbps",
    "gpu_inventory",
    "measure_in_gateway_pod",
    "recommend_weights",
    "review_page_tokens",
    "review_prompt",
    "tune_pool",
]
