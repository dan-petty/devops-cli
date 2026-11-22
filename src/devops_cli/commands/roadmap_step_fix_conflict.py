"""`devops roadmap step fix-conflict`: settle merge conflicts on a pull request (#5019).

Tier 1 runs code of the checkout of the pull request (`devops docs generate`, `uv lock`). So
`--confirm`, which runs tier 1 and pushes, runs only in a runner Job (`require_runner`). With
`--confirm`, `--phase` picks the phase of the round (#6703): `prepare`, `agent` or `publish` on the
run folder `--work`, or `all`, the three in one process. Each phase first makes its process
unreadable and adopts orphans; the agent phase then checks that it holds no App key, and the other
phases that they act as the App. Without `--confirm` the step prints its plan, runs no code of the
checkout and writes nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from devops_cli.core.repo import find_repo_root, get_repo_origin_name
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.lang import HELP
from devops_cli.output import print_error, write_stdout
from devops_cli.roadmap.phases.names import RunPhase

if TYPE_CHECKING:
    from devops_cli.roadmap.steps.fix_conflict import FixConflictReport


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
    phase: Annotated[
        RunPhase, typer.Option("--phase", help=HELP.roadmap.step_fix_conflict_phase)
    ] = RunPhase.ALL,
    work: Annotated[
        Path | None, typer.Option("--work", help=HELP.roadmap.step_fix_conflict_work)
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.step_fix_conflict_dry_run)
    ] = False,
) -> None:
    """Settle merge conflicts on a pull request with the default branch (#5019). With `--confirm`
    the command runs only in a runner Job, and hardens its process before the step."""
    if pull is None:
        print_error("Pass --pull <number>.")
        raise typer.Exit(1)
    if phase is not RunPhase.ALL and confirm and work is None:
        print_error("A phase of a round runs only with --work <folder>.")
        raise typer.Exit(1)
    if dry_run or is_dry_run():
        return
    try:
        report = _run(repo, pull, head, confirm, phase, work)
    except DevOpsCLIError as exc:
        print_error(f"Could not fix conflicts on PR #{pull}: {exc}", safe=True)
        raise typer.Exit(1) from exc
    if report is not None:
        write_stdout(report.to_json() + "\n")


def _run(
    repo: str | None,
    pull: int,
    head: str | None,
    confirm: bool,
    phase: RunPhase,
    work: Path | None,
) -> FixConflictReport | None:
    """The round, or the phase of it, that the options ask for: the report, or None for the agent
    phase, for a `prepare` that hands the round on, for a `publish` of a round that `prepare`
    ended and reported, and for `agent` and `publish` of a plan."""
    from devops_cli.roadmap.steps.fix_conflict import run_fix_conflict
    from devops_cli.roadmap.stores.store import get_roadmap_store

    if confirm:
        from devops_cli.core import process_hardening

        # Tier 1 runs code of the pull request as the user of the Job, so the process is
        # unreadable to its children before anything else, and adopts the orphans of that code,
        # as the fix-checks Job does.
        process_hardening.deny_environment_reads()
        process_hardening.adopt_orphans()
    target = _repository(repo)
    if confirm:
        from devops_cli.roadmap.implement.implement_run import (
            require_agent_runner,
            require_runner,
        )

        # The agent phase holds the model key only; the other phases act as the App.
        if phase is RunPhase.AGENT:
            require_agent_runner()
        else:
            require_runner(target)
    if phase is RunPhase.ALL or (not confirm and phase is RunPhase.PREPARE):
        return run_fix_conflict(get_roadmap_store(target), target, pull, head=head, confirm=confirm)
    # The command refuses a confirmed phase with no `--work`, so a phase with no run folder is a
    # plan: `agent` and `publish` of a plan do nothing.
    if not confirm or work is None:
        return None
    return _phase(target, pull, head, phase, work)


def _phase(
    target: str, pull: int, head: str | None, phase: RunPhase, work: Path
) -> FixConflictReport | None:
    """One phase on the run folder `work`. The agent phase makes no GitHub call, so it reads no
    store and gets no client."""
    from devops_cli.github.session import get_github_session
    from devops_cli.roadmap.phases.files import RunFolders
    from devops_cli.roadmap.steps.fix_conflict_phases import (
        agent_phase,
        prepare_phase,
        publish_phase,
    )
    from devops_cli.roadmap.stores.store import get_roadmap_store

    folders = RunFolders(work)
    if phase is RunPhase.AGENT:
        agent_phase(folders)
        return None
    store = get_roadmap_store(target)
    client = get_github_session().client
    if phase is RunPhase.PREPARE:
        return prepare_phase(store, client, target, pull, head=head, folders=folders)
    return publish_phase(store, client, folders, repo=target, pull=pull, head=head)
