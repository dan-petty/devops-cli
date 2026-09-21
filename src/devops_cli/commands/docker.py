"""Docker command group (Engine API over the daemon socket)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.constants import (
    CONST_DOCKER_CPU_CRITICAL_PERCENT,
    CONST_DOCKER_CPU_WARNING_PERCENT,
)
from devops_cli.config.defaults import (
    DEFAULT_CURRENT_PATH,
    DEFAULT_SANDBOX_NETWORK,
)
from devops_cli.core.cli import new_typer
from devops_cli.docker.engine import DockerEngineService, get_engine
from devops_cli.dry_run import is_dry_run
from devops_cli.exceptions.docker import DockerError
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.models.docker import BuildCacheReport, ContainerStatEntry
from devops_cli.output import (
    TablePayload,
    format_docker_stats_table,
    format_duration,
    print_error,
    print_info,
    print_success,
    print_table,
    render_dry_run_result,
    write_stderr,
    write_stdout,
)
from devops_cli.output import (
    format_bytes as _format_bytes,
)

app = new_typer(help=HELP.docker.app, no_args_is_help=True)


# =============================================================================
# Docker Engine API Connection Helper
# =============================================================================


def _engine() -> DockerEngineService:
    """Resolve the shared Engine API service, surfacing daemon failures as CLI errors."""
    engine = get_engine()
    try:
        engine.client()
    except DockerError as exc:
        print_error(ERRORS.docker.cannot_connect.format(exc=exc), prefix=False)
        raise typer.Exit(1)
    return engine


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
    images = _engine().list_images(name=name)

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
    client = _engine().client()
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
    client = _engine().client()
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
    client = _engine().client()
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


def _cpu_color(cpu_percentage: float) -> str:
    """Select the utilisation severity colour for a CPU percentage."""
    if cpu_percentage > CONST_DOCKER_CPU_CRITICAL_PERCENT:
        return "red"
    return "yellow" if cpu_percentage > CONST_DOCKER_CPU_WARNING_PERCENT else "green"


def _stats_row(sample: ContainerStatEntry) -> list[str]:
    """Render a typed container resource sample as a Rich table row."""
    color = _cpu_color(sample.cpu_percentage)
    return [
        sample.name,
        f"[{color}]{sample.cpu_percentage:.1f}%[/{color}]",
        f"{_format_bytes(sample.memory_usage_bytes)} / {_format_bytes(sample.memory_limit_bytes)}",
        f"{_format_bytes(sample.net_io_in_bytes)} / {_format_bytes(sample.net_io_out_bytes)}",
    ]


def _build_docker_stats_table(name_filter: str | None) -> TablePayload:
    """Build a TablePayload of live Docker container statistics from the Engine API."""
    engine = _engine()
    try:
        containers = engine.list_containers(name=name_filter)
    except DockerError:
        containers = []

    rows: list[list[str]] = []
    for container in containers:
        try:
            rows.append(_stats_row(engine.container_stats(container.container_id)))
        except DockerError:
            rows.append([container.name, "—", "—", "—"])

    return format_docker_stats_table(rows)


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
            lambda: _build_docker_stats_table(name).render(),
            interval_seconds=interval,
            name="docker_stats",
        )
        watcher.watch()
    else:
        from devops_cli.output import print

        print(_build_docker_stats_table(name))


# =============================================================================
# Command: devops docker cache
# =============================================================================


def _build_cache_rows(report: BuildCacheReport) -> list[list[str]]:
    """Render BuildKit cache records as Rich table rows ordered by descending size."""
    ordered = sorted(report.records, key=lambda record: record.size_bytes, reverse=True)
    return [
        [
            record.cache_id[:12],
            record.cache_type or "—",
            _format_bytes(record.size_bytes),
            str(record.usage_count),
            "yes" if record.in_use else "no",
            "yes" if record.shared else "no",
            record.description[:60] or "—",
        ]
        for record in ordered
    ]


@app.command("cache")
def build_cache(
    prune: Annotated[bool, typer.Option("--prune", help=HELP.docker.prune_cache)] = False,
    json_output: Annotated[bool, typer.Option("--json", help=HELP.options.json_output)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Introspect BuildKit multi-stage layer cache occupancy, reuse, and reclaimable space."""
    from devops_cli.output import format_json

    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops docker cache",
            action="docker_build_cache_introspect",
            details={"prune": prune},
        )
        return

    engine = _engine()
    report = engine.build_cache()

    if json_output:
        write_stdout(format_json(report.model_dump()) + "\n")
        return

    print_table(
        title=MESSAGES.docker.table_title_build_cache,
        columns=[
            ("ID", "cyan"),
            "Type",
            ("Size", "right"),
            ("Uses", "right"),
            "In Use",
            "Shared",
            "Step",
        ],
        rows=_build_cache_rows(report),
    )
    print_info(
        MESSAGES.docker.build_cache_summary.format(
            total=_format_bytes(report.total_bytes),
            reclaimable=_format_bytes(report.reclaimable_bytes),
            reuse=report.reuse_ratio * 100,
            in_use=report.in_use_count,
            shared=report.shared_count,
        )
    )

    if prune:
        reclaimed = engine.prune_build_cache()
        print_success(MESSAGES.docker.build_cache_pruned.format(reclaimed=_format_bytes(reclaimed)))


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


# =============================================================================
# Command: devops docker sandbox
# =============================================================================


@app.command("sandbox")
def docker_sandbox(
    command: Annotated[
        list[str],
        typer.Argument(help="Workload command to execute inside container sandbox"),
    ],
    image: Annotated[
        str,
        typer.Option("--image", "-i", help="Docker container image to execute within"),
    ] = "python:3.14-slim",
    workspace: Annotated[
        Path,
        typer.Option("--workspace", "-w", help="Workspace directory to mount"),
    ] = Path(DEFAULT_CURRENT_PATH),
    memory: Annotated[
        str,
        typer.Option("--memory", "-m", help="Memory limit (e.g. 2g, 512m)"),
    ] = "2g",
    cpus: Annotated[
        float,
        typer.Option("--cpus", "-c", help="CPU limit"),
    ] = 2.0,
    network: Annotated[
        str,
        typer.Option(
            "--network",
            "-n",
            help="Network mode: isolated | sandbox_namespace | public_whitelist | local_whitelist | bridge",
        ),
    ] = DEFAULT_SANDBOX_NETWORK,
    network_mode: Annotated[
        str | None,
        typer.Option(
            "--network-mode",
            help="Multi-tier network mode: isolated | sandbox_namespace | public_whitelist | local_whitelist | bridge",
        ),
    ] = None,
    public_whitelist: Annotated[
        str | None,
        typer.Option(
            "--public-whitelist", help="Comma-separated public domains/IPs allowed for egress"
        ),
    ] = None,
    local_whitelist: Annotated[
        str | None,
        typer.Option("--local-whitelist", help="Comma-separated local URLs/IPs allowed for egress"),
    ] = None,
    read_only: Annotated[
        bool,
        typer.Option("--read-only", help="Mount workspace as read-only"),
    ] = False,
    rootless: Annotated[
        bool,
        typer.Option("--rootless/--root", help="Run container with host user UID/GID"),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Execute workload inside an isolated, disposable Docker container sandbox."""
    from devops_cli.docker.sandbox import WorkloadSandboxConfig, WorkloadSandboxRunner

    effective_mode = network_mode or network
    pub_list = (
        [item.strip() for item in public_whitelist.split(",") if item.strip()]
        if public_whitelist
        else []
    )
    loc_list = (
        [item.strip() for item in local_whitelist.split(",") if item.strip()]
        if local_whitelist
        else []
    )

    cfg = WorkloadSandboxConfig(
        workspace_dir=workspace,
        command=command,
        image=image,
        read_only=read_only,
        memory_limit=memory,
        cpu_limit=cpus,
        network_mode=effective_mode,
        public_whitelist=pub_list,
        local_whitelist=loc_list,
        rootless=rootless,
    )
    sandbox_runner = WorkloadSandboxRunner(cfg)

    if dry_run or is_dry_run():
        render_dry_run_result(
            command=f"devops docker sandbox {' '.join(command)}",
            action="docker_workload_sandbox",
            details=sandbox_runner.build_dry_run_details(),
        )
        return

    print_info(f"Running command in sandbox ({image}, network={cfg.network_mode})...")
    res = sandbox_runner.run()
    if res.stdout:
        write_stdout(res.stdout)
    if res.stderr:
        write_stderr(res.stderr)

    if res.exit_code != 0:
        raise typer.Exit(res.exit_code)
    print_success(f"✓ Sandbox workload completed in {format_duration(res.duration_seconds)}")


# =============================================================================
# Sigstore Cosign Commands (Signing & Verification)
# =============================================================================


@app.command("sign")
def docker_sign(
    image: Annotated[
        str, typer.Argument(help="Target container image reference (name:tag or digest)")
    ],
    key: Annotated[
        str | None,
        typer.Option("--key", "-k", help="Path to private key or keyring:<name>"),
    ] = None,
    keyless: Annotated[
        bool,
        typer.Option("--keyless/--keyed", help="Sign keylessly using OIDC/Fulcio"),
    ] = True,
    oidc_token: Annotated[
        str | None,
        typer.Option(
            "--oidc-token", help="OIDC identity token or keyring:<name> for keyless signing"
        ),
    ] = None,
    annotation: Annotated[
        list[str] | None,
        typer.Option("--annotation", "-a", help="Custom supply chain key=value annotations"),
    ] = None,
    upload: Annotated[
        bool,
        typer.Option("--upload/--no-upload", help="Upload signature to remote registry"),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Sign a container image using Sigstore Cosign (keyless or keyed)."""
    from devops_cli.docker.cosign import CosignRunner
    from devops_cli.exceptions.docker import CosignError
    from devops_cli.exceptions.tools import DependencyError
    from devops_cli.models.docker import DockerSignRequest

    runner = CosignRunner()
    req = DockerSignRequest(
        image=image,
        key=key,
        keyless=keyless,
        oidc_token=oidc_token,
        annotations=annotation or [],
        upload=upload,
        dry_run=dry_run or is_dry_run(),
    )

    if req.dry_run:
        render_dry_run_result(
            command=f"devops docker sign {image}",
            action="docker_cosign_sign",
            details={
                "image": image,
                "keyless": keyless,
                "key": key or "none",
                "annotations": annotation or [],
                "upload": upload,
            },
        )
        return

    try:
        res = runner.sign_image(req)
        print_success(f"✓ Image '{image}' signed successfully. (signature: {res.signature_ref})")
    except (DependencyError, CosignError) as exc:
        print_error(str(exc))
        raise typer.Exit(1)


@app.command("verify")
def docker_verify(
    image: Annotated[str, typer.Argument(help="Target container image reference to verify")],
    key: Annotated[
        str | None,
        typer.Option("--key", "-k", help="Path to public key or keyring:<name>"),
    ] = None,
    certificate_identity: Annotated[
        str | None,
        typer.Option(
            "--certificate-identity", help="Expected signer certificate identity (SAN/email/URI)"
        ),
    ] = None,
    certificate_oidc_issuer: Annotated[
        str | None,
        typer.Option("--certificate-oidc-issuer", help="Expected OIDC certificate issuer URL"),
    ] = None,
    attestation: Annotated[
        bool,
        typer.Option(
            "--attestation", help="Verify in-toto attestation predicate instead of signature"
        ),
    ] = False,
    predicate_type: Annotated[
        str | None,
        typer.Option(
            "--type", help="Attestation predicate type (e.g. slsaprovenance, spdx, custom)"
        ),
    ] = None,
    insecure_ignore_tlog: Annotated[
        bool,
        typer.Option("--insecure-ignore-tlog", help="Ignore Rekor transparency log verification"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Verify container image signature or attestation using Sigstore Cosign."""
    from devops_cli.docker.cosign import CosignRunner
    from devops_cli.exceptions.docker import CosignVerificationError
    from devops_cli.exceptions.tools import DependencyError
    from devops_cli.models.docker import DockerVerifyRequest

    runner = CosignRunner()
    req = DockerVerifyRequest(
        image=image,
        key=key,
        cert_identity=certificate_identity,
        cert_issuer=certificate_oidc_issuer,
        attestation=attestation,
        predicate_type=predicate_type,
        insecure_ignore_tlog=insecure_ignore_tlog,
        dry_run=dry_run or is_dry_run(),
    )

    if req.dry_run:
        render_dry_run_result(
            command=f"devops docker verify {image}",
            action="docker_cosign_verify",
            details={
                "image": image,
                "key": key or "none",
                "cert_identity": certificate_identity or "none",
                "cert_issuer": certificate_oidc_issuer or "none",
                "attestation": attestation,
            },
        )
        return

    try:
        res = runner.verify_image(req)
        print_success(
            f"✓ Image '{image}' signature verified successfully ({len(res.signatures)} signatures)."
        )
    except (DependencyError, CosignVerificationError) as exc:
        print_error(str(exc))
        raise typer.Exit(1)
