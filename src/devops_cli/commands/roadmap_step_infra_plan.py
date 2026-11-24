"""`devops roadmap step infra-plan`: plan an open infra pull request and post or update its marked comment (#5129)."""

from __future__ import annotations

from typing import Annotated

import typer

from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.lang import HELP


@dry_run_class("request-plan")
def infra_plan_cmd(
    repo: Annotated[str, typer.Option("--repo", "-R", help=HELP.roadmap.repo)],
    pull: Annotated[
        int, typer.Option("--pull", "-p", min=1, help=HELP.roadmap.step_infra_plan_pull)
    ],
    head: Annotated[str, typer.Option("--head", help=HELP.roadmap.step_infra_plan_head)],
    playbook: Annotated[
        str, typer.Option("--playbook", help=HELP.infra.plan_playbook)
    ] = "site.yaml",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.step_review_dry_run)
    ] = False,
) -> None:
    """Plan an open infra pull request and post or update its marked comment (#5129)."""
    from devops_cli.roadmap.steps.infra_plan import run_infra_plan

    code = run_infra_plan(repo, pull, head, playbook=playbook, dry_run=dry_run or is_dry_run())
    if code != 0:
        raise typer.Exit(code)


__all__ = ["infra_plan_cmd"]
