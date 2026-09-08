"""CLI command implementation for devops ai chaos-model."""

from __future__ import annotations

from typing import Annotated

import typer

from devops_cli.ai.chaos import (
    ChaosConfig,
    ChaosMode,
    ChaosStatus,
    ModelChaosInjector,
    ModelChaosReport,
)
from devops_cli.config.defaults import DEFAULT_TABLE_FORMAT
from devops_cli.lang import HELP
from devops_cli.output import (
    format_json,
    print_error,
    print_success,
    print_table,
    write_stdout,
)


def _build_status_cell(status: ChaosStatus) -> str:
    """Format outcome status badge for table rendering."""
    status_map = {
        ChaosStatus.RECOVERED: "[green]✓ RECOVERED[/green]",
        ChaosStatus.FAILED: "[red]✗ FAILED[/red]",
        ChaosStatus.INJECTED: "[yellow]INJECTED[/yellow]",
        ChaosStatus.SKIPPED: "[dim]SKIPPED[/dim]",
    }
    return status_map.get(status, status.value)


def _build_report_rows(report: ModelChaosReport) -> list[list[str]]:
    """Build summary table rows from chaos test results."""
    rows: list[list[str]] = []
    for res in report.results:
        fallback_str = (
            f"{res.fallback_provider}/{res.fallback_model}" if res.fallback_engaged else "None"
        )
        latency_str = f"{res.fault_latency_ms:.1f}ms" if res.fault_latency_ms > 0 else "-"
        rows.append(
            [
                res.mode.value,
                _build_status_cell(res.status),
                res.fault_injected,
                fallback_str,
                latency_str,
            ]
        )
    return rows


def run_chaos_model_cmd(
    mode: Annotated[
        str,
        typer.Option("--mode", "-m", help=HELP.options.chaos_mode),
    ] = "all",
    latency_ms: Annotated[
        int,
        typer.Option("--latency-ms", help=HELP.options.chaos_latency_ms),
    ] = 500,
    error_rate: Annotated[
        float,
        typer.Option("--error-rate", help=HELP.options.chaos_error_rate),
    ] = 1.0,
    primary_provider: Annotated[
        str,
        typer.Option("--primary-provider", help=HELP.options.provider),
    ] = "openai",
    primary_model: Annotated[
        str,
        typer.Option("--primary-model", help=HELP.options.model),
    ] = "gpt-4o",
    fallback_provider: Annotated[
        str,
        typer.Option("--fallback-provider", help=HELP.options.fallback_provider),
    ] = "ollama",
    fallback_model: Annotated[
        str,
        typer.Option("--fallback-model", help=HELP.options.fallback_model),
    ] = "qwen2.5-coder:7b",
    prompt: Annotated[
        str,
        typer.Option("--prompt", help=HELP.options.prompt),
    ] = "def test_health(): return True",
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Execute model dependency chaos fault injection and verify automated fallback recovery."""
    try:
        chaos_mode = ChaosMode(mode.lower())
    except ValueError:
        valid_modes = ", ".join(m.value for m in ChaosMode)
        print_error(f"Invalid chaos mode '{mode}'. Choose from: {valid_modes}")
        raise typer.Exit(code=1)

    if latency_ms < 0:
        print_error(f"Invalid --latency-ms '{latency_ms}': must be non-negative (>= 0).")
        raise typer.Exit(code=1)

    if not (0.0 <= error_rate <= 1.0):
        print_error(f"Invalid --error-rate '{error_rate}': must be between 0.0 and 1.0.")
        raise typer.Exit(code=1)

    config = ChaosConfig(
        mode=chaos_mode,
        latency_ms=latency_ms,
        error_rate=error_rate,
        primary_provider=primary_provider,
        primary_model=primary_model,
        fallback_provider=fallback_provider,
        fallback_model=fallback_model,
        prompt=prompt,
        dry_run=dry_run,
    )

    injector = ModelChaosInjector(config)
    report = injector.execute()

    if output_format.lower() == "json":
        write_stdout(format_json(report.model_dump()) + "\n")
        if not report.all_passed:
            raise typer.Exit(code=1)
        return

    rows = _build_report_rows(report)
    print_table(
        title="AI Model Dependency Chaos Engineering Suite",
        columns=[
            ("Fault Mode", "cyan"),
            ("Status", "bold"),
            ("Fault Simulation", "white"),
            ("Fallback Route", "yellow"),
            ("Latency", "dim"),
        ],
        rows=rows,
        box_style=None,
    )

    if report.all_passed:
        print_success(report.summary)
    else:
        print_error(report.summary)
        raise typer.Exit(code=1)
