"""Repos command group: clone-org, clone, list, update."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import git as gitlib
import typer
from rich import print as rprint
from rich.console import Console
from rich.progress import track
from rich.table import Table

from devops_cli.commands.workspace import sync_from_repos
from devops_cli.config.constants import (
    CONST_GITHUB_HOST,
    CONST_GITHUB_REPO_SUFFIX,
    CONST_URL_SCHEME_HTTPS,
    CONST_VSCODE_CLI,
    CONST_VSCODE_WORKSPACE_FILE,
)
from devops_cli.core.cli import new_typer, repo_label
from devops_cli.git.operations import (
    clone_repo,
    fetch_all,
    iter_workspace_repos,
    pull_tracking,
)

if TYPE_CHECKING:
    from devops_cli.config.settings import Settings
    from devops_cli.github.client import GitHubClient

app = new_typer(help="Clone and manage repositories.", no_args_is_help=True)
console = Console()


def _github_https_url(full_name: str) -> str:
    return f"{CONST_URL_SCHEME_HTTPS}{CONST_GITHUB_HOST}/{full_name}{CONST_GITHUB_REPO_SUFFIX}"


def load_settings() -> Settings:
    from devops_cli.config.settings import load_settings as _load_settings

    return _load_settings()


def get_github_token(settings: Settings) -> str | None:
    from devops_cli.config.settings import get_github_token as _get_github_token

    return _get_github_token(settings)


def _require_client(settings: Settings) -> GitHubClient:
    from devops_cli.github.client import GitHubClient

    token = get_github_token(settings)
    if not token:
        rprint(
            "[red]GitHub token not configured. "
            "Run 'devops config init' or set DEVOPS_CLI_GITHUB_TOKEN.[/red]"
        )
        raise typer.Exit(1)
    return GitHubClient(token)


def _current_branch(repo_dir: Path) -> str:
    try:
        repo = gitlib.Repo(str(repo_dir))
        return "HEAD detached" if repo.head.is_detached else repo.active_branch.name
    except Exception:
        return "unknown"


def _resolve_workspace_file(root: Path, workspace_file: Path) -> Path:
    if workspace_file.is_absolute():
        return workspace_file
    if workspace_file == CONST_VSCODE_WORKSPACE_FILE:
        return root.parent / workspace_file
    return workspace_file


def _reload_workspace(workspace_file: Path) -> None:
    try:
        subprocess.run([CONST_VSCODE_CLI, "--reuse-window", str(workspace_file)], check=False)
    except OSError:
        rprint("[yellow]Workspace updated, but VS Code CLI is not available to reload.[/yellow]")


def _sync_and_reload_workspace(root: Path, workspace_file: Path) -> None:
    resolved_workspace_file = _resolve_workspace_file(root, workspace_file)
    sync_from_repos(root, resolved_workspace_file)
    _reload_workspace(resolved_workspace_file)


@app.command("clone-org")
def clone_org(
    org: Annotated[
        str | None,
        typer.Argument(help="GitHub organisation name", show_default=False),
    ] = None,
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
    private: Annotated[bool, typer.Option("--private/--no-private")] = True,
    forks: Annotated[bool, typer.Option("--forks/--no-forks")] = False,
) -> None:
    """Clone all repos from a GitHub org into repos/<org>/."""
    settings = load_settings()
    org_name = org or settings.github.default_org
    if not org_name:
        rprint(
            "[red]No GitHub organisation configured. Set github.default_org "
            "or pass an org name.[/red]"
        )
        raise typer.Exit(1)

    root = (base_dir or settings.repos.base_dir).resolve()
    client = _require_client(settings)

    repos = client.get_org_repos(
        org_name,
        include_private=private,
        include_forks=forks,
        include_archived=False,
    )
    org_dir = root / org_name
    org_dir.mkdir(parents=True, exist_ok=True)

    rprint(f"Cloning [bold]{len(repos)}[/bold] repos into [dim]{org_dir}[/dim]")
    for repo in track(repos, description="Cloning..."):
        dest = (org_dir / repo.name).resolve()
        if not dest.is_relative_to(org_dir.resolve()):
            rprint(f"  [red]skip[/red] {repo.name} (path traversal detected)")
            continue
        if dest.exists():
            rprint(f"  [yellow]skip[/yellow] {repo.name} (already exists)")
            continue
        try:
            clone_repo(_github_https_url(repo.full_name), dest)
            rprint(f"  [green]done[/green] {repo.name}")
        except Exception as exc:
            rprint(f"  [red]fail[/red] {repo.name}: {exc}")

    _sync_and_reload_workspace(root, settings.workspace.file)


@app.command()
def clone(
    url: Annotated[str, typer.Argument(help="Repository URL (SSH or HTTPS)")],
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
) -> None:
    """Clone an individual repository into repos/_standalone/<name>/."""
    settings = load_settings()
    root = (base_dir or settings.repos.base_dir).resolve()
    dest_dir = root / "_standalone"
    dest_dir.mkdir(parents=True, exist_ok=True)

    name = url.rstrip("/").split("/")[-1].removesuffix(CONST_GITHUB_REPO_SUFFIX)
    dest = dest_dir / name

    if dest.exists():
        rprint(f"[yellow]Repository already exists at {dest}[/yellow]")
        raise typer.Exit(1)

    rprint(f"Cloning [dim]{url}[/dim] → [dim]{dest}[/dim]")
    clone_repo(url, dest)
    _sync_and_reload_workspace(root, settings.workspace.file)
    rprint("[green]Done.[/green]")


@app.command("list")
def list_repos(
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
) -> None:
    """List all cloned repositories."""
    settings = load_settings()
    root = base_dir or settings.repos.base_dir

    if not root.exists():
        rprint(f"[yellow]Repos directory not found: {root}[/yellow]")
        raise typer.Exit(0)

    table = Table(title=f"Cloned repositories — {root}")
    table.add_column("Org / Group", style="cyan")
    table.add_column("Repository")
    table.add_column("Branch", style="green")

    for repo_dir in iter_workspace_repos(root):
        table.add_row(
            repo_dir.parent.name,
            repo_dir.name,
            _current_branch(repo_dir),
        )

    console.print(table)


@app.command("sync")
@app.command()
def update(
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
    pull: Annotated[bool, typer.Option("--pull/--no-pull")] = True,
) -> None:
    """Fetch (and optionally pull) all tracking branches across repos."""
    settings = load_settings()
    root = (base_dir or settings.repos.base_dir).resolve()

    repos_list = list(iter_workspace_repos(root))
    if not repos_list:
        rprint("[yellow]No repositories found.[/yellow]")
        raise typer.Exit(0)

    for repo_dir in track(repos_list, description="Updating..."):
        label = repo_label(repo_dir)
        try:
            fetch_all(repo_dir)
            if pull:
                pull_tracking(repo_dir)
            rprint(f"  [green]✓[/green] {label}")
        except Exception as exc:
            rprint(f"  [red]✗[/red] {label}: {exc}")

    _sync_and_reload_workspace(root, settings.workspace.file)
