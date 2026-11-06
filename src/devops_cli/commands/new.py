"""Write the files of a new command or a new test in project form (#3204)."""

from __future__ import annotations

from typing import Annotated

import typer

from devops_cli.core.cli import new_typer
from devops_cli.core.repo import find_worktree_root
from devops_cli.dry_run import is_dry_run
from devops_cli.dry_run.decorator import dry_run_class
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_info, print_success
from devops_cli.scaffold.plan import ScaffoldPlan, apply_plan, plan_command, plan_test
from devops_cli.telemetry import trace_span

app = new_typer(help=HELP.new.app, no_args_is_help=True)


def _finish(plan: ScaffoldPlan, *, dry_run: bool) -> None:
    """Print the paths of a plan under a dry run, else write them, then print the manual steps."""
    root = find_worktree_root()
    if dry_run or is_dry_run():
        for change in plan.changes:
            text = MESSAGES.new.would_write if change.created else MESSAGES.new.would_edit
            print_info(text.format(path=change.path.as_posix()), prefix=False)
        return
    apply_plan(root, plan)
    for change in plan.changes:
        text = MESSAGES.new.wrote if change.created else MESSAGES.new.edited
        print_success(text.format(path=change.path.as_posix()), prefix=False)
    print_info(MESSAGES.new.steps_title, prefix=False)
    for step in plan.steps:
        print_info(f"- {step}", prefix=False)


@app.command("command", help=HELP.new.command)
@dry_run_class("no-external-request")
@trace_span("new.command")
def command(
    group: Annotated[str, typer.Argument(help=HELP.new.command_group)],
    name: Annotated[str, typer.Argument(help=HELP.new.command_name)],
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Plan a command of an existing group, then write it."""
    _finish(plan_command(find_worktree_root(), group, name), dry_run=dry_run)


@app.command("test", help=HELP.new.test)
@dry_run_class("no-external-request")
@trace_span("new.test")
def test(
    module: Annotated[str, typer.Argument(help=HELP.new.test_module)],
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Plan the test file of a source module, then write it."""
    _finish(plan_test(find_worktree_root(), module), dry_run=dry_run)
