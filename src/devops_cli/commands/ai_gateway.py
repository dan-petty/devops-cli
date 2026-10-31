"""LLM Gateway and distributed model router CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import httpx2
import typer

from devops_cli.ai.client.models import AICredentialsError
from devops_cli.ai.gateway import GatewayRoute, GatewayRouter, probe_gateway_liveliness_and_models
from devops_cli.ai.gateway_tune import (
    GatewayTuneError,
    GpuInfo,
    TuneReport,
    tune_pool,
)
from devops_cli.ai.pool_load import PoolLoad, pool_load, prometheus_query
from devops_cli.ai.run_store import Mechanism, record_run
from devops_cli.commands.ai_runs import announce_run
from devops_cli.config.constants import (
    CONST_AI_GATEWAY_VIRTUAL_MODELS,
    CONST_CAPABILITY_PROBE_NAMES,
    CONST_OUTPUT_FORMAT_TABLE,
)
from devops_cli.config.defaults import (
    DEFAULT_AI_GATEWAY_DEPLOYMENT,
    DEFAULT_AI_GATEWAY_HEALTH_TIMEOUT_SECONDS,
    DEFAULT_AI_GATEWAY_SERVICE,
    DEFAULT_AI_GATEWAY_URL,
    DEFAULT_GATEWAY_TUNE_CONCURRENCY,
    DEFAULT_GATEWAY_TUNE_IMAGE,
    DEFAULT_GATEWAY_TUNE_MAX_TOKENS,
    DEFAULT_GATEWAY_TUNE_MODEL_GROUP,
    DEFAULT_GATEWAY_TUNE_PROMPT_TOKENS,
    DEFAULT_GATEWAY_TUNE_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_GATEWAY_TUNE_ROUNDS,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_LLM_NAMESPACE,
    DEFAULT_POOL_LOAD_WINDOW,
)
from devops_cli.config.settings import get_ai_api_key, load_settings, save_settings
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.dry_run.requests import render_request_plan
from devops_cli.exceptions import DevOpsCLIError, SSRFBlockedError, ValidationError
from devops_cli.http.egress import configured_level
from devops_cli.k8s.context import resolve_context
from devops_cli.k8s.node_port import NodePortSpec, ServiceNotReachableError, node_port_address
from devops_cli.lang import HELP, MESSAGES
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


@dry_run_class("request-plan")
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
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Probe LLM Gateway health, latency, and circuit breaker metrics."""
    if dry_run or is_dry_run():
        from devops_cli.ai.ai_plans import plan_ai_gateway_status
        from devops_cli.ai.gateway import GatewayStatus

        planned = plan_ai_gateway_status(gateway_url)
        resolved = normalize_format(output_format)
        if resolved != CONST_OUTPUT_FORMAT_TABLE:
            settings = load_settings()
            effective_url = gateway_url or settings.ai.gateway_url or DEFAULT_AI_GATEWAY_URL
            res = GatewayStatus(
                healthy=True,
                gateway_url=effective_url,
                dry_run=True,
                requests=[r.__dict__ for r in planned],
            )
            emit_serialized(res.model_dump(), resolved)
            return
        render_request_plan("Plan for LLM gateway status", planned)
        return

    settings = load_settings()
    router = GatewayRouter(settings.ai, provider=provider)
    result = router.probe_gateway(gateway_url, provider=provider)

    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(result.model_dump(), resolved)
        return

    print_section("LLM Gateway Status")
    status_msg = f"Gateway URL: {result.gateway_url}\nHealthy: {result.healthy}\nCircuit Breaker: {result.circuit_breaker_tripped}"
    if result.failover_routes:
        status_msg += (
            f"\nFailover routes: {', '.join(result.failover_routes)}"
            "\nTo restore the default routes, run `devops ai gateway failover --reset`."
        )
    if not result.healthy:
        print_error(status_msg)
    elif result.failover_routes:
        print_warning(status_msg)
    else:
        print_success(status_msg)

    if result.active_routes:
        _render_routes_table(result.active_routes)


@dry_run_class("request-plan")
@app.command("routes")
def routes_cmd(
    gateway_url: Annotated[
        str | None,
        typer.Option(
            "--gateway-url",
            "-u",
            help="Optional gateway base URL override. Only the configured gateway gets the AI API key.",
        ),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option("--provider", "-p", help="Gateway provider: litellm or portkey."),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """List registered virtual models and target backend inference instances."""
    if dry_run or is_dry_run():
        from devops_cli.ai.ai_plans import plan_ai_gateway_routes

        planned = plan_ai_gateway_routes(gateway_url)
        resolved = normalize_format(output_format)
        if resolved != CONST_OUTPUT_FORMAT_TABLE:
            emit_serialized({"dry_run": True, "requests": [r.__dict__ for r in planned]}, resolved)
            return
        render_request_plan("Plan for LLM gateway routes", planned)
        return

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


@dry_run_class("request-plan")
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
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Find the cluster's LLM gateway NodePort, verify it answers, and configure LAN review calls."""
    if dry_run or is_dry_run():
        from devops_cli.ai.ai_plans import plan_ai_gateway_connect

        planned = plan_ai_gateway_connect(context=context, namespace=namespace, service=service)
        render_request_plan("Plan for connecting to LLM gateway", planned)
        return

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

    base_url = str(httpx2.URL(scheme="http", host=host, port=port))
    node_port_url = f"{base_url}/v1"

    settings = load_settings()
    api_key = get_ai_api_key(settings)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    try:
        probe_gateway_liveliness_and_models(base_url, headers, timeout)
    except ValidationError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1) from exc
    except (httpx2.HTTPError, OSError, SSRFBlockedError) as exc:
        print_error(f"The LLM gateway at {base_url} does not answer: {str(exc)[:256]}")
        raise typer.Exit(code=1) from exc

    settings.ai.gateway_url = node_port_url
    settings.ai.allow_private_network = True
    save_settings(settings)
    print_success(f"Connected to LLM gateway at {node_port_url} (LAN path enabled).")


@dry_run_class("no-external-request")
@app.command("failover")
def failover_cmd(
    virtual_model: Annotated[
        str | None,
        typer.Argument(
            help=f"Virtual model alias to trigger failover for ({', '.join(CONST_AI_GATEWAY_VIRTUAL_MODELS)}). Give none with --reset."
        ),
    ] = None,
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
    reset: Annotated[
        bool,
        typer.Option(
            "--reset",
            help="Restore the default route of every virtual model and clear the circuit breaker. --simulate and --force apply only to a failover.",
        ),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Trigger or test circuit-breaker failover of a virtual model to secondary backends, or restore the default routes with --reset."""
    if reset == bool(virtual_model):
        raise typer.BadParameter("Give a virtual model or --reset, but not both.")

    settings = load_settings()
    router = GatewayRouter(settings.ai)
    resolved = normalize_format(output_format)
    if dry_run or is_dry_run():
        from devops_cli.ai.gateway import _failover_virtual_models

        if not virtual_model:
            outcome = {
                "status": "dry_run",
                "restored_routes": _failover_virtual_models(router._active_routes),
                "circuit_breaker_tripped": False,
                "dry_run": True,
            }
            _report_failover_reset(outcome, resolved)
            return
        outcome = router.trigger_failover(virtual_model, simulate=True, force=force)
        outcome["dry_run"] = True
        if resolved != CONST_OUTPUT_FORMAT_TABLE:
            emit_serialized(outcome, resolved)
            return
        print_section("Model Failover Execution")
        print_info(
            f"Virtual Model: {outcome['virtual_model']}\n"
            f"Fallback Target: {outcome['fallback_target']}\n"
            f"Circuit Breaker Tripped: {outcome['circuit_breaker_tripped']}\n"
            "Simulated: True (dry run)"
        )
        print_success(f"Failover status: {outcome['status']}")
        return
    if not virtual_model:
        _report_failover_reset(router.reset_failover(), resolved)
        return
    try:
        outcome = router.trigger_failover(virtual_model, simulate=simulate, force=force)
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(code=1) from exc

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


def _report_failover_reset(outcome: dict[str, Any], resolved_format: str) -> None:
    """Show the virtual models whose failover route a reset restored."""
    if resolved_format != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(outcome, resolved_format)
        return
    print_section("Model Failover Reset")
    restored = outcome["restored_routes"]
    print_success(
        f"Restored the default routes. Routes that were in failover: {', '.join(restored)}."
        if restored
        else "Restored the default routes. No route was in failover."
    )


@dry_run_class("request-plan")
@app.command("probe-backend")
def probe_backend_cmd(
    backend: Annotated[
        str,
        typer.Argument(help="Backend to probe (e.g. ollama)."),
    ],
    backend_url: Annotated[
        str | None,
        typer.Option("--backend-url", "-u", help="Optional backend base URL override."),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Directly probe health and latency of an inference backend."""
    if dry_run or is_dry_run():
        from devops_cli.ai.ai_plans import plan_ai_gateway_probe_backend

        planned = plan_ai_gateway_probe_backend(backend, backend_url=backend_url)
        resolved = normalize_format(output_format)
        if resolved != CONST_OUTPUT_FORMAT_TABLE:
            emit_serialized(
                {
                    "backend_type": backend,
                    "url": backend_url or f"http://{backend}.local",
                    "healthy": True,
                    "latency_ms": 0.0,
                    "dry_run": True,
                    "requests": [r.__dict__ for r in planned],
                },
                resolved,
            )
            return
        render_request_plan(f"Plan for probing inference backend '{backend}'", planned)
        return

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
        "Capabilities",
    ]
    rows = [
        [
            dep.backend,
            dep.engine + (f" ({dep.kv_cache_tokens:,} KV)" if dep.kv_cache_tokens else ""),
            _describe_gpus(dep.gpus),
            f"{dep.prompt_tokens:,}",
            f"{dep.capacity_tokens_per_second:.0f} @ {dep.best_concurrency}"
            if dep.best_concurrency
            else (
                f"{dep.capacity_tokens_per_second:.0f}" if dep.capacity_tokens_per_second else "-"
            ),
            "-" if dep.cost_tokens_per_request is None else f"{dep.cost_tokens_per_request:.0f}",
            f"{dep.requests_per_second:.2f}",
            "-" if dep.current_weight is None else f"{dep.current_weight:g}",
            str(dep.recommended_weight),
            "-" if dep.recommended_concurrency is None else str(dep.recommended_concurrency),
            dep.capabilities.summary_label,
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


@dry_run_class("request-plan")
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
        int,
        typer.Option(
            "--prompt-tokens",
            help="Prompt size in tokens.",
        ),
    ] = DEFAULT_GATEWAY_TUNE_PROMPT_TOKENS,
    max_tokens: Annotated[
        int, typer.Option("--max-tokens", help="Completion tokens requested per call.")
    ] = DEFAULT_GATEWAY_TUNE_MAX_TOKENS,
    gateway_url: Annotated[
        str | None,
        typer.Option(
            "--gateway-url",
            "-u",
            help="Optional gateway base URL override. Only the configured gateway gets the AI API key.",
        ),
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
    estimate: Annotated[
        bool,
        typer.Option(
            "--estimate",
            help="Estimate capacity from prior measurements and GPU memory bandwidth without sending load.",
        ),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Measure each deployment of a gateway model group and recommend routing weights.

    Each deployment is measured on its own from an ephemeral container attached to the gateway
    pod, since the backends admit only the gateway. Read-only: the gateway configuration is not
    changed.
    """
    if dry_run or is_dry_run():
        from devops_cli.ai.ai_plans import plan_ai_gateway_tune

        planned = plan_ai_gateway_tune(model=model, gateway_url=gateway_url)
        resolved = normalize_format(output_format)
        if resolved != CONST_OUTPUT_FORMAT_TABLE:
            rep = TuneReport(
                model_group=model,
                prompt_tokens=prompt_tokens
                if prompt_tokens is not None
                else DEFAULT_GATEWAY_TUNE_PROMPT_TOKENS,
                max_tokens=max_tokens,
                deployments=[],
                dry_run=True,
                requests=[r.__dict__ for r in planned],
            )
            emit_serialized(rep.model_dump(), resolved)
            return
        render_request_plan(f"Plan for tuning LLM gateway pool for '{model}'", planned)
        return

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
                prompt_tokens if prompt_tokens is not None else DEFAULT_GATEWAY_TUNE_PROMPT_TOKENS,
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
            estimate=estimate,
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
            "estimate": estimate,
            "probes": list(CONST_CAPABILITY_PROBE_NAMES) if not estimate else [],
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
        ],
        rows=[
            [
                b.backend,
                f"{b.requests:.0f}",
                f"{b.failures:.0f}",
                f"{b.mean_in_flight:.2f}",
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


@dry_run_class("request-plan")
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
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Report how busy each LLM backend and GPU was over a window, from Prometheus.

    Mean in flight is the gateway's call seconds per second on each deployment.
    """
    if dry_run or is_dry_run():
        from devops_cli.ai.ai_plans import plan_ai_gateway_load

        planned = plan_ai_gateway_load(window=window)
        resolved = normalize_format(output_format)
        if resolved != CONST_OUTPUT_FORMAT_TABLE:
            load_obj = PoolLoad(
                window=window,
                backends=[],
                gpus=[],
                dry_run=True,
                requests=[r.__dict__ for r in planned],
            )
            emit_serialized(load_obj.model_dump(), resolved)
            return
        render_request_plan(f"Plan for querying pool load over '{window}'", planned)
        return

    settings = load_settings()
    if not settings.prometheus.url:
        print_error(MESSAGES.prometheus.url_not_configured, prefix=False)
        raise typer.Exit(1)
    try:
        query = prometheus_query(
            settings.prometheus.url.rstrip("/"),
            DEFAULT_HTTP_TIMEOUT_SECONDS,
            configured_level(settings.ai),
        )
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
            "gateway and DCGM exporter monitors are applied (k8s/monitoring)."
        )
        return
    _render_pool_load(load)


@dry_run_class("no-external-request")
@app.command("render")
def render_cmd(
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Write rendered gateway configuration to file."),
    ] = False,
    config_path: Annotated[
        Path | None,
        typer.Option("--config", help="Path to the gateway's LiteLLM config file."),
    ] = None,
    profiles_path: Annotated[
        Path | None,
        typer.Option("--profiles", help="Path to Ollama profiles YAML."),
    ] = None,
    services_path: Annotated[
        Path | None,
        typer.Option("--services", help="Path to LLM services YAML."),
    ] = None,
) -> None:
    """Render LLM gateway configuration from Ollama profiles and services, showing unified diff."""
    import sys

    from devops_cli.ai.gateway_render import (
        diff_gateway_config,
        load_service_context_lengths,
        load_tier_context_lengths,
        render_gateway_config,
    )
    from devops_cli.config.defaults import (
        DEFAULT_LLM_GATEWAY_CONFIG_PATH,
        DEFAULT_LLM_PROFILES_PATH,
        DEFAULT_LLM_SERVICES_PATH,
    )

    target_config = config_path or DEFAULT_LLM_GATEWAY_CONFIG_PATH
    target_prof = profiles_path or DEFAULT_LLM_PROFILES_PATH
    target_svc = services_path or DEFAULT_LLM_SERVICES_PATH

    if not target_config.is_file():
        print_error(f"Gateway config file not found: {target_config}", prefix=False)
        raise typer.Exit(1)
    if not target_prof.is_file():
        print_error(f"Profiles file not found: {target_prof}", prefix=False)
        raise typer.Exit(1)
    if not target_svc.is_file():
        print_error(f"Services file not found: {target_svc}", prefix=False)
        raise typer.Exit(1)

    tier_lengths = load_tier_context_lengths(target_prof)
    svc_lengths = load_service_context_lengths(target_svc, tier_lengths)
    current_content = target_config.read_text(encoding="utf-8")
    rendered_content = render_gateway_config(current_content, svc_lengths)
    diff = diff_gateway_config(current_content, rendered_content, filename=target_config.name)

    if not diff:
        print_info(f"Gateway configuration at {target_config} is already up to date.", prefix=False)
        return

    sys.stdout.write(diff)
    if apply:
        target_config.write_text(rendered_content, encoding="utf-8")
        print_info(f"Wrote rendered gateway configuration to {target_config}.", prefix=False)
