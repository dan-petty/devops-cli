"""VS Code workspace file management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.constants import CONST_VSCODE_CLI
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_SHORT_TIMEOUT_SECONDS
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.git.operations import iter_workspace_repos
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.output import print_error, print_success, print_warning, write_json_file

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


def _load(ws_file: Path) -> dict[str, Any]:
    if ws_file.exists():
        try:
            if ws_file.stat().st_size > 10 * 1024 * 1024:  # 10 MiB guard
                print_warning(ERRORS.workspace.file_too_large.format(ws_file=str(ws_file)))
                return {"folders": [], "settings": {}}
            data = json.loads(ws_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "folders" in data and isinstance(data["folders"], list):
                return data
            print_warning(ERRORS.workspace.malformed.format(ws_file=str(ws_file)))
        except json.JSONDecodeError:
            print_warning(ERRORS.workspace.corrupted.format(ws_file=str(ws_file)))
    return {"folders": [], "settings": {}}


_FORBIDDEN_SYSTEM_DIRS = (
    Path("/etc"),
    Path("/usr"),
    Path("/bin"),
    Path("/sbin"),
    Path("/var"),
    Path("/sys"),
    Path("/proc"),
)


# NOTE (Design Justification - OWASP A01:2021): _is_safe_workspace_file restricts
# target workspace file writes to .code-workspace and .json filenames while blocking
# system directories (_FORBIDDEN_SYSTEM_DIRS) to prevent unauthorized file creation.
def _is_safe_workspace_file(ws_file: Path) -> bool:
    resolved = ws_file.resolve()
    for sys_dir in _FORBIDDEN_SYSTEM_DIRS:
        if resolved == sys_dir or resolved.is_relative_to(sys_dir):
            return False
    return resolved.name.endswith((".code-workspace", ".json"))


def _save(ws_file: Path, data: dict[str, Any]) -> None:
    if not _is_safe_workspace_file(ws_file):
        print_error(f"Cannot write workspace file '{ws_file.resolve()}' outside boundary.")
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
def add(
    repo_path: Annotated[Path, typer.Argument(help="Folder path to add")],
    workspace_file: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
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

    data["folders"].append({"path": folder_str})
    _save(ws_file, data)
    print_success(MESSAGES.workspace.added_folder.format(path=folder_str))


# =============================================================================
# Command: devops workspace remove
# =============================================================================


@app.command()
def remove(
    repo_path: Annotated[Path, typer.Argument(help=HELP.workspace.remove)],
    workspace_file: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
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

    _save(ws_file, data)
    print_success(MESSAGES.workspace.removed_folder.format(path=folder_str))


# =============================================================================
# Command: devops workspace generate
# =============================================================================


@app.command()
def generate(
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
    workspace_file: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
) -> None:
    """Regenerate the workspace file from all repos in the repos directory."""
    settings = load_settings()
    root = _resolve_from_project_root(base_dir or settings.repos.base_dir)
    ws_file = _resolve_from_project_root(workspace_file or settings.workspace.file)

    if not root.exists():
        print_warning(ERRORS.workspace.repos_not_found.format(path=str(root)))
        raise typer.Exit(0)

    data = _workspace_data_from_repos(root)
    _save(ws_file, data)
    msg = MESSAGES.workspace.generated_with_count.format(
        ws_file=str(ws_file), count=len(data["folders"])
    )
    print_success(msg)


# =============================================================================
# Command: devops workspace open
# =============================================================================


@app.command("open")
def open_workspace(
    workspace_file: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
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
        timeout=DEFAULT_SUBPROCESS_SHORT_TIMEOUT_SECONDS,
    )
