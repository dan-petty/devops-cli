"""`devops roadmap`: the roadmap on GitHub, its one-time migration, its generated view and the
current release's rules.

Every command reads `.github/roadmap.toml` through the contents API at `--ref`, then opens the
roadmap store on the board it names. `migrate` writes to GitHub only with `--confirm`, and only
once a person has made the option edits its plan lists; `render` writes no GitHub state, only
`docs/ROADMAP.md`, which git review covers. `reprioritize` writes GitHub state only with
`--confirm`, and never a commit.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

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
from devops_cli.roadmap import store as roadmap_store
from devops_cli.roadmap.config import RoadmapConfig, read_roadmap_config
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


def _open_roadmap(repo: str | None, ref: str | None) -> tuple[str, RoadmapConfig, RoadmapStore]:
    """The repository, its roadmap configuration on `ref`, and the store on its board."""
    target = repo or get_repo_origin_name()
    if not target or "/" not in target:
        print_error("Cannot resolve the repository; pass --repo owner/name.")
        raise typer.Exit(1)
    config = read_roadmap_config(roadmap_store.get_roadmap_store(target), ref=ref)
    owner = target.split("/")[0]
    store = roadmap_store.get_roadmap_store(target, board_owner=owner, board_number=config.board)
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
