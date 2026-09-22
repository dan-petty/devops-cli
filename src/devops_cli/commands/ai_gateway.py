"""LLM Gateway and distributed model router CLI commands."""

from __future__ import annotations

from typing import Annotated, Any

import typer

from devops_cli.ai.gateway import GatewayRoute, GatewayRouter
from devops_cli.config.constants import CONST_AI_GATEWAY_VIRTUAL_MODELS, CONST_OUTPUT_FORMAT_TABLE
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer
from devops_cli.output import (
    print_error,
    print_info,
    print_section,
    print_success,
    print_table,
)
from devops_cli.output.serialization import emit_serialized, normalize_format

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
    b_name = "LightLLM" if outcome.get("backend") == "lightllm" else "vLLM"
    print_section(f"{b_name} Inference Scaling Configuration")
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
        title=f"{b_name} Scale Parameters",
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
    router = GatewayRouter(settings.ai, provider=provider)
    routes = router.list_routes(gateway_url)

    resolved = normalize_format(output_format)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized([r.model_dump() for r in routes], resolved)
        return

    _render_routes_table(routes)


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
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """Trigger or test circuit-breaker failover of a virtual model to secondary backends."""
    settings = load_settings()
    router = GatewayRouter(settings.ai)
    try:
        outcome = router.trigger_failover(virtual_model, simulate=simulate)
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
    backend: Annotated[
        str,
        typer.Option("--backend", "-b", help="Inference backend to scale: vllm or lightllm."),
    ] = "vllm",
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
    """Inspect or scale inference backend (vLLM, LightLLM) serving configurations."""
    settings = load_settings()
    router = GatewayRouter(settings.ai)
    clean_backend = backend.lower()
    if clean_backend == "lightllm":
        outcome = router.scale_lightllm(replicas=replicas, apply=apply)
    else:
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
        typer.Argument(help="Backend to probe: vllm, lightllm, or ollama."),
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
