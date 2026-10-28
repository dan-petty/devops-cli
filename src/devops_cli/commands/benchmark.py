"""Benchmark command group for evaluating, cross-grading, and scoring LLM models."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import BaseModel

from devops_cli.ai.benchmark.model_spec import parse_model_list
from devops_cli.config.constants import CONST_BENCHMARK_TYPES
from devops_cli.config.defaults import (
    DEFAULT_BENCHMARK_CONCURRENCY,
    DEFAULT_BENCHMARK_FORMAT,
    DEFAULT_BENCHMARK_SAMPLES,
    DEFAULT_BENCHMARK_TYPE,
)
from devops_cli.core.cli import exit_on_error, new_typer
from devops_cli.exceptions.validation import ValidationError
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


def _validate_benchmark_type(benchmark_type: str) -> None:
    """Refuse a `--type` other than auto, chat or embedding, which ran the chat tasks instead."""
    if benchmark_type.strip().lower() not in CONST_BENCHMARK_TYPES:
        raise ValidationError(
            ERRORS.ai.unknown_benchmark_type.format(
                value=benchmark_type, choices=", ".join(CONST_BENCHMARK_TYPES)
            ),
            field="type",
        )


def _validate_corpus_choice(document: Path | None, code: Path | None) -> None:
    """Refuse `--document` with `--code`: each chooses the corpus the embedding run ranks."""
    if document and code:
        raise ValidationError(ERRORS.ai.benchmark_corpus_conflict, field="code")


def _parse_server_list(servers: str | None) -> list[str] | None:
    """Parse comma-separated Ollama server URLs, each checked as `ai.ollama_urls` checks a URL.

    The check reads the URL only. The client of each benchmark call checks the address at the
    connect.
    """
    if not servers:
        return None
    from pydantic import TypeAdapter
    from pydantic import ValidationError as PydanticValidationError

    from devops_cli.config.settings import HttpUrlStr

    url_type = TypeAdapter(HttpUrlStr)
    server_list: list[str] = []
    for entry in (s.strip() for s in servers.split(",")):
        if not entry:
            continue
        try:
            server_list.append(url_type.validate_python(entry))
        except PydanticValidationError as exc:
            raise ValidationError(
                ERRORS.ai.benchmark_server_url.format(url=entry), field="servers"
            ) from exc
    return server_list or None


def _record_benchmark(
    kind: str,
    report: BaseModel,
    *,
    setup: dict[str, Any],
    subject: dict[str, Any],
    format_type: str,
) -> None:
    """Keep a benchmark run in the run store, announcing on stderr beside JSON or Markdown."""
    from devops_cli.ai.run_store import Mechanism, record_run
    from devops_cli.commands.ai_runs import announce_run

    saved = record_run(
        Mechanism.AI_BENCHMARK,
        setup=setup,
        subject={"kind": kind} | subject,
        results=report.model_dump(mode="json"),
    )
    announce_run(saved, to_stderr=format_type.lower() in ("json", "markdown"))


def _benchmark_setup(
    model_list: list[str],
    settings: Any,
    provider: str | None,
    safe_concurrency: int,
    server_list: list[str] | None,
) -> dict[str, Any]:
    """What a benchmark's results depend on besides its subject."""
    return {
        "models": sorted(model_list),
        "provider": provider or settings.ai.provider,
        "servers": sorted(server_list or []),
        "concurrency": safe_concurrency,
    }


def _execute_embedding_benchmark(
    model_list: list[str],
    settings: Any,
    provider: str | None,
    dry_run: bool,
    safe_concurrency: int,
    server_list: list[str] | None,
    document: Path | None,
    code: Path | None,
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
        code_path=code,
        sample_count=samples,
    )
    with exit_on_error(ValidationError):
        embed_report = embed_runner.run()

    failed_cnt = (
        embed_report.failed_count
        if embed_report.failed_count is not None
        else sum(1 for m in embed_report.models if getattr(m, "failed", False))
    )
    total_cnt = (
        embed_report.total_count
        if embed_report.total_count is not None
        else len(embed_report.models)
    )
    if total_cnt > 0 and failed_cnt >= total_cnt:
        if output:
            resolved_output = output.resolve()
            write_text_file(resolved_output, embed_report.model_dump_json(indent=2))
        embed_runner.print_report(embed_report, format_type=format_type)
        print_error("All embedding benchmark requests failed.", prefix=False)
        raise typer.Exit(1)

    if not dry_run:
        from devops_cli.ai.benchmark.code_chunk_corpus import code_tree_digest
        from devops_cli.ai.run_store import file_digest

        _record_benchmark(
            "embedding",
            embed_report,
            setup=_benchmark_setup(model_list, settings, provider, safe_concurrency, server_list),
            subject={
                "document": file_digest(document) if document else None,
                "samples": samples,
                **({"code": code_tree_digest(code)} if code else {}),
            },
            format_type=format_type,
        )

    if output:
        resolved_output = output.resolve()
        write_text_file(resolved_output, embed_report.model_dump_json(indent=2))
        print_success(f"Exported custom report to {resolved_output}")

    embed_runner.print_report(embed_report, format_type=format_type)


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
    if not dry_run:
        _record_benchmark(
            "tasks",
            report,
            setup=_benchmark_setup(model_list, settings, provider, safe_concurrency, server_list),
            subject={"tasks": sorted(task.id for task in task_list)},
            format_type=format_type,
        )

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
    code: Annotated[
        Path | None,
        typer.Option(
            "--code",
            help=HELP.benchmark.code_dir,
            exists=True,
            file_okay=False,
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

    with exit_on_error(ValidationError):
        _validate_benchmark_type(benchmark_type)
        _validate_corpus_choice(document, code)
        server_list = _parse_server_list(servers)

    from devops_cli.ai.endpoints import resolve_ai_endpoint
    from devops_cli.config.settings import load_settings
    from devops_cli.exceptions import ConfigurationError

    settings = load_settings()
    effective_ai_cfg = settings.ai
    if provider:
        effective_ai_cfg = settings.ai.model_copy(update={"provider": provider})
    if servers:
        effective_ai_cfg = effective_ai_cfg.model_copy(update={"ollama_urls": server_list or []})

    try:
        resolve_ai_endpoint(effective_ai_cfg)
    except ConfigurationError as exc:
        print_error(f"Configuration error: {exc.message} ({exc.key})", prefix=False)
        raise typer.Exit(1) from exc

    model_list = parse_model_list(models, settings.ai.model)
    safe_concurrency = max(1, min(concurrency, 32))

    kind = benchmark_type.strip().lower()
    is_embedding = kind == "embedding" or (
        kind == "auto" and any(_is_embedding_model(m) for m in model_list)
    )

    if is_embedding:
        if not models:
            effective_provider = provider or settings.ai.provider
            if effective_provider == "gateway":
                model_list = ["devops-embedding"]
            else:
                emb_model = getattr(getattr(settings.ai.tasks, "embedding", None), "model", None)
                model_list = [emb_model] if emb_model else [settings.ai.model]
        _execute_embedding_benchmark(
            model_list=model_list,
            settings=settings,
            provider=provider,
            dry_run=dry_run,
            safe_concurrency=safe_concurrency,
            server_list=server_list,
            document=document,
            code=code,
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
