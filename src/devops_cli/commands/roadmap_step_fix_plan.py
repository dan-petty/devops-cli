"""`devops roadmap step fix-plan`: one repair of an open plan pull request that holds the label
`plan/needs-fix` (#5061). The step is `devops_cli.roadmap.steps.fix_plan`. Without `--confirm` the
command prints the plan pull request that the step selects, calls no model and writes nothing.
`--confirm` runs the attempt in every mode of `roadmap.fix_plan.mode`, because a person chose it.
`--dry-run` makes no request. During an attempt the command writes the line of each round and the
result line of the step to stderr as they come (#5363): a Job runs the command, and its log is what
the command writes, so a pod that the deadline of its Job stops still leaves these lines. The
Service writes the same lines in its own log. `--skip-wait` leaves out the wait of 6 hours for the
one item that `--item` or `--pull` names, and needs `--confirm` (#5413). While the step runs, the
first SIGTERM ends the attempt as a kill (`sigterm_raises`): the step writes the class of the kill,
and the command exits 75 for `evicted` and 143 for `deadline`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from devops_cli.core.repo import find_repo_root, get_repo_origin_name
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info, write_stdout


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
    skip_wait: Annotated[
        bool, typer.Option("--skip-wait", help=HELP.roadmap.step_fix_plan_skip_wait)
    ] = False,
) -> None:
    """Repair one open plan pull request that holds the label plan/needs-fix."""
    if dry_run and confirm:
        print_error(MESSAGES.roadmap.plan_modes_exclusive.format(modes="--dry-run and --confirm"))
        raise typer.Exit(1)
    if item is not None and pull is not None:
        print_error(MESSAGES.roadmap.plan_modes_exclusive.format(modes="--item and --pull"))
        raise typer.Exit(1)
    if skip_wait and (not confirm or (item is None and pull is None)):
        print_error(MESSAGES.roadmap.fix_plan_skip_wait_needs)
        raise typer.Exit(1)
    from devops_cli.roadmap.attempt_kill import AttemptKilled, sigterm_raises
    from devops_cli.roadmap.job_result import job_lines_to_stderr
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
        with job_lines_to_stderr(), sigterm_raises():
            run = run_fix_plan(
                get_roadmap_store(target),
                repo=target,
                source=source or model_clone(target),
                confirm=confirm,
                item=item,
                pull=pull,
                model=ToolboxModel(get_task_model("stage")) if confirm else None,
                verifier=ToolboxModel(get_task_model("verification")) if confirm else None,
                skip_wait=skip_wait,
            )
    except DevOpsCLIError as exc:
        print_error(f"Could not run fix-plan: {exc}", safe=True)
        raise typer.Exit(1) from exc
    except AttemptKilled as killed:
        kill = killed.kill.value if killed.kill is not None else "none"
        print_error(MESSAGES.roadmap.fix_plan_sigterm.format(kill=kill))
        raise typer.Exit(killed.exit_status) from None
    write_stdout(render_fix_plan(run) + "\n")
    if not confirm:
        print_info(MESSAGES.roadmap.preview_only)
