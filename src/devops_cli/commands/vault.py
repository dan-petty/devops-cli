"""CLI command module for HashiCorp Vault enterprise secret broker."""

from __future__ import annotations

import re
from typing import Annotated, Any

import typer

from devops_cli.core.cli import new_typer
from devops_cli.core.paths import validate_no_path_traversal
from devops_cli.dry_run.models import CommandDryRunResult
from devops_cli.dry_run.state import is_dry_run, set_dry_run
from devops_cli.exceptions.vault import VaultConfigurationError
from devops_cli.lang import HELP
from devops_cli.output import (
    print_error,
    print_success,
    print_table,
    render_dry_run_result,
)
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.security.vault_broker import VaultSecretBroker

VAULT_PATH_PATTERN = re.compile(r"^(?:vault://)?[a-zA-Z0-9_\-./#]+$")

_LEASE_REGISTRY: Any = None


def get_lease_registry(default: Any) -> Any:
    """Return the session-scoped lease registry, creating it on first use."""
    global _LEASE_REGISTRY
    if _LEASE_REGISTRY is None:
        _LEASE_REGISTRY = default
    return _LEASE_REGISTRY


def reset_lease_registry() -> None:
    """Reset the session lease registry for clean test isolation."""
    global _LEASE_REGISTRY
    _LEASE_REGISTRY = None


def _validate_vault_path(path: str) -> None:
    """Validate Vault secret path format and reject path traversal sequences."""
    clean = path.strip()
    if not clean:
        raise VaultConfigurationError("Vault secret path cannot be empty.")
    validate_no_path_traversal(
        clean,
        error_cls=VaultConfigurationError,
        label="Vault secret path",
    )
    if not VAULT_PATH_PATTERN.match(clean):
        raise VaultConfigurationError(f"Vault secret path contains invalid characters: '{path}'")


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
    except (ValueError, VaultConfigurationError) as exc:
        print_error(mask_secrets(str(exc)), prefix=False)
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
    except (ValueError, VaultConfigurationError) as exc:
        print_error(mask_secrets(str(exc)), prefix=False)
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
    except (ValueError, VaultConfigurationError) as exc:
        print_error(mask_secrets(str(exc)), prefix=False)
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


# =============================================================================
# Command: devops vault login
# =============================================================================


@app.command("login")
def vault_login(
    method: Annotated[
        str, typer.Option("--method", "-m", help="Authentication method: approle or kubernetes")
    ] = "approle",
    role: Annotated[
        str | None, typer.Option("--role", help="Vault role name (kubernetes method)")
    ] = None,
    role_id: Annotated[str | None, typer.Option("--role-id", help="AppRole role_id")] = None,
    secret_id: Annotated[str | None, typer.Option("--secret-id", help="AppRole secret_id")] = None,
    store: Annotated[
        bool, typer.Option("--store/--no-store", help="Persist the issued token to the OS keyring")
    ] = True,
) -> None:
    """Authenticate with Vault natively via AppRole or the in-cluster ServiceAccount."""
    from devops_cli.config.constants import CONST_VAULT_AUTH_METHODS
    from devops_cli.exceptions.vault import VaultAuthenticationError
    from devops_cli.security.vault_lease import login_approle, login_kubernetes

    if method not in CONST_VAULT_AUTH_METHODS:
        print_error(
            f"Unsupported Vault auth method '{method}'. "
            f"Choose one of: {', '.join(sorted(CONST_VAULT_AUTH_METHODS))}."
        )
        raise typer.Exit(1)

    broker = VaultSecretBroker()
    if is_dry_run():
        render_dry_run_result(
            command=f"devops vault login --method {method}",
            action="vault_authenticate",
            details={"method": method, "role": role, "store": store},
        )
        return

    try:
        if method == "kubernetes":
            result = login_kubernetes(
                broker.vault_addr, role or "", namespace=broker.vault_namespace
            )
        else:
            result = login_approle(
                broker.vault_addr,
                role_id or "",
                secret_id or "",
                namespace=broker.vault_namespace,
            )
    except VaultAuthenticationError as exc:
        print_error(str(exc))
        raise typer.Exit(1)

    if store:
        from devops_cli.config.settings import set_keyring_secret

        set_keyring_secret("vault_token", result.client_token)

    print_success(
        f"✓ Authenticated with Vault via {result.method}. "
        f"Lease: {result.lease_duration}s, renewable: {result.renewable}, "
        f"policies: {', '.join(result.policies) or 'none'}."
    )


# =============================================================================
# Command: devops vault leases
# =============================================================================


@app.command("leases")
def vault_leases(
    renew: Annotated[
        bool, typer.Option("--renew", help="Renew every tracked lease nearing expiry")
    ] = False,
    revoke: Annotated[
        str | None, typer.Option("--revoke", help="Revoke a single lease by id")
    ] = None,
) -> None:
    """Inspect, renew, or revoke tracked Vault dynamic secret leases."""
    from devops_cli.security.vault_lease import LeaseRegistry

    broker = VaultSecretBroker()
    if is_dry_run():
        render_dry_run_result(
            command="devops vault leases",
            action="vault_lease_lifecycle",
            details={"renew": renew, "revoke": revoke},
        )
        return

    registry = get_lease_registry(
        LeaseRegistry(
            vault_addr=broker.vault_addr,
            token=broker.vault_token,
            namespace=broker.vault_namespace,
        )
    )

    if revoke:
        revoked = registry.revoke(revoke)
        if not revoked:
            print_error(f"Could not revoke lease '{mask_secrets(revoke)}'.")
            raise typer.Exit(1)
        print_success(f"✓ Revoked lease '{mask_secrets(revoke)}'.")
        return

    if renew:
        report = registry.renew_expiring()
        print_success(
            f"✓ Renewed {len(report.renewed)} lease(s); "
            f"{len(report.failed)} failed, {len(report.skipped)} still within lifetime."
        )
        if report.failed:
            raise typer.Exit(1)
        return

    leases = registry.leases()
    if not leases:
        print_success("No Vault leases are currently tracked in this session.")
        return

    print_table(
        title="Vault Dynamic Secret Leases",
        columns=[("Lease", "cyan"), "Path", "Remaining", "Renewable", "Renewals"],
        rows=[
            [
                mask_secrets(lease.lease_id),
                lease.secret_path or "—",
                f"{lease.remaining_seconds():.0f}s",
                "yes" if lease.renewable else "no",
                str(lease.renewal_count),
            ]
            for lease in leases
        ],
    )


# =============================================================================
# Command: devops vault audit
# =============================================================================


@app.command("audit")
def vault_audit(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the audit trail as JSON")
    ] = False,
) -> None:
    """Show which provider satisfied each credential lookup in this session.

    The trail records the logical secret name and the answering provider only; secret
    values are never stored or rendered.
    """
    from devops_cli.output import format_json, write_stdout
    from devops_cli.security.secrets import audit_entries

    entries = audit_entries()
    if json_output:
        write_stdout(format_json([entry.__dict__ for entry in entries]) + "\n")
        return

    if not entries:
        print_success("No credential lookups have been recorded in this session.")
        return

    print_table(
        title="Credential Access Audit",
        columns=[("Secret", "cyan"), "Provider", "Resolved", "Timestamp"],
        rows=[
            [
                entry.secret_name,
                entry.provider or "—",
                "yes" if entry.resolved else "no",
                entry.timestamp,
            ]
            for entry in entries
        ],
    )
