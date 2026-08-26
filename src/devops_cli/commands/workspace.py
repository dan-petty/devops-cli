"""VS Code workspace file management."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.constants import (
    CONST_FORBIDDEN_SYSTEM_DIRS,
    CONST_VSCODE_CLI,
)
from devops_cli.config.defaults import (
    DEFAULT_CLEAN_WORKSPACE_DAYS,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.cli import new_typer
from devops_cli.lang import ERRORS, HELP, MESSAGES

_LAZY_OBJECT_MAPPING: dict[str, tuple[str, str]] = {
    "load_settings": ("devops_cli.config.settings", "load_settings"),
    "iter_workspace_repos": ("devops_cli.git.operations", "iter_workspace_repos"),
    "run_subprocess": ("devops_cli.core.process", "run_subprocess"),
    "cleanup_data_tier": ("devops_cli.core.cleanup", "cleanup_data_tier"),
    "render_dry_run_result": ("devops_cli.dry_run", "render_dry_run_result"),
    "print_error": ("devops_cli.output", "print_error"),
    "print_info": ("devops_cli.output", "print_info"),
    "print_muted": ("devops_cli.output", "print_muted"),
    "print_success": ("devops_cli.output", "print_success"),
    "print_warning": ("devops_cli.output", "print_warning"),
    "write_json_file": ("devops_cli.output", "write_json_file"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_OBJECT_MAPPING:
        mod_path, obj_name = _LAZY_OBJECT_MAPPING[name]
        module = importlib.import_module(mod_path)
        return getattr(module, obj_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _get(name: str) -> Any:
    mod_dict = sys.modules[__name__].__dict__
    if name in mod_dict:
        return mod_dict[name]
    if name in _LAZY_OBJECT_MAPPING:
        mod_path, obj_name = _LAZY_OBJECT_MAPPING[name]
        module = importlib.import_module(mod_path)
        return getattr(module, obj_name)
    return getattr(sys.modules[__name__], name)


app = new_typer(help=HELP.workspace.app, no_args_is_help=True)

# Repo root: src/devops_cli/commands/workspace.py -> parents[3]
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


# =============================================================================
# Workspace File Resolution & IO Helpers
# =============================================================================


def _resolve_from_project_root(path: Path) -> Path:
    resolved = path.resolve() if path.is_absolute() else (_PROJECT_ROOT / path).resolve()
    settings = _get("load_settings")()
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
    folders = [{"path": str(repo_dir.resolve())} for repo_dir in _get("iter_workspace_repos")(root)]
    return {
        "folders": folders,
        "settings": {
            "editor.formatOnSave": True,
            "files.trimTrailingWhitespace": True,
            "editor.rulers": [100],
        },
    }


def _load(ws_file: Path) -> dict[str, Any]:
    if ws_file.exists():
        try:
            if ws_file.stat().st_size > 10 * 1024 * 1024:  # 10 MiB guard
                _get("print_warning")(ERRORS.workspace.file_too_large.format(ws_file=str(ws_file)))
                return {"folders": [], "settings": {}}
            data = json.loads(ws_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "folders" in data and isinstance(data["folders"], list):
                return data
            _get("print_warning")(ERRORS.workspace.malformed.format(ws_file=str(ws_file)))
        except json.JSONDecodeError:
            _get("print_warning")(ERRORS.workspace.corrupted.format(ws_file=str(ws_file)))
    return {"folders": [], "settings": {}}


# NOTE (Design Justification - OWASP A01:2021): _is_safe_workspace_file restricts
# target workspace file writes to .code-workspace and .json filenames while blocking
# system directories (CONST_FORBIDDEN_SYSTEM_DIRS) to prevent unauthorized file creation.
def _is_safe_workspace_file(ws_file: Path) -> bool:
    resolved = ws_file.resolve()
    for sys_dir in CONST_FORBIDDEN_SYSTEM_DIRS:
        if resolved == sys_dir or resolved.is_relative_to(sys_dir):
            return False
    return resolved.name.endswith((".code-workspace", ".json"))


def _save(ws_file: Path, data: dict[str, Any]) -> None:
    if not _is_safe_workspace_file(ws_file):
        _get("print_error")(f"Cannot write workspace file '{ws_file.resolve()}' outside boundary.")
        raise typer.Exit(1)
    _get("write_json_file")(ws_file, _ensure_root_entry(data), indent=2, atomic=True)


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
def add(
    repo_path: Annotated[Path, typer.Argument(help=HELP.workspace.add)],
    workspace_file: Annotated[
        Path | None, typer.Option("--workspace", "-w", help=HELP.options.workspace_file)
    ] = None,
) -> None:
    """Add a folder to the VS Code workspace file."""
    settings = _get("load_settings")()
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
        _get("print_error")(ERRORS.workspace.outside_roots.format(path=str(repo_resolved)))
        raise typer.Exit(1)

    folder_str = str(repo_resolved)
    if any(folder.get("path") == folder_str for folder in data["folders"]):
        _get("print_warning")(ERRORS.workspace.already_present.format(path=folder_str))
        raise typer.Exit(0)

    data["folders"].append({"path": folder_str})
    _save(ws_file, data)
    _get("print_success")(MESSAGES.workspace.added_folder.format(path=folder_str))


# =============================================================================
# Command: devops workspace remove
# =============================================================================


@app.command()
def remove(
    repo_path: Annotated[Path, typer.Argument(help=HELP.workspace.remove)],
    workspace_file: Annotated[
        Path | None, typer.Option("--workspace", "-w", help=HELP.options.workspace_file)
    ] = None,
) -> None:
    """Remove a folder from the VS Code workspace file."""
    settings = _get("load_settings")()
    ws_file = _resolve_from_project_root(workspace_file or settings.workspace.file)
    data = _load(ws_file)

    folder_str = str(repo_path.resolve())
    before = len(data["folders"])
    data["folders"] = [folder for folder in data["folders"] if folder.get("path") != folder_str]

    if len(data["folders"]) == before:
        _get("print_warning")(ERRORS.workspace.not_present.format(path=folder_str))
        raise typer.Exit(0)

    _save(ws_file, data)
    _get("print_success")(MESSAGES.workspace.removed_folder.format(path=folder_str))


# =============================================================================
# Command: devops workspace generate
# =============================================================================


@app.command()
def generate(
    base_dir: Annotated[
        Path | None, typer.Option("--base-dir", "-d", help=HELP.options.base_dir)
    ] = None,
    workspace_file: Annotated[
        Path | None, typer.Option("--workspace", "-w", help=HELP.options.workspace_file)
    ] = None,
) -> None:
    """Regenerate the workspace file from all repos in the repos directory."""
    settings = _get("load_settings")()
    root = _resolve_from_project_root(base_dir or settings.repos.base_dir)
    ws_file = _resolve_from_project_root(workspace_file or settings.workspace.file)

    if not root.exists():
        _get("print_warning")(ERRORS.workspace.repos_not_found.format(path=str(root)))
        raise typer.Exit(0)

    data = _workspace_data_from_repos(root)
    _save(ws_file, data)
    msg = MESSAGES.workspace.generated_with_count.format(
        ws_file=str(ws_file), count=len(data["folders"])
    )
    _get("print_success")(msg)


# =============================================================================
# Command: devops workspace open
# =============================================================================


@app.command("open")
def open_workspace(
    workspace_file: Annotated[
        Path | None, typer.Option("--workspace", "-w", help=HELP.options.workspace_file)
    ] = None,
) -> None:
    """Open the workspace in VS Code."""
    settings = _get("load_settings")()
    ws_file = _resolve_from_project_root(workspace_file or settings.workspace.file)
    if not ws_file.exists():
        _get("print_error")(ERRORS.workspace.file_not_found.format(ws_file=str(ws_file)))
        raise typer.Exit(1)
    _get("run_subprocess")(
        [CONST_VSCODE_CLI, str(ws_file)],
        check=True,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )


# =============================================================================
# Command: devops workspace clean
# =============================================================================


@app.command("clean")
def clean_workspace(
    older_than_days: Annotated[
        int,
        typer.Option("--older-than", "-d", help=HELP.workspace.older_than),
    ] = DEFAULT_CLEAN_WORKSPACE_DAYS,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Clean stale review sessions, old analysis caches, and temporary traces under .data/."""
    if dry_run:
        _get("render_dry_run_result")(
            command=f"devops workspace clean --older-than {older_than_days}",
            action="cleanup_data_tier",
            details={"older_than_days": older_than_days},
        )
        return

    _get("print_muted")(f"Pruning artifacts older than {older_than_days} days under .data/...")
    summary = _get("cleanup_data_tier")(
        older_than_seconds=float(older_than_days * 86400),
        dry_run=False,
    )

    freed_mb = summary.freed_bytes / (1024 * 1024)
    if not summary.pruned_files and not summary.pruned_dirs:
        _get("print_info")("✓ Data tier is clean; no stale artifacts found.")
        return

    nf = len(summary.pruned_files)
    nd = len(summary.pruned_dirs)
    _get("print_success")(f"✓ Cleaned {nf} files and {nd} directories ({freed_mb:.2f} MB freed).")
