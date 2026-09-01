"""Docker command group (Docker SDK)."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_DOCKER_TIMEOUT_SECONDS,
)
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
    name: Annotated[str | None, typer.Option("--name", "-n", help=HELP.docker.name_filter)] = None,
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

    rows: list[list[str]] = []
    for image in images:
        tags = image.tags or ["<none>:<none>"]
        for tag in tags:
            repo, _, t = tag.rpartition(":")
            size_mb = image.attrs.get("Size", 0) // (1024 * 1024)
            rows.append([repo or "<none>", t or "<none>", image.short_id, f"{size_mb} MB"])

    print_table(
        title=MESSAGES.docker.table_title_images,
        columns=[("Repository", "cyan"), "Tag", "ID", "Size"],
        rows=rows,
    )


# =============================================================================
# Command: devops docker build
# =============================================================================


@app.command()
def build(
    context: Annotated[Path, typer.Argument(help=HELP.docker.context_dir)] = DEFAULT_CURRENT_PATH,
    tag: Annotated[str | None, typer.Option("--tag", "-t", help=HELP.docker.tag)] = None,
    dockerfile: Annotated[
        Path | None, typer.Option("--file", "-f", help=HELP.docker.dockerfile)
    ] = None,
    no_cache: Annotated[bool, typer.Option("--no-cache", help=HELP.docker.no_cache)] = False,
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
    image: Annotated[str, typer.Argument(help=HELP.docker.image_name)],
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
    volumes: Annotated[bool, typer.Option("--volumes", help=HELP.docker.volumes)] = False,
    force: Annotated[bool, typer.Option("--force", "-f", help=HELP.options.force)] = False,
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
# Command: devops docker stats
# =============================================================================


def _format_bytes(raw: int | None) -> str:
    """Format bytes into a human-readable string (B / KB / MB / GB)."""
    n = raw or 0
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n //= 1024
    return f"{n:.1f} TB"


def _parse_docker_stats_row(container: Any) -> list[str]:
    """Extract a single Rich table row from a running Docker container stats stream."""
    name = container.name
    stats = container.stats(stream=False)
    cpu_stats = stats.get("cpu_stats", {})
    precpu_stats = stats.get("precpu_stats", {})
    memory_stats = stats.get("memory_stats", {})
    networks = stats.get("networks", {})

    cpu_delta = cpu_stats.get("cpu_usage", {}).get("total_usage", 0) - precpu_stats.get(
        "cpu_usage", {}
    ).get("total_usage", 0)
    system_delta = cpu_stats.get("system_cpu_usage", 0) - precpu_stats.get("system_cpu_usage", 0)
    num_cpus = cpu_stats.get("online_cpus") or len(
        cpu_stats.get("cpu_usage", {}).get("percpu_usage", [1])
    )
    cpu_pct = (cpu_delta / system_delta * num_cpus * 100.0) if system_delta > 0 else 0.0

    mem_usage = memory_stats.get("usage", 0)
    mem_cache = memory_stats.get("stats", {}).get("cache", 0)
    mem_net = mem_usage - mem_cache
    mem_limit = memory_stats.get("limit", 0)

    net_rx = sum(v.get("rx_bytes", 0) for v in networks.values())
    net_tx = sum(v.get("tx_bytes", 0) for v in networks.values())

    cpu_color = "red" if cpu_pct > 80 else ("yellow" if cpu_pct > 50 else "green")
    return [
        name,
        f"[{cpu_color}]{cpu_pct:.1f}%[/{cpu_color}]",
        f"{_format_bytes(mem_net)} / {_format_bytes(mem_limit)}",
        f"{_format_bytes(net_rx)} / {_format_bytes(net_tx)}",
    ]


def _build_docker_stats_table(name_filter: str | None) -> Any:
    """Build a Rich Table of live Docker container statistics."""
    from rich.table import Table

    client = _client()
    try:
        containers = client.containers.list(filters={"name": name_filter} if name_filter else None)
    except Exception:
        containers = []

    table = Table(title="Docker Container Stats", show_header=True, header_style="bold cyan")
    table.add_column("Container", style="cyan", no_wrap=True)
    table.add_column("CPU %", justify="right")
    table.add_column("MEM Usage / Limit", justify="right")
    table.add_column("NET I/O (RX/TX)", justify="right")

    for container in containers:
        try:
            row = _parse_docker_stats_row(container)
            table.add_row(*row)
        except Exception:
            table.add_row(container.name, "—", "—", "—")

    return table


@app.command("stats")
def stats(
    name: Annotated[str | None, typer.Option("--name", "-n", help=HELP.docker.name_filter)] = None,
    watch: Annotated[bool, typer.Option("--watch", "-w", help=HELP.docker.watch)] = False,
    interval: Annotated[float, typer.Option("--interval", "-i", help=HELP.docker.interval)] = 2.0,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Display live container CPU, memory, and network I/O statistics."""
    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops docker stats",
            action="docker_container_stats",
            details={"name_filter": name, "watch": watch, "interval": interval},
        )
        return

    if watch:
        from devops_cli.watchers.live_resource import LiveResourceWatcher

        watcher = LiveResourceWatcher(
            lambda: _build_docker_stats_table(name),
            interval_seconds=interval,
            name="docker_stats",
        )
        watcher.watch()
    else:
        from rich import get_console

        get_console().print(_build_docker_stats_table(name))


# =============================================================================
# Command: devops docker analyze-layers
# =============================================================================


@app.command("analyze-layers")
def analyze_layers(
    image: Annotated[str, typer.Argument(help=HELP.docker.image_name)],
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
    json_output: Annotated[bool, typer.Option("--json", help=HELP.options.json_output)] = False,
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

    rows = []
    for lyr in result.layers:
        size_mb = f"{lyr.size_bytes / (1024 * 1024):.2f}"
        wasted_mb = f"{lyr.wasted_bytes / (1024 * 1024):.2f}"
        rows.append([str(lyr.index), size_mb, wasted_mb, lyr.command[:80]])

    print_table(
        title=MESSAGES.docker.table_title_layers.format(image=result.image_name),
        columns=[
            ("Layer", "right"),
            ("Size (MB)", "right"),
            ("Wasted (MB)", "right"),
            "Command / Directive",
        ],
        rows=rows,
    )
    eff_pct = result.efficiency_score * 100
    tot_mb = result.total_bytes / (1024 * 1024)
    wst_mb = result.wasted_bytes / (1024 * 1024)
    print_info(MESSAGES.docker.efficiency_summary.format(eff=eff_pct, size=tot_mb, wasted=wst_mb))
