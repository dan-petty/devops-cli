"""`devops roadmap step review`: give a bot pull request one verdict (#5969)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from devops_cli.core.repo import find_repo_root, get_repo_origin_name
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.lang import HELP
from devops_cli.output import print_error, write_stdout

if TYPE_CHECKING:
    from devops_cli.roadmap.steps.review import Withdraw


def _repository(repo: str | None) -> str:
    """`--repo`, or the origin of the checkout, which reads no network."""
    target = repo or get_repo_origin_name(find_repo_root(Path.cwd()))
    if not target or "/" not in target:
        print_error("Cannot resolve the repository; pass --repo owner/name.")
        raise typer.Exit(1)
    return target


def job_withdraw(repo: str, source: Path | None) -> Withdraw:
    """The delete of a branch of `origin` in the clone `source`, or in the clone `model-clone`,
    which is made or updated only when a discard needs it. The push carries a lease on the judged
    head, so a push of another writer keeps the branch."""

    def withdraw(branch: str, lease: str) -> None:
        from devops_cli.roadmap.implement.git_isolation import OriginGit, origin_url
        from devops_cli.roadmap.run import model_clone

        clone = source or model_clone(repo)
        OriginGit(clone, origin_url(clone)).push(branch, None, lease=lease)

    return withdraw


@dry_run_class("request-plan")
def review_cmd(
    repo: Annotated[str | None, typer.Option("--repo", "-R", help=HELP.roadmap.repo)] = None,
    pull: Annotated[
        int | None, typer.Option("--pull", "-p", min=1, help=HELP.roadmap.step_review_pull)
    ] = None,
    head: Annotated[str | None, typer.Option("--head", help=HELP.roadmap.step_review_head)] = None,
    source: Annotated[
        Path | None, typer.Option("--source", help=HELP.roadmap.step_review_source)
    ] = None,
    confirm: Annotated[
        bool, typer.Option("--confirm", help=HELP.roadmap.step_review_confirm)
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.step_review_dry_run)
    ] = False,
) -> None:
    """Give a bot pull request one verdict (#5969). With `--confirm` in the mode `on` of
    `roadmap.review.mode`, the command runs only in a runner Job."""
    if pull is None:
        print_error("Pass --pull <number>.")
        raise typer.Exit(1)
    if dry_run or is_dry_run():
        return

    from devops_cli.config.settings import load_settings
    from devops_cli.roadmap.steps.review import run_review
    from devops_cli.roadmap.stores.store import get_roadmap_store

    target = _repository(repo)
    store = get_roadmap_store(target)
    try:
        withdraw: Withdraw | None = None
        if confirm and load_settings().roadmap.review.mode == "on":
            from devops_cli.roadmap.implement.implement_run import require_runner

            require_runner(target)
            withdraw = job_withdraw(target, source)
        report = run_review(store, target, pull, head=head, confirm=confirm, withdraw=withdraw)
    except DevOpsCLIError as exc:
        print_error(f"Could not review PR #{pull}: {exc}", safe=True)
        raise typer.Exit(1) from exc

    write_stdout(report.to_json() + "\n")
