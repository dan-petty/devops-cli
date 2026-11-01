"""Branches command group: update, jira, list, clean."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.constants import CONST_GIT_DIR_NAME
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer, repo_label
from devops_cli.dry_run import is_dry_run
from devops_cli.dry_run.decorator import dry_run_class
from devops_cli.dry_run.requests import PlannedRequest, render_request_plan
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.git.git_plans import plan_repo_sync
from devops_cli.git.operations import (
    create_branch,
    delete_merged_branches,
    fetch_all,
    iter_workspace_repos,
    list_branches,
    pull_tracking,
)
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info, print_success, print_table

app = new_typer(help=HELP.branches.app, no_args_is_help=True)

_JIRA_RE = re.compile(r"^([A-Z][A-Z0-9]+-\d+)$", re.IGNORECASE)


# =============================================================================
# Command: devops branches update / sync
# =============================================================================


@app.command("sync")
@app.command()
@dry_run_class("request-plan")
def update(
    base_dir: Annotated[
        Path | None, typer.Option("--base-dir", "-d", help=HELP.options.base_dir)
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Fetch and pull tracking branches across all repos."""
    settings = load_settings()
    root = base_dir or settings.repos.base_dir

    if dry_run or is_dry_run():
        _plan_update(root)
        return

    failed = False
    for repo_dir in iter_workspace_repos(root):
        label = repo_label(repo_dir)
        try:
            fetch_all(repo_dir)
            pull_tracking(repo_dir)
            print_success(label)
        except (DevOpsCLIError, OSError, ValueError) as exc:
            failed = True
            print_error(f"{label}: {exc}")

    if failed:
        raise typer.Exit(1)


def _plan_update(root: Path) -> None:
    """Print the fetches and pulls of `branches sync`, and make none. A repository whose plan
    fails is reported as the run reports it, and the exit status is 1."""
    requests: list[PlannedRequest] = []
    failed = False
    for repo_dir in iter_workspace_repos(root):
        label = repo_label(repo_dir)
        try:
            requests.extend(plan_repo_sync(repo_dir, label))
        except (DevOpsCLIError, OSError, ValueError) as exc:
            failed = True
            print_error(f"{label}: {exc}")
    render_request_plan(MESSAGES.branches.sync_dry_run_heading, requests)
    if failed:
        raise typer.Exit(1)


# =============================================================================
# Command: devops branches jira
# =============================================================================


@app.command()
@dry_run_class("no-external-request")
def jira(
    ticket_id: Annotated[str, typer.Argument(help=HELP.branches.ticket_id)],
    slug: Annotated[str | None, typer.Option("--slug", "-s", help=HELP.branches.slug)] = None,
    repo: Annotated[Path | None, typer.Option("--repo", "-r", help=HELP.options.repo)] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Create a feature branch for a Jira ticket: feature/PROJ-123[-slug]."""
    if not _JIRA_RE.fullmatch(ticket_id):
        err_msg = MESSAGES.branches.invalid_ticket_id.format(ticket_id=ticket_id)
        print_error(err_msg, prefix=False)
        raise typer.Exit(1)

    repo_path = repo or Path.cwd()
    if not (repo_path / CONST_GIT_DIR_NAME).exists():
        err_msg = MESSAGES.branches.not_a_git_repo.format(repo_path=repo_path)
        print_error(err_msg, prefix=False)
        raise typer.Exit(1)

    ticket_upper = ticket_id.upper()
    if slug:
        safe_slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
        branch_name = f"feature/{ticket_upper}-{safe_slug}"
    else:
        branch_name = f"feature/{ticket_upper}"

    if dry_run or is_dry_run():
        print_info(MESSAGES.branches.jira_dry_run.format(branch_name=branch_name), prefix=False)
        return

    try:
        create_branch(repo_path, branch_name)
        ok_msg = MESSAGES.branches.created_branch.format(branch_name=branch_name)
        print_success(ok_msg, prefix=False)
    except ValueError as exc:
        print_error(str(exc), prefix=False)
        raise typer.Exit(1) from exc


# =============================================================================
# Command: devops branches list
# =============================================================================


@app.command("list")
@dry_run_class("no-external-request")
def list_all(
    base_dir: Annotated[
        Path | None, typer.Option("--base-dir", "-d", help=HELP.options.base_dir)
    ] = None,
    all_branches: Annotated[
        bool, typer.Option("--all", "-a", help=HELP.branches.all_branches)
    ] = False,
) -> None:
    """List branches across all repos."""
    settings = load_settings()
    root = base_dir or settings.repos.base_dir

    rows: list[list[str]] = []
    for repo_dir in iter_workspace_repos(root):
        label = repo_label(repo_dir)
        result = list_branches(repo_dir, all_branches=all_branches)
        for branch in result.branches:
            indicator = "[green]●[/green]" if branch == result.current else ""
            rows.append([label, branch, indicator])

    print_table(
        title="Branches across repositories",
        columns=[("Repo", "cyan"), "Branch", ("", "center")],
        rows=rows,
    )


# =============================================================================
# Command: devops branches clean
# =============================================================================


@app.command()
@dry_run_class("no-external-request")
def clean(
    base_dir: Annotated[
        Path | None, typer.Option("--base-dir", "-d", help=HELP.options.base_dir)
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help=HELP.options.dry_run)] = False,
) -> None:
    """Delete local branches merged into main/master."""
    dry_run = dry_run or is_dry_run()
    settings = load_settings()
    root = base_dir or settings.repos.base_dir
    any_deleted = False

    for repo_dir in iter_workspace_repos(root):
        label = repo_label(repo_dir)
        deleted = delete_merged_branches(repo_dir, dry_run=dry_run)
        for branch in deleted:
            any_deleted = True
            verb = "[yellow]would delete[/yellow]" if dry_run else "[red]deleted[/red]"
            print_info(f"{verb} {label}: [bold]{branch}[/bold]", prefix=False)

    if not any_deleted:
        print_success(MESSAGES.branches.no_merged_branches, prefix=False)
