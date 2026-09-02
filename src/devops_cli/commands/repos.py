"""Repos command group: clone-org, clone, list, update."""

from __future__ import annotations

import importlib
import subprocess
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, cast

import typer

from devops_cli.config.constants import (
    CONST_GITHUB_HOST,
    CONST_GITHUB_REPO_SUFFIX,
    CONST_URL_SCHEME_HTTPS,
    CONST_VSCODE_CLI,
    CONST_VSCODE_WORKSPACE_FILE,
)
from devops_cli.core.cli import new_typer, repo_label
from devops_cli.dry_run import is_dry_run
from devops_cli.lang import HELP, MESSAGES

if TYPE_CHECKING:
    from devops_cli.config.settings import Settings
    from devops_cli.github.client import GitHubClient

_LAZY_OBJECT_MAPPING: dict[str, tuple[str, str]] = {
    "sync_from_repos": ("devops_cli.commands.workspace", "sync_from_repos"),
    "Settings": ("devops_cli.config.settings", "Settings"),
    "get_github_token": ("devops_cli.config.settings", "get_github_token"),
    "load_settings": ("devops_cli.config.settings", "load_settings"),
    "run_subprocess": ("devops_cli.core.process", "run_subprocess"),
    "clone_repo": ("devops_cli.git.operations", "clone_repo"),
    "fetch_all": ("devops_cli.git.operations", "fetch_all"),
    "iter_workspace_repos": ("devops_cli.git.operations", "iter_workspace_repos"),
    "pull_tracking": ("devops_cli.git.operations", "pull_tracking"),
    "GitHubClient": ("devops_cli.github.client", "GitHubClient"),
    "print_error": ("devops_cli.output", "print_error"),
    "print_info": ("devops_cli.output", "print_info"),
    "print_success": ("devops_cli.output", "print_success"),
    "print_table": ("devops_cli.output", "print_table"),
    "print_warning": ("devops_cli.output", "print_warning"),
    "render_dry_run_result": ("devops_cli.output", "render_dry_run_result"),
    "track_progress": ("devops_cli.output", "track_progress"),
}

_IMPORT_LOCK = threading.Lock()


def __getattr__(name: str) -> Any:
    if name in _LAZY_OBJECT_MAPPING:
        mod_path, obj_name = _LAZY_OBJECT_MAPPING[name]
        module = importlib.import_module(mod_path)
        return getattr(module, obj_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _get(name: str) -> Any:
    """Retrieve module-level attribute with lazy resolution and mock transparency."""
    if name in sys.modules[__name__].__dict__:
        return sys.modules[__name__].__dict__[name]
    if name in _LAZY_OBJECT_MAPPING:
        mod_path, obj_name = _LAZY_OBJECT_MAPPING[name]
        module = importlib.import_module(mod_path)
        return getattr(module, obj_name)
    return getattr(sys.modules[__name__], name)


app = new_typer(help=HELP.repos.app, no_args_is_help=True)


# =============================================================================
# Repos & Workspace Synchronization Helpers
# =============================================================================


def _github_https_url(full_name: str) -> str:
    return f"{CONST_URL_SCHEME_HTTPS}{CONST_GITHUB_HOST}/{full_name}{CONST_GITHUB_REPO_SUFFIX}"


def _require_client(settings: Settings) -> GitHubClient:
    token = _get("get_github_token")(settings)
    if not token:
        _get("print_error")(
            "GitHub token not configured. Run 'devops config init' or set DEVOPS_CLI_GITHUB_TOKEN.",
            prefix=False,
        )
        raise typer.Exit(1)
    client_cls = _get("GitHubClient")
    return cast("GitHubClient", client_cls(token))


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

    try:
        _get("run_subprocess")(
            [CONST_VSCODE_CLI, "--reuse-window", "--", str(workspace_file)],
            check=False,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except OSError, subprocess.SubprocessError:
        from devops_cli.lang import MESSAGES

        _get("print_warning")(MESSAGES.messages.vscode_cli_unavailable, prefix=False)


def _sync_and_reload_workspace(root: Path, ws_file: Path) -> None:
    _get("sync_from_repos")(root, ws_file)
    _reload_workspace(ws_file)


# =============================================================================
# Command: devops repos clone-org
# =============================================================================


@app.command("clone-org")
def clone_org(
    org: Annotated[
        str | None,
        typer.Argument(help=HELP.repos.org_name, show_default=False),
    ] = None,
    base_dir: Annotated[
        Path | None, typer.Option("--base-dir", "-d", help=HELP.options.base_dir)
    ] = None,
    private: Annotated[bool, typer.Option("--private/--no-private")] = True,
    forks: Annotated[bool, typer.Option("--forks/--no-forks")] = False,
) -> None:
    """Clone all repos from a GitHub org into repos/<org>/."""
    if is_dry_run():
        _get("render_dry_run_result")(
            command="devops repos clone-org",
            target=org,
            action="clone_org_repositories",
            details={"org": org, "private": private, "forks": forks},
        )
        return

    settings = _get("load_settings")()
    org_name = org or settings.github.default_org
    if not org_name:
        _get("print_error")(MESSAGES.repos.no_org_configured, prefix=False)
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

    _get("print_info")(
        MESSAGES.repos.cloning_org_repos.format(count=len(repos), dest=org_dir), prefix=False
    )
    for repo in _get("track_progress")(repos, description="Cloning..."):
        dest = (org_dir / repo.name).resolve()
        if not dest.is_relative_to(org_dir.resolve()):
            _get("print_error")(f"skip {repo.name} (path traversal detected)")
            continue
        if dest.exists():
            _get("print_warning")(f"skip {repo.name} (already exists)")
            continue
        try:
            _get("clone_repo")(_github_https_url(repo.full_name), dest)
            _get("print_success")(f"done {repo.name}")
        except (OSError, subprocess.SubprocessError, Exception) as exc:
            _get("print_error")(f"fail {repo.name}: {exc}")

    _sync_and_reload_workspace(root, settings.workspace.file)


# =============================================================================
# Command: devops repos clone
# =============================================================================


@app.command()
def clone(
    url: Annotated[str, typer.Argument(help=HELP.repos.repo_url)],
    base_dir: Annotated[
        Path | None, typer.Option("--base-dir", "-d", help=HELP.options.base_dir)
    ] = None,
) -> None:
    """Clone an individual repository into repos/_standalone/<name>/."""
    if is_dry_run():
        _get("render_dry_run_result")(
            command="devops repos clone",
            target=url,
            action="clone_single_repository",
            details={"url": url},
        )
        return

    settings = _get("load_settings")()
    root = (base_dir or settings.repos.base_dir).resolve()
    dest_dir = root / "_standalone"
    dest_dir.mkdir(parents=True, exist_ok=True)

    raw_name = Path(url.rstrip("/").split("/")[-1].removesuffix(CONST_GITHUB_REPO_SUFFIX)).name
    dest = (dest_dir / raw_name).resolve()
    if not dest.is_relative_to(dest_dir.resolve()):
        _get("print_error")(MESSAGES.repos.invalid_dest_path, prefix=False)
        raise typer.Exit(1)

    if dest.exists():
        _get("print_warning")(MESSAGES.repos.already_exists.format(dest=dest), prefix=False)
        raise typer.Exit(1)

    if url.startswith("-"):
        _get("print_error")(MESSAGES.repos.invalid_url_hyphen, prefix=False)
        raise typer.Exit(1)

    _get("print_info")(MESSAGES.repos.cloning_repo.format(url=url, dest=dest), prefix=False)
    _get("clone_repo")(url, dest)
    _sync_and_reload_workspace(root, settings.workspace.file)
    _get("print_success")(MESSAGES.repos.done, prefix=False)


# =============================================================================
# Command: devops repos list
# =============================================================================


@app.command("list")
def list_repos(
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
) -> None:
    """List all cloned repositories."""
    if is_dry_run():
        _get("render_dry_run_result")(
            command="devops repos list",
            action="list_cloned_repositories",
            details={},
        )
        return

    settings = _get("load_settings")()
    root = base_dir or settings.repos.base_dir

    if not root.exists():
        _get("print_warning")(MESSAGES.repos.repos_dir_not_found.format(root=root), prefix=False)
        raise typer.Exit(0)

    rows = [
        [repo_dir.parent.name, repo_dir.name, _current_branch(repo_dir)]
        for repo_dir in _get("iter_workspace_repos")(root)
    ]

    _get("print_table")(
        title=MESSAGES.repos.table_title_cloned.format(root=root),
        columns=[("Org / Group", "cyan"), "Repository", ("Branch", "green")],
        rows=rows,
    )


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
        _get("render_dry_run_result")(
            command="devops repos sync",
            action="sync_workspace_repositories",
            details={"pull": pull},
        )
        return

    settings = _get("load_settings")()
    root = (base_dir or settings.repos.base_dir).resolve()

    repos_list = list(_get("iter_workspace_repos")(root))
    if not repos_list:
        _get("print_warning")(MESSAGES.repos.no_repos_found, prefix=False)
        raise typer.Exit(0)

    for repo_dir in _get("track_progress")(repos_list, description="Updating..."):
        label = repo_label(repo_dir)
        try:
            _get("fetch_all")(repo_dir)
            if pull:
                _get("pull_tracking")(repo_dir)
            _get("print_success")(f"{label}")
        except (OSError, subprocess.SubprocessError, Exception) as exc:
            _get("print_error")(f"{label}: {exc}")

    _sync_and_reload_workspace(root, settings.workspace.file)
