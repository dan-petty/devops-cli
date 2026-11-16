"""`devops roadmap step fix-checks`: repair a failed check on a pull request (#5023)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.core.repo import find_repo_root, get_repo_origin_name
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.lang import HELP
from devops_cli.output import print_error, write_stdout

_RUNNER: Callable[..., Any] | None = None


def set_fix_checks_runner(runner: Callable[..., Any] | None) -> None:
    """Set an override runner for tests (#5023)."""
    global _RUNNER
    _RUNNER = runner


def _repository(repo: str | None) -> str:
    """`--repo`, or the origin of the checkout, which reads no network."""
    target = repo or get_repo_origin_name(find_repo_root(Path.cwd()))
    if not target or "/" not in target:
        print_error("Cannot resolve the repository; pass --repo owner/name.")
        raise typer.Exit(1)
    return target


@dry_run_class("request-plan")
def fix_checks_cmd(
    repo: Annotated[str | None, typer.Option("--repo", "-R", help=HELP.roadmap.repo)] = None,
    pull: Annotated[
        int | None, typer.Option("--pull", "-p", min=1, help=HELP.roadmap.step_fix_checks_pull)
    ] = None,
    head: Annotated[
        str | None, typer.Option("--head", help=HELP.roadmap.step_fix_checks_head)
    ] = None,
    confirm: Annotated[
        bool, typer.Option("--confirm", help=HELP.roadmap.step_fix_checks_confirm)
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.step_fix_checks_dry_run)
    ] = False,
) -> None:
    """Repair a failed check on a pull request (#5023)."""
    if pull is None:
        print_error("Pass --pull <number>.")
        raise typer.Exit(1)
    if dry_run or is_dry_run():
        return

    from devops_cli.roadmap.steps.fix_checks import run_fix_checks
    from devops_cli.roadmap.stores.store import get_roadmap_store

    target = _repository(repo)
    store = get_roadmap_store(target)
    runner = _RUNNER or run_fix_checks
    try:
        report = runner(store, target, pull, head=head, confirm=confirm)
    except DevOpsCLIError as exc:
        print_error(f"Could not fix checks on PR #{pull}: {exc}", safe=True)
        raise typer.Exit(1) from exc

    write_stdout(report.to_json() + "\n")
