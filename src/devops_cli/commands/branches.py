"""Branches command group: update, jira, list, clean."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.config.constants import CONST_GIT_DIR_NAME
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer, repo_label
from devops_cli.git.operations import (
    create_branch,
    delete_merged_branches,
    fetch_all,
    iter_workspace_repos,
    list_branches,
    pull_tracking,
)
from devops_cli.lang import MESSAGES

app = new_typer(help="Branch management and Jira workflows.", no_args_is_help=True)
console = Console()

_JIRA_RE = re.compile(r"^([A-Z][A-Z0-9]+-\d+)$", re.IGNORECASE)


@app.command("sync")
@app.command()
def update(
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
) -> None:
    """Fetch and pull tracking branches across all repos."""
    settings = load_settings()
    root = base_dir or settings.repos.base_dir

    for repo_dir in iter_workspace_repos(root):
        label = repo_label(repo_dir)
        try:
            fetch_all(repo_dir)
            pull_tracking(repo_dir)
            rprint(f"[green]✓[/green] {label}")
        except Exception as exc:
            rprint(f"[red]✗[/red] {label}: {exc}")


@app.command()
def jira(
    ticket_id: Annotated[str, typer.Argument(help="Jira ticket ID, e.g. PROJ-123")],
    slug: Annotated[
        str | None, typer.Option("--slug", "-s", help="Short branch description")
    ] = None,
    repo: Annotated[
        Path | None, typer.Option("--repo", "-r", help="Target repo (default: cwd)")
    ] = None,
) -> None:
    """Create a feature branch for a Jira ticket: feature/PROJ-123[-slug]."""
    if not _JIRA_RE.match(ticket_id):
        err_msg = MESSAGES.branches.invalid_ticket_id.format(ticket_id=ticket_id)
        rprint(f"[red]{err_msg}[/red]")
        raise typer.Exit(1)

    repo_path = repo or Path.cwd()
    if not (repo_path / CONST_GIT_DIR_NAME).exists():
        err_msg = MESSAGES.branches.not_a_git_repo.format(repo_path=repo_path)
        rprint(f"[red]{err_msg}[/red]")
        raise typer.Exit(1)

    ticket_upper = ticket_id.upper()
    if slug:
        safe_slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
        branch_name = f"feature/{ticket_upper}-{safe_slug}"
    else:
        branch_name = f"feature/{ticket_upper}"

    try:
        create_branch(repo_path, branch_name)
        ok_msg = MESSAGES.branches.created_branch.format(branch_name=branch_name)
        rprint(f"[green]{ok_msg}[/green]")
    except ValueError as exc:
        rprint(f"[red]{exc}[/red]")
        raise typer.Exit(1)


@app.command("list")
def list_all(
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
    all_branches: Annotated[
        bool, typer.Option("--all", "-a", help="Include remote branches")
    ] = False,
) -> None:
    """List branches across all repos."""
    settings = load_settings()
    root = base_dir or settings.repos.base_dir

    table = Table(title="Branches across repositories")
    table.add_column("Repo", style="cyan")
    table.add_column("Branch")
    table.add_column("", justify="center")  # current indicator

    for repo_dir in iter_workspace_repos(root):
        label = repo_label(repo_dir)
        result = list_branches(repo_dir, all_branches=all_branches)
        for branch in result.branches:
            indicator = "[green]●[/green]" if branch == result.current else ""
            table.add_row(label, branch, indicator)

    console.print(table)


@app.command()
def clean(
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", "-n", help="Show what would be deleted")
    ] = False,
) -> None:
    """Delete local branches merged into main/master."""
    settings = load_settings()
    root = base_dir or settings.repos.base_dir
    any_deleted = False

    for repo_dir in iter_workspace_repos(root):
        label = repo_label(repo_dir)
        deleted = delete_merged_branches(repo_dir, dry_run=dry_run)
        for branch in deleted:
            any_deleted = True
            verb = "[yellow]would delete[/yellow]" if dry_run else "[red]deleted[/red]"
            rprint(f"{verb} {label}: [bold]{branch}[/bold]")

    if not any_deleted:
        rprint(f"[green]{MESSAGES.branches.no_merged_branches}[/green]")
