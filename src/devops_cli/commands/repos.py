"""Repos command group: clone-org, clone, list, update."""

from __future__ import annotations

import subprocess
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.progress import track
from rich.table import Table

from devops_cli.git.operations import clone_repo, fetch_all, pull_tracking

if TYPE_CHECKING:
    from devops_cli.config import Settings
    from devops_cli.github.client import GitHubClient

app = typer.Typer(help="Clone and manage repositories.", no_args_is_help=True)
console = Console()


def _github_https_url(full_name: str) -> str:
    return f"https://github.com/{full_name}.git"


def _normalize_clone_url(url: str) -> str:
    if url.startswith(("git@github.com:", "ssh://git@github.com/")):
        return url
    if url.startswith("github.com/"):
        return f"https://{url}"
    if url.startswith("http://github.com/"):
        return f"https://{url.removeprefix('http://')}"
    return url


def load_settings() -> Settings:
    from devops_cli.config import load_settings as _load_settings

    return _load_settings()


def get_github_token(settings: Settings) -> str | None:
    from devops_cli.config import get_github_token as _get_github_token

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


def _iter_repos(root: Path) -> Generator[Path]:
    """Yield all repo directories under *root*."""
    if not root.exists():
        return
    for group_dir in sorted(root.iterdir()):
        if not group_dir.is_dir():
            continue
        for repo_dir in sorted(group_dir.iterdir()):
            if (repo_dir / ".git").exists():
                yield repo_dir


def _current_branch(repo_dir: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", str(repo_dir), "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        )
        return r.stdout.strip() or "HEAD detached"
    except subprocess.CalledProcessError:
        return "unknown"


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

    root = base_dir or settings.repos.base_dir
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
        dest = org_dir / repo.name
        if dest.exists():
            rprint(f"  [yellow]skip[/yellow] {repo.name} (already exists)")
            continue
        try:
            clone_repo(_github_https_url(repo.full_name), dest)
            rprint(f"  [green]done[/green] {repo.name}")
        except Exception as exc:
            rprint(f"  [red]fail[/red] {repo.name}: {exc}")


@app.command()
def clone(
    url: Annotated[str, typer.Argument(help="Repository URL (SSH or HTTPS)")],
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
) -> None:
    """Clone an individual repository into repos/_standalone/<name>/."""
    settings = load_settings()
    root = base_dir or settings.repos.base_dir
    dest_dir = root / "_standalone"
    dest_dir.mkdir(parents=True, exist_ok=True)

    name = url.rstrip("/").split("/")[-1].removesuffix(".git")
    dest = dest_dir / name

    if dest.exists():
        rprint(f"[yellow]Repository already exists at {dest}[/yellow]")
        raise typer.Exit(1)

    clone_url = _normalize_clone_url(url)
    rprint(f"Cloning [dim]{clone_url}[/dim] → [dim]{dest}[/dim]")
    clone_repo(clone_url, dest)
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

    for repo_dir in _iter_repos(root):
        table.add_row(
            repo_dir.parent.name,
            repo_dir.name,
            _current_branch(repo_dir),
        )

    console.print(table)


@app.command()
def update(
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
    pull: Annotated[bool, typer.Option("--pull/--no-pull")] = True,
) -> None:
    """Fetch (and optionally pull) all tracking branches across repos."""
    settings = load_settings()
    root = base_dir or settings.repos.base_dir

    repos_list = list(_iter_repos(root))
    if not repos_list:
        rprint("[yellow]No repositories found.[/yellow]")
        raise typer.Exit(0)

    for repo_dir in track(repos_list, description="Updating..."):
        label = f"{repo_dir.parent.name}/{repo_dir.name}"
        try:
            fetch_all(repo_dir)
            if pull:
                pull_tracking(repo_dir)
            rprint(f"  [green]✓[/green] {label}")
        except Exception as exc:
            rprint(f"  [red]✗[/red] {label}: {exc}")
