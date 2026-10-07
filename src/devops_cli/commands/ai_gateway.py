"""LLM Gateway and distributed model router CLI commands."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from devops_cli.ai.client import AICredentialsError
from devops_cli.ai.gateway import GatewayRoute, GatewayRouter
from devops_cli.ai.gateway_tune import (
    GatewayTuneError,
    GpuInfo,
    TuneReport,
    review_page_tokens,
    tune_pool,
)
from devops_cli.ai.pool_load import PoolLoad, pool_load, prometheus_query
from devops_cli.ai.run_store import Mechanism, record_run
from devops_cli.commands.ai_runs import announce_run
from devops_cli.config.constants import CONST_AI_GATEWAY_VIRTUAL_MODELS, CONST_OUTPUT_FORMAT_TABLE
from devops_cli.config.defaults import (
    DEFAULT_AI_GATEWAY_DEPLOYMENT,
    DEFAULT_AI_GATEWAY_HEALTH_TIMEOUT_SECONDS,
    DEFAULT_AI_GATEWAY_SERVICE,
    DEFAULT_GATEWAY_TUNE_CONCURRENCY,
    DEFAULT_GATEWAY_TUNE_IMAGE,
    DEFAULT_GATEWAY_TUNE_MAX_TOKENS,
    DEFAULT_GATEWAY_TUNE_MODEL_GROUP,
    DEFAULT_GATEWAY_TUNE_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_GATEWAY_TUNE_ROUNDS,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_LLM_NAMESPACE,
    DEFAULT_POOL_LOAD_WINDOW,
)
from devops_cli.config.settings import get_ai_api_key, load_settings, save_settings
from devops_cli.core.cli import new_typer
from devops_cli.core.validation import validate_url_egress
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.http.validation import validate_service_url
from devops_cli.k8s.context import resolve_context
from devops_cli.k8s.node_port import NodePortSpec, ServiceNotReachableError, node_port_address
from devops_cli.lang import MESSAGES
from devops_cli.output import (
    print_error,
    print_info,
    print_section,
    print_success,
    print_table,
    print_warning,
)
from devops_cli.output.serialization import emit_serialized, normalize_format
from devops_cli.security.sanitizer import mask_secrets

app = new_typer(
    help="LLM Gateway and distributed inference mesh management.",
    no_args_is_help=True,
)


def _render_routes_table(routes: list[GatewayRoute]) -> None:
    """Render table of virtual model routes."""
    headers = ["Virtual Model", "Target Model", "Backend Type", "Backend URL", "Status"]
    rows = [
        [
            r.virtual_model,
            r.target_model,
            r.backend_type,
            r.backend_url,
            "✓ healthy" if r.healthy else "✗ degraded",
        ]
        for r in routes
    ]
    print_table(columns=headers, rows=rows, title="LLM Gateway Virtual Model Routes")


def _render_scale_table(outcome: dict[str, Any]) -> None:
    """Render scale parameters for inference backend."""
    print_section("vLLM Inference Scaling Configuration")
    rows = [
        ["Model", str(outcome.get("model", ""))],
        ["Replicas", str(outcome.get("replicas", 1))],
        ["Total VRAM (GB)", str(outcome.get("total_vram_gb", 0))],
        ["Serving Status", str(outcome.get("status", ""))],
    ]
    if "tensor_parallel_size" in outcome:
        rows.insert(2, ["Tensor Parallel Size", str(outcome["tensor_parallel_size"])])
    if "max_model_len" in outcome:
        rows.insert(3, ["Max Model Length", str(outcome["max_model_len"])])
    print_table(
        columns=["Property", "Configured Value"],
        rows=rows,
        title="vLLM Scale Parameters",
    )


@app.command("status")
def status_cmd(
    gateway_url: Annotated[
        str | None,
        typer.Option("--gateway-url", "-u", help="Optional gateway base URL override."),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option("--provider", "-p", help="Gateway provider: litellm or portkey."),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """Probe LLM Gateway health, latency, and circuit breaker metrics."""
    settings = load_settings()
    router = GatewayRouter(settings.ai, provider=provider)
    result = router.probe_gateway(gateway_url, provider=provider)

    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(result.model_dump(), resolved)
        return

    print_section("LLM Gateway Status")
    status_msg = f"Gateway URL: {result.gateway_url}\nHealthy: {result.healthy}\nCircuit Breaker: {result.circuit_breaker_tripped}"
    if result.healthy:
        print_success(status_msg)
    else:
        print_error(status_msg)

    if result.active_routes:
        _render_routes_table(result.active_routes)


@app.command("routes")
def routes_cmd(
    gateway_url: Annotated[
        str | None,
        typer.Option("--gateway-url", "-u", help="Optional gateway base URL override."),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option("--provider", "-p", help="Gateway provider: litellm or portkey."),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """List registered virtual models and target backend inference instances."""
    settings = load_settings()
    router = GatewayRouter(settings.ai, provider=provider, api_key=get_ai_api_key(settings))
    try:
        routes = router.list_routes(gateway_url or router.gateway_url)
    except AICredentialsError as exc:
        print_error(str(exc))
        raise typer.Exit(1) from exc

    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized([r.model_dump() for r in routes], resolved)
        return

    _render_routes_table(routes)


def _probe_gateway_liveliness_and_models(
    base_url: str,
    headers: dict[str, str],
    timeout: float,
) -> None:
    """Probe gateway liveliness and model info endpoints before configuring connection."""
    import httpx2

    try:
        with httpx2.Client(timeout=timeout) as client:
            live_resp = client.get(f"{base_url}/health/liveliness")
            if live_resp.status_code >= 400:
                print_error(
                    f"The LLM gateway at {base_url} is not live: HTTP {live_resp.status_code}"
                )
                raise typer.Exit(code=1)
            model_resp = client.get(f"{base_url}/model/info", headers=headers)
            if model_resp.status_code >= 400:
                print_error(
                    f"The LLM gateway at {base_url} rejected model info query: HTTP {model_resp.status_code}"
                )
                raise typer.Exit(code=1)
    except (httpx2.HTTPError, OSError) as exc:
        print_error(f"The LLM gateway at {base_url} does not answer: {str(exc)[:256]}")
        raise typer.Exit(code=1) from exc


@app.command("connect")
def connect_cmd(
    context: Annotated[
        str | None,
        typer.Option("--context", help="Kubernetes context to query (defaults to current)."),
    ] = None,
    namespace: Annotated[
        str,
        typer.Option("--namespace", "-n", help="Kubernetes namespace."),
    ] = DEFAULT_LLM_NAMESPACE,
    service: Annotated[
        str,
        typer.Option("--service", help="Name of the Service running the gateway."),
    ] = DEFAULT_AI_GATEWAY_SERVICE,
    timeout: Annotated[
        float,
        typer.Option("--timeout", help="Health probe timeout in seconds."),
    ] = DEFAULT_AI_GATEWAY_HEALTH_TIMEOUT_SECONDS,
) -> None:
    """Find the cluster's LLM gateway NodePort, verify it answers, and configure LAN review calls."""
    spec = NodePortSpec(
        what="LLM gateway",
        port=4000,
        port_name="http",
        port_label="HTTP",
        manifest="k8s/llm/gateway/service.yaml",
    )
    try:
        host, port = node_port_address(context, namespace, service, spec)
    except ServiceNotReachableError as exc:
        print_error(f"Cannot find the LLM gateway: {exc.message}", prefix=False)
        raise typer.Exit(code=1) from exc

    base_url = f"http://{host}:{port}"
    node_port_url = f"{base_url}/v1"
    validate_url_egress(base_url, purpose="AI gateway", allow_private=True)

    settings = load_settings()
    api_key = get_ai_api_key(settings)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    _probe_gateway_liveliness_and_models(base_url, headers, timeout)

    settings.ai.gateway_url = node_port_url
    settings.ai.allow_private_network = True
    save_settings(settings)
    print_success(f"Connected to LLM gateway at {node_port_url} (LAN path enabled).")


@app.command("failover")
def failover_cmd(
    virtual_model: Annotated[
        str,
        typer.Argument(
            help=f"Virtual model alias to trigger failover for ({', '.join(CONST_AI_GATEWAY_VIRTUAL_MODELS)})."
        ),
    ],
    simulate: Annotated[
        bool,
        typer.Option(
            "--simulate/--no-simulate",
            help="Simulate failover without altering active routing table.",
        ),
    ] = True,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Bypass model capability tier minimum checks during failover.",
        ),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """Trigger or test circuit-breaker failover of a virtual model to secondary backends."""
    settings = load_settings()
    router = GatewayRouter(settings.ai)
    try:
        outcome = router.trigger_failover(virtual_model, simulate=simulate, force=force)
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1) from exc

    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(outcome, resolved)
        return

    print_section("Model Failover Execution")
    print_info(
        f"Virtual Model: {outcome['virtual_model']}\n"
        f"Fallback Target: {outcome['fallback_target']}\n"
        f"Circuit Breaker Tripped: {outcome['circuit_breaker_tripped']}\n"
        f"Simulated: {outcome['simulated']}"
    )
    print_success(f"Failover status: {outcome['status']}")


@app.command("scale")
def scale_cmd(
    replicas: Annotated[
        int | None,
        typer.Option("--replicas", "-r", help="Replica count for backend deployment."),
    ] = None,
    tensor_parallel_size: Annotated[
        int | None,
        typer.Option(
            "--tensor-parallel-size", "-tp", help="Tensor Parallelism degree for vLLM (e.g. 2)."
        ),
    ] = None,
    apply: Annotated[
        bool,
        typer.Option(
            "--apply/--no-apply",
            help="Apply replica scale mutation to Kubernetes deployment via kubectl.",
        ),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """Inspect or scale vLLM inference backend serving configuration."""
    settings = load_settings()
    router = GatewayRouter(settings.ai)
    outcome = router.scale_vllm(
        replicas=replicas, tensor_parallel_size=tensor_parallel_size, apply=apply
    )

    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(outcome, resolved)
        return

    _render_scale_table(outcome)


@app.command("probe-backend")
def probe_backend_cmd(
    backend: Annotated[
        str,
        typer.Argument(help="Backend to probe: vllm or ollama."),
    ],
    backend_url: Annotated[
        str | None,
        typer.Option("--backend-url", "-u", help="Optional backend base URL override."),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """Directly probe health and latency of an inference backend."""
    settings = load_settings()
    router = GatewayRouter(settings.ai)
    result = router.probe_backend(backend, backend_url=backend_url)

    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(result, resolved)
        return

    print_section(f"Inference Backend Health: {result['backend_type']}")
    msg = f"URL: {result['url']}\nHealthy: {result['healthy']}\nLatency: {result['latency_ms']}ms"
    if result["healthy"]:
        print_success(msg)
    else:
        print_error(msg)


def _parse_levels(raw: str) -> list[int]:
    """Parse comma-separated concurrency levels, e.g. `1,4,8`."""
    try:
        levels = sorted({int(part) for part in raw.split(",") if part.strip()})
    except ValueError as exc:
        raise typer.BadParameter(f"'{raw}' is not a comma-separated list of integers.") from exc
    if not levels or levels[0] < 1:
        raise typer.BadParameter("Concurrency levels must be positive integers.")
    return levels


def _describe_gpus(gpus: list[GpuInfo]) -> str:
    """Summarise GPUs as e.g. `2x RTX 3090 24 GB 936 GB/s`, grouping identical models."""
    counts: dict[tuple[str, int, float | None], int] = {}
    for gpu in gpus:
        key = (
            gpu.name.removeprefix("NVIDIA ").removeprefix("GeForce "),
            gpu.memory_mib,
            gpu.bandwidth_gbps,
        )
        counts[key] = counts.get(key, 0) + 1
    parts = [
        f"{n}x {name} {mib // 1024} GB" + (f" {bw:g} GB/s" if bw else "")
        for (name, mib, bw), n in counts.items()
    ]
    return ", ".join(parts) or "-"


def _render_tune_report(report: TuneReport) -> None:
    """Render hardware, capacity, cost and recommended weight per deployment."""
    headers = [
        "Deployment",
        "Engine",
        "GPUs",
        "Prompt tok",
        "Capacity tok/s",
        "Tokens/request",
        "Est. req/s",
        "Weight",
        "Recommended",
        "Max Parallel",
    ]
    rows = [
        [
            dep.backend,
            dep.engine + (f" ({dep.kv_cache_tokens:,} KV)" if dep.kv_cache_tokens else ""),
            _describe_gpus(dep.gpus),
            f"{dep.prompt_tokens:,}",
            f"{dep.capacity_tokens_per_second:.0f} @ {dep.best_concurrency}"
            if dep.best_concurrency
            else "-",
            "-" if dep.cost_tokens_per_request is None else f"{dep.cost_tokens_per_request:.0f}",
            f"{dep.requests_per_second:.2f}",
            "-" if dep.current_weight is None else f"{dep.current_weight:g}",
            str(dep.recommended_weight),
            "-" if dep.recommended_concurrency is None else str(dep.recommended_concurrency),
        ]
        for dep in report.deployments
    ]
    print_table(columns=headers, rows=rows, title=f"Gateway Tuning: {report.model_group}")
    for dep in report.deployments:
        levels = [*dep.capacity, *([dep.cost] if dep.cost else [])]
        failed = [lvl for lvl in levels if lvl.errors]
        if failed:
            print_error(
                f"{dep.backend}: {sum(lvl.errors for lvl in failed)} request(s) failed; "
                f"last error: {failed[-1].last_error}"
            )
    print_info(
        "Capacity is fixed-length tokens/s at the best concurrency; tokens/request is the "
        "model's natural reply length on a review-style prompt. Read-only: nothing was changed. "
        "To apply, set litellm_params.weight on each deployment in the gateway configuration.",
        prefix=False,
    )


@app.command("tune")
def tune_cmd(
    model: Annotated[
        str, typer.Option("--model", "-m", help="Gateway model group to measure.")
    ] = DEFAULT_GATEWAY_TUNE_MODEL_GROUP,
    concurrency: Annotated[
        str,
        typer.Option("--concurrency", "-c", help="Comma-separated concurrency levels to measure."),
    ] = DEFAULT_GATEWAY_TUNE_CONCURRENCY,
    rounds: Annotated[
        int, typer.Option("--rounds", help="Requests per worker at each concurrency level.")
    ] = DEFAULT_GATEWAY_TUNE_ROUNDS,
    prompt_tokens: Annotated[
        int | None,
        typer.Option(
            "--prompt-tokens",
            help="Prompt size in tokens (default: one review page for the analysis task).",
        ),
    ] = None,
    max_tokens: Annotated[
        int, typer.Option("--max-tokens", help="Completion tokens requested per call.")
    ] = DEFAULT_GATEWAY_TUNE_MAX_TOKENS,
    gateway_url: Annotated[
        str | None,
        typer.Option("--gateway-url", "-u", help="Optional gateway base URL override."),
    ] = None,
    namespace: Annotated[
        str, typer.Option("--namespace", "-n", help="Namespace of the gateway deployment.")
    ] = DEFAULT_LLM_NAMESPACE,
    deployment: Annotated[
        str, typer.Option("--deployment", help="Gateway deployment to run the sweep in.")
    ] = DEFAULT_AI_GATEWAY_DEPLOYMENT,
    context: Annotated[
        str | None, typer.Option("--context", help="Kubernetes context override.")
    ] = None,
    image: Annotated[
        str, typer.Option("--image", help="Python image for the sweep container.")
    ] = DEFAULT_GATEWAY_TUNE_IMAGE,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """Measure each deployment of a gateway model group and recommend routing weights.

    Each deployment is measured on its own from an ephemeral container attached to the gateway
    pod, since the backends admit only the gateway. Read-only: the gateway configuration is not
    changed.
    """
    levels = _parse_levels(concurrency)
    settings = load_settings()
    router = GatewayRouter(settings.ai)
    resolved = normalize_format(output_format)
    as_table = resolved == CONST_OUTPUT_FORMAT_TABLE

    def announce(dep: dict[str, Any]) -> None:
        if as_table:
            print_info(f"[dim]Measuring {dep['model']} at {dep['api_base']}...[/dim]", prefix=False)

    try:
        report = tune_pool(
            gateway_url=gateway_url or router.gateway_url,
            allow_private=settings.ai.allow_private_network,
            api_key=get_ai_api_key(settings),
            model_group=model,
            levels=levels,
            rounds=max(1, rounds),
            prompt_tokens=max(
                1,
                prompt_tokens
                or review_page_tokens(settings.ai.for_task("analysis").context_window),
            ),
            max_tokens=max(1, max_tokens),
            request_timeout=DEFAULT_GATEWAY_TUNE_REQUEST_TIMEOUT_SECONDS,
            namespace=namespace,
            deployment=deployment,
            context=resolve_context(context),
            image=image,
            on_deployment=announce,
            overrides=settings.ai.gateway_weights,
            concurrency_overrides=settings.ai.gateway_concurrency,
        )
    except (AICredentialsError, GatewayTuneError) as exc:
        print_error(str(exc))
        raise typer.Exit(1) from exc

    saved = record_run(
        Mechanism.GATEWAY_TUNE,
        setup={
            "levels": levels,
            "rounds": max(1, rounds),
            "prompt_tokens": report.prompt_tokens,
            "max_tokens": report.max_tokens,
            "pool": sorted(
                (
                    {
                        "backend": d.backend,
                        "model": d.model,
                        "weight": d.current_weight,
                        "engine": d.engine,
                        "gpus": [gpu.name for gpu in d.gpus],
                    }
                    for d in report.deployments
                ),
                key=lambda d: (d["backend"], d["model"]),
            ),
        },
        subject={"model_group": report.model_group},
        results=report.model_dump(mode="json"),
    )
    if not as_table:
        emit_serialized(report.model_dump(), resolved)
    else:
        _render_tune_report(report)
    announce_run(saved, to_stderr=not as_table)


def _share(value: float | None) -> str:
    return "—" if value is None else f"{value:.0%}"


def _render_pool_load(load: PoolLoad) -> None:
    """Show each backend's and GPU's load, busiest first."""
    print_section(f" LLM Pool Load, Last {load.window} ", style="bold cyan")
    backends = sorted(load.backends, key=lambda b: -b.mean_in_flight)
    print_table(
        title="Backends",
        columns=[
            ("Backend", "cyan"),
            ("Requests", "right"),
            ("Failures", "right"),
            ("Mean in Flight", "right"),
            ("Busy (vLLM)", "right"),
            ("Queue Mean / Max (vLLM)", "right"),
        ],
        rows=[
            [
                b.backend,
                f"{b.requests:.0f}",
                f"{b.failures:.0f}",
                f"{b.mean_in_flight:.2f}",
                _share(b.busy_share),
                "—"
                if b.mean_waiting is None
                else f"{b.mean_waiting:.1f} / {b.max_waiting or 0:.0f}",
            ]
            for b in backends
        ],
    )
    if load.gpus:
        print_table(
            title="GPUs",
            columns=[
                ("Host", "cyan"),
                ("GPU", "right"),
                ("Model", "magenta"),
                ("Mean Utilisation", "right"),
                ("Peak Memory (MiB)", "right"),
            ],
            rows=[
                [g.host, g.gpu, g.model, f"{g.mean_utilisation:.0f}%", f"{g.peak_memory_mib:.0f}"]
                for g in load.gpus
            ],
        )


@app.command("load")
def load_cmd(
    window: Annotated[
        str,
        typer.Option("--window", "-w", help="How far back to look, e.g. 30m, 2h or 1d."),
    ] = DEFAULT_POOL_LOAD_WINDOW,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """Report how busy each LLM backend and GPU was over a window, from Prometheus.

    Mean in flight is the gateway's call seconds per second on each deployment, so it covers the
    Ollama nodes too; busy share and queue come from the vLLM servers themselves.
    """
    settings = load_settings()
    if not settings.prometheus.url:
        print_error(MESSAGES.prometheus.url_not_configured, prefix=False)
        raise typer.Exit(1)
    try:
        validate_service_url(
            settings.prometheus.url, "Prometheus", allow=settings.ai.allow_private_network
        )
        query = prometheus_query(settings.prometheus.url.rstrip("/"), DEFAULT_HTTP_TIMEOUT_SECONDS)
        load = pool_load(query, window)
    except (ValueError, DevOpsCLIError) as exc:
        print_error(mask_secrets(str(exc)), prefix=False)
        raise typer.Exit(1) from exc

    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(load.model_dump(), resolved)
        return
    if not load.backends and not load.gpus:
        print_warning(
            f"No LLM pool or GPU metrics in Prometheus over the last {window}; check that the "
            "gateway, vLLM and DCGM exporter monitors are applied (k8s/monitoring)."
        )
        return
    _render_pool_load(load)
