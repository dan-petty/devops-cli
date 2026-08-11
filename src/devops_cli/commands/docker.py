"""Docker command group (Docker SDK)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.core.cli import new_typer
from devops_cli.core.dry_run import is_dry_run

app = new_typer(help="Docker image management.", no_args_is_help=True)
console = Console()


def _client() -> Any:
    try:
        import docker  # type: ignore[import-untyped]
        from docker.errors import DockerException  # type: ignore[import-untyped]

        return docker.from_env(timeout=300)
    except (ImportError, DockerException) as exc:
        rprint(f"[red]Cannot connect to Docker: {exc}[/red]")
        raise typer.Exit(1)


@app.command("images")
def list_images(
    name: Annotated[str | None, typer.Option("--name", "-n", help="Filter by name")] = None,
) -> None:
    """List local Docker images."""
    if is_dry_run():
        rprint("[yellow][dry-run][/yellow] Would list local Docker images.")
        return
    client = _client()
    images = client.images.list(name=name)

    table = Table(title="Docker Images")
    table.add_column("Repository", style="cyan")
    table.add_column("Tag")
    table.add_column("ID")
    table.add_column("Size")

    for image in images:
        tags = image.tags or ["<none>:<none>"]
        for tag in tags:
            repo, _, t = tag.rpartition(":")
            size_mb = image.attrs.get("Size", 0) // (1024 * 1024)
            table.add_row(repo or "<none>", t or "<none>", image.short_id, f"{size_mb} MB")

    console.print(table)


@app.command()
def build(
    context: Annotated[Path, typer.Argument(help="Build context directory")] = Path("."),
    tag: Annotated[str | None, typer.Option("--tag", "-t")] = None,
    dockerfile: Annotated[Path | None, typer.Option("--file", "-f")] = None,
    no_cache: Annotated[bool, typer.Option("--no-cache")] = False,
) -> None:
    """Build a Docker image."""
    if is_dry_run():
        rprint(f"[yellow][dry-run][/yellow] Would build Docker image from {context}.")
        return
    client = _client()
    kwargs: dict[str, Any] = {"path": str(context), "rm": True, "nocache": no_cache}
    if tag:
        kwargs["tag"] = tag
    if dockerfile:
        kwargs["dockerfile"] = str(dockerfile)

    rprint(f"Building from [dim]{context}[/dim]...")
    image, build_logs = client.images.build(**kwargs)
    for chunk in build_logs:
        if "stream" in chunk:
            line = chunk["stream"].rstrip()
            if line:
                rprint(line)
    rprint(f"[green]Built:[/green] {image.short_id}" + (f" ({tag})" if tag else ""))


@app.command()
def push(
    image: Annotated[str, typer.Argument(help="Image name[:tag] to push")],
) -> None:
    """Push a Docker image to a registry."""
    if is_dry_run():
        rprint(f"[yellow][dry-run][/yellow] Would push Docker image {image}.")
        return
    import re

    if not re.match(r"^[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)*(?::[a-zA-Z0-9_.-]+)?$", image):
        rprint(f"[red]Invalid Docker image name format: '{image}'[/red]")
        raise typer.Exit(1)
    client = _client()
    rprint(f"Pushing [dim]{image}[/dim]...")
    for chunk in client.images.push(image, stream=True, decode=True):
        if "status" in chunk and "progressDetail" not in chunk:
            rprint(chunk["status"])
        elif "error" in chunk:
            rprint(f"[red]{chunk['error']}[/red]")
            raise typer.Exit(1)
    rprint("[green]Pushed.[/green]")


@app.command()
def prune(
    volumes: Annotated[bool, typer.Option("--volumes", help="Also remove unused volumes")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove unused containers, images, and networks."""
    if is_dry_run():
        rprint(
            "[yellow][dry-run][/yellow] Would prune unused Docker containers, images, and networks."
        )
        return
    if not force:
        typer.confirm(
            "Remove all unused containers, images, and networks?",
            abort=True,
        )
    client = _client()
    result = client.system.prune(volumes=volumes)
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict):
        reclaimed_bytes = sum(result[1].values())
    elif isinstance(result, dict):
        reclaimed_bytes = result.get("SpaceReclaimed", 0)
    else:
        reclaimed_bytes = 0
    reclaimed_mb = reclaimed_bytes // (1024 * 1024)
    rprint(f"[green]Pruned. Space reclaimed: {reclaimed_mb} MB[/green]")
