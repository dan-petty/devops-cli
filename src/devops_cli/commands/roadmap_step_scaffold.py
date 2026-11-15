"""`devops roadmap step scaffold`: make, resume, adopt or hold the item branch (#5499)."""

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
def scaffold_cmd(
    repo: Annotated[str | None, typer.Option("--repo", "-R", help=HELP.roadmap.repo)] = None,
    source: Annotated[Path | None, typer.Option("--source", help=HELP.roadmap.stage_source)] = None,
    item: Annotated[
        int | None, typer.Option("--item", "-i", min=1, help=HELP.roadmap.step_scaffold_item)
    ] = None,
    kind: Annotated[
        str, typer.Option("--kind", "-k", help=HELP.roadmap.step_scaffold_kind)
    ] = "plan",
    slug: Annotated[
        str | None, typer.Option("--slug", help=HELP.roadmap.step_scaffold_slug)
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.step_scaffold_dry_run)
    ] = False,
) -> None:
    """Make, resume, adopt or hold the item branch for a roadmap stage run (#5499)."""
    if item is None:
        print_error("Pass --item <number>.")
        raise typer.Exit(1)
    from devops_cli.github.request_scope import request_scope
    from devops_cli.roadmap.job_result import job_lines_to_stderr
    from devops_cli.roadmap.run import model_clone
    from devops_cli.roadmap.steps.scaffold import run_scaffold
    from devops_cli.roadmap.stores.store import get_roadmap_store

    target = _repository(repo)
    checkout = source or (find_repo_root(Path.cwd()) if not repo else model_clone(target))

    try:
        with (
            job_lines_to_stderr(),
            request_scope(repo=target, row="scaffold"),
        ):
            report = run_scaffold(
                get_roadmap_store(target),
                repo=target,
                item=item,
                source=checkout,
                kind=kind,
                slug=slug,
                dry_run=dry_run or is_dry_run(),
            )
    except DevOpsCLIError as exc:
        print_error(f"Could not scaffold item #{item}: {exc}", safe=True)
        raise typer.Exit(1) from exc

    write_stdout(report.to_json() + "\n")
