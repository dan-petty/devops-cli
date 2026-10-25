"""`devops roadmap`: the roadmap on GitHub. Intake is the one way new work becomes an item,
refine readies items, and return sends an item back to New.

Every command reads `.github/roadmap.toml` through the contents API at `--ref`, then opens the
roadmap store on the board it names. `intake`, `refine` and `return` write GitHub state only
with `--confirm`, and never a commit. A person plans the milestones on the board; no command
sets one.

Every job's `--dry-run` makes no request at all (#412, #1125): it returns the job's result type
marked as a dry run and prints the requests a run makes, each with its exact `gh` command.
Intake's `--plan`, and intake with no mode flag, read GitHub and call the model, and write
nothing. Every run that reads ends with the GraphQL points it spent and the points left.
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn

import typer

from devops_cli.config.constants import (
    CONST_ROADMAP_INTAKE_BOARD_FILTER,
    CONST_ROADMAP_REFINE_BOARD_FILTER,
    CONST_ROADMAP_RUN_BOARD_FILTER,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_REFINE_LIMIT
from devops_cli.core.cli import new_typer
from devops_cli.core.repo import get_repo_origin_name
from devops_cli.dry_run import is_dry_run
from devops_cli.exceptions import DevOpsCLIError, RoadmapRunError
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info, print_success, write_stdout
from devops_cli.roadmap.config import RoadmapConfig, open_roadmap
from devops_cli.roadmap.intake import (
    Filer,
    NewCandidate,
    Outcome,
    apply_intake,
    dry_run_intake,
    plan_intake,
    raise_for_failed_placements,
    render_intake,
    render_intake_dry_run,
)
from devops_cli.roadmap.intake_model import build_intake_model
from devops_cli.roadmap.intake_requests import SpendMeter
from devops_cli.roadmap.request_plan import render_dry_run
from devops_cli.roadmap.store import RoadmapStore

if TYPE_CHECKING:
    from devops_cli.roadmap.github_store import GhRunner

logger = logging.getLogger(__name__)

app = new_typer(help=HELP.roadmap.app, no_args_is_help=True)

RepoOption = Annotated[str | None, typer.Option("--repo", "-R", help=HELP.roadmap.repo)]
RefOption = Annotated[str | None, typer.Option("--ref", help=HELP.roadmap.ref)]


@contextmanager
def _exit_on_failure(action: str) -> Iterator[None]:
    """Report a failed read or write as `action` failing, and exit 1."""
    try:
        yield
    except DevOpsCLIError as exc:
        print_error(f"{action}: {exc}", safe=True)
        raise typer.Exit(1) from exc


def _target(repo: str | None) -> str:
    """The repository: `--repo`, or the checkout's origin, which reads no network."""
    target = repo or get_repo_origin_name()
    if not target or "/" not in target:
        print_error("Cannot resolve the repository; pass --repo owner/name.")
        raise typer.Exit(1)
    return target


def _open_roadmap(
    repo: str | None, ref: str | None, board_filter: str, runner: GhRunner | None = None
) -> tuple[str, RoadmapConfig, RoadmapStore]:
    """The repository, its roadmap configuration on `ref`, and the store on its board, whose
    board reads pass the job's Projects filter."""
    target = _target(repo)
    config, store = open_roadmap(target, ref=ref, runner=runner, board_filter=board_filter)
    return target, config, store


def _one_mode(**modes: bool) -> None:
    """Refuse more than one mode flag."""
    if sum(modes.values()) > 1:
        flags = [f"--{name.replace('_', '-')}" for name in modes]
        listed = f"{', '.join(flags[:-1])} and {flags[-1]}"
        _refuse(MESSAGES.roadmap.plan_modes_exclusive.format(modes=listed))


@contextmanager
def _reporting_spend(stores: list[RoadmapStore]) -> Iterator[None]:
    """End the run, however it ends, with the GraphQL points it spent and the points left, read
    from GraphQL itself, once it has opened a store that spends them (#1125)."""
    try:
        yield
    finally:
        for store in stores:
            try:
                spend = store.graphql_spend()
            except DevOpsCLIError as exc:
                logger.warning("Could not read the GraphQL budget: %s", exc)
                continue
            if spend is not None:
                print_info(spend.line())


def _refuse(message: str) -> NoReturn:
    print_error(message)
    raise typer.Exit(1)


def _new_candidate(title: str | None, body_file: Path | None) -> tuple[str, str] | None:
    """The title and body `--title` and `--body-file` give together, or None when neither is."""
    if title is None and body_file is None:
        return None
    if title is None or body_file is None:
        _refuse(MESSAGES.roadmap.intake_title_needs_body)
    return title, body_file.read_text(encoding="utf-8")


def _intake_dry_run(
    repo: str | None,
    ref: str | None,
    issues: Collection[int],
    new: NewCandidate | None,
    limit: int | None,
) -> None:
    """Print the requests an intake run makes, making none: no store opens, no model is built."""
    target = _target(repo)
    with _exit_on_failure("Could not plan intake"):
        planned = dry_run_intake(target, ref=ref, issues=issues, new=new, limit=limit)
    render_intake_dry_run(planned, repo=target)


@app.command("intake", help=HELP.roadmap.intake)
def intake_cmd(
    repo: RepoOption = None,
    ref: RefOption = None,
    issue: Annotated[
        list[int] | None, typer.Option("--issue", min=1, help=HELP.roadmap.intake_issue)
    ] = None,
    title: Annotated[str | None, typer.Option("--title", help=HELP.roadmap.intake_title)] = None,
    body_file: Annotated[
        Path | None,
        typer.Option(
            "--body-file", exists=True, dir_okay=False, help=HELP.roadmap.intake_body_file
        ),
    ] = None,
    source: Annotated[str | None, typer.Option("--source", help=HELP.roadmap.intake_source)] = None,
    filed_by: Annotated[
        Filer, typer.Option("--filed-by", help=HELP.roadmap.intake_filed_by)
    ] = Filer.AGENT,
    limit: Annotated[
        int | None, typer.Option("--limit", min=1, help=HELP.roadmap.intake_limit)
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.intake_dry_run)] = False,
    plan_only: Annotated[bool, typer.Option("--plan", help=HELP.roadmap.intake_plan)] = False,
    confirm: Annotated[bool, typer.Option("--confirm", help=HELP.roadmap.intake_confirm)] = False,
) -> None:
    """Turn candidates into items: possible duplicates, type, priority, Value, Effort and
    placement."""
    _one_mode(dry_run=dry_run, plan=plan_only, confirm=confirm)
    given = _new_candidate(title, body_file)
    if given is not None and issue:
        _refuse(MESSAGES.roadmap.intake_issue_or_title)
    new = (
        NewCandidate(title=given[0], body=given[1], source=source, filed_by=filed_by)
        if given is not None
        else None
    )
    if dry_run or is_dry_run():
        _intake_dry_run(repo, ref, issue or (), new, limit)
        return
    if not (plan_only or confirm):
        print_info(MESSAGES.roadmap.intake_plain_note)
    opened: list[RoadmapStore] = []
    with _reporting_spend(opened):
        _intake(repo, ref, issue or (), new, limit, confirm=confirm, opened=opened)


def _intake(
    repo: str | None,
    ref: str | None,
    issues: Sequence[int],
    new: NewCandidate | None,
    limit: int | None,
    *,
    confirm: bool,
    opened: list[RoadmapStore],
) -> None:
    with _exit_on_failure("Could not plan intake"):
        # Counts from here the requests the identity's ledger paces, gh's and the session's.
        meter = SpendMeter()
        target, _config, store = _open_roadmap(repo, ref, CONST_ROADMAP_INTAKE_BOARD_FILTER)
        opened.append(store)
        plan = plan_intake(
            store,
            repo=target,
            model=meter.model(build_intake_model()),
            ref=ref,
            issues=issues,
            new=new,
            limit=limit,
        )
    if not confirm:
        plan = replace(plan, spend=meter.spend())
    write_stdout(render_intake(plan, repo=target))
    if not plan.has_writes:
        if new is not None and confirm and any(d.outcome is Outcome.SKIP for d in plan.decisions):
            raise typer.Exit(1)
        return
    if not confirm:
        print_info(MESSAGES.roadmap.intake_preview)
        return
    with _exit_on_failure("Intake stopped part-way; run it again to finish"):
        applied = apply_intake(store, plan)
    print_success(MESSAGES.roadmap.intake_applied.format(placed=applied.placed))
    for number in applied.filed:
        print_info(MESSAGES.roadmap.intake_filed.format(number=number))
    for number in applied.finished:
        print_info(MESSAGES.roadmap.intake_finished.format(number=number))
    with _exit_on_failure("Intake finished with candidates it could not write"):
        raise_for_failed_placements(applied)


@app.command("refine", help=HELP.roadmap.refine)
def refine_cmd(
    repo: RepoOption = None,
    ref: RefOption = None,
    source: Annotated[Path, typer.Option("--source", help=HELP.roadmap.refine_source)] = Path("."),
    item: Annotated[int | None, typer.Option("--item", help=HELP.roadmap.refine_item)] = None,
    limit: Annotated[
        int, typer.Option("--limit", help=HELP.roadmap.refine_limit)
    ] = DEFAULT_ROADMAP_REFINE_LIMIT,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.refine_dry_run)] = False,
    confirm: Annotated[bool, typer.Option("--confirm", help=HELP.roadmap.refine_confirm)] = False,
) -> None:
    """Refine roadmap items to Ready with proposed design, tasks and acceptance criteria."""
    _one_mode(dry_run=dry_run, confirm=confirm)
    target_repo = repo or get_repo_origin_name(source)
    if not target_repo or "/" not in target_repo:
        print_error("Cannot resolve the repository; pass --repo owner/name.")
        raise typer.Exit(1)

    if dry_run or is_dry_run():
        from devops_cli.roadmap.refine import dry_run_refine
        from devops_cli.roadmap.request_plan import render_dry_run

        plan = dry_run_refine(target_repo, ref=ref, item=item, limit=limit)
        render_dry_run("refine", target_repo, plan.requests, plan.write_requests)
        return

    from devops_cli.roadmap.refine import (
        apply_refine,
        plan_refine,
        raise_for_failed_items,
        render_refine_plan,
    )

    opened: list[RoadmapStore] = []
    with _reporting_spend(opened):
        with _exit_on_failure("Could not plan refinement"):
            _, _config, store = _open_roadmap(target_repo, ref, CONST_ROADMAP_REFINE_BOARD_FILTER)
            opened.append(store)
            plan = plan_refine(
                store, repo=target_repo, source=source, ref=ref, item_number=item, limit=limit
            )
        write_stdout(render_refine_plan(plan) + "\n")
        if not confirm:
            print_info(MESSAGES.roadmap.preview_only)
        elif plan.has_writes:
            with _exit_on_failure("Could not apply refinement"):
                applied = apply_refine(store, plan)
                print_success(
                    f"Refined {applied.refined_count} item(s): {applied.readied_count} set to "
                    f"Ready, {applied.split_count} marked for split."
                )
        with _exit_on_failure("Refinement incomplete"):
            raise_for_failed_items(plan)


@app.command("run", help=HELP.roadmap.run)
def run_cmd(
    repo: RepoOption = None,
    ref: RefOption = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.run_dry_run)] = False,
    confirm: Annotated[bool, typer.Option("--confirm", help=HELP.roadmap.run_confirm)] = False,
) -> None:
    """Run the roadmap jobs that are due, in order: metrics, intake and refinement."""
    target, _config, store = _open_roadmap(repo, ref, CONST_ROADMAP_RUN_BOARD_FILTER)
    from devops_cli.roadmap.run import run_due_jobs

    if dry_run or not confirm or is_dry_run():
        due = run_due_jobs(target, store, batch={("poll", "", ""): 1}, dry_run=True)
        if due:
            write_stdout(f"Due: {', '.join(due)}\n")
        else:
            write_stdout("Due: (none)\n")
        return

    try:
        ran = run_due_jobs(target, store, batch={("poll", "", ""): 1}, dry_run=False)
        if ran:
            print_success(f"Roadmap jobs completed: {', '.join(ran)}")
    except RoadmapRunError as exc:
        print_error(str(exc), safe=True)
        raise typer.Exit(1) from exc


def _resolve_comment(comment: str, comment_file: Path | None) -> str:
    """Extract comment text from inline option or file, raising if invalid or missing."""
    clean = comment.strip()
    if comment_file is not None:
        if not comment_file.is_file():
            print_error(f"Comment file not found: {comment_file}")
            raise typer.Exit(1)
        clean = comment_file.read_text(encoding="utf-8").strip()
    if not clean:
        print_error("An evidence comment is required (--comment or --comment-file).")
        raise typer.Exit(1)
    return clean


@app.command("return", help=HELP.roadmap.return_item)
def return_cmd(
    item: Annotated[int, typer.Argument(help=HELP.roadmap.return_item_arg)],
    comment: Annotated[str, typer.Option("--comment", "-c", help=HELP.roadmap.return_comment)] = "",
    comment_file: Annotated[
        Path | None, typer.Option("--comment-file", help=HELP.roadmap.return_comment_file)
    ] = None,
    repo: RepoOption = None,
    ref: RefOption = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.return_dry_run)] = False,
    confirm: Annotated[bool, typer.Option("--confirm", help=HELP.roadmap.return_confirm)] = False,
) -> None:
    """Return an item to New on the roadmap board with an evidence comment."""
    _one_mode(dry_run=dry_run, confirm=confirm)
    clean_comment = _resolve_comment(comment, comment_file)
    target = _target(repo)

    from devops_cli.roadmap.return_item import (
        apply_return,
        dry_run_return,
        plan_return,
        render_return_plan,
    )

    if dry_run or is_dry_run():
        reads, writes = dry_run_return(target, item)
        render_dry_run("return", target, reads, writes)
        return

    opened: list[RoadmapStore] = []
    with _reporting_spend(opened):
        with _exit_on_failure("Could not return roadmap item"):
            _, _cfg, store = _open_roadmap(target, ref, CONST_ROADMAP_REFINE_BOARD_FILTER)
            opened.append(store)
            plan = plan_return(store, item, clean_comment, target)
            if not confirm:
                write_stdout(render_return_plan(plan) + "\n\nPlan only: pass --confirm to apply.\n")
                return
            apply_return(store, plan)
            print_success(f"Returned item #{item} to New and posted evidence comment.")
