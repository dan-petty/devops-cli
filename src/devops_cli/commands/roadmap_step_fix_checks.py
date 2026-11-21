"""`devops roadmap step fix-checks`: repair a failed check on a pull request (#5023).

The fix-checks Job of the watch row runs this command with `--head` and `--check` (#5027). With
`--confirm`, `--phase` picks the phase of the repair (#6601): `prepare`, `agent` or `publish` on the
run folder `--work`, or `all`, the three in one process, which the Job runs now. Each phase first
makes the process unreadable to its children (`deny_environment_reads`), before it reads a file or
starts a child. While
the step runs, the first SIGTERM, from an eviction, a drain or the deadline of the Job, ends the
command with exit 75 (`EX_TEMPFAIL`) and no result line, so the Service starts the next attempt
within its cap (`sigterm_raises`).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from devops_cli.core.repo import find_repo_root, get_repo_origin_name
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, write_stdout
from devops_cli.roadmap.phases.names import RunPhase

if TYPE_CHECKING:
    from devops_cli.roadmap.phases.files import RunFolders
    from devops_cli.roadmap.steps.fix_checks import FixChecksReport, Repair


def _repository(repo: str | None) -> str:
    """`--repo`, or the origin of the checkout, which reads no network."""
    target = repo or get_repo_origin_name(find_repo_root(Path.cwd()))
    if not target or "/" not in target:
        print_error("Cannot resolve the repository; pass --repo owner/name.")
        raise typer.Exit(1)
    return target


@dry_run_class("request-plan")
def fix_checks_cmd(
    repo: Annotated[str | None, typer.Option("--repo", "-R", help=HELP.roadmap.repo)] = None,
    pull: Annotated[
        int | None, typer.Option("--pull", "-p", min=1, help=HELP.roadmap.step_fix_checks_pull)
    ] = None,
    head: Annotated[
        str | None, typer.Option("--head", help=HELP.roadmap.step_fix_checks_head)
    ] = None,
    check: Annotated[
        str | None, typer.Option("--check", help=HELP.roadmap.step_fix_checks_check)
    ] = None,
    source: Annotated[
        Path | None, typer.Option("--source", help=HELP.roadmap.step_fix_checks_source)
    ] = None,
    confirm: Annotated[
        bool, typer.Option("--confirm", help=HELP.roadmap.step_fix_checks_confirm)
    ] = False,
    phase: Annotated[
        RunPhase, typer.Option("--phase", help=HELP.roadmap.step_fix_checks_phase)
    ] = RunPhase.ALL,
    work: Annotated[
        Path | None, typer.Option("--work", help=HELP.roadmap.step_fix_checks_work)
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.step_fix_checks_dry_run)
    ] = False,
) -> None:
    """Repair a failed check on a pull request (#5023). With `--confirm` the command runs only in
    a runner Job, and gives the step the checkout of the pull request and its fixers (#5971)."""
    if pull is None:
        print_error("Pass --pull <number>.")
        raise typer.Exit(1)
    if phase is not RunPhase.ALL and (not confirm or work is None):
        print_error("A phase other than all runs only with --confirm and --work <folder>.")
        raise typer.Exit(1)
    if dry_run or is_dry_run():
        return
    from devops_cli.roadmap.attempt_kill import AttemptKill, AttemptKilled, sigterm_raises

    try:
        with sigterm_raises():
            report = _run(repo, pull, head, check, source, confirm, phase, work)
    except DevOpsCLIError as exc:
        print_error(f"Could not fix checks on PR #{pull}: {exc}", safe=True)
        raise typer.Exit(1) from exc
    except AttemptKilled:
        print_error(MESSAGES.roadmap.fix_checks_sigterm)
        raise typer.Exit(AttemptKilled(AttemptKill.EVICTED).exit_status) from None
    if report is not None:
        write_stdout(report.to_json() + "\n")


def _run(
    repo: str | None,
    pull: int,
    head: str | None,
    check: str | None,
    source: Path | None,
    confirm: bool,
    phase: RunPhase,
    work: Path | None,
) -> FixChecksReport | None:
    """The round, or the phase of it, that the options ask for: the report, or None for the agent
    phase, for a `prepare` that hands the round on, and for a `publish` of a round that `prepare`
    ended and reported."""
    from devops_cli.roadmap.steps.fix_checks import run_fix_checks
    from devops_cli.roadmap.stores.store import get_roadmap_store

    repair: Repair | None = None
    if confirm:
        from devops_cli.core import process_hardening

        # The repair runs an agent step whose shell has the user of the Job, so the process is
        # unreadable to its children before anything else, and adopts the orphans of a step, as
        # the implement Job does (#2667, #6601).
        process_hardening.deny_environment_reads()
        process_hardening.adopt_orphans()
    target = _repository(repo)
    if confirm:
        from devops_cli.roadmap.implement.implement_run import (
            require_agent_runner,
            require_runner,
        )
        from devops_cli.roadmap.steps.fix_checks_repair import job_repair

        # The agent phase holds the model key only; the other phases act as the App (#6601).
        if phase is RunPhase.AGENT:
            require_agent_runner()
        else:
            require_runner(target)
        repair = job_repair(target, source=source)
    if phase is RunPhase.ALL:
        return run_fix_checks(
            get_roadmap_store(target),
            target,
            pull,
            head=head,
            check=check,
            confirm=confirm,
            repair=repair,
        )
    from devops_cli.roadmap.phases.files import RunFolders

    if repair is None or work is None:
        raise ValueError("A phase needs --confirm and --work")
    return _phase(target, pull, head, check, repair, phase, RunFolders(work))


def _phase(
    target: str,
    pull: int,
    head: str | None,
    check: str | None,
    repair: Repair,
    phase: RunPhase,
    folders: RunFolders,
) -> FixChecksReport | None:
    """One phase on the run folder `folders`. The agent phase makes no GitHub call, so it reads
    no store and gets no client."""
    from devops_cli.github.session import get_github_session
    from devops_cli.roadmap.steps.fix_checks_phases import (
        agent_phase,
        prepare_phase,
        publish_phase,
    )
    from devops_cli.roadmap.stores.store import get_roadmap_store

    if phase is RunPhase.AGENT:
        agent_phase(folders, repair)
        return None
    store = get_roadmap_store(target)
    client = get_github_session().client
    if phase is RunPhase.PREPARE:
        return prepare_phase(
            store, client, target, pull, head=head, check=check, repair=repair, folders=folders
        )
    return publish_phase(
        store, client, folders, repair, repo=target, pull=pull, head=head, check=check
    )
