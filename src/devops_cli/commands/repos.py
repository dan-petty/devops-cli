"""Repos command group: clone-org, clone, list, update."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer
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
from devops_cli.config.settings import Settings, get_github_token, load_settings
from devops_cli.core.cli import new_typer, repo_label
from devops_cli.dry_run import is_dry_run
from devops_cli.git.operations import (
    clone_repo,
    fetch_all,
    iter_workspace_repos,
    pull_tracking,
)
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    render_dry_run_result,
)

if TYPE_CHECKING:
    from devops_cli.github.client import GitHubClient

app = new_typer(help=HELP.repos.app, no_args_is_help=True)


# =============================================================================
# Repos & Workspace Synchronization Helpers
# =============================================================================


def _github_https_url(full_name: str) -> str:
    return f"{CONST_URL_SCHEME_HTTPS}{CONST_GITHUB_HOST}/{full_name}{CONST_GITHUB_REPO_SUFFIX}"


def _require_client(settings: Settings) -> GitHubClient:
    from devops_cli.github.client import GitHubClient

    token = get_github_token(settings)
    if not token:
        print_error(
            "GitHub token not configured. Run 'devops config init' or set DEVOPS_CLI_GITHUB_TOKEN.",
            prefix=False,
        )
        raise typer.Exit(1)
    return GitHubClient(token)


def _current_branch(repo_dir: Path) -> str:
    try:
        import git as gitlib

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
    from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
    from devops_cli.core.process import run_subprocess

    try:
        run_subprocess(
            [CONST_VSCODE_CLI, "--reuse-window", "--", str(workspace_file)],
            check=False,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except OSError, subprocess.SubprocessError:
        from devops_cli.lang import MESSAGES

        print_warning(MESSAGES.messages.vscode_cli_unavailable, prefix=False)


def _sync_and_reload_workspace(root: Path, ws_file: Path) -> None:
    sync_from_repos(root, ws_file)
    _reload_workspace(ws_file)


# =============================================================================
# Command: devops repos clone-org
# =============================================================================


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
    if is_dry_run():
        render_dry_run_result(
            command="devops repos clone-org",
            target=org,
            action="clone_org_repositories",
            details={"org": org, "private": private, "forks": forks},
        )
        return

    settings = load_settings()
    org_name = org or settings.github.default_org
    if not org_name:
        print_error(MESSAGES.repos.no_org_configured, prefix=False)
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

    print_info(
        MESSAGES.repos.cloning_org_repos.format(count=len(repos), dest=org_dir), prefix=False
    )
    for repo in track(repos, description="Cloning..."):
        dest = (org_dir / repo.name).resolve()
        if not dest.is_relative_to(org_dir.resolve()):
            print_error(f"skip {repo.name} (path traversal detected)")
            continue
        if dest.exists():
            print_warning(f"skip {repo.name} (already exists)")
            continue
        try:
            clone_repo(_github_https_url(repo.full_name), dest)
            print_success(f"done {repo.name}")
        except (OSError, subprocess.SubprocessError, Exception) as exc:
            print_error(f"fail {repo.name}: {exc}")

    _sync_and_reload_workspace(root, settings.workspace.file)


# =============================================================================
# Command: devops repos clone
# =============================================================================


@app.command()
def clone(
    url: Annotated[str, typer.Argument(help="Repository URL (SSH or HTTPS)")],
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
) -> None:
    """Clone an individual repository into repos/_standalone/<name>/."""
    if is_dry_run():
        render_dry_run_result(
            command="devops repos clone",
            target=url,
            action="clone_single_repository",
            details={"url": url},
        )
        return

    settings = load_settings()
    root = (base_dir or settings.repos.base_dir).resolve()
    dest_dir = root / "_standalone"
    dest_dir.mkdir(parents=True, exist_ok=True)

    raw_name = Path(url.rstrip("/").split("/")[-1].removesuffix(CONST_GITHUB_REPO_SUFFIX)).name
    dest = (dest_dir / raw_name).resolve()
    if not dest.is_relative_to(dest_dir.resolve()):
        print_error(MESSAGES.repos.invalid_dest_path, prefix=False)
        raise typer.Exit(1)

    if dest.exists():
        print_warning(f"Repository already exists at {dest}", prefix=False)
        raise typer.Exit(1)

    if url.startswith("-"):
        print_error(MESSAGES.repos.invalid_url_hyphen, prefix=False)
        raise typer.Exit(1)

    print_info(f"Cloning [dim]{url}[/dim] → [dim]{dest}[/dim]", prefix=False)
    clone_repo(url, dest)
    _sync_and_reload_workspace(root, settings.workspace.file)
    print_success(MESSAGES.repos.done, prefix=False)


# =============================================================================
# Command: devops repos list
# =============================================================================


@app.command("list")
def list_repos(
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
) -> None:
    """List all cloned repositories."""
    if is_dry_run():
        render_dry_run_result(
            command="devops repos list",
            action="list_cloned_repositories",
            details={},
        )
        return

    settings = load_settings()
    root = base_dir or settings.repos.base_dir

    if not root.exists():
        print_warning(f"Repos directory not found: {root}", prefix=False)
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

    print_table(table)


# =============================================================================
# Command: devops repos sync / update
# =============================================================================


@app.command("sync")
@app.command()
def update(
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
    pull: Annotated[bool, typer.Option("--pull/--no-pull")] = True,
) -> None:
    """Fetch (and optionally pull) all tracking branches across repos."""
    if is_dry_run():
        render_dry_run_result(
            command="devops repos sync",
            action="sync_workspace_repositories",
            details={"pull": pull},
        )
        return

    settings = load_settings()
    root = (base_dir or settings.repos.base_dir).resolve()

    repos_list = list(iter_workspace_repos(root))
    if not repos_list:
        print_warning(MESSAGES.repos.no_repos_found, prefix=False)
        raise typer.Exit(0)

    for repo_dir in track(repos_list, description="Updating..."):
        label = repo_label(repo_dir)
        try:
            fetch_all(repo_dir)
            if pull:
                pull_tracking(repo_dir)
            print_success(f"{label}")
        except (OSError, subprocess.SubprocessError, Exception) as exc:
            print_error(f"{label}: {exc}")

    _sync_and_reload_workspace(root, settings.workspace.file)
