"""Benchmark command group for evaluating and cross-grading LLM models."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint

from devops_cli.ai.benchmark.runner import BenchmarkRunner
from devops_cli.ai.benchmark.tasks import get_benchmark_tasks
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer
from devops_cli.lang import ERRORS, HELP

app = new_typer(
    help=HELP.ai.benchmark,
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def run_benchmark(
    ctx: typer.Context,
    models: Annotated[
        str | None,
        typer.Option(
            "--models",
            "-m",
            help="Comma-separated candidate models (e.g. 'qwen2.5-coder:7b,mistral:latest')",
        ),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option("--provider", "-p", help="AI provider (ollama, claude, copilot, openai)"),
    ] = None,
    tasks_filter: Annotated[
        str | None,
        typer.Option(
            "--tasks",
            "-t",
            help="Filter specific task categories or IDs (e.g. 'security,kubernetes')",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Destination JSON report filepath"),
    ] = None,
    format_type: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: table, json, markdown"),
    ] = "table",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate benchmark without sending remote LLM requests"),
    ] = False,
) -> None:
    """Run benchmark tasks across candidate models and execute cross-model peer grading."""
    if ctx.invoked_subcommand is not None:
        return

    settings = load_settings()

    # Parse models list
    if models:
        model_list = [m.strip() for m in models.split(",") if m.strip()]
    else:
        model_list = [settings.ai.model]

    # Parse task filters
    cat_filters = [c.strip() for c in tasks_filter.split(",")] if tasks_filter else None
    task_list = get_benchmark_tasks(cat_filters)

    if not task_list:
        err = ERRORS.ai.unsupported_provider.format(provider="No matching tasks found")
        rprint(f"[red]{err}[/red]")
        raise typer.Exit(1)

    runner = BenchmarkRunner(
        models=model_list,
        tasks=task_list,
        settings=settings,
        provider=provider,
        is_dry_run=dry_run,
    )

    report = runner.execute()

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        rprint(f"[green]✓ Exported custom report to {output}[/green]")

    if format_type.lower() == "json":
        print(report.model_dump_json(indent=2))
    else:
        runner.render_results(report)
