"""`devops roadmap step open`: open, update, or recover the draft pull request of an item (#5020)."""

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
def open_cmd(
    repo: Annotated[str | None, typer.Option("--repo", "-R", help=HELP.roadmap.repo)] = None,
    item: Annotated[
        int | None, typer.Option("--item", "-i", min=1, help=HELP.roadmap.step_open_item)
    ] = None,
    head: Annotated[str | None, typer.Option("--head", help=HELP.roadmap.step_open_head)] = None,
    base: Annotated[str | None, typer.Option("--base", help=HELP.roadmap.step_open_base)] = None,
    title: Annotated[str | None, typer.Option("--title", help=HELP.roadmap.step_open_title)] = None,
    body: Annotated[str | None, typer.Option("--body", help=HELP.roadmap.step_open_body)] = None,
    kind: Annotated[str, typer.Option("--kind", "-k", help=HELP.roadmap.step_open_kind)] = "plan",
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.step_open_dry_run)
    ] = False,
) -> None:
    """Open, update, or recover the draft pull request of an item (#5020)."""
    if not head:
        print_error("Pass --head <branch>.")
        raise typer.Exit(1)
    if not title:
        print_error("Pass --title <title>.")
        raise typer.Exit(1)

    from devops_cli.github.repo_ref import RepoRef
    from devops_cli.github.request_scope import request_scope
    from devops_cli.roadmap.job_result import job_lines_to_stderr
    from devops_cli.roadmap.steps.open import OpenRequest, open_or_update
    from devops_cli.roadmap.stores.store import get_roadmap_store

    target = _repository(repo)

    try:
        with (
            job_lines_to_stderr(),
            request_scope(repo=target, row="open"),
        ):
            store = get_roadmap_store(target)
            request = OpenRequest(
                repo=target,
                head=head,
                base=base or "main",
                title=title,
                body=body or "",
                kind=kind,
                item=item,
                dry_run=dry_run or is_dry_run(),
                store=store,
                reviewers=(RepoRef(target).owner,),
            )
            result = open_or_update(request)
    except DevOpsCLIError as exc:
        print_error(f"Could not open pull request: {exc}", safe=True)
        raise typer.Exit(1) from exc

    write_stdout(result.to_json() + "\n")
