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
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.output import (
    print_error,
    print_info,
    print_success,
    print_table,
    render_dry_run_result,
)

app = new_typer(help=HELP.docker.app, no_args_is_help=True)


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
        print_error(ERRORS.docker.cannot_connect.format(exc=exc), prefix=False)
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

    table = Table(title=MESSAGES.docker.table_title_images)
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

    print_info(MESSAGES.docker.building_from.format(context=context), prefix=False)
    image, build_logs = client.images.build(**kwargs)
    for chunk in build_logs:
        if "stream" in chunk:
            line = re.sub(r"[\x00-\x1f\x7f]", "", chunk["stream"]).rstrip()
            if line:
                print_info(line, prefix=False)
    tag_suffix = f" ({tag})" if tag else ""
    print_success(MESSAGES.docker.built_image.format(short_id=image.short_id, suffix=tag_suffix))


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
        print_error(ERRORS.docker.invalid_image_name.format(image=image), prefix=False)
        raise typer.Exit(1)
    client = _client()
    print_info(MESSAGES.docker.pushing_image.format(image=image), prefix=False)
    for chunk in client.images.push(image, stream=True, decode=True):
        if "status" in chunk and "progressDetail" not in chunk:
            clean_status = re.sub(r"[\x00-\x1f\x7f]", "", str(chunk["status"]))
            print_info(clean_status, prefix=False)
        elif "error" in chunk:
            clean_err = re.sub(r"[\x00-\x1f\x7f]", "", str(chunk["error"]))
            print_error(clean_err, prefix=False)
            raise typer.Exit(1)
    print_success(MESSAGES.docker.pushed_success)


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
    print_success(MESSAGES.docker.pruned_success.format(mb=reclaimed_mb))


# =============================================================================
# Command: devops docker analyze-layers
# =============================================================================


@app.command("analyze-layers")
def analyze_layers(
    image: Annotated[str, typer.Argument(help="Container image tag or ID to analyze")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Simulate layer analysis")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output metrics as JSON")] = False,
) -> None:
    """Analyze container image layer efficiency and wasted space using Dive."""
    from devops_cli.output import format_json, print_muted, write_stdout
    from devops_cli.security.dive import run_dive_analysis

    if dry_run or is_dry_run():
        render_dry_run_result(
            command=f"devops docker analyze-layers {image}",
            action="dive_layer_analysis",
            target=image,
        )
        return

    print_muted(MESSAGES.docker.analyzing_layers.format(image=image))
    result = run_dive_analysis(image_name=image)

    if json_output:
        write_stdout(format_json(result.model_dump()) + "\n")
        return

    table = Table(title=MESSAGES.docker.table_title_layers.format(image=result.image_name))
    table.add_column("Layer", justify="right")
    table.add_column("Size (MB)", justify="right")
    table.add_column("Wasted (MB)", justify="right")
    table.add_column("Command / Directive")

    for lyr in result.layers:
        size_mb = f"{lyr.size_bytes / (1024 * 1024):.2f}"
        wasted_mb = f"{lyr.wasted_bytes / (1024 * 1024):.2f}"
        table.add_row(str(lyr.index), size_mb, wasted_mb, lyr.command[:80])

    print_table(table)
    eff_pct = result.efficiency_score * 100
    tot_mb = result.total_bytes / (1024 * 1024)
    wst_mb = result.wasted_bytes / (1024 * 1024)
    print_info(MESSAGES.docker.efficiency_summary.format(eff=eff_pct, size=tot_mb, wasted=wst_mb))
