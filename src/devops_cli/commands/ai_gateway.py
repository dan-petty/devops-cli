"""LLM Gateway and distributed model router CLI commands."""

from __future__ import annotations

from typing import Annotated

import typer

from devops_cli.ai.gateway import GatewayRoute, GatewayRouter
from devops_cli.config.constants import CONST_AI_GATEWAY_VIRTUAL_MODELS
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer
from devops_cli.output import (
    format_json,
    print_error,
    print_info,
    print_section,
    print_success,
    print_table,
    write_stdout,
)

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


@app.command("status")
def status_cmd(
    gateway_url: Annotated[
        str | None,
        typer.Option("--gateway-url", "-u", help="Optional gateway base URL override."),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """Probe LLM Gateway health, latency, and circuit breaker metrics."""
    settings = load_settings()
    router = GatewayRouter(settings.ai)
    result = router.probe_gateway(gateway_url)

    if output_format.lower() == "json":
        write_stdout(format_json(result.model_dump()))
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
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """List registered virtual models and target backend inference instances."""
    settings = load_settings()
    router = GatewayRouter(settings.ai)
    routes = router.list_routes(gateway_url)

    if output_format.lower() == "json":
        write_stdout(format_json([r.model_dump() for r in routes]))
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

    if output_format.lower() == "json":
        write_stdout(format_json(outcome))
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
        typer.Option("--replicas", "-r", help="Replica count for vLLM Tensor-Parallel deployment."),
    ] = None,
    tensor_parallel_size: Annotated[
        int | None,
        typer.Option("--tensor-parallel-size", "-tp", help="Tensor Parallelism degree (e.g. 2)."),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table or json."),
    ] = "table",
) -> None:
    """Inspect or scale vLLM Tensor Parallelism serving configurations."""
    settings = load_settings()
    router = GatewayRouter(settings.ai)
    outcome = router.scale_vllm(replicas=replicas, tensor_parallel_size=tensor_parallel_size)

    if output_format.lower() == "json":
        write_stdout(format_json(outcome))
        return

    print_section("vLLM Tensor Parallelism Configuration")
    print_table(
        columns=["Property", "Configured Value"],
        rows=[
            ["Model", outcome["model"]],
            ["Replicas", str(outcome["replicas"])],
            ["Tensor Parallel Size", str(outcome["tensor_parallel_size"])],
            ["Total VRAM (GB)", str(outcome["total_vram_gb"])],
            ["Serving Status", outcome["status"]],
        ],
        title="vLLM Scale Parameters",
    )
