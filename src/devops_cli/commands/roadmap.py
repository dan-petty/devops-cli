"""`devops roadmap`: the roadmap on GitHub, its one-time migration, its generated view, the
current release's rules and intake, the one way new work becomes an item.

Every command reads `.github/roadmap.toml` through the contents API at `--ref`, then opens the
roadmap store on the board it names. `migrate` writes to GitHub only with `--confirm`, and only
once a person has made the option edits its plan lists; `close` closes delivered items and cuts
the release only with `--confirm`, the cut in the clone at `--root`; `render` writes no GitHub state, only
`docs/ROADMAP.md`, which git review covers. `reprioritize` and `intake` write GitHub state only
with `--confirm`, and never a commit.

Every job's `--dry-run` makes no request at all (#412, #1125): it returns the job's result type
marked as a dry run and prints the requests a run makes, each with its exact `gh` command. Its
`--plan`, and `migrate`, `reprioritize` and `intake` with no mode flag, read GitHub (and, for
intake, call the model) and write nothing. Every run that reads ends with the GraphQL points it
spent and the points left.
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn

import typer

from devops_cli.config.constants import (
    CONST_ROADMAP_CONFIG_PATH,
    CONST_ROADMAP_DOCUMENT_PATH,
    CONST_ROADMAP_INTAKE_BOARD_FILTER,
    CONST_ROADMAP_MIGRATE_BOARD_FILTER,
    CONST_ROADMAP_REFINE_BOARD_FILTER,
    CONST_ROADMAP_RENDER_BOARD_FILTER,
    CONST_ROADMAP_RENDER_FILE_MODE,
    CONST_ROADMAP_REPRIORITIZE_BOARD_FILTER,
    CONST_ROADMAP_RUN_BOARD_FILTER,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_REFINE_LIMIT
from devops_cli.core.cli import new_typer
from devops_cli.core.repo import get_repo_origin_name
from devops_cli.dry_run import is_dry_run
from devops_cli.exceptions import DevOpsCLIError, RoadmapRunError
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info, print_success, write_stdout
from devops_cli.output.file_writer import write_text_file
from devops_cli.roadmap.close import (
    CUT_FILES,
    Cut,
    apply_close,
    dry_run_close,
    plan_close,
    render_close,
)
from devops_cli.roadmap.config import RoadmapConfig, open_roadmap
from devops_cli.roadmap.intake import (
    BorrowReason,
    Filer,
    NewCandidate,
    apply_intake,
    dry_run_intake,
    plan_intake,
    render_intake,
    render_intake_dry_run,
)
from devops_cli.roadmap.intake_model import build_intake_model
from devops_cli.roadmap.intake_requests import SpendMeter
from devops_cli.roadmap.migrate import (
    apply_migration,
    dry_run_migration,
    plan_migration,
    render_report,
    require_option_edits_made,
)
from devops_cli.roadmap.render import dry_run_render, render, render_roadmap
from devops_cli.roadmap.reprioritize import (
    apply_reprioritization,
    dry_run_reprioritization,
    plan_reprioritization,
    render_plan,
)
from devops_cli.roadmap.request_plan import render_dry_run
from devops_cli.roadmap.store import RoadmapStore

if TYPE_CHECKING:
    from devops_cli.github.check_verdict import CheckVerdictSummary
    from devops_cli.roadmap.github_store import GhRunner
    from devops_cli.roadmap.store import MergedPullRequest

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


@app.command("migrate", help=HELP.roadmap.migrate)
def migrate_cmd(
    repo: RepoOption = None,
    ref: RefOption = None,
    confirm: Annotated[bool, typer.Option("--confirm", help=HELP.roadmap.confirm)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.migrate_dry_run)] = False,
    plan_only: Annotated[bool, typer.Option("--plan", help=HELP.roadmap.migrate_plan)] = False,
) -> None:
    """Plan the move of the roadmap's source to GitHub, and make it with --confirm."""
    _one_mode(dry_run=dry_run, plan=plan_only, confirm=confirm)
    if dry_run or is_dry_run():
        target = _target(repo)
        plan = dry_run_migration(target, ref=ref)
        render_dry_run("migrate", target, plan.requests, plan.write_requests)
        return
    opened: list[RoadmapStore] = []
    with _reporting_spend(opened):
        _migrate(repo, ref, confirm=confirm, opened=opened)


def _migrate(
    repo: str | None, ref: str | None, *, confirm: bool, opened: list[RoadmapStore]
) -> None:
    with _exit_on_failure("Could not plan the roadmap migration"):
        target, config, store = _open_roadmap(repo, ref, CONST_ROADMAP_MIGRATE_BOARD_FILTER)
        opened.append(store)
        plan = plan_migration(store, repo=target, ref=ref, config=config)
    write_stdout(render_report(plan))
    if not plan.writes:
        if plan.option_edits:
            print_info(MESSAGES.roadmap.nothing_to_write)
        else:
            print_success(MESSAGES.roadmap.nothing_to_do)
        return
    if not confirm:
        print_info(MESSAGES.roadmap.preview_only)
        return
    with _exit_on_failure("Nothing was written"):
        require_option_edits_made(plan)
    with _exit_on_failure("The roadmap migration stopped part-way; run it again to continue"):
        created = apply_migration(store, plan)
    print_success(MESSAGES.roadmap.applied.format(count=len(plan.writes)))
    if created is not None:
        print_info(
            MESSAGES.roadmap.board_created.format(
                number=created.number, url=created.url, config=CONST_ROADMAP_CONFIG_PATH
            )
        )


@app.command("render", help=HELP.roadmap.render)
def render_cmd(
    repo: RepoOption = None,
    ref: RefOption = None,
    output: Annotated[Path, typer.Option("--output", "-o", help=HELP.roadmap.output)] = Path(
        CONST_ROADMAP_DOCUMENT_PATH
    ),
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.render_dry_run)] = False,
    plan_only: Annotated[bool, typer.Option("--plan", help=HELP.roadmap.render_plan)] = False,
) -> None:
    """Write the roadmap's Markdown view from GitHub; a failed read writes nothing."""
    _one_mode(dry_run=dry_run, plan=plan_only)
    if dry_run or is_dry_run():
        target = _target(repo)
        planned = dry_run_render(target, ref=ref)
        notes = [MESSAGES.roadmap.plan_dry_run_render.format(path=output)]
        render_dry_run("render", target, planned.requests, notes=notes)
        return
    opened: list[RoadmapStore] = []
    with _reporting_spend(opened):
        with _exit_on_failure("Could not render the roadmap"):
            target, config, store = _open_roadmap(repo, ref, CONST_ROADMAP_RENDER_BOARD_FILTER)
            opened.append(store)
            rendered = render(store, repo=target, config=config)
        if plan_only:
            write_stdout(rendered.text)
            return
        _write_render(output, rendered.text)


def _write_render(output: Path, text: str) -> None:
    write_text_file(output, text, mode=CONST_ROADMAP_RENDER_FILE_MODE)
    items = sum(line.startswith("- [") for line in text.splitlines())
    sections = sum(line.startswith("## ") for line in text.splitlines())
    print_success(
        MESSAGES.roadmap.render_written.format(path=output, items=items, sections=sections)
    )


@app.command("reprioritize", help=HELP.roadmap.reprioritize)
def reprioritize_cmd(
    repo: RepoOption = None,
    ref: RefOption = None,
    confirm: Annotated[
        bool, typer.Option("--confirm", help=HELP.roadmap.reprioritize_confirm)
    ] = False,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help=HELP.roadmap.reprioritize_dry_run)
    ] = False,
    plan_only: Annotated[bool, typer.Option("--plan", help=HELP.roadmap.reprioritize_plan)] = False,
) -> None:
    """Hold the current release to its rules, and start the next one once it ships."""
    _one_mode(dry_run=dry_run, plan=plan_only, confirm=confirm)
    if dry_run or is_dry_run():
        target = _target(repo)
        plan = dry_run_reprioritization(target, ref=ref, now=datetime.now(UTC))
        render_dry_run("reprioritize", target, plan.requests, plan.write_requests)
        return
    opened: list[RoadmapStore] = []
    with _reporting_spend(opened):
        _reprioritize(repo, ref, confirm=confirm, opened=opened)


def _reprioritize(
    repo: str | None, ref: str | None, *, confirm: bool, opened: list[RoadmapStore]
) -> None:
    with _exit_on_failure("Could not plan reprioritization"):
        target, config, store = _open_roadmap(repo, ref, CONST_ROADMAP_REPRIORITIZE_BOARD_FILTER)
        opened.append(store)
        plan = plan_reprioritization(store, repo=target, config=config, now=datetime.now(UTC))
    write_stdout(render_plan(plan))
    if not plan.has_writes:
        return
    if not confirm:
        print_info(MESSAGES.roadmap.reprioritize_preview)
        return
    with _exit_on_failure("Reprioritization stopped part-way; run it again to continue"):
        apply_reprioritization(store, plan)
    print_success(
        MESSAGES.roadmap.reprioritize_applied.format(
            changes=len(plan.release_writes) + len(plan.changes), records=plan.records
        )
    )


def _refuse(message: str) -> NoReturn:
    print_error(message)
    raise typer.Exit(1)


def _new_candidate(
    title: str | None, body_file: Path | None, borrow_reason: BorrowReason | None
) -> tuple[str, str] | None:
    """The title and body `--title` and `--body-file` give together, or None when neither is."""
    if title is None and body_file is None:
        if borrow_reason is not None:
            _refuse(MESSAGES.roadmap.intake_borrow_needs_title)
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
    borrow_reason: Annotated[
        BorrowReason | None,
        typer.Option("--borrow-reason", help=HELP.roadmap.intake_borrow_reason),
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
    """Turn candidates into items: duplicate check, type, priority, Value, Effort and placement."""
    _one_mode(dry_run=dry_run, plan=plan_only, confirm=confirm)
    given = _new_candidate(title, body_file, borrow_reason)
    if given is not None and issue:
        _refuse(MESSAGES.roadmap.intake_issue_or_title)
    if borrow_reason is not None and not source:
        _refuse(MESSAGES.roadmap.intake_borrow_needs_source)
    new = (
        NewCandidate(
            title=given[0],
            body=given[1],
            source=source,
            borrow_reason=borrow_reason,
            filed_by=filed_by,
        )
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
    meter = SpendMeter()
    with _exit_on_failure("Could not plan intake"):
        target, config, store = _open_roadmap(
            repo, ref, CONST_ROADMAP_INTAKE_BOARD_FILTER, runner=meter.run
        )
        opened.append(store)
        plan = plan_intake(
            store,
            repo=target,
            config=config,
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
        return
    if not confirm:
        print_info(MESSAGES.roadmap.intake_preview)
        return
    with _exit_on_failure("Intake stopped part-way; run it again to finish"):
        applied = apply_intake(store, plan)
    print_success(
        MESSAGES.roadmap.intake_applied.format(placed=applied.placed, closed=applied.closed)
    )
    for number in applied.filed:
        print_info(MESSAGES.roadmap.intake_filed.format(number=number))
    for number in applied.finished:
        print_info(MESSAGES.roadmap.intake_finished.format(number=number))


@app.command("close", help=HELP.roadmap.close)
def close_cmd(
    repo: RepoOption = None,
    ref: RefOption = None,
    root: Annotated[
        Path, typer.Option("--root", file_okay=False, help=HELP.roadmap.close_root)
    ] = Path(),
    confirm: Annotated[bool, typer.Option("--confirm", help=HELP.roadmap.close_confirm)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.close_dry_run)] = False,
    plan_only: Annotated[bool, typer.Option("--plan", help=HELP.roadmap.close_plan)] = False,
) -> None:
    """Close each delivered item with a summary, and cut the release once it holds no open item."""
    _one_mode(dry_run=dry_run, plan=plan_only, confirm=confirm)
    if dry_run or is_dry_run():
        target = _target(repo)
        plan = dry_run_close(target, ref=ref)
        notes = [MESSAGES.roadmap.close_dry_run_note.format(files=", ".join(CUT_FILES))]
        render_dry_run("close", target, plan.requests, plan.write_requests, notes=notes)
        return
    opened: list[RoadmapStore] = []
    with _reporting_spend(opened):
        _close(repo, ref, root, confirm=confirm, opened=opened)


def _close(
    repo: str | None, ref: str | None, root: Path, *, confirm: bool, opened: list[RoadmapStore]
) -> None:
    from devops_cli.github.check_verdict import fetch_pr_check_verdicts

    with _exit_on_failure("Could not plan closure"):
        target, config, store = _open_roadmap(repo, ref, CONST_ROADMAP_RENDER_BOARD_FILTER)
        opened.append(store)

        def checks(pull_request: MergedPullRequest) -> CheckVerdictSummary:
            return fetch_pr_check_verdicts(
                pull_request.number, repo=target, head_sha=pull_request.head_commit
            )

        plan = plan_close(store, repo=target, checks=checks)
    write_stdout(render_close(plan))
    if plan.has_writes and not confirm:
        print_info(MESSAGES.roadmap.close_preview)
    elif plan.has_writes:

        def cut(planned: Cut) -> None:
            from devops_cli.commands.release import cut_release

            def write_roadmap(clone: Path) -> None:
                text = render_roadmap(store, repo=target, config=config)
                write_text_file(
                    clone / CONST_ROADMAP_DOCUMENT_PATH, text, mode=CONST_ROADMAP_RENDER_FILE_MODE
                )

            cut_release(
                version=planned.version,
                base=planned.base,
                draft=False,
                sync_docs=False,
                is_prepare=True,
                repo_root=root.resolve(),
                edits=write_roadmap,
            )

        with _exit_on_failure("Closure stopped part-way; run it again to continue"):
            apply_close(store, plan, cut)
        print_success(MESSAGES.roadmap.close_applied.format(count=len(plan.closings)))
    if plan.unread:
        print_error(MESSAGES.roadmap.close_failed.format(count=len(plan.unread)))
        raise typer.Exit(1)


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
    from devops_cli.roadmap.refine import (
        apply_refine,
        plan_refine,
        raise_for_failed_items,
        render_refine_plan,
    )

    target_repo = repo or get_repo_origin_name(source)
    if not target_repo or "/" not in target_repo:
        print_error("Cannot resolve the repository; pass --repo owner/name.")
        raise typer.Exit(1)

    opened: list[RoadmapStore] = []
    with _reporting_spend(opened):
        with _exit_on_failure("Could not plan refinement"):
            _, config, store = _open_roadmap(target_repo, ref, CONST_ROADMAP_REFINE_BOARD_FILTER)
            opened.append(store)
            plan = plan_refine(
                store,
                repo=target_repo,
                source=source,
                ref=ref,
                item_number=item,
                limit=limit,
                config=config,
            )
        write_stdout(render_refine_plan(plan) + "\n")
        if dry_run or not confirm or is_dry_run():
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
    """Run the roadmap jobs that are due, in order: closure, reprioritization, metrics, intake
    and refinement."""
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
        msg = f"Roadmap jobs failed: {', '.join(exc.failed_jobs)}" if exc.failed_jobs else str(exc)
        print_error(msg)
        raise typer.Exit(1) from exc
