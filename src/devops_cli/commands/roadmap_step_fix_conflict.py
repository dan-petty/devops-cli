"""`devops roadmap step fix-conflict`: settle merge conflicts on a pull request (#5019).

Tier 1 runs code of the checkout of the pull request (`devops docs generate`, `uv lock`). So
`--confirm`, which runs tier 1 and pushes, runs only in a runner Job (`require_runner`). Without it
the step prints its plan, runs no code of the checkout and writes nothing.
"""

from __future__ import annotations

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
def fix_conflict_cmd(
    repo: Annotated[str | None, typer.Option("--repo", "-R", help=HELP.roadmap.repo)] = None,
    pull: Annotated[
        int | None, typer.Option("--pull", "-p", min=1, help=HELP.roadmap.step_fix_conflict_pull)
    ] = None,
    head: Annotated[
        str | None, typer.Option("--head", help=HELP.roadmap.step_fix_conflict_head)
    ] = None,
    confirm: Annotated[
        bool, typer.Option("--confirm", help=HELP.roadmap.step_fix_conflict_confirm)
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.step_fix_conflict_dry_run)
    ] = False,
) -> None:
    """Settle merge conflicts on a pull request with the default branch (#5019). With `--confirm`
    the command runs only in a runner Job, and hardens its process before the step."""
    if pull is None:
        print_error("Pass --pull <number>.")
        raise typer.Exit(1)
    if dry_run or is_dry_run():
        return

    from devops_cli.roadmap.steps.fix_conflict import run_fix_conflict
    from devops_cli.roadmap.stores.store import get_roadmap_store

    target = _repository(repo)
    store = get_roadmap_store(target)
    try:
        if confirm:
            from devops_cli.core import process_hardening
            from devops_cli.roadmap.implement.implement_run import require_runner

            require_runner(target)
            # Tier 1 runs code of the pull request as the user of the Job, so the Job makes its
            # process unreadable and adopts the orphans of that code first, as fix-checks does.
            process_hardening.deny_environment_reads()
            process_hardening.adopt_orphans()
        report = run_fix_conflict(store, target, pull, head=head, confirm=confirm)
    except DevOpsCLIError as exc:
        print_error(f"Could not fix conflicts on PR #{pull}: {exc}", safe=True)
        raise typer.Exit(1) from exc

    write_stdout(report.to_json() + "\n")
