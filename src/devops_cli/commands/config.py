"""Config command group: show, get, set, unset, init."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Annotated, Any, BinaryIO

import httpx2
import typer
from pydantic import TypeAdapter

from devops_cli.config.constants import (
    CONST_GH_CLI,
    CONST_OUTPUT_FORMAT_TABLE,
    CONST_SECRET_FILE_MAX_BYTES,
)
from devops_cli.config.defaults import (
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    DEFAULT_TABLE_FORMAT,
)
from devops_cli.config.env import (
    EnvVarSpec,
    credential,
    env_var_for_option,
    get_all_env_var_specs,
    keyring_names,
    secret_keys,
    setting_variables,
)
from devops_cli.config.os_keyring import (
    SecretStorageError,
    backend_info,
    has_keyring_secret,
    remember_secret,
)
from devops_cli.config.settings import (
    _SECRET_FIELDS,
    _YAML_LOAD_ERRORS,
    Settings,
    _yaml_error_location,
    config_layer_paths,
    dotted_get,
    dotted_set,
    get_active_config_path,
    is_config_key,
    load_settings,
    remove_config_key,
    save_settings,
    similar_config_keys,
)
from devops_cli.core.binaries import check_binary
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run
from devops_cli.dry_run.decorator import dry_run_class
from devops_cli.dry_run.requests import PlannedRequest, render_request_plan
from devops_cli.http.egress import EgressLevel, vet_addresses
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
)
from devops_cli.output.serialization import emit_serialized, resolve_format

logger = logging.getLogger(__name__)

# Turns a settings value, such as a path or a list of them, into its JSON form for `config show`.
_JSON_VALUE: TypeAdapter[Any] = TypeAdapter(Any)

app = new_typer(help=HELP.config.app, no_args_is_help=True)


# =============================================================================
# Secret Storage & Auth Helpers
# =============================================================================


def _render_secret_store_error(key: str, exc: SecretStorageError) -> None:
    from devops_cli.security.sanitizer import mask_secrets

    env_var = env_var_for_option(key)
    masked_err = mask_secrets(str(exc))
    print_warning(f"Could not store secret for {key}: {masked_err}", prefix=False)
    if env_var:
        print_warning(f"Use environment variable fallback: export {env_var}=<value>", prefix=False)


def _unknown_key(key: str) -> typer.Exit:
    """Print that the settings do not know `key`, and the known keys with a similar name.

    Return the exit 1 that the command raises.
    """
    print_error(MESSAGES.config.unknown_key.format(key=key), prefix=False, safe=True)
    similar = similar_config_keys(key)
    if similar:
        keys = ", ".join(similar)
        print_info(MESSAGES.config.similar_keys.format(keys=keys), prefix=False, safe=True)
    return typer.Exit(1)


def _gh_auth_status() -> bool:
    from devops_cli.github.rate_limiter import run_gh

    try:
        result = run_gh(
            ["auth", "status"],
            quiet=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except OSError, subprocess.SubprocessError:
        return False
    return result.returncode == 0


# =============================================================================
# Command: devops config show
# =============================================================================


@app.command()
@dry_run_class("no-external-request")
def show(
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", "-j", help=HELP.options.json_output),
    ] = False,
) -> None:
    """Print every setting that a variable sets and every credential. A credential shows as set or not set, never its value."""
    settings = load_settings()
    values = [
        (key, _shown_value(settings, key))
        for key in sorted(setting_variables().keys() | secret_keys())
    ]
    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized([{"key": key, "value": value} for key, value in values], resolved)
        return

    not_set_str = f"[dim]{MESSAGES.config.not_set}[/dim]"
    rows: list[list[str]] = []
    for key, value in values:
        if value is None or value == []:
            display = not_set_str
        elif key in _SECRET_FIELDS:
            display = "[green]set (****)[/green]"
        elif isinstance(value, list):
            display = ", ".join(str(v) for v in value)
        else:
            display = str(value)
        rows.append([key, display])

    print_table(
        title=MESSAGES.config.header,
        columns=[(MESSAGES.config.key_col, "bold cyan"), MESSAGES.config.val_col],
        rows=rows,
    )
    print_info(f"\nConfig file: [dim]{get_active_config_path()}[/dim]", prefix=False)
    # The pricing registry logs a warning for each reference model it cannot price. It is not a
    # load error, so a registry update cannot break config loading (#1672).
    from devops_cli.ai.spend.ledger import resolve_reference_pricing

    resolve_reference_pricing()


# =============================================================================
# Command: devops config get
# =============================================================================


@app.command("get")
@dry_run_class("no-external-request")
def get_value(
    key: Annotated[str, typer.Argument(help=HELP.config.key)],
) -> None:
    """Print a single configuration value."""
    if key in _SECRET_FIELDS:
        print_warning(
            "Secret keys cannot be retrieved with 'get'. Use 'config show'.", prefix=False
        )
        raise typer.Exit(1)
    settings = load_settings()
    try:
        value = dotted_get(settings, key)
        print_info(str(value) if value is not None else "[dim](not set)[/dim]", prefix=False)
    except AttributeError as exc:
        raise _unknown_key(key) from exc


# =============================================================================
# Command: devops config set
# =============================================================================


def _value_or_prompt(key: str, value: str | None) -> str:
    """The given value, or a credential typed at a hidden prompt, keeping it out of argv.

    A non-credential key without a value exits 2.
    """
    if value is not None:
        return value
    if key not in _SECRET_FIELDS:
        print_error(MESSAGES.config.value_required.format(key=key), prefix=False, safe=True)
        raise typer.Exit(2)
    return str(typer.prompt(MESSAGES.config.secret_prompt.format(key=key), hide_input=True))


def _from_file_error(message: str) -> typer.BadParameter:
    return typer.BadParameter(message, param_hint="'--from-file'")


def _read_to_end(source: BinaryIO, limit: int) -> bytes | None:
    """Every byte up to the end of `source`, or None once more than `limit` bytes arrive.

    The io contract lets one read of a terminal return less than it asks for before the end, so
    the loop reads until a read returns nothing.
    """
    data = bytearray()
    while chunk := source.read(limit + 1 - len(data)):
        data += chunk
        if len(data) > limit:
            return None
    return bytes(data)


def _secret_from_file(key: str, value: str | None, source: BinaryIO) -> str:
    """The credential a file or stdin holds, as its UTF-8 text, with no line added or removed.

    A key that is not a credential, a VALUE given as well, and an input that is empty, too
    large or not UTF-8 each exit 2 before anything is stored. No message quotes the input.
    """
    if key not in _SECRET_FIELDS:
        raise _from_file_error(MESSAGES.config.from_file_not_secret.format(key=key))
    if value is not None:
        raise _from_file_error(MESSAGES.config.from_file_and_value)
    raw = _read_to_end(source, CONST_SECRET_FILE_MAX_BYTES)
    if raw is None:
        limit = CONST_SECRET_FILE_MAX_BYTES
        raise _from_file_error(MESSAGES.config.from_file_oversize.format(limit=limit))
    try:
        secret = raw.decode("utf-8")
    except UnicodeDecodeError:
        # The decode error quotes the bytes it could not decode, and they are part of the secret.
        raise _from_file_error(MESSAGES.config.from_file_not_text) from None
    if not secret.strip():
        raise _from_file_error(MESSAGES.config.from_file_empty)
    return secret


@app.command("set")
@dry_run_class("no-external-request")
def set_value(
    key: Annotated[str, typer.Argument(help=HELP.config.key)],
    value: Annotated[str | None, typer.Argument(help=HELP.config.value)] = None,
    from_file: Annotated[
        typer.FileBinaryRead | None,
        typer.Option("--from-file", metavar="PATH", help=HELP.config.from_file),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Set a configuration value. Credentials go to the OS keyring; omit VALUE to type one hidden.

    A multi-line credential, such as a PEM private key, comes from a file or stdin:
    `devops config set <key> --from-file key.pem`, or `--from-file -` to read stdin.
    """
    # An unknown key exits before the prompt, the read of the file and the load of the settings.
    if not is_config_key(key):
        raise _unknown_key(key)
    value = (
        _value_or_prompt(key, value)
        if from_file is None
        else _secret_from_file(key, value, from_file)
    )
    if dry_run or is_dry_run():
        if key in _SECRET_FIELDS:
            print_info(f"Would store secret '{key}' in keyring.", prefix=False)
        else:
            print_info(f"Would set {key} = {value}", prefix=False)
        return
    settings = load_settings()
    try:
        dotted_set(settings, key, value)
        # A credential goes to the keyring, so the config file gets no key for it.
        save_settings(settings, keys=() if key in _SECRET_FIELDS else (key,))
        if key in _SECRET_FIELDS:
            print_success(f"Secret '{key}' stored in keyring.", prefix=False)
        else:
            print_success(f"{key} = {value}", prefix=False)
    except SecretStorageError as exc:
        _render_secret_store_error(key, exc)
        raise typer.Exit(1) from exc
    except (AttributeError, ValueError) as exc:
        print_error(f"Failed to set {key!r}: {exc}", prefix=False)
        raise typer.Exit(1) from exc


# =============================================================================
# Command: devops config unset
# =============================================================================


@app.command("unset")
@dry_run_class("no-external-request")
def unset_value(
    key: Annotated[str, typer.Argument(help=HELP.config.key)],
) -> None:
    """Remove a key from the config file, also a key that stops the settings from loading.

    The command edits the active config file and loads no settings. To edit another file, set
    `DEVOPS_CLI_CONFIG` to its path for the command. It keeps the other lines and comments, and
    it copies the file to `<name>.bak-<YYYYMMDD-HHMMSS>` before the change. In that copy, and in
    each older copy, a credential that the command removes shows as `***REDACTED***`, so no copy
    holds its value. A key that the file does not hold exits 1. A credential in the OS keyring
    stays. Store a credential before you remove it, with `devops config set <key>`, or with
    `--from-file <path>` for a multi-line one.
    """
    removal = remove_config_key(key, dry_run=False)
    print_success(
        MESSAGES.config.unset_success.format(key=removal.key, path=removal.path, line=removal.line),
        prefix=False,
        safe=True,
    )
    print_info(MESSAGES.config.unset_backup.format(backup=removal.backup), prefix=False, safe=True)


# =============================================================================
# Command: devops config init
# =============================================================================


def _validate_wizard_service_url(url: str, purpose: str, *, allow_private: bool) -> None:
    """Validate a typed service URL in the config init wizard.

    Time-of-check gap: this check runs against a typed URL and dials nothing.
    vet_addresses verifies the host at check time; later real connections verify at connect.
    """
    clean_url = str(url).strip()
    try:
        parsed = httpx2.URL(clean_url)
    except Exception as exc:
        raise ValueError(f"Invalid {purpose} URL: {exc}") from exc

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid {purpose} URL scheme '{parsed.scheme}': must be http or https")
    if not parsed.host:
        raise ValueError(f"{purpose} URL missing valid hostname")

    port = parsed.origin.port or 80
    level = EgressLevel.PRIVATE if allow_private else EgressLevel.LOOPBACK
    try:
        vet_addresses(parsed.host, port, level)
    except Exception as exc:
        raise ValueError(f"{purpose} URL egress check failed: {exc}") from exc


@app.command()
@dry_run_class("request-plan")
def init(  # noqa: C901
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Interactive first-time setup wizard."""
    if dry_run or is_dry_run():
        plans = [
            PlannedRequest(
                method="gh",
                target="auth status",
                argv=("gh", "auth", "status"),
            ),
        ]
        if json_output:
            emit_serialized(
                {"dry_run": True, "requests": [r.__dict__ for r in plans]},
                "json",
            )
            return
        render_request_plan("devops config init", plans)
        return
    settings = load_settings()
    print_info("[bold]devops-cli setup wizard[/bold]\n", prefix=False)

    # ── GitHub ─────────────────────────────────────────────────────────────
    print_info("[cyan]GitHub[/cyan]", prefix=False)
    if not check_binary(CONST_GH_CLI):
        print_warning(
            "GitHub CLI (gh) not found. devops-cli acts on GitHub as gh's login: "
            "install gh, then run 'gh auth login'.",
            prefix=False,
        )
    elif _gh_auth_status():
        print_success("Using GitHub CLI authentication via 'gh auth token'.")
    elif typer.confirm("Authenticate with GitHub CLI now using 'gh auth login'?", default=True):
        from devops_cli.github.rate_limiter import run_gh

        run_gh(
            ["auth", "login"],
            check=False,
            capture_output=False,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS * 4,
        )
    else:
        print_warning(
            "No GitHub CLI session found. You can run 'gh auth login' later.", prefix=False
        )

    default_org = typer.prompt("Default org (leave blank to skip)", default="")
    if default_org:
        settings.github.default_org = default_org

    # ── Repositories ───────────────────────────────────────────────────────
    print_info("\n[cyan]Repositories[/cyan]", prefix=False)
    base_dir = typer.prompt("Repos base directory", default=str(settings.repos.base_dir))
    settings.repos.base_dir = Path(base_dir)

    # ── Grafana ────────────────────────────────────────────────────────────
    print_info("\n[cyan]Grafana[/cyan]", prefix=False)
    grafana_url = typer.prompt("Grafana URL (leave blank to skip)", default="")
    if grafana_url:
        try:
            _validate_wizard_service_url(
                grafana_url, "Grafana", allow_private=settings.ai.allow_private_network
            )
            settings.grafana.url = grafana_url
        except ValueError as exc:
            print_error(f"{exc}", prefix=False)
        g_token = typer.prompt("Grafana API token", hide_input=True, default="")
        if g_token:
            try:
                dotted_set(settings, "grafana.token", g_token)
            except SecretStorageError as exc:
                _render_secret_store_error("grafana.token", exc)

    # ── Prometheus ─────────────────────────────────────────────────────────
    print_info("\n[cyan]Prometheus[/cyan]", prefix=False)
    prom_url = typer.prompt("Prometheus URL (leave blank to skip)", default="")
    if prom_url:
        try:
            _validate_wizard_service_url(
                prom_url, "Prometheus", allow_private=settings.ai.allow_private_network
            )
            settings.prometheus.url = prom_url
        except ValueError as exc:
            print_error(f"{exc}", prefix=False)

    # ── ArgoCD ─────────────────────────────────────────────────────────────
    print_info("\n[cyan]ArgoCD[/cyan]", prefix=False)
    argocd_url = typer.prompt("ArgoCD URL (leave blank to skip)", default="")
    if argocd_url:
        try:
            _validate_wizard_service_url(
                argocd_url, "ArgoCD", allow_private=settings.ai.allow_private_network
            )
            settings.argocd.url = argocd_url
        except ValueError as exc:
            print_error(f"{exc}", prefix=False)
        a_token = typer.prompt("ArgoCD API token", hide_input=True, default="")
        if a_token:
            try:
                dotted_set(settings, "argocd.token", a_token)
            except SecretStorageError as exc:
                _render_secret_store_error("argocd.token", exc)

    # The write and the message use one resolved path, so the message names the written file.
    config_path = get_active_config_path()
    save_settings(settings, config_path)
    print_success("Configuration saved!")
    print_info(f"Config file: [dim]{config_path}[/dim]", prefix=False)


# =============================================================================
def _shown_value(settings: Settings, key: str) -> Any:
    """The value `config show` prints for `key`: `****` for a credential that has one."""
    if key in _SECRET_FIELDS:
        return "****" if _is_secret_configured(key) else None
    return _JSON_VALUE.dump_python(dotted_get(settings, key), mode="json")


def _is_secret_configured(key: str) -> bool:
    """Check whether a secret key is configured without retrieving the secret value."""
    entry = credential(key)
    if has_keyring_secret(entry.keyring_name):
        return True
    return any(os.environ.get(variable) for variable in entry.env_vars)


def _resolve_env_spec_value(spec: EnvVarSpec, settings: Settings) -> tuple[object, bool]:
    """Return (value, is_from_env) for an environment variable specification."""
    if spec.is_secret:
        is_env = bool(os.environ.get(spec.env_var))
        is_set = bool(is_env or (spec.option_key and _is_secret_configured(spec.option_key)))
        return ("****" if is_set else None), is_env

    env_val = os.environ.get(spec.env_var)
    if env_val is not None:
        return env_val, True

    if spec.option_key is None:
        return None, False

    try:
        val: object = dotted_get(settings, spec.option_key)
        return val, False
    except AttributeError:
        return None, False


# =============================================================================
# Command: devops config output / env
# =============================================================================


@app.command("output")
@app.command("env")
@app.command("env-vars")
@dry_run_class("no-external-request")
def output_env_vars(  # noqa: C901
    export: Annotated[
        bool,
        typer.Option(
            "--export",
            "-e",
            help=HELP.config.export_env,
        ),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help=HELP.options.format_type,
        ),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help=HELP.config.json_env,
        ),
    ] = False,
) -> None:
    """Output environment variables available for devops-cli configuration."""
    settings = load_settings()
    specs = get_all_env_var_specs()

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        data = []
        for spec in specs:
            val, is_from_env = _resolve_env_spec_value(spec, settings)
            display_val = (
                "****" if (spec.is_secret and val) else (str(val) if val is not None else None)
            )
            data.append(
                {
                    "env_var": spec.env_var,
                    "option_key": spec.option_key,
                    "value": display_val,
                    "is_secret": spec.is_secret,
                    "from_env": is_from_env,
                    "description": spec.description,
                }
            )
        emit_serialized(data, resolved)
        return

    if export:
        import shlex

        print_info("# devops-cli environment variables export", prefix=False)
        for spec in specs:
            val, _ = _resolve_env_spec_value(spec, settings)
            if spec.is_secret:
                print_info(
                    f'# export {spec.env_var}="****"  # secret (stored in OS keyring)', prefix=False
                )
            elif val is not None:
                quoted = shlex.quote(str(val))
                print_info(f"export {spec.env_var}={quoted}", prefix=False)
            else:
                print_info(f'# export {spec.env_var}=""  # {spec.description}', prefix=False)
        return

    rows: list[list[str]] = []
    for spec in specs:
        val, is_from_env = _resolve_env_spec_value(spec, settings)
        key_display = spec.option_key or "[dim](config file)[/dim]"
        if spec.is_secret:
            val_display = "[green]set (****)[/green]" if val else "[dim]not set[/dim]"
        elif is_from_env:
            val_display = f"[bold yellow]{val}[/bold yellow] [cyan](via env)[/cyan]"
        elif val is not None:
            val_display = str(val)
        else:
            val_display = "[dim]not set[/dim]"

        rows.append([spec.env_var, key_display, val_display, spec.description])

    print_table(
        title="devops-cli environment variables",
        columns=[
            ("Environment Variable", "bold cyan"),
            ("Config Key", "dim"),
            "Current Value",
            "Description",
        ],
        rows=rows,
    )


# =============================================================================
# Command: devops config auth-headless
# =============================================================================


@app.command("auth-headless")
@dry_run_class("no-external-request")
def auth_headless(
    key: Annotated[str, typer.Argument(help=HELP.config.secret_key)],
    token: Annotated[str, typer.Argument(help=HELP.config.secret_token)],
) -> None:
    """Load secret tokens into ephemeral memory for headless CI environments lacking DBus."""
    names = keyring_names()
    if key not in names:
        print_error(
            f"Invalid secret key '{key}'. Must be one of: {list(names)}",
            prefix=False,
        )
        raise typer.Exit(1)

    keyring_field = names[key]
    remember_secret(keyring_field, token)
    print_success(f"Ephemeral secret loaded into memory: {key}")


# =============================================================================
# Command: devops config audit-stream
# =============================================================================


@app.command("audit-stream")
@dry_run_class("no-external-request")
def audit_stream(
    destination: Annotated[str, typer.Argument(help=HELP.config.destination)],
) -> None:
    """Stream stored audit records to SIEM destination URL."""
    from devops_cli.core.audit import stream_audit_records

    count = stream_audit_records(destination_url=destination)
    print_success(f"Streamed {count} audit record(s) → [bold]{destination}[/bold]")


# =============================================================================
# Command: devops config audit-keys
# =============================================================================

# The audit refuses the errors that the settings load refuses (#1468), and an error that stops the
# read of the file.
_AUDIT_READ_ERRORS: tuple[type[Exception], ...] = (*_YAML_LOAD_ERRORS, OSError)


def _scan_yaml_for_secret_keys(cfg_file: Path) -> list[str] | None:
    """Return each secret-named key that holds a value in ``cfg_file``, as ``<path>:<section>.<key>``,
    or None if the file is unreadable.

    A leak names the full path: the global config file and a project config file can both have the
    name ``config.yaml`` (#2426).
    """
    import yaml

    from devops_cli.security.sanitizer import is_secret_field

    secret_options = secret_keys()
    try:
        raw_cfg = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
    except _AUDIT_READ_ERRORS as err:
        # The message of the error and the mark of a YAML error quote the file's content, which
        # may hold the value.
        where = _yaml_error_location(err)
        logger.warning("Could not audit config file %s: %s%s", cfg_file, type(err).__name__, where)
        return None
    if not isinstance(raw_cfg, dict):
        return []
    leaks: list[str] = []
    for section_name, section_dict in raw_cfg.items():
        if not isinstance(section_dict, dict):
            continue
        for opt_name, value in section_dict.items():
            composite = f"{section_name}.{opt_name}"
            # A secret-named key that is no longer an option is still a plaintext secret.
            if value and is_secret_field(str(opt_name), composite, secret_options):
                leaks.append(f"{cfg_file}:{composite}")
    return leaks


def _detect_keyring_secret_leaks(scanned_files: list[Path]) -> tuple[list[str], list[Path]]:
    """Find plaintext secret values saved in YAML configs instead of OS Keyring.

    Returns the leaks and the files that could not be read or parsed, which are unaudited.
    """
    unique_files = sorted(list({p.resolve() for p in scanned_files if p.exists()}))
    leaks: list[str] = []
    unaudited: list[Path] = []
    for cfg_file in unique_files:
        file_leaks = _scan_yaml_for_secret_keys(cfg_file)
        if file_leaks is None:
            unaudited.append(cfg_file)
        else:
            leaks.extend(file_leaks)
    return leaks, unaudited


@app.command("audit-keys")
@dry_run_class("no-external-request")
def audit_keys_cmd(
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool,
        typer.Option("--json", help=HELP.options.json_output),
    ] = False,
) -> None:
    """Audit OS Keyring token health, backend status, and zero-plaintext secret compliance. The audit scans each config file that the settings merge: the global config file and the project config file. It also scans config.yaml and .devops/config.yaml in the current directory. Exits 0 only when the audit is compliant. Exits 1 when a config file holds a plaintext secret, or when a config file cannot be read or parsed, reporting it unaudited. The full report prints before the exit. The alert of a leak names two commands. `devops config set <key>` stores a credential in the keyring. Add `--from-file <path>` for a multi-line credential, such as a PEM key. `DEVOPS_CLI_CONFIG=<file> devops config unset <key>` removes the value from the file of the leak."""
    backend = backend_info()
    backend_name = backend.name
    backend_priority = backend.priority

    scanned_files = [
        *(path for path in config_layer_paths() if path is not None),
        Path.cwd() / "config.yaml",
        Path.cwd() / ".devops" / "config.yaml",
    ]
    unique_files = sorted(list({p.resolve() for p in scanned_files if p.exists()}))
    plaintext_leaks, unaudited_files = _detect_keyring_secret_leaks(scanned_files)

    rows: list[list[str]] = []
    key_audit_records: list[dict[str, Any]] = []

    for option_key, keyring_name in keyring_names().items():
        has_keyring = has_keyring_secret(keyring_name)

        env_var = env_var_for_option(option_key)
        has_env = bool(os.environ.get(env_var)) if env_var else False

        is_leaked = any(option_key in leak for leak in plaintext_leaks)
        effective = "CONFIGURED" if (has_keyring or has_env) else "UNSET"

        keyring_state = "[green]STORED[/green]" if has_keyring else "[dim]EMPTY[/dim]"
        env_state = f"[cyan]OVERRIDE ({env_var})[/cyan]" if has_env else "[dim]NONE[/dim]"
        if is_leaked:
            leak_state = "[red]LEAK DETECTED[/red]"
            comp_state = "[red]NON-COMPLIANT[/red]"
        elif unaudited_files:
            leak_state = comp_state = "[yellow]UNAUDITED[/yellow]"
        else:
            leak_state = "[green]CLEAN (0 Plaintext)[/green]"
            comp_state = (
                "[green]COMPLIANT[/green]"
                if effective == "CONFIGURED"
                else "[yellow]UNSET[/yellow]"
            )

        rows.append(
            [
                f"[bold]{option_key}[/bold]",
                keyring_state,
                env_state,
                f"[bold]{effective}[/bold]",
                leak_state,
                comp_state,
            ]
        )

        key_audit_records.append(
            {
                "key": option_key,
                "keyring_name": keyring_name,
                "has_keyring": has_keyring,
                "env_var": env_var,
                "has_env": has_env,
                "effective_status": effective,
                "plaintext_leak": is_leaked,
                "compliant": not is_leaked and not unaudited_files,
            }
        )

    is_overall_compliant = not plaintext_leaks and not unaudited_files

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        report = {
            "keyring_backend": backend_name,
            "backend_priority": backend_priority,
            "scanned_config_files": [str(p) for p in unique_files],
            "plaintext_leak_count": len(plaintext_leaks),
            "has_plaintext_leaks": len(plaintext_leaks) > 0,
            "plaintext_leaks": plaintext_leaks,
            "unaudited_config_files": [str(p) for p in unaudited_files],
            "is_compliant": is_overall_compliant,
            "keys": key_audit_records,
        }
        emit_serialized(report, resolved)
        if not is_overall_compliant:
            raise typer.Exit(1)
        return

    print_info(
        f"[bold]Keyring & Secret Health Audit[/bold] "
        f"(Backend: [cyan]{backend_name}[/cyan], Priority: {backend_priority})",
        prefix=False,
    )
    print_table(
        columns=[
            "Secret Key",
            "OS Keyring State",
            "Environment Variable",
            "Resolution",
            "Zero-Plaintext Check",
            "Compliance",
        ],
        rows=rows,
        border_style="cyan",
    )

    if plaintext_leaks:
        print_error(
            MESSAGES.config.plaintext_alert.format(leaks=plaintext_leaks),
            prefix=False,
            safe=True,
        )
    if unaudited_files:
        print_error(
            f"Unaudited: could not read or parse {', '.join(str(p) for p in unaudited_files)}; "
            "fix the file and re-run 'devops config audit-keys'.",
            prefix=False,
            safe=True,
        )
    if not is_overall_compliant:
        raise typer.Exit(1)
    print_success(
        "Zero-Trust Secret Isolation: All configuration files verified free of plaintext secrets.",
    )
