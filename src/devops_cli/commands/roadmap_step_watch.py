"""`devops roadmap step watch`: watch one pull request until its verdict settles (#5021)."""

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
from devops_cli.roadmap.failure import FailureClass


def _repository(repo: str | None) -> str:
    """`--repo`, or the origin of the checkout, which reads no network."""
    target = repo or get_repo_origin_name(find_repo_root(Path.cwd()))
    if not target or "/" not in target:
        print_error("Cannot resolve the repository; pass --repo owner/name.")
        raise typer.Exit(1)
    return target


@dry_run_class("request-plan")
def watch_cmd(
    repo: Annotated[str | None, typer.Option("--repo", "-R", help=HELP.roadmap.repo)] = None,
    pull: Annotated[
        int | None, typer.Option("--pull", "-p", min=1, help=HELP.roadmap.step_watch_pull)
    ] = None,
    head: Annotated[str | None, typer.Option("--head", help=HELP.roadmap.step_watch_head)] = None,
    block: Annotated[
        bool, typer.Option("--block/--no-block", help=HELP.roadmap.step_watch_block)
    ] = True,
    timeout: Annotated[int, typer.Option("--timeout", help=HELP.roadmap.step_watch_timeout)] = 3600,
    interval: Annotated[
        int, typer.Option("--interval", help=HELP.roadmap.step_watch_interval)
    ] = 60,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.step_watch_dry_run)
    ] = False,
) -> None:
    """Watch pull request checks and state until the verdict settles (#5021)."""
    if pull is None:
        print_error("Pass --pull <number>.")
        raise typer.Exit(1)
    if dry_run or is_dry_run():
        return

    from devops_cli.roadmap.steps.watch import watch

    target = _repository(repo)
    try:
        verdict = watch(
            target,
            pull,
            expected_head=head,
            timeout=timeout,
            interval=interval,
            block=block,
        )
    except DevOpsCLIError as exc:
        print_error(f"Could not watch PR #{pull}: {exc}", safe=True)
        raise typer.Exit(1) from exc

    payload = {
        "job": "watch",
        "repo": target,
        "pull": pull,
        "head": head,
        "verdict": verdict.verdict.value,
        "check": verdict.check,
        "failure_class": (
            verdict.failure_class.value
            if isinstance(verdict.failure_class, FailureClass)
            else verdict.failure_class
        ),
        "reason": verdict.reason,
    }
    write_stdout(json.dumps(payload) + "\n")
