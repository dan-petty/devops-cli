"""Branches command group: update, jira, list, clean."""

from __future__ import annotations

import importlib
import re
import sys
import threading
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.constants import CONST_GIT_DIR_NAME
from devops_cli.core.cli import new_typer, repo_label
from devops_cli.lang import HELP, MESSAGES

_LAZY_OBJECT_MAPPING: dict[str, tuple[str, str]] = {
    "load_settings": ("devops_cli.config.settings", "load_settings"),
    "create_branch": ("devops_cli.git.operations", "create_branch"),
    "delete_merged_branches": ("devops_cli.git.operations", "delete_merged_branches"),
    "fetch_all": ("devops_cli.git.operations", "fetch_all"),
    "iter_workspace_repos": ("devops_cli.git.operations", "iter_workspace_repos"),
    "list_branches": ("devops_cli.git.operations", "list_branches"),
    "pull_tracking": ("devops_cli.git.operations", "pull_tracking"),
    "print_error": ("devops_cli.output", "print_error"),
    "print_info": ("devops_cli.output", "print_info"),
    "print_success": ("devops_cli.output", "print_success"),
    "print_table": ("devops_cli.output", "print_table"),
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


app = new_typer(help=HELP.branches.app, no_args_is_help=True)

_JIRA_RE = re.compile(r"^([A-Z][A-Z0-9]+-\d+)$", re.IGNORECASE)


# =============================================================================
# Command: devops branches update / sync
# =============================================================================


@app.command("sync")
@app.command()
def update(
    base_dir: Annotated[
        Path | None, typer.Option("--base-dir", "-d", help=HELP.options.base_dir)
    ] = None,
) -> None:
    """Fetch and pull tracking branches across all repos."""
    settings = _get("load_settings")()
    root = base_dir or settings.repos.base_dir

    for repo_dir in _get("iter_workspace_repos")(root):
        label = repo_label(repo_dir)
        try:
            _get("fetch_all")(repo_dir)
            _get("pull_tracking")(repo_dir)
            _get("print_success")(label)
        except (OSError, ValueError) as exc:
            _get("print_error")(f"{label}: {exc}")


# =============================================================================
# Command: devops branches jira
# =============================================================================


@app.command()
def jira(
    ticket_id: Annotated[str, typer.Argument(help=HELP.branches.ticket_id)],
    slug: Annotated[str | None, typer.Option("--slug", "-s", help=HELP.branches.slug)] = None,
    repo: Annotated[Path | None, typer.Option("--repo", "-r", help=HELP.options.repo)] = None,
) -> None:
    """Create a feature branch for a Jira ticket: feature/PROJ-123[-slug]."""
    if not _JIRA_RE.match(ticket_id):
        err_msg = MESSAGES.branches.invalid_ticket_id.format(ticket_id=ticket_id)
        _get("print_error")(err_msg, prefix=False)
        raise typer.Exit(1)

    repo_path = repo or Path.cwd()
    if not (repo_path / CONST_GIT_DIR_NAME).exists():
        err_msg = MESSAGES.branches.not_a_git_repo.format(repo_path=repo_path)
        _get("print_error")(err_msg, prefix=False)
        raise typer.Exit(1)

    ticket_upper = ticket_id.upper()
    if slug:
        safe_slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-")
        branch_name = f"feature/{ticket_upper}-{safe_slug}"
    else:
        branch_name = f"feature/{ticket_upper}"

    try:
        _get("create_branch")(repo_path, branch_name)
        ok_msg = MESSAGES.branches.created_branch.format(branch_name=branch_name)
        _get("print_success")(ok_msg, prefix=False)
    except ValueError as exc:
        _get("print_error")(str(exc), prefix=False)
        raise typer.Exit(1)


# =============================================================================
# Command: devops branches list
# =============================================================================


@app.command("list")
def list_all(
    base_dir: Annotated[
        Path | None, typer.Option("--base-dir", "-d", help=HELP.options.base_dir)
    ] = None,
    all_branches: Annotated[
        bool, typer.Option("--all", "-a", help=HELP.branches.all_branches)
    ] = False,
) -> None:
    """List branches across all repos."""
    settings = _get("load_settings")()
    root = base_dir or settings.repos.base_dir

    rows: list[list[str]] = []
    for repo_dir in _get("iter_workspace_repos")(root):
        label = repo_label(repo_dir)
        result = _get("list_branches")(repo_dir, all_branches=all_branches)
        for branch in result.branches:
            indicator = "[green]●[/green]" if branch == result.current else ""
            rows.append([label, branch, indicator])

    _get("print_table")(
        title="Branches across repositories",
        columns=[("Repo", "cyan"), "Branch", ("", "center")],
        rows=rows,
    )


# =============================================================================
# Command: devops branches clean
# =============================================================================


@app.command()
def clean(
    base_dir: Annotated[
        Path | None, typer.Option("--base-dir", "-d", help=HELP.options.base_dir)
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", "-n", help=HELP.options.dry_run)] = False,
) -> None:
    """Delete local branches merged into main/master."""
    settings = _get("load_settings")()
    root = base_dir or settings.repos.base_dir
    any_deleted = False

    for repo_dir in _get("iter_workspace_repos")(root):
        label = repo_label(repo_dir)
        deleted = _get("delete_merged_branches")(repo_dir, dry_run=dry_run)
        for branch in deleted:
            any_deleted = True
            verb = "[yellow]would delete[/yellow]" if dry_run else "[red]deleted[/red]"
            _get("print_info")(f"{verb} {label}: [bold]{branch}[/bold]", prefix=False)

    if not any_deleted:
        _get("print_success")(MESSAGES.branches.no_merged_branches, prefix=False)
