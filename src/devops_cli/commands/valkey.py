"""CLI command group for Valkey high-performance workstation caching tier."""

from __future__ import annotations

import time
from typing import Annotated, Any

import typer

from devops_cli.config.settings import Settings, get_valkey_password, load_settings
from devops_cli.core.cli import new_typer
from devops_cli.dry_run.decorator import dry_run_command
from devops_cli.exceptions.valkey import ValkeyError
from devops_cli.lang import HELP
from devops_cli.output import (
    format_duration,
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
)
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.telemetry import trace_span
from devops_cli.valkey.client import ValkeyClient

app = new_typer(help="Valkey workstation caching and in-memory data store commands")


def _print_valkey_error(action: str, exc: ValkeyError) -> None:
    """Print sanitized Valkey error message masking any credentials or sensitive tokens."""
    safe_msg = mask_secrets(exc.message)
    print_error(f"{action}: {safe_msg}")


def _resolve_client(
    host: str | None = None,
    port: int | None = None,
    settings: Settings | None = None,
) -> ValkeyClient:
    """Resolve and construct a configured ValkeyClient instance."""
    cfg_settings = settings or load_settings()
    cfg = cfg_settings.valkey
    target_host = host or cfg.host
    target_port = port or cfg.port
    password = get_valkey_password(cfg_settings)
    return ValkeyClient(
        host=target_host,
        port=target_port,
        password=password,
        db=cfg.db,
        timeout=cfg.timeout,
    )


@app.command("ping")
@trace_span("valkey.ping")
def valkey_ping(
    host: Annotated[str | None, typer.Option("--host", "-h", help="Valkey server host")] = None,
    port: Annotated[int | None, typer.Option("--port", "-p", help="Valkey server port")] = None,
) -> None:
    """Test connection and measure round-trip latency to the Valkey server."""
    try:
        client = _resolve_client(host=host, port=port)
        start = time.perf_counter()
        res = client.ping()
        elapsed = time.perf_counter() - start
        if res:
            print_success(f"PONG (latency: {format_duration(elapsed)})")
        else:
            print_warning("Server responded without PONG acknowledgment.")
    except ValkeyError as exc:
        _print_valkey_error("Valkey ping failed", exc)
        raise typer.Exit(code=exc.exit_code) from exc


@app.command("info")
@trace_span("valkey.info")
def valkey_info(
    section: Annotated[
        str | None,
        typer.Option(
            "--section", "-s", help="Specific INFO section (server, memory, clients, stats)"
        ),
    ] = None,
    host: Annotated[str | None, typer.Option("--host", "-h", help="Valkey server host")] = None,
    port: Annotated[int | None, typer.Option("--port", "-p", help="Valkey server port")] = None,
) -> None:
    """Inspect server configuration, memory allocation, and operational metrics."""
    try:
        client = _resolve_client(host=host, port=port)
        info_data = client.info(section)
        columns = [("Property", "bold cyan"), "Value"]
        rows = [[k, str(v)] for k, v in sorted(info_data.items())]
        sec_title = f" [{section.upper()}]" if section else ""
        print_table(f"Valkey Node Information{sec_title}", columns=columns, rows=rows)
    except ValkeyError as exc:
        _print_valkey_error("Valkey info retrieval failed", exc)
        raise typer.Exit(code=exc.exit_code) from exc


@app.command("stats")
@trace_span("valkey.stats")
def valkey_stats(
    host: Annotated[str | None, typer.Option("--host", "-h", help="Valkey server host")] = None,
    port: Annotated[int | None, typer.Option("--port", "-p", help="Valkey server port")] = None,
) -> None:
    """Display quick diagnostic summary of server health, memory, and keys."""
    try:
        client = _resolve_client(host=host, port=port)
        info = client.info()
        dbsize = client.dbsize()
        uptime_sec = float(info.get("uptime_in_seconds", 0))

        columns = [("Metric", "bold cyan"), "Value"]
        rows = [
            [
                "Valkey Version",
                str(info.get("valkey_version") or info.get("redis_version", "unknown")),
            ],
            ["Host:Port", f"{client.host}:{client.port}"],
            ["Uptime", format_duration(uptime_sec)],
            ["Connected Clients", str(info.get("connected_clients", "unknown"))],
            ["Used Memory", str(info.get("used_memory_human", "unknown"))],
            ["Peak Memory", str(info.get("used_memory_peak_human", "unknown"))],
            ["Total Keys (Current DB)", str(dbsize)],
            ["Total Connections Received", str(info.get("total_connections_received", "unknown"))],
            ["Total Commands Processed", str(info.get("total_commands_processed", "unknown"))],
        ]
        print_table("Valkey Server Diagnostic Statistics", columns=columns, rows=rows)
    except ValkeyError as exc:
        _print_valkey_error("Failed collecting Valkey statistics", exc)
        raise typer.Exit(code=exc.exit_code) from exc


@app.command("keys")
@trace_span("valkey.keys")
def valkey_keys(
    pattern: Annotated[str, typer.Argument(help="Glob pattern to search for keys")] = "*",
    host: Annotated[str | None, typer.Option("--host", "-h", help="Valkey server host")] = None,
    port: Annotated[int | None, typer.Option("--port", "-p", help="Valkey server port")] = None,
) -> None:
    """List keys matching a glob pattern."""
    try:
        client = _resolve_client(host=host, port=port)
        matched_keys = client.keys(pattern)
        if not matched_keys:
            print_info(f"No keys matching '{pattern}' in database {client.db}.")
            return
        columns = [("Index", "dim"), ("Key", "bold")]
        rows = [[str(idx + 1), k] for idx, k in enumerate(sorted(matched_keys))]
        print_table(f"Valkey Keys ({len(matched_keys)} found)", columns=columns, rows=rows)
    except ValkeyError as exc:
        _print_valkey_error("Valkey keys search failed", exc)
        raise typer.Exit(code=exc.exit_code) from exc


@app.command("get")
@trace_span("valkey.get")
def valkey_get(
    key: Annotated[str, typer.Argument(help="Key to retrieve")],
    host: Annotated[str | None, typer.Option("--host", "-h", help="Valkey server host")] = None,
    port: Annotated[int | None, typer.Option("--port", "-p", help="Valkey server port")] = None,
) -> None:
    """Retrieve string value stored at key."""
    try:
        client = _resolve_client(host=host, port=port)
        val = client.get(key)
        if val is None:
            print_warning(f"Key '{key}' not found (nil).")
        else:
            typer.echo(val)
    except ValkeyError as exc:
        _print_valkey_error(f"Failed to get key '{mask_secrets(key)}'", exc)
        raise typer.Exit(code=exc.exit_code) from exc


@app.command("set")
@dry_run_command(
    command="devops valkey set",
    action="valkey_set_key",
    target_param="key",
    detail_params=["value", "ex"],
)
@trace_span("valkey.set")
def valkey_set(
    key: Annotated[str, typer.Argument(help="Key name to set")],
    value: Annotated[str, typer.Argument(help="Value to associate with key")],
    ex: Annotated[int | None, typer.Option("--ex", help="Expiration timeout in seconds")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
    host: Annotated[str | None, typer.Option("--host", "-h", help="Valkey server host")] = None,
    port: Annotated[int | None, typer.Option("--port", "-p", help="Valkey server port")] = None,
) -> None:
    """Set string value of key with optional expiration TTL."""
    try:
        client = _resolve_client(host=host, port=port)
        client.set(key, value, ex_seconds=ex)
        ttl_msg = f" (TTL: {ex}s)" if ex else ""
        print_success(f"Set '{key}' successfully{ttl_msg}.")
    except ValkeyError as exc:
        _print_valkey_error(f"Failed to set key '{mask_secrets(key)}'", exc)
        raise typer.Exit(code=exc.exit_code) from exc


@app.command("flush")
@dry_run_command(
    command="devops valkey flush",
    action="valkey_flush_db",
    detail_params=["all_databases"],
)
@trace_span("valkey.flush")
def valkey_flush(
    all_databases: Annotated[
        bool,
        typer.Option("--all", "-a", help="Flush all databases instead of just active one"),
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
    host: Annotated[str | None, typer.Option("--host", "-h", help="Valkey server host")] = None,
    port: Annotated[int | None, typer.Option("--port", "-p", help="Valkey server port")] = None,
) -> None:
    """Flush and purge keys from current or all databases."""
    try:
        client = _resolve_client(host=host, port=port)
        if all_databases:
            client.flushall()
            print_success("Flushed all Valkey databases.")
        else:
            client.flushdb()
            print_success(f"Flushed Valkey database {client.db}.")
    except ValkeyError as exc:
        _print_valkey_error("Valkey flush failed", exc)
        raise typer.Exit(code=exc.exit_code) from exc


@app.command("backup")
@dry_run_command(
    command="devops valkey backup",
    action="valkey_bgsave",
)
@trace_span("valkey.backup")
def valkey_backup(
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
    host: Annotated[str | None, typer.Option("--host", "-h", help="Valkey server host")] = None,
    port: Annotated[int | None, typer.Option("--port", "-p", help="Valkey server port")] = None,
) -> None:
    """Trigger background RDB persistence snapshot (BGSAVE)."""
    try:
        client = _resolve_client(host=host, port=port)
        res = client.bgsave()
        print_success(f"Backup initiated: {res}")
    except ValkeyError as exc:
        _print_valkey_error("Failed to initiate Valkey backup", exc)
        raise typer.Exit(code=exc.exit_code) from exc


@app.command("cli")
@trace_span("valkey.cli")
def valkey_cli(
    command_args: Annotated[
        list[str] | None,
        typer.Argument(
            help="Optional command and arguments to execute directly (e.g. PING or DBSIZE)"
        ),
    ] = None,
    host: Annotated[str | None, typer.Option("--host", "-h", help="Valkey server host")] = None,
    port: Annotated[int | None, typer.Option("--port", "-p", help="Valkey server port")] = None,
) -> None:
    """Execute raw Valkey commands directly against the server."""
    try:
        client = _resolve_client(host=host, port=port)
        if not command_args:
            print_info(
                f"Connected to Valkey at {client.host}:{client.port}. Specify command arguments to run."
            )
            return
        cmd = command_args[0].upper()
        args: list[Any] = command_args[1:]
        res = client.execute(cmd, *args)
        if isinstance(res, list):
            for item in res:
                typer.echo(str(item))
        else:
            typer.echo(str(res))
    except ValkeyError as exc:
        _print_valkey_error("Valkey command execution failed", exc)
        raise typer.Exit(code=exc.exit_code) from exc
