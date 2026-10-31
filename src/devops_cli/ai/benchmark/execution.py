"""Benchmark execution and runner dispatch for tasks and embeddings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from devops_cli.ai.benchmark.labels import model_label, server_label
from devops_cli.ai.run_store import Mechanism, announce_run, file_digest, record_run
from devops_cli.dry_run import is_dry_run
from devops_cli.lang import ERRORS
from devops_cli.output import print_error, print_success, write_stdout, write_text_file


def benchmark_setup(
    model_list: list[str],
    settings: Any,
    provider: str | None,
    safe_concurrency: int,
    server_list: list[str] | None,
) -> dict[str, Any]:
    """What a benchmark's results depend on besides its subject.

    A server and the endpoint of a model are named by their `host[:port]`, never by their URL,
    which can hold userinfo.
    """
    return {
        "models": sorted(model_label(entry) for entry in model_list),
        "provider": provider or settings.ai.provider,
        "servers": sorted(server_label(url) for url in server_list or []),
        "concurrency": safe_concurrency,
    }


def record_benchmark(
    kind: str,
    report: Any,
    *,
    setup: dict[str, Any],
    subject: dict[str, Any],
    format_type: str,
) -> None:
    """Keep a benchmark run in the run store, announcing on stderr beside JSON or Markdown."""
    saved = record_run(
        Mechanism.AI_BENCHMARK,
        setup=setup,
        subject={"kind": kind} | subject,
        results=report.model_dump(mode="json"),
    )
    announce_run(saved, to_stderr=format_type.lower() in ("json", "markdown"))


def render_tasks_dry_run(
    report: Any,
    runner: Any,
    planned: list[Any],
    format_type: str,
) -> None:
    """Render simulated results and request plan during dry-run."""
    from devops_cli.dry_run.requests import render_request_plan

    if format_type.lower() == "json":
        data = report.model_dump(mode="json")
        data["requests"] = [r.__dict__ for r in planned]
        write_stdout(json.dumps(data, indent=2) + "\n")
    elif format_type.lower() == "markdown":
        write_stdout(runner.to_markdown(report) + "\n")
    else:
        render_request_plan("Plan for AI benchmark", planned)
        runner.render_results(report)


def execute_embedding_benchmark(
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
    from devops_cli.ai.ai_plans import plan_ai_benchmark
    from devops_cli.ai.benchmark.embedding_runner import EmbeddingBenchmarkRunner
    from devops_cli.dry_run.requests import render_request_plan

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

        record_benchmark(
            "embedding",
            embed_report,
            setup=benchmark_setup(model_list, settings, provider, safe_concurrency, server_list),
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

    if dry_run or is_dry_run():
        planned = plan_ai_benchmark(
            models=model_list,
            servers=server_list,
            benchmark_type="embedding",
        )
        if format_type.lower() != "json":
            render_request_plan("Plan for AI benchmark", planned)

    embed_runner.print_report(embed_report, format_type=format_type)


def execute_tasks_benchmark(
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
    from devops_cli.ai.ai_plans import plan_ai_benchmark
    from devops_cli.ai.benchmark.runner import BenchmarkRunner
    from devops_cli.ai.benchmark.tasks import get_benchmark_tasks
    from devops_cli.models.benchmark import BenchmarkReport

    cat_filters = [c.strip() for c in tasks_filter.split(",")] if tasks_filter else None
    task_list = get_benchmark_tasks(cat_filters)

    if not task_list:
        err = ERRORS.ai.unsupported_provider.format(provider="No matching tasks found")
        print_error(err)
        raise typer.Exit(1)

    effective_dry_run = dry_run or is_dry_run()
    if effective_dry_run and format_type.lower() == "json":
        planned = plan_ai_benchmark(
            models=model_list,
            servers=server_list,
            benchmark_type="tasks",
        )
        rep = BenchmarkReport(
            session_id="dry-run",
            models_evaluated=model_list,
            tasks_run=task_list,
            responses=[],
            peer_grades=[],
            leaderboard=[],
            server_benchmarks=[],
            is_dry_run=True,
        )
        data = rep.model_dump(mode="json")
        data["requests"] = [r.__dict__ for r in planned]
        if output:
            resolved_output = output.resolve()
            write_text_file(resolved_output, json.dumps(data, indent=2))
            print_success(f"Exported custom report to {resolved_output}")
        write_stdout(json.dumps(data, indent=2) + "\n")
        return

    runner = BenchmarkRunner(
        models=model_list,
        tasks=task_list,
        settings=settings,
        provider=provider,
        is_dry_run=effective_dry_run,
        concurrency=safe_concurrency,
        servers=server_list,
    )

    report = runner.execute()
    if not effective_dry_run:
        record_benchmark(
            "tasks",
            report,
            setup=benchmark_setup(model_list, settings, provider, safe_concurrency, server_list),
            subject={"tasks": sorted(task.id for task in task_list)},
            format_type=format_type,
        )

    if effective_dry_run:
        planned = plan_ai_benchmark(
            models=model_list,
            servers=server_list,
            benchmark_type="tasks",
        )
        report.is_dry_run = True

    if output:
        resolved_output = output.resolve()
        write_text_file(resolved_output, report.model_dump_json(indent=2))
        print_success(f"Exported custom report to {resolved_output}")

    if effective_dry_run:
        render_tasks_dry_run(report, runner, planned, format_type)
        return

    if format_type.lower() == "json":
        write_stdout(report.model_dump_json(indent=2) + "\n")
    elif format_type.lower() == "markdown":
        write_stdout(runner.to_markdown(report) + "\n")
    else:
        runner.render_results(report)
