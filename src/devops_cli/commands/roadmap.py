"""`devops roadmap`: the roadmap on GitHub, its one-time migration, its generated view, the
current release's rules and intake, the one way new work becomes an item.

Every command reads `.github/roadmap.toml` through the contents API at `--ref`, then opens the
roadmap store on the board it names. `migrate` writes to GitHub only with `--confirm`, and only
once a person has made the option edits its plan lists; `render` writes no GitHub state, only
`docs/ROADMAP.md`, which git review covers. `reprioritize` and `intake` write GitHub state only
with `--confirm`, and never a commit. `intake --dry-run` makes no request at all and prints the
requests a run makes; `intake --plan`, and `intake` with no mode flag, read GitHub and call the
model, write nothing, and report what they spent.
"""

from __future__ import annotations

from collections.abc import Collection, Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn

import typer

from devops_cli.config.constants import (
    CONST_ROADMAP_CONFIG_PATH,
    CONST_ROADMAP_DOCUMENT_PATH,
    CONST_ROADMAP_RENDER_FILE_MODE,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.repo import get_repo_origin_name
from devops_cli.dry_run import is_dry_run
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info, print_success, write_stdout
from devops_cli.output.file_writer import write_text_file
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
    plan_migration,
    render_report,
    require_option_edits_made,
)
from devops_cli.roadmap.render import render_roadmap
from devops_cli.roadmap.reprioritize import (
    apply_reprioritization,
    plan_reprioritization,
    render_plan,
)
from devops_cli.roadmap.store import RoadmapStore

if TYPE_CHECKING:
    from devops_cli.roadmap.github_store import GhRunner

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
    repo: str | None, ref: str | None, runner: GhRunner | None = None
) -> tuple[str, RoadmapConfig, RoadmapStore]:
    """The repository, its roadmap configuration on `ref`, and the store on its board."""
    target = _target(repo)
    config, store = open_roadmap(target, ref=ref, runner=runner)
    return target, config, store


@app.command("migrate", help=HELP.roadmap.migrate)
def migrate_cmd(
    repo: RepoOption = None,
    ref: RefOption = None,
    confirm: Annotated[bool, typer.Option("--confirm", help=HELP.roadmap.confirm)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.migrate_dry_run)] = False,
) -> None:
    """Plan the move of the roadmap's source to GitHub, and make it with --confirm."""
    with _exit_on_failure("Could not plan the roadmap migration"):
        target, config, store = _open_roadmap(repo, ref)
        plan = plan_migration(store, repo=target, ref=ref, config=config)
    write_stdout(render_report(plan))
    if not plan.writes:
        if plan.option_edits:
            print_info(MESSAGES.roadmap.nothing_to_write)
        else:
            print_success(MESSAGES.roadmap.nothing_to_do)
        return
    if dry_run or is_dry_run() or not confirm:
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
) -> None:
    """Write the roadmap's Markdown view from GitHub; a failed read writes nothing."""
    with _exit_on_failure("Could not render the roadmap"):
        target, config, store = _open_roadmap(repo, ref)
        text = render_roadmap(store, repo=target, config=config)
    if dry_run or is_dry_run():
        write_stdout(text)
        return
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
) -> None:
    """Hold the current release to its rules, and start the next one once it ships."""
    with _exit_on_failure("Could not plan reprioritization"):
        target, config, store = _open_roadmap(repo, ref)
        plan = plan_reprioritization(store, repo=target, config=config, now=datetime.now(UTC))
    write_stdout(render_plan(plan))
    if not plan.has_writes:
        return
    if dry_run or is_dry_run() or not confirm:
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
    repo: str | None, ref: str | None, issues: Collection[int], new: NewCandidate | None
) -> None:
    """Print the requests an intake run makes, making none: no store opens, no model is built."""
    target = _target(repo)
    with _exit_on_failure("Could not plan intake"):
        planned = dry_run_intake(target, ref=ref, issues=issues, new=new)
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
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.roadmap.intake_dry_run)] = False,
    plan_only: Annotated[bool, typer.Option("--plan", help=HELP.roadmap.intake_plan)] = False,
    confirm: Annotated[bool, typer.Option("--confirm", help=HELP.roadmap.intake_confirm)] = False,
) -> None:
    """Turn candidates into items: duplicate check, type, priority, Value, Effort and placement."""
    if dry_run + plan_only + confirm > 1:
        _refuse(MESSAGES.roadmap.intake_modes_exclusive)
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
        _intake_dry_run(repo, ref, issue or (), new)
        return
    if not (plan_only or confirm):
        print_info(MESSAGES.roadmap.intake_plain_note)
    meter = SpendMeter()
    with _exit_on_failure("Could not plan intake"):
        target, config, store = _open_roadmap(repo, ref, runner=meter.run)
        plan = plan_intake(
            store,
            config=config,
            model=meter.model(build_intake_model()),
            ref=ref,
            issues=issue or (),
            new=new,
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
