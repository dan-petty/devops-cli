"""Devcontainer management commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from jinja2 import Environment, FileSystemLoader, select_autoescape
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.cli import new_typer

app = new_typer(help="Manage devcontainer configurations.", no_args_is_help=True)
console = Console()

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


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
    python_version: Annotated[str, typer.Option("--python")] = "3.14",
) -> None:
    """Scaffold .devcontainer/ in a repository using the standard template."""
    dc_dir = repo_path / ".devcontainer"
    dc_file = dc_dir / "devcontainer.json"

    if dc_file.exists():
        rprint(f"[yellow]devcontainer.json already exists: {dc_file}[/yellow]")
        raise typer.Exit(1)

    name = project_name or repo_path.resolve().name
    dc_dir.mkdir(parents=True, exist_ok=True)

    env = _jinja_env()

    dc_file.write_text(
        env.get_template("devcontainer.json.j2").render(
            project_name=name, python_version=python_version
        ),
        encoding="utf-8",
    )

    sh_file = dc_dir / "postCreate.sh"
    sh_file.write_text(
        env.get_template("postCreate.sh.j2").render(python_version=python_version),
        encoding="utf-8",
    )
    sh_file.chmod(0o755)

    rprint(f"[green]Created:[/green] {dc_file}")
    rprint(f"[green]Created:[/green] {sh_file}")


@app.command()
def update(
    repo_path: Annotated[Path, typer.Argument(help="Path to the repository")] = Path("."),
    python_version: Annotated[str, typer.Option("--python")] = "3.14",
) -> None:
    """Update the Python image version in an existing devcontainer.json."""
    dc_file = repo_path / ".devcontainer" / "devcontainer.json"
    if not dc_file.exists():
        rprint(f"[red]No devcontainer.json found: {dc_file}[/red]")
        raise typer.Exit(1)

    data = json.loads(dc_file.read_text(encoding="utf-8"))
    data["image"] = f"mcr.microsoft.com/devcontainers/python:{python_version}"
    dc_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    rprint(f"[green]Updated image → python:{python_version}[/green]")


@app.command("list")
def list_devcontainers(
    base_dir: Annotated[Path | None, typer.Option("--base-dir", "-d")] = None,
) -> None:
    """List repos with their devcontainer status."""
    from devops_cli.config import load_settings

    settings = load_settings()
    root = base_dir or settings.repos.base_dir

    if not root.exists():
        rprint(f"[yellow]Repos directory not found: {root}[/yellow]")
        raise typer.Exit(0)

    table = Table(title="Devcontainer Status")
    table.add_column("Repository", style="cyan")
    table.add_column("devcontainer.json")
    table.add_column("postCreate.sh", justify="center")

    for group_dir in sorted(root.iterdir()):
        if not group_dir.is_dir():
            continue
        for repo_dir in sorted(group_dir.iterdir()):
            if not (repo_dir / ".git").exists():
                continue
            dc_ok = (repo_dir / ".devcontainer" / "devcontainer.json").exists()
            sh_ok = (repo_dir / ".devcontainer" / "postCreate.sh").exists()
            table.add_row(
                f"{group_dir.name}/{repo_dir.name}",
                "[green]✓ configured[/green]" if dc_ok else "[yellow]✗ missing[/yellow]",
                "[green]✓[/green]" if sh_ok else "[dim]—[/dim]",
            )

    console.print(table)
