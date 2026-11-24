"""`devops roadmap step infra-apply`: apply a merged infra pull request (#5130)."""

from __future__ import annotations

from typing import Annotated

import typer

from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.lang import HELP


@dry_run_class("request-plan")
def infra_apply_cmd(
    repo: Annotated[str, typer.Option("--repo", "-R", help=HELP.roadmap.repo)],
    pull: Annotated[
        int, typer.Option("--pull", "-p", min=1, help=HELP.roadmap.step_infra_apply_pull)
    ],
    commit: Annotated[str, typer.Option("--commit", help=HELP.roadmap.step_infra_apply_commit)],
    playbook: Annotated[
        str, typer.Option("--playbook", help=HELP.roadmap.step_infra_apply_playbook)
    ] = "site.yaml",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.step_infra_apply_dry_run)
    ] = False,
) -> None:
    """Apply a merged infra pull request in a step job (#5130)."""
    from devops_cli.roadmap.steps.infra_apply import run_infra_apply

    code = run_infra_apply(repo, pull, commit, playbook=playbook, dry_run=dry_run or is_dry_run())
    if code != 0:
        raise typer.Exit(code)


__all__ = ["infra_apply_cmd"]
