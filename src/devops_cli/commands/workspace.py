"""VS Code workspace file management."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Annotated, Any

import typer
from rich import print as rprint

from devops_cli.config.constants import CONST_GIT_DIR_NAME, CONST_VSCODE_CLI
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer

app = new_typer(help="Manage VS Code workspace files.", no_args_is_help=True)

# Repo root: src/devops_cli/commands/workspace.py -> parents[3]
_PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _resolve_from_project_root(path: Path) -> Path:
    if path.is_absolute():
        return path
    return _PROJECT_ROOT / path


def _ensure_root_entry(data: dict[str, Any]) -> dict[str, Any]:
    folders_raw = data.get("folders", [])
    folders = [folder for folder in folders_raw if isinstance(folder, dict)]
    folders = [folder for folder in folders if folder.get("path") != "."]
    folders.append({"path": "."})
    data["folders"] = folders
    return data


def _workspace_data_from_repos(root: Path) -> dict[str, Any]:
    resolved_root = root.resolve()
    folders = [
        {"path": str(repo_dir.resolve())}
        for group_dir in sorted(root.iterdir())
        if group_dir.is_dir()
        for repo_dir in sorted(group_dir.iterdir())
        if (repo_dir / CONST_GIT_DIR_NAME).exists()
        and repo_dir.resolve().is_relative_to(resolved_root)
    ]
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
            data: dict[str, Any] = json.loads(ws_file.read_text(encoding="utf-8"))
            return data
        except json.JSONDecodeError:
            rprint(f"[yellow]Corrupted workspace file: {ws_file}. Using defaults.[/yellow]")
    return {"folders": [], "settings": {}}


def _save(ws_file: Path, data: dict[str, Any]) -> None:
    ws_file.parent.mkdir(parents=True, exist_ok=True)
    ws_file.write_text(json.dumps(_ensure_root_entry(data), indent=2) + "\n", encoding="utf-8")


def sync_from_repos(
    base_dir: Path,
    workspace_file: Path,
) -> None:
    """Regenerate the workspace file from all repos under *base_dir*."""
    if not base_dir.exists():
        return

    _save(workspace_file, _workspace_data_from_repos(base_dir))


@app.command()
def add(
    repo_path: Annotated[Path, typer.Argument(help="Folder path to add")],
    workspace_file: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
) -> None:
    """Add a folder to the VS Code workspace file."""
    settings = load_settings()
    ws_file = _resolve_from_project_root(workspace_file or settings.workspace.file)
    data = _load(ws_file)

    folder_str = str(repo_path.resolve())
    if any(folder.get("path") == folder_str for folder in data["folders"]):
        rprint(f"[yellow]Already in workspace: {folder_str}[/yellow]")
        raise typer.Exit(0)

    data["folders"].append({"path": folder_str})
    _save(ws_file, data)
    rprint(f"[green]Added:[/green] {folder_str}")


@app.command()
def remove(
    repo_path: Annotated[Path, typer.Argument(help="Folder path to remove")],
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
        rprint(f"[yellow]Not found in workspace: {folder_str}[/yellow]")
        raise typer.Exit(0)

    _save(ws_file, data)
    rprint(f"[green]Removed:[/green] {folder_str}")


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
        rprint(f"[yellow]Repos directory not found: {root}[/yellow]")
        raise typer.Exit(0)

    data = _workspace_data_from_repos(root)
    _save(ws_file, data)
    rprint(f"[green]Generated[/green] {ws_file} with [bold]{len(data['folders'])}[/bold] folders.")


@app.command("open")
def open_workspace(
    workspace_file: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
) -> None:
    """Open the workspace in VS Code."""
    settings = load_settings()
    ws_file = _resolve_from_project_root(workspace_file or settings.workspace.file)
    if not ws_file.exists():
        rprint(f"[red]Workspace file not found: {ws_file}[/red]")
        raise typer.Exit(1)
    subprocess.run([CONST_VSCODE_CLI, str(ws_file)], check=True)
