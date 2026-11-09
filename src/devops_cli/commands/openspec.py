"""Check the OpenSpec change folders, regenerate the agent skills and archive a change (ADR 0010)."""

from __future__ import annotations

from typing import Annotated

import typer

from devops_cli.core.cli import new_typer
from devops_cli.core.repo import find_worktree_root
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.dry_run.requests import render_request_plan
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.lang import HELP, MESSAGES
from devops_cli.openspec.archive import archive_change, plan_archive
from devops_cli.openspec.gate import check_openspec
from devops_cli.openspec.scaffold import scaffold_change
from devops_cli.openspec.skills import regenerate_skills
from devops_cli.openspec.tool import isolated_openspec
from devops_cli.output import print_error, print_info, print_success
from devops_cli.telemetry import trace_span

app = new_typer(help=HELP.openspec.app, no_args_is_help=True)


@app.command("check", help=HELP.openspec.check)
@dry_run_class("no-external-request")
@trace_span("openspec.check")
def check() -> None:
    """Run the OpenSpec gate over the checkout; exit 1 when it finds a problem."""
    findings = check_openspec(find_worktree_root())
    for finding in findings:
        print_error(finding.line(), prefix=False)
    if findings:
        print_error(MESSAGES.openspec.check_failed.format(count=len(findings)), prefix=False)
        raise typer.Exit(1)
    print_success(MESSAGES.openspec.check_passed)


@app.command("regenerate", help=HELP.openspec.regenerate)
@dry_run_class("no-external-request")
@trace_span("openspec.regenerate")
def regenerate() -> None:
    """Rewrite the committed OpenSpec skills under the isolated custom profile."""
    with isolated_openspec() as tool:
        regenerate_skills(tool, find_worktree_root())
    print_success(MESSAGES.openspec.regenerated)


@app.command("archive", help=HELP.openspec.archive)
@dry_run_class("no-external-request")
@trace_span("openspec.archive")
def archive(
    change: Annotated[str, typer.Argument(help=HELP.openspec.archive_change)],
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Archive a change into the living specs, then validate every spec and change."""
    if dry_run or is_dry_run():
        render_request_plan(
            MESSAGES.openspec.archive_dry_run_heading,
            plan_archive(change),
            [MESSAGES.openspec.archive_dry_run_output.format(change=change)],
        )
        return
    with isolated_openspec() as tool:
        archive_change(tool, find_worktree_root(), change)
    print_success(MESSAGES.openspec.archived.format(change=change))


@app.command("new", help=HELP.openspec.new)
@dry_run_class("no-external-request")
@trace_span("openspec.new")
def new_cmd(
    issue: Annotated[int, typer.Argument(min=1, help=HELP.openspec.new_issue)],
    title: Annotated[
        str | None,
        typer.Option("--title", "-t", help=HELP.openspec.new_title),
    ] = None,
    paths: Annotated[
        list[str] | None,
        typer.Option("--paths", "-p", help=HELP.openspec.new_paths),
    ] = None,
    capability: Annotated[
        list[str] | None,
        typer.Option("--capability", "-c", help=HELP.openspec.new_capability),
    ] = None,
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-R", help=HELP.pr.target_repo),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Create an OpenSpec change folder in project form for an issue."""
    try:
        res = scaffold_change(
            find_worktree_root(),
            issue,
            title=title,
            paths=paths,
            capabilities=capability,
            repo=repo,
            dry_run=dry_run or is_dry_run(),
        )
    except DevOpsCLIError as exc:
        print_error(str(exc), prefix=False)
        raise typer.Exit(1) from exc

    if res.dry_run:
        print_info(f"Would create {res.folder} on branch {res.branch}.")
        print_info(f"Folder: {res.folder}")
        print_info(f"Branch: {res.branch}")
        return

    print_success(
        f"Created {res.folder} on branch {res.branch}.\n\n"
        f"Branch:  {res.branch}\n"
        f"Checks:  uv run devops ci\n"
        f"Archive: uv run devops openspec archive {res.change}"
    )
