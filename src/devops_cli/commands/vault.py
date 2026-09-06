"""CLI command module for HashiCorp Vault enterprise secret broker."""

from __future__ import annotations

import re
from typing import Annotated

import typer

from devops_cli.core.cli import new_typer
from devops_cli.dry_run.models import CommandDryRunResult
from devops_cli.dry_run.state import is_dry_run, set_dry_run
from devops_cli.lang import HELP
from devops_cli.output import (
    print_error,
    print_success,
    print_table,
    render_dry_run_result,
)
from devops_cli.security.vault_broker import VaultSecretBroker

VAULT_PATH_PATTERN = re.compile(r"^(?:vault://)?[a-zA-Z0-9_\-./#]+$")


def _validate_vault_path(path: str) -> None:
    """Validate Vault secret path format and reject path traversal sequences."""
    clean = path.strip()
    if not clean:
        raise ValueError("Vault secret path cannot be empty.")
    if ".." in clean:
        raise ValueError("Vault secret path cannot contain '..' traversal sequences.")
    if not VAULT_PATH_PATTERN.match(clean):
        raise ValueError(f"Vault secret path contains invalid characters: '{path}'")


app = new_typer(help="Enterprise HashiCorp Vault secret broker commands", no_args_is_help=False)


@app.command("status")
def vault_status(
    vault_addr: Annotated[
        str | None,
        typer.Option("--addr", "-a", help="Vault cluster HTTP API address"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> CommandDryRunResult | None:
    """Inspect HashiCorp Vault cluster health and initialization status."""
    set_dry_run(dry_run)
    broker = VaultSecretBroker(vault_addr=vault_addr)

    if is_dry_run():
        render_dry_run_result(
            command="devops vault status",
            action="vault_health_status",
            details={"vault_addr": broker.vault_addr},
        )
        return None

    status = broker.get_status()
    columns = [("Property", "bold"), "Value"]
    rows = [
        ["Vault Address", broker.vault_addr],
        ["Initialized", "✓ Yes" if status.initialized else "✗ No"],
        ["Sealed", "✗ Sealed" if status.sealed else "✓ Unsealed"],
        ["Version", status.version or "Unknown"],
        ["Cluster", status.cluster_name or "N/A"],
        ["Health", "✓ Healthy" if status.is_healthy else "✗ Degraded"],
    ]
    if status.error_message:
        rows.append(["Error", status.error_message])

    print_table("HashiCorp Vault Cluster Status", columns=columns, rows=rows)
    return None


@app.command("get")
def vault_get(
    path: Annotated[
        str,
        typer.Argument(
            help="Vault secret path (e.g. secret/data/myapp or vault://secret/data/myapp#token)"
        ),
    ],
    key: Annotated[
        str | None,
        typer.Option("--key", "-k", help="Specific secret field key to extract"),
    ] = None,
    show: Annotated[
        bool,
        typer.Option("--show", help="Display secret in plain text without masking"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> CommandDryRunResult | None:
    """Fetch secret value from Vault or OS Keyring fallback."""
    set_dry_run(dry_run)
    try:
        _validate_vault_path(path)
    except ValueError as exc:
        print_error(str(exc), prefix=False)
        raise typer.Exit(1)
    broker = VaultSecretBroker()

    if is_dry_run():
        render_dry_run_result(
            command=f"devops vault get {path}",
            action="vault_get_secret",
            details={"path": path, "key": key, "vault_addr": broker.vault_addr},
        )
        return None

    val = broker.get_secret(path, key=key)
    if val is None:
        print_error(f"Secret not found at '{path}' (checked Vault and OS Keyring).", prefix=False)
        raise typer.Exit(1)

    if isinstance(val, dict):
        columns = [("Field", "bold"), "Value"]
        rows = [[k, str(v) if show else "***REDACTED***"] for k, v in val.items()]
        print_table(f"Vault Secrets: {path}", columns=columns, rows=rows)
    else:
        display_val = str(val) if show else "***REDACTED***"
        print_success(f"✓ {key or 'Secret'}: {display_val}")
    return None


@app.command("set")
def vault_set(
    path: Annotated[
        str,
        typer.Argument(help="Vault secret path (e.g. secret/data/myapp)"),
    ],
    key_values: Annotated[
        list[str],
        typer.Argument(help="Key-value pairs to store (format: KEY=VALUE)"),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> CommandDryRunResult | None:
    """Store secret key-value pairs in HashiCorp Vault KV-v2 engine."""
    set_dry_run(dry_run)
    try:
        _validate_vault_path(path)
    except ValueError as exc:
        print_error(str(exc), prefix=False)
        raise typer.Exit(1)
    broker = VaultSecretBroker()
    payload: dict[str, str] = {}

    for kv in key_values:
        if "=" in kv:
            k, v = kv.split("=", 1)
            payload[k.strip()] = v.strip()

    if not payload:
        print_error("No valid KEY=VALUE pairs provided.", prefix=False)
        raise typer.Exit(1)

    if is_dry_run():
        render_dry_run_result(
            command=f"devops vault set {path} ...",
            action="vault_set_secret",
            details={"path": path, "keys": list(payload.keys()), "vault_addr": broker.vault_addr},
        )
        return None

    ok = broker.set_secret(path, payload)
    if ok:
        print_success(f"✓ Successfully stored {len(payload)} secret(s) at '{path}'")
    else:
        print_error(f"Failed to write secrets to Vault at '{path}'", prefix=False)
        raise typer.Exit(1)
    return None


@app.command("sync")
def vault_sync(
    path: Annotated[
        str,
        typer.Argument(help="Vault secret path to synchronize into OS Keyring"),
    ],
    keys: Annotated[
        list[str] | None,
        typer.Option("--key", "-k", help="Specific keys to sync (syncs all keys if omitted)"),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> CommandDryRunResult | None:
    """Synchronize secrets from Vault into OS Keyring for offline/local CLI operations."""
    set_dry_run(dry_run)
    try:
        _validate_vault_path(path)
    except ValueError as exc:
        print_error(str(exc), prefix=False)
        raise typer.Exit(1)
    broker = VaultSecretBroker()

    if is_dry_run():
        render_dry_run_result(
            command=f"devops vault sync {path}",
            action="vault_sync_keyring",
            details={"path": path, "keys": keys, "vault_addr": broker.vault_addr},
        )
        return None

    count = broker.sync_to_keyring(path, keys=keys)
    print_success(f"✓ Synchronized {count} secret(s) from '{path}' into OS Keyring")
    return None
