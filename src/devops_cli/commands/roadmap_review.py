"""`devops roadmap review`: the project review of a version range or a period (#4686).

`run` resolves the window to two first-parent commits and two UTC times, reads the git facts of
the window from the checkout of the working directory, and writes data.json with its JSON Schema.
It makes no network request, and its `--dry-run` starts no program. `commands/roadmap.py`
registers the group once.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.core.cli import new_typer
from devops_cli.core.repo import find_repo_root, get_repo_origin_name
from devops_cli.dry_run import dry_run_class, is_dry_run, render_request_plan
from devops_cli.exceptions.roadmap import RoadmapReviewError
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import write_stdout
from devops_cli.roadmap.project_review.data import write_review
from devops_cli.roadmap.project_review.review import (
    planned_review,
    render_review,
    review_folder,
    run_review,
)
from devops_cli.roadmap.project_review.window import parse_window

review_app = new_typer(help=HELP.roadmap.review_app, no_args_is_help=True)


def _repository(checkout: Path, repo: str | None) -> str:
    """`--repo`, which must be the origin of the checkout when it has one, or that origin."""
    origin = get_repo_origin_name(checkout)
    if repo and origin and repo.lower() != origin.lower():
        raise RoadmapReviewError(
            MESSAGES.roadmap.review_repo_mismatch.format(origin=origin, repo=repo)
        )
    target = repo or origin
    if not target or "/" not in target:
        raise RoadmapReviewError(MESSAGES.roadmap.review_no_repo)
    return target


@review_app.command("run", help=HELP.roadmap.review_run)
@dry_run_class("request-plan")
def run_cmd(
    version: Annotated[
        str | None, typer.Option("--version", help=HELP.roadmap.review_version)
    ] = None,
    since: Annotated[str | None, typer.Option("--since", help=HELP.roadmap.review_since)] = None,
    until: Annotated[str | None, typer.Option("--until", help=HELP.roadmap.review_until)] = None,
    week: Annotated[str | None, typer.Option("--week", help=HELP.roadmap.review_week)] = None,
    last: Annotated[str | None, typer.Option("--last", help=HELP.roadmap.review_last)] = None,
    repo: Annotated[str | None, typer.Option("--repo", "-R", help=HELP.roadmap.review_repo)] = None,
    out: Annotated[Path | None, typer.Option("--out", help=HELP.roadmap.review_out)] = None,
    json_output: Annotated[bool, typer.Option("--json", help=HELP.roadmap.review_json)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.review_dry_run)] = False,
) -> None:
    """Read the git facts of one window and write data.json."""
    request = parse_window(
        version=version, since=since, until=until, week=week, last=last, now=datetime.now(UTC)
    )
    checkout = find_repo_root(Path.cwd())
    if dry_run or is_dry_run():
        heading = MESSAGES.roadmap.review_plan_heading.format(window=request.id, checkout=checkout)
        render_request_plan(heading, planned_review(checkout, request))
        return
    target = _repository(checkout, repo)
    data = run_review(checkout, target, request)
    written = write_review(data, out or review_folder(target, data.window.id))
    if json_output:
        write_stdout(data.model_dump_json(indent=2) + "\n")
    else:
        write_stdout(render_review(data, written) + "\n")
