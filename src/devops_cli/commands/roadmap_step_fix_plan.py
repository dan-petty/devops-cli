"""`devops roadmap step fix-plan`: one repair of an open plan pull request that holds the label
`plan/needs-fix` (#5061). The step is `devops_cli.roadmap.steps.fix_plan`. Without `--confirm` the
command prints the plan pull request that the step selects, calls no model and writes nothing.
`--confirm` runs the attempt in every mode of `roadmap.fix_plan.mode`, because a person chose it.
`--dry-run` makes no request. During an attempt the command writes the line of each round and the
result line of the step to stderr as they come (#5363): a Job runs the command, and its log is what
the command writes, so a pod that the deadline of its Job stops still leaves these lines. The
Service writes the same lines in its own log.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Final

import typer

from devops_cli.core.repo import find_repo_root, get_repo_origin_name
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info, write_stdout

# The loggers of the lines with counts of the step: one line for each review round and gate
# return, the progress line of each review (`round_log`), and the result line (`job_result`).
_LINE_LOGGERS: Final[tuple[str, ...]] = (
    "devops_cli.roadmap.round_log",
    "devops_cli.roadmap.job_result",
)


@contextmanager
def _lines_to_stderr() -> Iterator[None]:
    """Write the INFO lines of `_LINE_LOGGERS` to stderr while the block runs. The lines hold
    counts and names, and no text of a model or of an issue."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    loggers = [logging.getLogger(name) for name in _LINE_LOGGERS]
    levels = [each.level for each in loggers]
    for each in loggers:
        each.addHandler(handler)
        each.setLevel(logging.INFO)
    try:
        yield
    finally:
        for each, level in zip(loggers, levels, strict=True):
            each.removeHandler(handler)
            each.setLevel(level)


def _repository(repo: str | None) -> str:
    """`--repo`, or the origin of the checkout, which reads no network."""
    target = repo or get_repo_origin_name(find_repo_root(Path.cwd()))
    if not target or "/" not in target:
        print_error("Cannot resolve the repository; pass --repo owner/name.")
        raise typer.Exit(1)
    return target


@dry_run_class("request-plan")
def fix_plan_cmd(
    repo: Annotated[str | None, typer.Option("--repo", "-R", help=HELP.roadmap.repo)] = None,
    source: Annotated[Path | None, typer.Option("--source", help=HELP.roadmap.stage_source)] = None,
    item: Annotated[
        int | None, typer.Option("--item", min=1, help=HELP.roadmap.step_fix_plan_item)
    ] = None,
    pull: Annotated[
        int | None, typer.Option("--pull", min=1, help=HELP.roadmap.step_fix_plan_pull)
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.step_fix_plan_dry_run)
    ] = False,
    confirm: Annotated[
        bool, typer.Option("--confirm", help=HELP.roadmap.step_fix_plan_confirm)
    ] = False,
) -> None:
    """Repair one open plan pull request that holds the label plan/needs-fix."""
    if dry_run and confirm:
        print_error(MESSAGES.roadmap.plan_modes_exclusive.format(modes="--dry-run and --confirm"))
        raise typer.Exit(1)
    if item is not None and pull is not None:
        print_error(MESSAGES.roadmap.plan_modes_exclusive.format(modes="--item and --pull"))
        raise typer.Exit(1)
    from devops_cli.roadmap.request_plan import render_dry_run
    from devops_cli.roadmap.steps.fix_plan import dry_run_fix_plan, render_fix_plan, run_fix_plan

    target = _repository(repo)
    if dry_run or is_dry_run():
        planned = dry_run_fix_plan(target, item=item or pull)
        render_dry_run("fix-plan", target, planned.requests, planned.write_requests)
        return
    if not confirm:
        print_info(MESSAGES.roadmap.fix_plan_plain_note)
    from devops_cli.ai.client.factory import get_task_model
    from devops_cli.roadmap.run import model_clone
    from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
    from devops_cli.roadmap.stores.store import get_roadmap_store

    try:
        with _lines_to_stderr():
            run = run_fix_plan(
                get_roadmap_store(target),
                repo=target,
                source=source or model_clone(target),
                confirm=confirm,
                item=item,
                pull=pull,
                model=ToolboxModel(get_task_model("stage")) if confirm else None,
                verifier=ToolboxModel(get_task_model("verification")) if confirm else None,
            )
    except DevOpsCLIError as exc:
        print_error(f"Could not run fix-plan: {exc}", safe=True)
        raise typer.Exit(1) from exc
    write_stdout(render_fix_plan(run) + "\n")
    if not confirm:
        print_info(MESSAGES.roadmap.preview_only)
