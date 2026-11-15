"""`devops roadmap step ready`: mark a draft pull request ready for review (#5021)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.core.repo import find_repo_root, get_repo_origin_name
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.lang import HELP
from devops_cli.output import print_error, write_stdout


def _repository(repo: str | None) -> str:
    """`--repo`, or the origin of the checkout, which reads no network."""
    target = repo or get_repo_origin_name(find_repo_root(Path.cwd()))
    if not target or "/" not in target:
        print_error("Cannot resolve the repository; pass --repo owner/name.")
        raise typer.Exit(1)
    return target


@dry_run_class("request-plan")
def ready_cmd(
    repo: Annotated[str | None, typer.Option("--repo", "-R", help=HELP.roadmap.repo)] = None,
    pull: Annotated[
        int | None, typer.Option("--pull", "-p", min=1, help=HELP.roadmap.step_ready_pull)
    ] = None,
    head: Annotated[str | None, typer.Option("--head", help=HELP.roadmap.step_ready_head)] = None,
    force: Annotated[
        bool, typer.Option("--force", "-f", help=HELP.roadmap.step_ready_force)
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.step_ready_dry_run)
    ] = False,
) -> None:
    """Mark a draft pull request ready for review once checks pass (#5021)."""
    if pull is None:
        print_error("Pass --pull <number>.")
        raise typer.Exit(1)
    if dry_run or is_dry_run():
        return

    from devops_cli.roadmap.steps.ready import mark_ready

    target = _repository(repo)
    try:
        mark_ready(target, pull, expected_head=head)
    except DevOpsCLIError as exc:
        print_error(f"Could not mark PR #{pull} ready: {exc}", safe=True)
        raise typer.Exit(1) from exc

    payload = {
        "job": "ready",
        "repo": target,
        "pull": pull,
        "head": head,
        "status": "ready",
    }
    write_stdout(json.dumps(payload) + "\n")
