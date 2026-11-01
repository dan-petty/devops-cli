"""VS Code workspace file management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer

from devops_cli.config.constants import CONST_VSCODE_CLI
from devops_cli.config.defaults import (
    DEFAULT_CLEAN_WORKSPACE_DAYS,
    DEFAULT_MAX_AST_FILE_SIZE_BYTES,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer
from devops_cli.core.paths import is_forbidden_system_path
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run import is_dry_run
from devops_cli.dry_run.decorator import dry_run_class
from devops_cli.exceptions import SecurityError
from devops_cli.git.operations import iter_workspace_repos
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.output import (
    print_error,
    print_info,
    print_muted,
    print_success,
    print_warning,
    write_json_file,
)

app = new_typer(help=HELP.workspace.app, no_args_is_help=True)

# Repo root: src/devops_cli/commands/workspace.py -> parents[3]
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


# =============================================================================
# Workspace File Resolution & IO Helpers
# =============================================================================


def _resolve_from_project_root(path: Path) -> Path:
    resolved = path.resolve() if path.is_absolute() else (_PROJECT_ROOT / path).resolve()
    settings = load_settings()
    proj_root = _PROJECT_ROOT.resolve()
    base_dir = (
        settings.repos.base_dir
        if settings.repos.base_dir.is_absolute()
        else proj_root / settings.repos.base_dir
    ).resolve()
    if not (resolved.is_relative_to(proj_root) or resolved.is_relative_to(base_dir)):
        raise typer.BadParameter(
            f"Workspace path '{path}' is outside project root or repos directory."
        )
    return resolved


def _ensure_root_entry(data: dict[str, Any]) -> dict[str, Any]:
    folders_raw = data.get("folders", [])
    folders = [folder for folder in folders_raw if isinstance(folder, dict)]
    folders = [folder for folder in folders if folder.get("path") != "."]
    folders.append({"path": "."})
    data["folders"] = folders
    return data


def _workspace_data_from_repos(root: Path) -> dict[str, Any]:
    folders = [{"path": str(repo_dir.resolve())} for repo_dir in iter_workspace_repos(root)]
    return {
        "folders": folders,
        "settings": {
            "editor.formatOnSave": True,
            "files.trimTrailingWhitespace": True,
            "editor.rulers": [100],
        },
    }


def _refuse_unreadable(message: str, ws_file: Path) -> NoReturn:
    """Report a workspace file that cannot be read and exit 1 before anything saves over it."""
    print_error(message.format(ws_file=str(ws_file)))
    raise typer.Exit(1)


def _load(ws_file: Path) -> dict[str, Any]:
    """Read the workspace file, or start from empty defaults when it does not exist yet.

    A file that exists but cannot be read as a workspace stops the command: saving the
    defaults over it would drop every folder and setting it holds.
    """
    if not ws_file.exists():
        return {"folders": [], "settings": {}}
    if ws_file.stat().st_size > DEFAULT_MAX_AST_FILE_SIZE_BYTES:  # 50 MiB guard
        _refuse_unreadable(ERRORS.workspace.file_too_large, ws_file)
    try:
        data = json.loads(ws_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError, UnicodeDecodeError:
        _refuse_unreadable(ERRORS.workspace.corrupted, ws_file)
    if not (isinstance(data, dict) and isinstance(data.get("folders"), list)):
        _refuse_unreadable(ERRORS.workspace.malformed, ws_file)
    return data


# NOTE (Design Justification - OWASP A01:2021): _is_safe_workspace_file restricts
# target workspace file writes to .code-workspace and .json filenames while blocking
# system directories (CONST_FORBIDDEN_SYSTEM_DIRS) to prevent unauthorized file creation.
def _is_safe_workspace_file(ws_file: Path) -> bool:
    resolved = ws_file.resolve()
    if is_forbidden_system_path(resolved):
        return False
    return resolved.name.endswith((".code-workspace", ".json"))


def _save(ws_file: Path, data: dict[str, Any]) -> None:
    if not _is_safe_workspace_file(ws_file):
        print_error(ERRORS.workspace.outside_boundary.format(path=str(ws_file.resolve())))
        raise typer.Exit(1)
    write_json_file(ws_file, _ensure_root_entry(data), indent=2, atomic=True)


def sync_from_repos(
    base_dir: Path,
    workspace_file: Path,
) -> None:
    """Regenerate the workspace file from all repos under *base_dir*."""
    if not base_dir.exists():
        return

    _save(workspace_file, _workspace_data_from_repos(base_dir))


# =============================================================================
# Command: devops workspace add
# =============================================================================


@app.command()
@dry_run_class("no-external-request")
def add(
    repo_path: Annotated[Path, typer.Argument(help=HELP.workspace.add)],
    workspace_file: Annotated[
        Path | None, typer.Option("--workspace", "-w", help=HELP.options.workspace_file)
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Add a folder to the VS Code workspace file."""
    settings = load_settings()
    ws_file = _resolve_from_project_root(workspace_file or settings.workspace.file)
    data = _load(ws_file)

    repo_resolved = repo_path.resolve()
    base_dir = settings.repos.base_dir.resolve()
    proj_root = _PROJECT_ROOT.resolve()
    if not (
        repo_resolved == base_dir
        or repo_resolved == proj_root
        or repo_resolved.is_relative_to(base_dir)
        or repo_resolved.is_relative_to(proj_root)
    ):
        print_error(ERRORS.workspace.outside_roots.format(path=str(repo_resolved)))
        raise typer.Exit(1)

    folder_str = str(repo_resolved)
    if any(folder.get("path") == folder_str for folder in data["folders"]):
        print_warning(ERRORS.workspace.already_present.format(path=folder_str))
        raise typer.Exit(0)

    if dry_run or is_dry_run():
        print_info(f"Would add folder '{folder_str}' to workspace {ws_file}", prefix=False)
        return

    data["folders"].append({"path": folder_str})
    _save(ws_file, data)
    print_success(MESSAGES.workspace.added_folder.format(path=folder_str))


# =============================================================================
# Command: devops workspace remove
# =============================================================================


@app.command()
@dry_run_class("no-external-request")
def remove(
    repo_path: Annotated[Path, typer.Argument(help=HELP.workspace.remove)],
    workspace_file: Annotated[
        Path | None, typer.Option("--workspace", "-w", help=HELP.options.workspace_file)
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Remove a folder from the VS Code workspace file."""
    settings = load_settings()
    ws_file = _resolve_from_project_root(workspace_file or settings.workspace.file)
    data = _load(ws_file)

    folder_str = str(repo_path.resolve())
    before = len(data["folders"])
    data["folders"] = [folder for folder in data["folders"] if folder.get("path") != folder_str]

    if len(data["folders"]) == before:
        print_warning(ERRORS.workspace.not_present.format(path=folder_str))
        raise typer.Exit(0)

    if dry_run or is_dry_run():
        print_info(f"Would remove folder '{folder_str}' from workspace {ws_file}", prefix=False)
        return

    _save(ws_file, data)
    print_success(MESSAGES.workspace.removed_folder.format(path=folder_str))


# =============================================================================
# Command: devops workspace generate
# =============================================================================


@app.command()
@dry_run_class("no-external-request")
def generate(
    base_dir: Annotated[
        Path | None, typer.Option("--base-dir", "-d", help=HELP.options.base_dir)
    ] = None,
    workspace_file: Annotated[
        Path | None, typer.Option("--workspace", "-w", help=HELP.options.workspace_file)
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Regenerate the workspace file from all repos in the repos directory."""
    settings = load_settings()
    root = _resolve_from_project_root(base_dir or settings.repos.base_dir)
    ws_file = _resolve_from_project_root(workspace_file or settings.workspace.file)

    if not root.exists():
        print_warning(ERRORS.workspace.repos_not_found.format(path=str(root)))
        raise typer.Exit(0)

    data = _workspace_data_from_repos(root)
    if dry_run or is_dry_run():
        print_info(
            f"Would generate workspace {ws_file} with {len(data['folders'])} folders",
            prefix=False,
        )
        return

    _save(ws_file, data)
    msg = MESSAGES.workspace.generated_with_count.format(
        ws_file=str(ws_file), count=len(data["folders"])
    )
    print_success(msg)


# =============================================================================
# Command: devops workspace open
# =============================================================================


@app.command("open")
@dry_run_class("no-external-request")
def open_workspace(
    workspace_file: Annotated[
        Path | None, typer.Option("--workspace", "-w", help=HELP.options.workspace_file)
    ] = None,
) -> None:
    """Open the workspace in VS Code."""
    settings = load_settings()
    ws_file = _resolve_from_project_root(workspace_file or settings.workspace.file)
    if not ws_file.exists():
        print_error(ERRORS.workspace.file_not_found.format(ws_file=str(ws_file)))
        raise typer.Exit(1)
    run_subprocess(
        [CONST_VSCODE_CLI, str(ws_file)],
        check=True,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )


# =============================================================================
# Command: devops workspace clean
# =============================================================================


@app.command("clean")
@dry_run_class("no-external-request")
def clean_workspace(
    older_than_days: Annotated[
        int,
        typer.Option("--older-than", "-d", help=HELP.workspace.older_than),
    ] = DEFAULT_CLEAN_WORKSPACE_DAYS,
) -> None:
    """Clean stale reviews, analysis, logs, traces, benchmarks and cache under the data directory.

    Child directories configured on their own, such as `data.reviews_dir`, are left alone.
    """
    from devops_cli.core.cleanup import cleanup_data_directory, cleanup_data_tier

    try:
        data_dir = cleanup_data_directory()
    except SecurityError as exc:
        print_error(str(exc))
        raise typer.Exit(1) from exc
    print_muted(MESSAGES.workspace.pruning_stale.format(days=older_than_days, data_dir=data_dir))
    summary = cleanup_data_tier(
        older_than_seconds=float(older_than_days * 86400),
        dry_run=False,
    )

    if not summary.pruned_files and not summary.pruned_dirs:
        print_info(MESSAGES.workspace.data_tier_clean)
        return

    print_success(
        MESSAGES.workspace.cleaned_artifacts.format(
            files=len(summary.pruned_files),
            dirs=len(summary.pruned_dirs),
            freed_mb=summary.freed_bytes / (1024 * 1024),
        )
    )
