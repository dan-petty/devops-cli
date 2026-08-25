"""Docker command group (Docker SDK)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.table import Table

from devops_cli.config.defaults import DEFAULT_DOCKER_TIMEOUT_SECONDS
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run
from devops_cli.output import (
    print_error,
    print_info,
    print_success,
    print_table,
    render_dry_run_result,
)

app = new_typer(help="Docker image management.", no_args_is_help=True)


# =============================================================================
# Docker SDK Client Connection Helper
# =============================================================================


def _client() -> Any:
    try:
        import docker  # type: ignore[import-untyped]
        from docker.errors import DockerException  # type: ignore[import-untyped]

        docker_host = os.environ.get("DOCKER_HOST", "").strip()
        if docker_host.startswith(("tcp://", "http://", "https://")):
            from devops_cli.config.settings import load_settings
            from devops_cli.core.validation import validate_service_url

            settings = load_settings()
            http_url = docker_host.replace("tcp://", "http://", 1)
            validate_service_url(http_url, "Docker Host", allow=settings.ai.allow_private_network)

        return docker.from_env(timeout=int(DEFAULT_DOCKER_TIMEOUT_SECONDS))
    except (ImportError, DockerException, ValueError) as exc:
        print_error(f"Cannot connect to Docker: {exc}", prefix=False)
        raise typer.Exit(1)


# =============================================================================
# Command: devops docker images
# =============================================================================


@app.command("images")
def list_images(
    name: Annotated[str | None, typer.Option("--name", "-n", help="Filter by name")] = None,
) -> None:
    """List local Docker images."""
    if is_dry_run():
        render_dry_run_result(
            command="devops docker images",
            action="list_docker_images",
            details={"name_filter": name},
        )
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

    print_table(table)


# =============================================================================
# Command: devops docker build
# =============================================================================


@app.command()
def build(
    context: Annotated[Path, typer.Argument(help="Build context directory")] = Path("."),
    tag: Annotated[str | None, typer.Option("--tag", "-t")] = None,
    dockerfile: Annotated[Path | None, typer.Option("--file", "-f")] = None,
    no_cache: Annotated[bool, typer.Option("--no-cache")] = False,
) -> None:
    """Build a Docker image."""
    if is_dry_run():
        render_dry_run_result(
            command="devops docker build",
            target=str(context),
            action="build_docker_image",
            details={
                "tag": tag,
                "dockerfile": str(dockerfile) if dockerfile else None,
                "no_cache": no_cache,
            },
        )
        return
    client = _client()
    kwargs: dict[str, Any] = {"path": str(context), "rm": True, "nocache": no_cache}
    if tag:
        kwargs["tag"] = tag
    if dockerfile:
        kwargs["dockerfile"] = str(dockerfile)

    print_info(f"Building from [dim]{context}[/dim]...", prefix=False)
    image, build_logs = client.images.build(**kwargs)
    for chunk in build_logs:
        if "stream" in chunk:
            line = re.sub(r"[\x00-\x1f\x7f]", "", chunk["stream"]).rstrip()
            if line:
                print_info(line, prefix=False)
    tag_suffix = f" ({tag})" if tag else ""
    print_success(f"Built: {image.short_id}{tag_suffix}")


# =============================================================================
# Command: devops docker push
# =============================================================================


@app.command()
def push(
    image: Annotated[str, typer.Argument(help="Image name[:tag] to push")],
) -> None:
    """Push a Docker image to a registry."""
    if is_dry_run():
        render_dry_run_result(
            command="devops docker push",
            target=image,
            action="push_docker_image",
            details={"image": image},
        )
        return
    if not re.match(r"^[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)*(?::[a-zA-Z0-9_.-]+)?$", image):
        print_error(f"Invalid Docker image name format: '{image}'", prefix=False)
        raise typer.Exit(1)
    client = _client()
    print_info(f"Pushing [dim]{image}[/dim]...", prefix=False)
    for chunk in client.images.push(image, stream=True, decode=True):
        if "status" in chunk and "progressDetail" not in chunk:
            clean_status = re.sub(r"[\x00-\x1f\x7f]", "", str(chunk["status"]))
            print_info(clean_status, prefix=False)
        elif "error" in chunk:
            clean_err = re.sub(r"[\x00-\x1f\x7f]", "", str(chunk["error"]))
            print_error(clean_err, prefix=False)
            raise typer.Exit(1)
    print_success("Pushed.")


# =============================================================================
# Command: devops docker prune
# =============================================================================


@app.command()
def prune(
    volumes: Annotated[bool, typer.Option("--volumes", help="Also remove unused volumes")] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove unused containers, images, and networks."""
    if is_dry_run():
        render_dry_run_result(
            command="devops docker prune",
            action="prune_docker_resources",
            details={"volumes": volumes, "force": force},
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
    print_success(f"Pruned. Space reclaimed: {reclaimed_mb} MB")
