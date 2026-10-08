"""CLI command module for HashiCorp Vault enterprise secret broker."""

from __future__ import annotations

import re
from typing import Annotated, Any

import typer

from devops_cli.config.constants import (
    CONST_VAULT_AUTH_METHODS,
    CONST_VAULT_LOGIN_KEYRING_KEY,
    CONST_VAULT_PATH_LEASE_REVOKE,
    CONST_VAULT_PATH_TOKEN_REVOKE_SELF,
    CONST_VAULT_TOKEN_REJECTED_STATUSES,
)
from devops_cli.config.settings import (
    SecretStorageError,
    keyring_delete,
    keyring_read,
    keyring_write,
    require_persistent_keyring,
)
from devops_cli.core.cli import exit_on_error, new_typer
from devops_cli.core.paths import validate_no_path_traversal
from devops_cli.dry_run.models import CommandDryRunResult
from devops_cli.dry_run.state import is_dry_run, set_dry_run
from devops_cli.exceptions.vault import VaultConfigurationError, VaultError, VaultLeaseError
from devops_cli.lang import HELP
from devops_cli.models.vault import (
    VaultAuthResult,
    VaultSecretLookup,
    VaultStoredLogin,
    VaultSyncReport,
)
from devops_cli.output import (
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    render_dry_run_result,
)
from devops_cli.security.sanitizer import mask_secrets
from devops_cli.security.vault_broker import VaultSecretBroker
from devops_cli.security.vault_http import vault_url
from devops_cli.security.vault_lease import (
    LeaseRegistry,
    login_approle,
    login_kubernetes,
    revoke_self,
)

VAULT_PATH_PATTERN = re.compile(r"^(?:vault://)?[a-zA-Z0-9_\-./#]+$")

# Where a token comes from when a run cannot keep one in the OS keyring.
_NO_STORE_HINT = (
    "Run `devops vault login --no-store` to check the credentials without keeping a token. Runs "
    "without an OS keyring, such as CI runners and pods, take VAULT_TOKEN from their platform's "
    "Vault integration."
)

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
    """Inspect HashiCorp Vault cluster health and initialization status.

    The health endpoint needs no token, and none is sent. The Token row names where the token
    other commands would use comes from, and why a stored token is not used for this address.
    """
    set_dry_run(dry_run)
    broker = VaultSecretBroker(vault_addr=vault_addr)

    if is_dry_run():
        render_dry_run_result(
            command="devops vault status",
            action="vault_health_status",
            details={"vault_addr": broker.vault_addr, "token_source": broker.token_source.source},
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
        ["Token", broker.token_source.describe()],
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
    """Fetch a secret from Vault, or from the OS keyring when Vault cannot answer.

    The keyring answers only with no usable token, when Vault has no value at the path, or when
    Vault is unreachable; never after Vault rejects the token. The output names the source.
    """
    set_dry_run(dry_run)
    try:
        _validate_vault_path(path)
    except (ValueError, VaultConfigurationError) as exc:
        print_error(mask_secrets(str(exc)), prefix=False)
        raise typer.Exit(1) from exc
    broker = VaultSecretBroker()

    if is_dry_run():
        render_dry_run_result(
            command=f"devops vault get {path}",
            action="vault_get_secret",
            details={
                "path": path,
                "key": key,
                "vault_addr": broker.vault_addr,
                "token_source": broker.token_source.source,
            },
        )
        return None

    with exit_on_error(VaultError):
        lookup = broker.get_secret(path, key=key)
    if lookup.value is None:
        print_error(
            f"Secret not found at '{path}' (checked: {', '.join(lookup.checked)}; "
            f"{lookup.fallback_reason}).",
            prefix=False,
            safe=True,
        )
        raise typer.Exit(1)
    _render_secret(path, key, lookup, show=show)
    return None


def _render_secret(path: str, key: str | None, lookup: VaultSecretLookup, *, show: bool) -> None:
    """Print a found secret, masked unless asked, with the source that answered."""
    if isinstance(lookup.value, dict):
        columns = [("Field", "bold"), "Value"]
        rows = [[k, str(v) if show else "***REDACTED***"] for k, v in lookup.value.items()]
        print_table(f"Vault Secrets: {path} (from {lookup.source})", columns=columns, rows=rows)
    else:
        display_val = str(lookup.value) if show else "***REDACTED***"
        print_success(f"✓ {key or 'Secret'} (from {lookup.source}): {display_val}")
    if lookup.fallback_reason:
        print_info(f"Answered from the OS keyring: {lookup.fallback_reason}.", safe=True)


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
        raise typer.Exit(1) from exc
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
            details={
                "path": path,
                "keys": list(payload.keys()),
                "vault_addr": broker.vault_addr,
                "token_source": broker.token_source.source,
            },
        )
        return None

    with exit_on_error(VaultError):
        broker.set_secret(path, payload)
    print_success(f"✓ Successfully stored {len(payload)} secret(s) at '{path}'")
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
    """Synchronize secrets from Vault into OS Keyring for offline/local CLI operations.

    Reads Vault alone. A path with no secret fails, and a field named like the entry that holds
    the `devops vault login` token is never written.
    """
    set_dry_run(dry_run)
    try:
        _validate_vault_path(path)
    except (ValueError, VaultConfigurationError) as exc:
        print_error(mask_secrets(str(exc)), prefix=False)
        raise typer.Exit(1) from exc
    broker = VaultSecretBroker()

    if is_dry_run():
        render_dry_run_result(
            command=f"devops vault sync {path}",
            action="vault_sync_keyring",
            details={
                "path": path,
                "keys": keys,
                "vault_addr": broker.vault_addr,
                "token_source": broker.token_source.source,
            },
        )
        return None

    with exit_on_error(VaultError):
        report = broker.sync_to_keyring(path, keys=keys)
    _report_sync(path, report)
    return None


def _report_sync(path: str, report: VaultSyncReport) -> None:
    """Print what a sync stored, skipped and could not store; exit 1 when anything was lost."""
    print_success(f"✓ Synchronized {len(report.synced)} secret(s) from '{path}' into OS Keyring")
    if report.skipped:
        print_warning(
            f"Skipped {', '.join(report.skipped)}: that keyring entry holds the token "
            "`devops vault login` stored, which sync never replaces."
        )
    if report.missing:
        print_error(f"Vault has no value for: {', '.join(report.missing)}.", prefix=False)
    if report.failed:
        print_error(f"The OS keyring did not store: {', '.join(report.failed)}.", prefix=False)
    if report.missing or report.failed:
        raise typer.Exit(1)


# =============================================================================
# Command: devops vault login
# =============================================================================


@app.command("login")
def vault_login(
    method: Annotated[
        str,
        typer.Option(
            "--method",
            "-m",
            help=(
                "Authentication method: approle or kubernetes. In a pod, use kubernetes with "
                "--no-store: it checks the ServiceAccount login without keeping the token, and "
                "the pod takes VAULT_TOKEN from its Vault integration."
            ),
        ),
    ] = "approle",
    role: Annotated[
        str | None, typer.Option("--role", help="Vault role name (kubernetes method)")
    ] = None,
    role_id: Annotated[str | None, typer.Option("--role-id", help="AppRole role_id")] = None,
    secret_id: Annotated[str | None, typer.Option("--secret-id", help="AppRole secret_id")] = None,
    store: Annotated[
        bool,
        typer.Option(
            "--store/--no-store",
            help=(
                "Keep the issued token in the OS keyring, for this Vault address and namespace "
                "only. --no-store checks the credentials without keeping the token: the form for "
                "CI and in-cluster runs, which take VAULT_TOKEN from their Vault integration."
            ),
        ),
    ] = True,
) -> None:
    """Authenticate with Vault natively via AppRole or the in-cluster ServiceAccount.

    With --store, the default, the token is kept in the OS keyring with the address and namespace
    that issued it, and other vault commands use it for that Vault only. The command fails before
    logging in when no encrypted, unlocked OS keyring can keep it. The token is never printed.
    """
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
            details={
                "method": method,
                "role": role,
                "store": store,
                "vault_addr": broker.vault_addr,
                "namespace": broker.vault_namespace,
            },
        )
        return

    if store:
        _require_keyring_for_login()
    with exit_on_error(VaultError):
        result = _login(method, broker, role=role, role_id=role_id, secret_id=secret_id)
    if store:
        _store_login(result.client_token, broker)

    kept = "kept the token in the OS keyring" if store else "did not keep the token (--no-store)"
    print_success(
        f"✓ Authenticated with Vault at {broker.vault_addr} via {result.method} and {kept}. "
        f"Lease: {result.lease_duration}s, renewable: {result.renewable}, "
        f"policies: {', '.join(result.policies) or 'none'}.",
        safe=True,
    )


def _login(
    method: str,
    broker: VaultSecretBroker,
    *,
    role: str | None,
    role_id: str | None,
    secret_id: str | None,
) -> VaultAuthResult:
    """Log in with the chosen method at the broker's address and namespace."""
    if method == "kubernetes":
        return login_kubernetes(broker.vault_addr, role or "", namespace=broker.vault_namespace)
    return login_approle(
        broker.vault_addr, role_id or "", secret_id or "", namespace=broker.vault_namespace
    )


def _require_keyring_for_login() -> None:
    """Exit 1 before logging in unless an encrypted, unlocked OS keyring can keep the token."""
    try:
        require_persistent_keyring()
    except SecretStorageError as exc:
        print_error(f"Cannot keep the Vault token: {exc}. {_NO_STORE_HINT}", safe=True)
        raise typer.Exit(1) from exc


def _store_login(token: str, broker: VaultSecretBroker) -> None:
    """Keep the token in the OS keyring with the address and namespace that issued it."""
    record = VaultStoredLogin(
        token=token, vault_addr=broker.vault_addr, namespace=broker.vault_namespace
    )
    try:
        keyring_write(CONST_VAULT_LOGIN_KEYRING_KEY, record.model_dump_json())
    except SecretStorageError as exc:
        print_error(
            f"Authenticated, but could not keep the Vault token: {exc}. {_NO_STORE_HINT}",
            safe=True,
        )
        raise typer.Exit(1) from exc


# =============================================================================
# Command: devops vault logout
# =============================================================================


@app.command("logout")
def vault_logout() -> None:
    """Revoke the token `devops vault login` stored, at the Vault that issued it, and delete it.

    The revoke goes to the address and namespace stored with the token, whatever VAULT_ADDR says
    now. The local copy is deleted even when the revoke fails, for example because Vault is
    unreachable or the token has expired, and the output says the revoke did not happen.
    """
    raw_record = _read_stored_login()
    if raw_record is None:
        print_success("No Vault token is stored; nothing to log out.")
        return
    login = _parse_stored_login(raw_record)
    if is_dry_run():
        render_dry_run_result(
            command="devops vault logout",
            action="vault_logout",
            details={
                "revoke": (
                    f"POST {vault_url(login.vault_addr, CONST_VAULT_PATH_TOKEN_REVOKE_SELF)}"
                    if login
                    else None
                ),
                "namespace": login.namespace if login else None,
                "keyring_delete": CONST_VAULT_LOGIN_KEYRING_KEY,
            },
        )
        return
    revoke_failure = _revoke_stored_login(login)
    _delete_stored_login()
    issuer = login.issuer() if login else "the Vault that issued it"
    if revoke_failure is None:
        print_success(
            f"✓ Revoked the stored Vault token at {issuer} and deleted it from the OS keyring.",
            safe=True,
        )
        return
    print_warning(
        f"Deleted the stored Vault token from the OS keyring, but did not revoke it at {issuer}: "
        f"{revoke_failure}. It stays valid until it expires.",
        safe=True,
    )


def _read_stored_login() -> str | None:
    """Read the stored login entry, exiting 1 when the OS keyring cannot be read."""
    try:
        require_persistent_keyring()
        return keyring_read(CONST_VAULT_LOGIN_KEYRING_KEY)
    except SecretStorageError as exc:
        print_error(f"Cannot read the stored Vault token: {exc}", safe=True)
        raise typer.Exit(1) from exc


def _parse_stored_login(raw_record: str) -> VaultStoredLogin | None:
    """Parse the stored login record; None when the entry is not one, such as a bare token."""
    from pydantic import ValidationError

    try:
        return VaultStoredLogin.model_validate_json(raw_record)
    except ValidationError:
        return None


def _revoke_stored_login(login: VaultStoredLogin | None) -> str | None:
    """Revoke the stored token at its own Vault, returning why that did not happen, if it did not.

    An entry that is not a login record names no Vault, so its token is not sent anywhere.
    """
    if login is None:
        return "the entry is not a `devops vault login` record, so it names no Vault to revoke at"
    try:
        revoke_self(login.vault_addr, login.token, login.namespace)
    except VaultError as exc:
        return exc.message
    return None


def _delete_stored_login() -> None:
    """Delete the stored login entry, exiting 1 when the OS keyring refuses."""
    try:
        keyring_delete(CONST_VAULT_LOGIN_KEYRING_KEY)
    except SecretStorageError as exc:
        print_error(f"Cannot delete the stored Vault token: {exc}", safe=True)
        raise typer.Exit(1) from exc


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
    """Inspect, renew, or revoke tracked Vault dynamic secret leases.

    Every mode needs a usable token and fails before any request without one.
    """
    broker = VaultSecretBroker()
    if is_dry_run():
        render_dry_run_result(
            command="devops vault leases",
            action="vault_lease_lifecycle",
            details={
                "renew": renew,
                "revoke": revoke,
                "vault_addr": broker.vault_addr,
                "token_source": broker.token_source.source,
            },
        )
        return

    with exit_on_error(VaultError):
        registry = get_lease_registry(
            LeaseRegistry(
                vault_addr=broker.vault_addr,
                token=broker.require_token(),
                namespace=broker.vault_namespace,
            )
        )
        if revoke:
            _revoke_lease(registry, revoke, broker)
            return
        if renew:
            _renew_leases(registry)
            return
    _list_leases(registry)


def _revoke_lease(registry: LeaseRegistry, lease_id: str, broker: VaultSecretBroker) -> None:
    """Revoke one lease, raising with the status Vault answered when it refuses."""
    masked = mask_secrets(lease_id)
    try:
        registry.revoke(lease_id)
    except VaultLeaseError as exc:
        status = exc.status_code
        if status is not None and status in CONST_VAULT_TOKEN_REJECTED_STATUSES:
            raise broker.status_error(status, CONST_VAULT_PATH_LEASE_REVOKE) from exc
        raise VaultLeaseError(
            f"Could not revoke lease '{masked}': {exc.message}",
            vault_addr=broker.vault_addr,
            status_code=status,
        ) from exc
    print_success(f"✓ Revoked lease '{masked}'.")


def _renew_leases(registry: LeaseRegistry) -> None:
    """Renew the tracked leases close to expiry; exit 1 when any renewal failed."""
    report = registry.renew_expiring()
    print_success(
        f"✓ Renewed {len(report.renewed)} lease(s); "
        f"{len(report.failed)} failed, {len(report.skipped)} still within lifetime."
    )
    if report.failed:
        raise typer.Exit(1)


def _list_leases(registry: LeaseRegistry) -> None:
    """Print the leases tracked in this session."""
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
        columns=[("Credential", "cyan"), "Provider", "Resolved", "Timestamp"],
        rows=[
            [
                entry.credential_id,
                entry.provider or "—",
                "yes" if entry.resolved else "no",
                entry.timestamp,
            ]
            for entry in entries
        ],
    )
