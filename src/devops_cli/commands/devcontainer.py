"""Devcontainer management commands."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Annotated

import typer
from jinja2 import Environment, FileSystemLoader, select_autoescape
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.config.constants import (
    CONST_DEVCONTAINER_DIR_NAME,
    CONST_DEVCONTAINER_IMAGE_PREFIX,
    CONST_DEVCONTAINER_JSON_NAME,
    CONST_DEVCONTAINER_JSON_PATH,
    CONST_DEVCONTAINER_POST_CREATE_NAME,
    CONST_DEVCONTAINER_POST_CREATE_PATH,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer, repo_label
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.git.operations import iter_workspace_repos

app = new_typer(help="Manage devcontainer configurations.", no_args_is_help=True)
console = Console()

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _project_python_version() -> str:
    pyproject = _PROJECT_ROOT / "pyproject.toml"
    if not pyproject.exists():
        return "3.14"
    with pyproject.open("rb") as file_handle:
        data = tomllib.load(file_handle)
    requires_python: str = str(data.get("project", {}).get("requires-python") or "")
    if not requires_python:
        return "3.14"
    match = re.search(r"^>=?\s*([\d.]+)", requires_python)
    if match:
        return match.group(1)
    return requires_python


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape([]),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


@app.command()
def init(
    repo_path: Annotated[Path, typer.Argument(help="Path to the repository")] = Path("."),
    project_name: Annotated[str | None, typer.Option("--name", "-n")] = None,
    python_version: Annotated[str, typer.Option("--python")] = _project_python_version(),
) -> None:
    """Scaffold .devcontainer/ in a repository using the standard template."""
    dc_dir = repo_path / CONST_DEVCONTAINER_DIR_NAME
    dc_file = dc_dir / CONST_DEVCONTAINER_JSON_NAME

    if dc_file.exists():
        rprint(f"[yellow]devcontainer.json already exists: {dc_file}[/yellow]")
        raise typer.Exit(1)

    raw_name = project_name or repo_path.resolve().name
    # Strip characters unsafe in container names / shell contexts
    name = re.sub(r"[^a-zA-Z0-9._-]+", "_", raw_name)
    dc_dir.mkdir(parents=True, exist_ok=True)

    env = _jinja_env()

    dc_file.write_text(
        env.get_template("devcontainer.json.j2").render(
            project_name=name, python_version=python_version
        ),
        encoding="utf-8",
    )

    sh_file = dc_dir / CONST_DEVCONTAINER_POST_CREATE_NAME
    sh_file.write_text(
        env.get_template("postCreate.sh.j2").render(python_version=python_version),
        encoding="utf-8",
    )
    sh_file.chmod(0o755)

    rprint(f"[green]Created:[/green] {dc_file}")
    rprint(f"[green]Created:[/green] {sh_file}")

    vscode_dir = repo_path / ".vscode"
    mcp_file = vscode_dir / "mcp.json"
    if not mcp_file.exists():
        vscode_dir.mkdir(parents=True, exist_ok=True)
        mcp_file.write_text(
            env.get_template("mcp.json.j2").render(project_name=name),
            encoding="utf-8",
        )
        rprint(f"[green]Created:[/green] {mcp_file}")


@app.command()
def update(
    repo_path: Annotated[Path, typer.Argument(help="Path to the repository")] = Path("."),
    python_version: Annotated[str, typer.Option("--python")] = _project_python_version(),
) -> None:
    """Update the Python image version in an existing devcontainer.json."""
    dc_file = repo_path / CONST_DEVCONTAINER_JSON_PATH
    if not dc_file.exists():
        rprint(f"[red]No devcontainer.json found: {dc_file}[/red]")
        raise typer.Exit(1)

    try:
        data = json.loads(dc_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        rprint(f"[red]Invalid JSON in {dc_file}: {exc}[/red]")
        raise typer.Exit(1)
    data["image"] = f"{CONST_DEVCONTAINER_IMAGE_PREFIX}{python_version}"
    dc_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    rprint(f"[green]Updated image → python:{python_version}[/green]")


@app.command("list")
def list_devcontainers(
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
) -> None:
    """List repos with their devcontainer status."""
    if is_dry_run():
        render_dry_run_result(
            command="devops devcontainer list",
            action="list_devcontainers",
            details={"repos": []},
        )
        return

    settings = load_settings()
    root = base_dir or settings.repos.base_dir

    if not root.exists():
        rprint(f"[yellow]Repos directory not found: {root}[/yellow]")
        raise typer.Exit(0)

    table = Table(title="Devcontainer Status")
    table.add_column("Repository", style="cyan")
    table.add_column(CONST_DEVCONTAINER_JSON_NAME)
    table.add_column(CONST_DEVCONTAINER_POST_CREATE_NAME, justify="center")

    for repo_dir in iter_workspace_repos(root):
        dc_ok = (repo_dir / CONST_DEVCONTAINER_JSON_PATH).exists()
        sh_ok = (repo_dir / CONST_DEVCONTAINER_POST_CREATE_PATH).exists()
        table.add_row(
            repo_label(repo_dir),
            "[green]✓ configured[/green]" if dc_ok else "[yellow]✗ missing[/yellow]",
            "[green]✓[/green]" if sh_ok else "[dim]—[/dim]",
        )

    console.print(table)
