"""Benchmark command group for evaluating and cross-grading LLM models."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint

from devops_cli.ai.benchmark.embedding_runner import EmbeddingBenchmarkRunner
from devops_cli.ai.benchmark.runner import BenchmarkRunner
from devops_cli.ai.benchmark.tasks import get_benchmark_tasks
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer
from devops_cli.lang import ERRORS, HELP

app = new_typer(
    help=HELP.ai.benchmark,
    no_args_is_help=False,
)

_EMBEDDING_MODEL_HINTS = {
    "embed",
    "embedding",
    "nomic",
    "minilm",
    "bge",
    "gte",
    "e5",
    "sentence-transformer",
    "text-embedding",
}


def _is_embedding_model(model_name: str) -> bool:
    m = model_name.lower()
    return any(hint in m for hint in _EMBEDDING_MODEL_HINTS)


@app.callback(invoke_without_command=True)
def run_benchmark(
    ctx: typer.Context,
    models: Annotated[
        str | None,
        typer.Option(
            "--models",
            "-m",
            help="Comma-separated candidate models (e.g. 'qwen2.5:0.5b,llama3.1:8b@http://gpu2:11434')",
        ),
    ] = None,
    servers: Annotated[
        str | None,
        typer.Option(
            "--servers",
            "--ollama-urls",
            help="Comma-separated Ollama server URLs for concurrent execution (e.g. 'http://node1:11434,http://node2:11434')",
        ),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option("--provider", "-p", help="AI provider (ollama, claude, copilot, openai)"),
    ] = None,
    benchmark_type: Annotated[
        str,
        typer.Option(
            "--type",
            "--mode",
            help="Benchmark mode: 'auto', 'chat', 'embedding' (default: auto)",
        ),
    ] = "auto",
    tasks_filter: Annotated[
        str | None,
        typer.Option(
            "--tasks",
            "-t",
            help="Filter specific task categories or IDs (e.g. 'security,kubernetes')",
        ),
    ] = None,
    concurrency: Annotated[
        int,
        typer.Option(
            "--concurrency",
            "-c",
            help="Number of concurrent model server workers (default: automatic per model count)",
        ),
    ] = 4,
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
    explain: Annotated[
        bool,
        typer.Option(
            "--explain",
            "-e",
            help="Explain benchmark metrics, terminology, and mathematical formulas",
        ),
    ] = False,
    document: Annotated[
        Path | None,
        typer.Option(
            "--document",
            "-d",
            help="Path to large test document for in-memory tokenization and section retrieval",
            exists=True,
            readable=True,
        ),
    ] = None,
    samples: Annotated[
        int,
        typer.Option(
            "--samples", help="Number of random sections to sample for retrieval evaluation"
        ),
    ] = 15,
) -> None:
    """Run benchmark tasks across candidate models and execute cross-model peer grading."""
    if ctx.invoked_subcommand is not None:
        return

    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("benchmark")
        return

    settings = load_settings()

    # Parse models list
    if models:
        model_list = [m.strip() for m in models.split(",") if m.strip()]
    else:
        model_list = [settings.ai.model]

    # Bound concurrency safely
    safe_concurrency = max(1, min(concurrency, 32))

    # Parse and validate servers list
    server_list: list[str] | None = None
    if servers:
        from devops_cli.core.validation import validate_service_url

        server_list = []
        for s in servers.split(","):
            clean_s = s.strip()
            if clean_s:
                validate_service_url(clean_s, "Ollama Server", allow=True)
                server_list.append(clean_s)

    # Check if embedding benchmark mode should be activated
    is_embedding = benchmark_type.lower() in ("embed", "embedding", "embeddings") or (
        benchmark_type.lower() == "auto" and any(_is_embedding_model(m) for m in model_list)
    )

    if is_embedding:
        embed_runner = EmbeddingBenchmarkRunner(
            models=model_list,
            settings=settings,
            provider=provider,
            is_dry_run=dry_run,
            concurrency=safe_concurrency,
            servers=server_list,
            document_path=document,
            sample_count=samples,
        )
        embed_report = embed_runner.run()

        if output:
            resolved_output = output.resolve()
            resolved_output.parent.mkdir(parents=True, exist_ok=True)
            resolved_output.write_text(embed_report.model_dump_json(indent=2), encoding="utf-8")
            rprint(f"[green]✓ Exported custom report to {resolved_output}[/green]")

        embed_runner.print_report(embed_report, format_type=format_type)
        return

    # Parse task filters for LLM Chat benchmark
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
        concurrency=safe_concurrency,
        servers=server_list,
    )

    report = runner.execute()

    if output:
        resolved_output = output.resolve()
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        resolved_output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        rprint(f"[green]✓ Exported custom report to {resolved_output}[/green]")

    if format_type.lower() == "json":
        print(report.model_dump_json(indent=2))
    elif format_type.lower() == "markdown":
        print(runner.to_markdown(report))
    else:
        runner.render_results(report)
