"""Branches command group: update, jira, list, clean."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

import git as gitlib
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
        except (OSError, ValueError) as exc:
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


@app.command("create")
def create(
    name: Annotated[str, typer.Argument(help="Branch name or slug (e.g. mcp-tools-enhancement)")],
    base: Annotated[
        str | None,
        typer.Option(
            "--base",
            "-b",
            help="Base branch to fork from (defaults to active release branch)",
        ),
    ] = None,
    branch_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Branch type prefix (feat, fix, docs, chore, refactor)"),
    ] = "feat",
    repo: Annotated[
        Path | None,
        typer.Option("--repo", "-r", help="Target repo directory (default: cwd)"),
    ] = None,
) -> None:
    """Create a topic branch following repository branching standards."""
    repo_path = repo or Path.cwd()
    if not (repo_path / CONST_GIT_DIR_NAME).exists():
        err_msg = MESSAGES.branches.not_a_git_repo.format(repo_path=repo_path)
        rprint(f"[red]{err_msg}[/red]")
        raise typer.Exit(1)

    clean_name = name.strip()
    valid_prefixes = ("feat/", "fix/", "docs/", "chore/", "refactor/", "release/")
    if any(clean_name.startswith(p) for p in valid_prefixes):
        full_branch_name = clean_name
    else:
        safe_slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", clean_name).strip("-")
        prefix = branch_type.rstrip("/")
        full_branch_name = f"{prefix}/{safe_slug}"

    # Fetch origin
    try:
        fetch_all(repo_path)
    except Exception:
        pass

    target_base = base
    if not target_base:
        # Detect active release branch from gitlib
        try:
            repo_obj = gitlib.Repo(str(repo_path))
            remote_branches = [ref.name for remote in repo_obj.remotes for ref in remote.refs]
            releases = [r.split("/")[-1] for r in remote_branches if "/release/v" in r]
            if releases:

                def _ver_key(v: str) -> tuple[int, ...]:
                    clean = v.split("release/v")[-1] if "release/v" in v else v.lstrip("v")
                    try:
                        return tuple(int(x) for x in clean.split("."))
                    except ValueError:
                        return (0, 0, 0)

                sorted_rels = sorted(set(releases), key=_ver_key, reverse=True)
                top_rel = sorted_rels[0]
                if top_rel.startswith("origin/"):
                    target_base = top_rel
                else:
                    target_base = f"origin/release/{top_rel}"
            else:
                target_base = "origin/main"

        except Exception:
            target_base = "origin/main"

    try:
        repo_obj = gitlib.Repo(str(repo_path))
        if full_branch_name in [b.name for b in repo_obj.branches]:
            rprint(
                f"[yellow]Branch '{full_branch_name}' already exists. Switching to it...[/yellow]"
            )
            repo_obj.git.checkout(full_branch_name)
        else:
            repo_obj.git.checkout("-b", full_branch_name, target_base)
        rprint(
            f"[green]✓ Created and checked out [bold]{full_branch_name}[/bold] "
            f"(forked from {target_base})[/green]"
        )
    except Exception as exc:
        rprint(f"[red]Failed to create branch: {exc}[/red]")
        raise typer.Exit(1)


@app.command("status")
def branch_status(
    repo: Annotated[
        Path | None,
        typer.Option("--repo", "-r", help="Target repo directory (default: cwd)"),
    ] = None,
) -> None:
    """Show detailed branch status, tracking state, ahead/behind drift, and worktree status."""
    repo_path = repo or Path.cwd()
    if not (repo_path / CONST_GIT_DIR_NAME).exists():
        rprint(f"[red]{MESSAGES.branches.not_a_git_repo.format(repo_path=repo_path)}[/red]")
        raise typer.Exit(1)

    try:
        repo_obj = gitlib.Repo(str(repo_path))
        current = "HEAD detached" if repo_obj.head.is_detached else repo_obj.active_branch.name
        tracking = ""
        ahead = 0
        behind = 0
        if not repo_obj.head.is_detached:
            tb = repo_obj.active_branch.tracking_branch()
            if tb:
                tracking = tb.name
                ahead = len(list(repo_obj.iter_commits(f"{tb.name}..{current}")))
                behind = len(list(repo_obj.iter_commits(f"{current}..{tb.name}")))

        dirty = repo_obj.is_dirty()
        untracked = len(repo_obj.untracked_files)

        table = Table(title=f"Git Branch Status — {repo_path.name}", title_style="bold")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="bold")

        table.add_row("Current Branch", f"[green]{current}[/green]")
        table.add_row("Tracking Branch", tracking or "[dim]none[/dim]")
        table.add_row("Ahead / Behind", f"+{ahead} / -{behind}")
        tree_status = "[red]dirty (uncommitted changes)[/red]" if dirty else "[green]clean[/green]"
        table.add_row("Working Tree", tree_status)
        table.add_row("Untracked Files", str(untracked))

        console.print(table)
    except Exception as exc:
        rprint(f"[red]Error inspecting git branch status: {exc}[/red]")
        raise typer.Exit(1)


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
