"""The research agent: read what the project pins and watch the upstream of each pin (#3896)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.constants import CONST_OUTPUT_FORMAT_TABLE
from devops_cli.config.defaults import DEFAULT_TABLE_FORMAT
from devops_cli.core.cli import new_typer
from devops_cli.core.process import github_token
from devops_cli.core.repo import find_repo_root
from devops_cli.dry_run.decorator import dry_run_class
from devops_cli.dry_run.requests import render_request_plan
from devops_cli.dry_run.state import is_dry_run
from devops_cli.exceptions.git import GitHubUnauthenticatedError
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info, print_table, write_stdout
from devops_cli.output.serialization import emit_serialized, resolve_format
from devops_cli.research.advisories import advisory_requests, find_advisories
from devops_cli.research.github_advisories import GitHubAdvisoryClient
from devops_cli.research.inventory import read_inventory
from devops_cli.research.models import AdvisoryReport
from devops_cli.research.watch import read_watch_list
from devops_cli.telemetry import trace_span

app = new_typer(
    help=HELP.research.app,
    no_args_is_help=True,
)


@app.callback()
def research() -> None:
    """Keep the group a group while it holds one command: `devops research inventory`."""


@app.command("inventory", help=HELP.research.inventory)
@dry_run_class("no-external-request")
@trace_span("research.inventory")
def inventory(
    root: Annotated[
        Path | None,
        typer.Option("--root", help=HELP.research.inventory_root),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help=HELP.options.json_output),
    ] = False,
) -> None:
    """List every pin of the project."""
    result = read_inventory(find_repo_root(root))
    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(result.model_dump(mode="json"), resolved)
        return

    messages = MESSAGES.research
    print_table(
        messages.inventory_title,
        [
            (messages.kind_column, "bold cyan"),
            messages.ecosystem_column,
            messages.name_column,
            messages.version_column,
            messages.location_column,
        ],
        [
            [c.kind.value, c.ecosystem.value, c.name, c.version, f"{c.file}:{c.line}"]
            for c in result.components
        ],
    )
    print_info(
        messages.inventory_summary.format(
            total=result.summary.total, unknown=result.summary.unknown
        )
    )


@app.command("advisories", help=HELP.research.advisories)
@dry_run_class("request-plan")
@trace_span("research.advisories")
def advisories(
    root: Annotated[
        Path | None,
        typer.Option("--root", help=HELP.research.inventory_root),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help=HELP.options.json_output),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """List the advisories that affect the pins of the project."""
    repo_root = find_repo_root(root)
    inventory = read_inventory(repo_root)
    watch = read_watch_list(repo_root)
    resolved = resolve_format(output_format, json_output=json_output)
    if dry_run or is_dry_run():
        planned = advisory_requests(inventory, watch)
        if resolved != CONST_OUTPUT_FORMAT_TABLE:
            emit_serialized({"dry_run": True, "requests": [r.__dict__ for r in planned]}, resolved)
        else:
            render_request_plan(MESSAGES.research.advisories_plan, planned)
        return

    report = find_advisories(
        inventory, watch=watch, github=GitHubAdvisoryClient(token=_optional_github_token())
    )
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(report.model_dump(mode="json"), resolved)
    else:
        _print_advisories(report)
    if report.failures or report.kev_failure:
        raise typer.Exit(code=1)


def _optional_github_token() -> str | None:
    """The GitHub token of the session, or None. The advisories are public, so a run with no token
    works within the lower rate limit of GitHub."""
    try:
        return github_token()
    except GitHubUnauthenticatedError:
        return None


def _print_advisories(report: AdvisoryReport) -> None:
    messages = MESSAGES.research
    if report.findings:
        print_table(
            messages.advisories_title,
            [
                (messages.name_column, "bold cyan"),
                messages.version_column,
                messages.advisory_column,
                messages.severity_column,
                messages.exploited_column,
                messages.affected_column,
                messages.fixed_column,
            ],
            [
                [
                    f.component.name,
                    f.component.version,
                    f.advisory_id,
                    f.severity,
                    messages.exploited_yes if f.exploited else "",
                    f.affected_range,
                    f.fixed_version,
                ]
                for f in report.findings
            ],
        )
    summary = report.summary
    print_info(
        messages.advisories_summary.format(
            findings=summary.findings,
            packages=summary.with_findings,
            queried=summary.queried,
            exploited=summary.exploited,
            unpinned=summary.unpinned,
            not_covered=sum(summary.not_covered.values()),
        )
    )
    _print_failures(report)


def _print_failures(report: AdvisoryReport) -> None:
    messages = MESSAGES.research
    for failure in report.failures:
        print_error(
            messages.advisories_failure.format(
                name=failure.name,
                version=failure.version,
                advisory=failure.advisory_id or messages.advisories_query,
                reason=failure.reason,
            )
        )
    if report.kev_failure:
        print_error(messages.advisories_kev_failure.format(reason=report.kev_failure))


@app.command("sweep", help=HELP.research.sweep)
@dry_run_class("request-plan")
@trace_span("research.sweep")
def sweep(
    root: Annotated[
        Path | None,
        typer.Option("--root", help=HELP.research.inventory_root),
    ] = None,
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-R", help=HELP.research.sweep_repo),
    ] = None,
    confirm: Annotated[
        bool,
        typer.Option("--confirm", help=HELP.research.sweep_confirm),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help=HELP.options.json_output),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """File one intake candidate for each actionable finding that no issue carries."""
    from devops_cli.core.repo import get_repo_origin_name
    from devops_cli.research.sweep import (
        digest_lines,
        record_open_findings,
        run_sweep,
        sweep_dry_run,
    )
    from devops_cli.roadmap.intake.intake_model import build_intake_model
    from devops_cli.roadmap.stores import store as roadmap_store

    checkout = find_repo_root(root)
    target = repo or get_repo_origin_name(checkout)
    if not target or "/" not in target:
        print_error(MESSAGES.review.hand_off_no_repo, prefix=False)
        raise typer.Exit(1)
    inventory = read_inventory(checkout)
    resolved = resolve_format(output_format, json_output=json_output)
    if dry_run or is_dry_run():
        planned = sweep_dry_run(inventory, target)
        if resolved != CONST_OUTPUT_FORMAT_TABLE:
            emit_serialized(planned.model_dump(mode="json"), resolved)
        else:
            numbered = [f"{n:>3}. {line}" for n, line in enumerate(planned.requests, start=1)]
            write_stdout("\n".join([MESSAGES.research.sweep_dry_run_title, *numbered]) + "\n")
        return

    found = find_advisories(inventory)
    swept = run_sweep(
        found,
        repo=target,
        store=roadmap_store.get_roadmap_store(target),
        model=build_intake_model(),
        confirm=confirm,
    )
    # A lookup with no answer makes the count incomplete: a gauge of zero would hide a finding.
    if not found.failures:
        record_open_findings(swept)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(swept.model_dump(mode="json"), resolved)
    else:
        for line in digest_lines(swept):
            print_info(line, prefix=False)
        if found.failures:
            print_info(MESSAGES.research.sweep_incomplete.format(count=len(found.failures)))
    _print_failures(found)
    if found.failures:
        raise typer.Exit(code=1)
