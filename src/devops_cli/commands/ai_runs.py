"""`devops ai runs`: benchmark and evaluation runs, kept in the data directory and shared (#554)."""

from __future__ import annotations

from typing import Annotated

import typer

from devops_cli.ai.run_store import (
    Mechanism,
    RunIndex,
    RunIndexNotConfiguredError,
    SavedRun,
    load_runs,
    runs_dir,
)
from devops_cli.config import options as opt
from devops_cli.config.constants import (
    CONST_RUNS_INDEX_NAMESPACE,
    CONST_RUNS_INDEX_SECRET,
    CONST_RUNS_INDEX_SERVICE,
)
from devops_cli.config.defaults import DEFAULT_VALKEY_PORT
from devops_cli.core.cli import new_typer
from devops_cli.exceptions.valkey import ValkeyError
from devops_cli.k8s.node_port import (
    NodePortSpec,
    ServiceNotReachableError,
    node_port_address,
    secret_value,
)
from devops_cli.output import (
    escape_text,
    get_stderr_console,
    print_error,
    print_info,
    print_success,
)
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry import trace_span

app = new_typer(
    help="Benchmark and evaluation runs, kept in the data directory and shared through Valkey.",
    no_args_is_help=True,
)


def announce_runs(saved: list[SavedRun], *, to_stderr: bool = False) -> None:
    """Say where runs were kept, and whether other workstations can see them.

    Commands writing JSON or Markdown to stdout announce on stderr, keeping their output parseable.
    """
    if not saved:
        return
    console = get_stderr_console() if to_stderr else None
    first = saved[0]
    kept = (
        f"{first.record.mechanism.value} run {first.record.run_id} → "
        f"[bold]{escape_text(str(first.path))}[/bold]"
        if len(saved) == 1
        else f"{len(saved)} {first.record.mechanism.value} runs → "
        f"[bold]{escape_text(str(first.path.parent))}[/bold]"
    )
    print_success(f"Saved {kept}", console=console)
    if not first.shared:
        print_info(
            f"Kept on this workstation only: {escape_text(first.detail)}.",
            prefix=False,
            console=console,
        )


def announce_run(saved: SavedRun, *, to_stderr: bool = False) -> None:
    """Say where a run was kept, and whether other workstations can see it."""
    announce_runs([saved], to_stderr=to_stderr)


@app.command("reindex")
@trace_span("ai.runs.reindex")
def reindex_cmd(
    mechanism: Annotated[
        Mechanism | None,
        typer.Option("--mechanism", "-m", help="Only index runs of this mechanism."),
    ] = None,
) -> None:
    """Rebuild the shared run index in Valkey from the run records in the data directory."""
    records = load_runs(mechanism)
    if not records:
        print_info(f"No runs recorded in {escape_text(str(runs_dir()))}.")
        return
    try:
        with RunIndex.from_settings() as index:
            count = index.put(*records)
            location = index.location
    except RunIndexNotConfiguredError as exc:
        print_error(exc.message)
        raise typer.Exit(code=1) from exc
    except ValkeyError as exc:
        print_error(f"The run index is unreachable: {mask_secrets(exc.message)}")
        raise typer.Exit(code=1) from exc
    print_success(f"Indexed {count} run(s) from {escape_text(str(runs_dir()))} at {location}.")


RUNS_INDEX = NodePortSpec(
    what="run index",
    port=DEFAULT_VALKEY_PORT,
    port_name="valkey",
    port_label="Valkey",
    manifest="k8s/llm/valkey-runs.yaml",
)


@app.command("connect")
@trace_span("ai.runs.connect")
def connect_cmd(
    context: Annotated[
        str | None, typer.Option("--context", help="Kubernetes context (default: current).")
    ] = None,
    namespace: Annotated[
        str, typer.Option("--namespace", "-n", help="Namespace of the run index.")
    ] = CONST_RUNS_INDEX_NAMESPACE,
    service: Annotated[
        str, typer.Option("--service", help="Service of the run index's Valkey.")
    ] = CONST_RUNS_INDEX_SERVICE,
    secret: Annotated[
        str, typer.Option("--secret", help="Secret holding the Valkey password.")
    ] = CONST_RUNS_INDEX_SECRET,
) -> None:
    """Find the cluster's run index, check it answers, share runs through it, and index them."""
    from devops_cli.config.settings import dotted_set, load_settings, save_settings

    try:
        host, port = node_port_address(context, namespace, service, RUNS_INDEX)
        password = secret_value(context, namespace, secret, "password")
    except ServiceNotReachableError as exc:
        print_error(f"Cannot find the run index: {exc.message}", prefix=False)
        raise typer.Exit(code=1) from exc
    url = f"valkey://{host}:{port}"
    records = load_runs()
    try:
        with RunIndex.connect(url, password) as index:
            count = index.put(*records) if records else 0
    except ValkeyError as exc:
        print_error(f"The run index at {host}:{port} does not answer: {mask_secrets(exc.message)}")
        raise typer.Exit(code=1) from exc
    settings = load_settings()
    dotted_set(settings, opt.RUNS_INDEX_PASSWORD, password)
    settings.runs.index_url = url
    save_settings(settings)
    print_success(
        f"Runs are shared through the run index at {host}:{port}; indexed {count} run(s)."
    )
