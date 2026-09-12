"""CLI command group for isolated workload sandbox lifecycle management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.core.cli import new_typer
from devops_cli.dry_run.models import CommandDryRunResult
from devops_cli.dry_run.state import is_dry_run, set_dry_run
from devops_cli.exceptions.sandbox import (
    SandboxError,
    SandboxNotFoundError,
    SandboxValidationError,
)
from devops_cli.lang import HELP
from devops_cli.output import (
    print_error,
    print_success,
    print_table,
    render_dry_run_result,
)
from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.models import (
    SandboxDeployConfig,
    SandboxInstance,
    SandboxStatus,
)

app = new_typer(help=HELP.sandbox.app, no_args_is_help=True)


def _parse_env_flags(env_list: list[str] | None) -> dict[str, str]:
    """Convert KEY=VALUE list into an environment dictionary."""
    if not env_list:
        return {}
    env_map: dict[str, str] = {}
    for item in env_list:
        if "=" in item:
            k, v = item.split("=", 1)
            env_map[k.strip()] = v.strip()
    return env_map


def _format_ports(inst: SandboxInstance) -> str:
    """Format port bindings for display in tables."""
    if not inst.port_bindings:
        return "-"
    return ", ".join(f"{b.host_port}->{b.container_port}/{b.protocol}" for b in inst.port_bindings)


def _render_instances_table(instances: list[SandboxInstance]) -> None:
    """Display sandbox instances in a Rich table."""
    columns = [
        ("Instance ID", "cyan"),
        ("Name", "bold"),
        ("Image", "white"),
        ("Status", "green"),
        ("Ports", "yellow"),
        ("Created", "dim"),
    ]
    rows = [
        [
            inst.instance_id,
            inst.name,
            inst.image,
            inst.status.value,
            _format_ports(inst),
            inst.created_at[:19].replace("T", " "),
        ]
        for inst in instances
    ]
    print_table("Workload Sandbox Instances", columns, rows)


@app.command("deploy")
def deploy(
    command: Annotated[list[str] | None, typer.Argument(help="Optional container command")] = None,
    image: Annotated[
        str, typer.Option("--image", "-i", help=HELP.sandbox.image)
    ] = "python:3.14-slim",
    name: Annotated[str | None, typer.Option("--name", "-n", help=HELP.sandbox.name)] = None,
    ports: Annotated[list[int] | None, typer.Option("--port", "-p", help=HELP.sandbox.port)] = None,
    workspace: Annotated[
        Path, typer.Option("--workspace", "-w", help=HELP.sandbox.workspace)
    ] = Path("."),
    memory: Annotated[str, typer.Option("--memory", "-m", help=HELP.sandbox.memory)] = "2g",
    cpus: Annotated[float, typer.Option("--cpus", "-c", help=HELP.sandbox.cpus)] = 2.0,
    read_only: Annotated[
        bool, typer.Option("--read-only/--no-read-only", help=HELP.sandbox.read_only)
    ] = True,
    network: Annotated[str, typer.Option("--network", help=HELP.sandbox.network)] = "bridge",
    env: Annotated[list[str] | None, typer.Option("--env", "-e", help=HELP.sandbox.env)] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> CommandDryRunResult | None:
    """Deploy an isolated background container sandbox with security containment."""
    set_dry_run(dry_run)
    engine = WorkloadSandboxEngine()
    env_map = _parse_env_flags(env)
    cmd_list = command or ["sleep", "infinity"]

    cfg = SandboxDeployConfig(
        image=image,
        name=name,
        ports=ports or [],
        command=cmd_list,
        workspace_dir=workspace,
        memory_limit=memory,
        cpu_limit=cpus,
        read_only=read_only,
        network_mode=network,
        env=env_map,
    )

    if is_dry_run():
        simulated = engine.deploy(cfg, dry_run=True)
        render_dry_run_result(
            command="devops sandbox deploy",
            action="deploy_workload_sandbox",
            details={
                "instance_id": simulated.instance_id,
                "name": simulated.name,
                "image": simulated.image,
                "workspace": str(simulated.workspace_dir),
                "ports": [b.model_dump() for b in simulated.port_bindings],
                "security": {
                    "cap_drop": ["ALL"],
                    "security_opt": ["no-new-privileges:true"],
                    "pids_limit": 256,
                    "read_only": read_only,
                },
            },
        )
        return None

    try:
        inst = engine.deploy(cfg)
        print_success(f"Sandbox '{inst.name}' deployed successfully [ID: {inst.instance_id}]")
        _render_instances_table([inst])
        return None
    except (SandboxValidationError, SandboxError) as exc:
        print_error(f"Failed deploying sandbox: {exc}")
        raise typer.Exit(1) from exc


@app.command("status")
def status(
    instance_id: Annotated[str | None, typer.Argument(help=HELP.sandbox.instance_id)] = None,
    all_instances: Annotated[
        bool, typer.Option("--all", "-a", help=HELP.sandbox.all_instances)
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help=HELP.sandbox.json_output)] = False,
) -> None:
    """Inspect status of deployed sandbox containers."""
    engine = WorkloadSandboxEngine()
    try:
        instances = engine.status(identifier=instance_id)
    except SandboxNotFoundError as exc:
        print_error(str(exc))
        raise typer.Exit(1) from exc

    if not all_instances and not instance_id:
        instances = [i for i in instances if i.status == SandboxStatus.RUNNING]

    if json_output:
        typer.echo(json.dumps([i.model_dump() for i in instances], indent=2))
        return

    if not instances:
        print_success("No sandbox instances found.")
        return

    _render_instances_table(instances)


@app.command("stop")
def stop(
    instance_id: Annotated[str | None, typer.Argument(help=HELP.sandbox.instance_id)] = None,
    all_instances: Annotated[
        bool, typer.Option("--all", "-a", help=HELP.sandbox.all_instances)
    ] = False,
    timeout: Annotated[int, typer.Option("--timeout", "-t", help=HELP.sandbox.timeout)] = 10,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> CommandDryRunResult | None:
    """Gracefully stop and tear down a sandbox container."""
    set_dry_run(dry_run)
    engine = WorkloadSandboxEngine()

    if not instance_id and not all_instances:
        print_error("Please specify a sandbox instance ID or use --all to stop all sandboxes.")
        raise typer.Exit(1)

    targets: list[str] = (
        [inst.instance_id for inst in engine.registry.list_instances()]
        if all_instances
        else ([instance_id] if instance_id else [])
    )

    if is_dry_run():
        render_dry_run_result(
            command="devops sandbox stop",
            action="stop_workload_sandbox",
            details={"targets": targets, "timeout": timeout},
        )
        return None

    for target in targets:
        try:
            stopped = engine.stop(target, timeout=timeout)
            print_success(
                f"Sandbox '{stopped.name}' stopped and removed [ID: {stopped.instance_id}]"
            )
        except SandboxNotFoundError as exc:
            print_error(f"Cannot stop '{target}': {exc}")
    return None


@app.command("exec")
def exec_cmd(
    instance_id: Annotated[str, typer.Argument(help=HELP.sandbox.instance_id)],
    command: Annotated[
        list[str], typer.Argument(help="Command and arguments to execute inside sandbox")
    ],
    workdir: Annotated[
        str | None, typer.Option("--workdir", "-w", help=HELP.sandbox.workdir)
    ] = None,
) -> None:
    """Execute a command inside an active sandbox container."""
    engine = WorkloadSandboxEngine()
    try:
        res = engine.exec(instance_id, command=command, workdir=workdir)
        if res.stdout:
            typer.echo(res.stdout, nl=False)
        if res.stderr:
            typer.echo(res.stderr, nl=False, err=True)
        if res.exit_code != 0:
            raise typer.Exit(res.exit_code)
    except (SandboxNotFoundError, SandboxError) as exc:
        print_error(f"Execution failed: {exc}")
        raise typer.Exit(1) from exc


__all__ = ["app"]
