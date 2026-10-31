"""Benchmark command group for evaluating, cross-grading, and scoring LLM models."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.ai.benchmark.model_spec import parse_model_list
from devops_cli.config.constants import CONST_BENCHMARK_TYPES
from devops_cli.config.defaults import (
    DEFAULT_BENCHMARK_CONCURRENCY,
    DEFAULT_BENCHMARK_FORMAT,
    DEFAULT_BENCHMARK_SAMPLES,
    DEFAULT_BENCHMARK_TYPE,
)
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.exceptions.validation import ValidationError
from devops_cli.lang import ERRORS, HELP
from devops_cli.output import print_error

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
    connect. An error names the entry by its position and its `host[:port]`, never by its userinfo.
    """
    if not servers:
        return None
    from pydantic import TypeAdapter
    from pydantic import ValidationError as PydanticValidationError

    from devops_cli.ai.benchmark.labels import server_label
    from devops_cli.config.settings import HttpUrlStr

    url_type = TypeAdapter(HttpUrlStr)
    server_list: list[str] = []
    for position, raw in enumerate(servers.split(","), 1):
        entry = raw.strip()
        if not entry:
            continue
        try:
            server_list.append(url_type.validate_python(entry))
        except PydanticValidationError as exc:
            raise ValidationError(
                ERRORS.ai.benchmark_server_url.format(
                    position=position, server=server_label(entry)
                ),
                field="servers",
            ) from exc
    return server_list or None


def _execute_embedding_benchmark(*args: Any, **kwargs: Any) -> None:
    from devops_cli.ai.benchmark.execution import execute_embedding_benchmark

    execute_embedding_benchmark(*args, **kwargs)


def _execute_tasks_benchmark(*args: Any, **kwargs: Any) -> None:
    from devops_cli.ai.benchmark.execution import execute_tasks_benchmark

    execute_tasks_benchmark(*args, **kwargs)


def _record_benchmark(*args: Any, **kwargs: Any) -> None:
    from devops_cli.ai.benchmark.execution import record_benchmark

    record_benchmark(*args, **kwargs)


@dry_run_class("request-plan")
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

    effective_dry_run = dry_run or is_dry_run()
    if not effective_dry_run:
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
            dry_run=effective_dry_run,
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
        dry_run=effective_dry_run,
        safe_concurrency=safe_concurrency,
        server_list=server_list,
        output=output,
        format_type=format_type,
    )
