"""VS Code workspace file management."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Annotated, Any

import typer
from rich import print as rprint

from devops_cli.cli import new_typer
from devops_cli.config import load_settings

app = new_typer(help="Manage VS Code workspace files.", no_args_is_help=True)


def _load(ws_file: Path) -> dict[str, Any]:
    if ws_file.exists():
        data: dict[str, Any] = json.loads(ws_file.read_text(encoding="utf-8"))
        return data
    return {"folders": [], "settings": {}}


def _save(ws_file: Path, data: dict[str, Any]) -> None:
    ws_file.parent.mkdir(parents=True, exist_ok=True)
    ws_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


@app.command()
def add(
    repo_path: Annotated[Path, typer.Argument(help="Folder path to add")],
    workspace_file: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
) -> None:
    """Add a folder to the VS Code workspace file."""
    settings = load_settings()
    ws_file = workspace_file or settings.workspace.file
    data = _load(ws_file)

    folder_str = str(repo_path.resolve())
    if any(f.get("path") == folder_str for f in data["folders"]):
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
    ws_file = workspace_file or settings.workspace.file
    data = _load(ws_file)

    folder_str = str(repo_path.resolve())
    before = len(data["folders"])
    data["folders"] = [f for f in data["folders"] if f.get("path") != folder_str]

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
    root = base_dir or settings.repos.base_dir
    ws_file = workspace_file or settings.workspace.file

    if not root.exists():
        rprint(f"[yellow]Repos directory not found: {root}[/yellow]")
        raise typer.Exit(0)

    folders = [
        {"path": str(repo_dir.resolve())}
        for group_dir in sorted(root.iterdir())
        if group_dir.is_dir()
        for repo_dir in sorted(group_dir.iterdir())
        if (repo_dir / ".git").exists()
    ]

    data = {
        "folders": folders,
        "settings": {
            "editor.formatOnSave": True,
            "files.trimTrailingWhitespace": True,
            "editor.rulers": [100],
        },
    }
    _save(ws_file, data)
    rprint(f"[green]Generated[/green] {ws_file} with [bold]{len(folders)}[/bold] folders.")


@app.command("open")
def open_workspace(
    workspace_file: Annotated[Path | None, typer.Option("--workspace", "-w")] = None,
) -> None:
    """Open the workspace in VS Code."""
    settings = load_settings()
    ws_file = workspace_file or settings.workspace.file
    if not ws_file.exists():
        rprint(f"[red]Workspace file not found: {ws_file}[/red]")
        raise typer.Exit(1)
    subprocess.run(["code", str(ws_file)], check=True)
