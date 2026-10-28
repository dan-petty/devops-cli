"""Check the OpenSpec change folders, regenerate the agent skills and archive a change (ADR 0010)."""

from __future__ import annotations

from typing import Annotated

import typer

from devops_cli.config.commands import build_openspec_cmd
from devops_cli.core.cli import new_typer
from devops_cli.core.repo import find_worktree_root
from devops_cli.dry_run import dry_run_command, format_command, is_dry_run, render_dry_run_result
from devops_cli.lang import HELP, MESSAGES
from devops_cli.openspec.archive import archive_change, archive_commands
from devops_cli.openspec.gate import check_openspec
from devops_cli.openspec.skills import regenerate_skills
from devops_cli.openspec.tool import isolated_openspec
from devops_cli.output import print_error, print_success
from devops_cli.telemetry import trace_span

app = new_typer(help=HELP.openspec.app, no_args_is_help=True)


@app.command("check", help=HELP.openspec.check)
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
@dry_run_command(command="devops openspec regenerate", action="openspec_regenerate_skills")
@trace_span("openspec.regenerate")
def regenerate(
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Rewrite the committed OpenSpec skills under the isolated custom profile."""
    with isolated_openspec() as tool:
        regenerate_skills(tool, find_worktree_root())
    print_success(MESSAGES.openspec.regenerated)


@app.command("archive", help=HELP.openspec.archive)
@trace_span("openspec.archive")
def archive(
    change: Annotated[str, typer.Argument(help=HELP.openspec.archive_change)],
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Archive a change into the living specs, then validate every spec and change."""
    if dry_run or is_dry_run():
        commands = [format_command(build_openspec_cmd(*args)) for args in archive_commands(change)]
        render_dry_run_result(
            command="devops openspec archive",
            action="openspec_archive_change",
            target=change,
            details={"commands": commands},
        )
        return
    with isolated_openspec() as tool:
        archive_change(tool, find_worktree_root(), change)
    print_success(MESSAGES.openspec.archived.format(change=change))
