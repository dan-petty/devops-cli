"""Benchmark command group for evaluating, cross-grading, and scoring LLM models."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.defaults import (
    DEFAULT_BENCHMARK_CONCURRENCY,
    DEFAULT_BENCHMARK_FORMAT,
    DEFAULT_BENCHMARK_SAMPLES,
    DEFAULT_BENCHMARK_TYPE,
)
from devops_cli.core.cli import new_typer
from devops_cli.lang import ERRORS, HELP
from devops_cli.output import print_error, print_success, write_stdout, write_text_file

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
    """Check if model name matches common embedding model patterns."""
    m = model_name.lower()
    return any(hint in m for hint in _EMBEDDING_MODEL_HINTS)


def _parse_model_list(models: str | None, default_model: str) -> list[str]:
    """Parse comma-separated model string into list of models."""
    if models:
        return [m.strip() for m in models.split(",") if m.strip()]
    return [default_model]


def _parse_server_list(servers: str | None) -> list[str] | None:
    """Parse and validate comma-separated Ollama server endpoints."""
    if not servers:
        return None
    from devops_cli.core.validation import validate_service_url

    server_list: list[str] = []
    for s in servers.split(","):
        clean_s = s.strip()
        if clean_s:
            validate_service_url(clean_s, "Ollama Server", allow=True)
            server_list.append(clean_s)
    return server_list or None


def _execute_embedding_benchmark(
    model_list: list[str],
    settings: Any,
    provider: str | None,
    dry_run: bool,
    safe_concurrency: int,
    server_list: list[str] | None,
    document: Path | None,
    samples: int,
    output: Path | None,
    format_type: str,
) -> None:
    """Execute embedding model benchmark run."""
    from devops_cli.ai.benchmark.embedding_runner import EmbeddingBenchmarkRunner

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
        write_text_file(resolved_output, embed_report.model_dump_json(indent=2))
        print_success(f"Exported custom report to {resolved_output}")

    embed_runner.print_report(embed_report, format_type=format_type)


def _execute_suite_benchmark(
    model_list: list[str],
    dataset: Path | None,
    settings: Any,
    provider: str | None,
    dry_run: bool,
    safe_concurrency: int,
    server_list: list[str] | None,
    output: Path | None,
    format_type: str,
) -> None:
    """Execute feedback-grounded multi-model benchmark evaluation suite."""
    from devops_cli.ai.benchmark.suite import BenchmarkSuiteRunner

    suite_runner = BenchmarkSuiteRunner(
        models=model_list,
        dataset_path=dataset,
        settings=settings,
        provider=provider,
        is_dry_run=dry_run,
        concurrency=safe_concurrency,
        servers=server_list,
        quiet=format_type.lower() == "json",
    )
    suite_report = suite_runner.run()

    if output:
        resolved_output = output.resolve()
        write_text_file(resolved_output, suite_report.model_dump_json(indent=2))
        print_success(f"Exported custom report to {resolved_output}")

    if format_type.lower() == "json":
        write_stdout(suite_report.model_dump_json(indent=2) + "\n")
    elif format_type.lower() == "markdown":
        write_stdout(suite_runner.to_markdown(suite_report) + "\n")
    else:
        suite_runner.render_results(suite_report)


def _execute_tasks_benchmark(
    model_list: list[str],
    tasks_filter: str | None,
    settings: Any,
    provider: str | None,
    dry_run: bool,
    safe_concurrency: int,
    server_list: list[str] | None,
    output: Path | None,
    format_type: str,
) -> None:
    """Execute peer-grading task benchmark run."""
    from devops_cli.ai.benchmark.runner import BenchmarkRunner
    from devops_cli.ai.benchmark.tasks import get_benchmark_tasks

    cat_filters = [c.strip() for c in tasks_filter.split(",")] if tasks_filter else None
    task_list = get_benchmark_tasks(cat_filters)

    if not task_list:
        err = ERRORS.ai.unsupported_provider.format(provider="No matching tasks found")
        print_error(err)
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
        write_text_file(resolved_output, report.model_dump_json(indent=2))
        print_success(f"Exported custom report to {resolved_output}")

    if format_type.lower() == "json":
        write_stdout(report.model_dump_json(indent=2) + "\n")
    elif format_type.lower() == "markdown":
        write_stdout(runner.to_markdown(report) + "\n")
    else:
        runner.render_results(report)


@app.callback(invoke_without_command=True)
def run_benchmark(
    ctx: typer.Context,
    models: Annotated[
        str | None,
        typer.Option(
            "--models",
            "-m",
            help=HELP.benchmark.models,
        ),
    ] = None,
    servers: Annotated[
        str | None,
        typer.Option(
            "--servers",
            "--ollama-urls",
            help=HELP.benchmark.ollama_urls,
        ),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option("--provider", "-p", help=HELP.options.provider),
    ] = None,
    benchmark_type: Annotated[
        str,
        typer.Option(
            "--type",
            "--mode",
            help=HELP.benchmark.mode,
        ),
    ] = DEFAULT_BENCHMARK_TYPE,
    suite: Annotated[
        bool,
        typer.Option(
            "--suite",
            help=HELP.benchmark.suite,
        ),
    ] = False,
    dataset: Annotated[
        Path | None,
        typer.Option(
            "--dataset",
            help=HELP.benchmark.dataset,
        ),
    ] = None,
    tasks_filter: Annotated[
        str | None,
        typer.Option(
            "--tasks",
            "-t",
            help=HELP.benchmark.tasks,
        ),
    ] = None,
    concurrency: Annotated[
        int,
        typer.Option(
            "--concurrency",
            "-c",
            help=HELP.benchmark.workers,
        ),
    ] = DEFAULT_BENCHMARK_CONCURRENCY,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help=HELP.options.output),
    ] = None,
    format_type: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_BENCHMARK_FORMAT,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
    explain: Annotated[
        bool,
        typer.Option(
            "--explain",
            "-e",
            help=HELP.benchmark.explain,
        ),
    ] = False,
    document: Annotated[
        Path | None,
        typer.Option(
            "--document",
            "-d",
            help=HELP.benchmark.test_doc,
            exists=True,
            readable=True,
        ),
    ] = None,
    samples: Annotated[
        int,
        typer.Option("--samples", help=HELP.benchmark.samples),
    ] = DEFAULT_BENCHMARK_SAMPLES,
) -> None:
    """Run benchmark tasks across candidate models and execute cross-model peer grading."""
    if ctx.invoked_subcommand is not None:
        return

    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("benchmark")
        return

    from devops_cli.config.settings import load_settings

    settings = load_settings()
    model_list = _parse_model_list(models, settings.ai.model)
    safe_concurrency = max(1, min(concurrency, 32))
    server_list = _parse_server_list(servers)

    is_suite = suite or benchmark_type.lower() == "suite"
    if is_suite:
        _execute_suite_benchmark(
            model_list=model_list,
            dataset=dataset,
            settings=settings,
            provider=provider,
            dry_run=dry_run,
            safe_concurrency=safe_concurrency,
            server_list=server_list,
            output=output,
            format_type=format_type,
        )
        return

    is_embedding = benchmark_type.lower() in ("embed", "embedding", "embeddings") or (
        benchmark_type.lower() == "auto" and any(_is_embedding_model(m) for m in model_list)
    )

    if is_embedding:
        _execute_embedding_benchmark(
            model_list=model_list,
            settings=settings,
            provider=provider,
            dry_run=dry_run,
            safe_concurrency=safe_concurrency,
            server_list=server_list,
            document=document,
            samples=samples,
            output=output,
            format_type=format_type,
        )
        return

    _execute_tasks_benchmark(
        model_list=model_list,
        tasks_filter=tasks_filter,
        settings=settings,
        provider=provider,
        dry_run=dry_run,
        safe_concurrency=safe_concurrency,
        server_list=server_list,
        output=output,
        format_type=format_type,
    )
