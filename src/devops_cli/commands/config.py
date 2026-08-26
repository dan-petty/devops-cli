"""Config command group: show, get, set, init."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config import options as opt
from devops_cli.config.constants import CONST_CONFIG_PATH
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.config.env import EnvVarSpec, env_var_for_option, get_all_env_var_specs
from devops_cli.config.settings import (
    _SECRET_FIELDS,
    SecretStorageError,
    Settings,
    dotted_get,
    dotted_set,
    get_active_config_path,
    get_ai_api_key,
    get_argocd_token,
    get_github_token,
    get_grafana_token,
    load_settings,
    save_settings,
)
from devops_cli.core.process import run_subprocess
from devops_cli.http.validation import validate_service_url
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import (
    format_json,
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    write_stdout,
)

app = typer.Typer(help=HELP.config.app, no_args_is_help=True)


# =============================================================================
# Secret Storage & Auth Helpers
# =============================================================================


def _render_secret_store_error(key: str, exc: SecretStorageError) -> None:
    from devops_cli.ai.review.sanitization import _mask_secrets_in_content

    env_var = env_var_for_option(key)
    masked_err = _mask_secrets_in_content(str(exc))
    print_warning(f"Could not store secret for {key}: {masked_err}", prefix=False)
    if env_var:
        print_warning(f"Use environment variable fallback: export {env_var}=<value>", prefix=False)


def _gh_auth_status() -> bool:
    from devops_cli.core.process import run_subprocess

    try:
        result = run_subprocess(
            ["gh", "auth", "status"],
            quiet=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except OSError, subprocess.SubprocessError:
        return False
    return result.returncode == 0


def _gh_auth_token() -> str | None:
    from devops_cli.core.process import run_subprocess

    try:
        result = run_subprocess(
            ["gh", "auth", "token"],
            quiet=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except OSError, subprocess.SubprocessError:
        return None

    if result.returncode != 0:
        return None
    token = result.stdout.strip()
    return token or None


# =============================================================================
# Command: devops config show
# =============================================================================


@app.command()
def show() -> None:
    """Print all configuration values, masking secrets."""
    settings = load_settings()

    rows: list[list[str]] = []

    def _row(key: str, value: object, secret: bool = False) -> None:
        not_set_str = f"[dim]{MESSAGES.config.not_set}[/dim]"
        if secret:
            display = "[green]set (****)[/green]" if value else not_set_str
        elif isinstance(value, list):
            display = ", ".join(str(v) for v in value) if value else not_set_str
        else:
            display = str(value) if value is not None else not_set_str
        rows.append([key, display])

    _row(opt.GITHUB_TOKEN, get_github_token(settings), secret=True)
    _row(opt.GITHUB_DEFAULT_ORG, settings.github.default_org)
    _row(opt.SSH_KEY_DIR, settings.ssh.key_dir)
    _row(opt.SSH_ROTATION_DAYS, settings.ssh.rotation_days)
    _row(opt.REPOS_BASE_DIR, settings.repos.base_dir)
    _row(opt.WORKSPACE_FILE, settings.workspace.file)
    _row(opt.GRAFANA_URL, settings.grafana.url)
    _row(opt.GRAFANA_TOKEN, get_grafana_token(settings), secret=True)
    _row(opt.PROMETHEUS_URL, settings.prometheus.url)
    _row(opt.ARGOCD_URL, settings.argocd.url)
    _row(opt.ARGOCD_TOKEN, get_argocd_token(settings), secret=True)
    _row(opt.AI_PROVIDER, settings.ai.provider)
    _row(opt.AI_MODEL, settings.ai.model)
    _row(opt.AI_OLLAMA_URLS, settings.ai.ollama_urls)
    _row(opt.AI_API_BASE_URL, settings.ai.api_base_url)
    _row(opt.AI_ALLOW_PRIVATE_NETWORK, settings.ai.allow_private_network)
    _row(opt.AI_API_KEY, get_ai_api_key(settings), secret=True)

    print_table(
        title=MESSAGES.config.header,
        columns=[(MESSAGES.config.key_col, "bold cyan"), MESSAGES.config.val_col],
        rows=rows,
    )
    print_info(f"\nConfig file: [dim]{get_active_config_path()}[/dim]", prefix=False)


# =============================================================================
# Command: devops config get
# =============================================================================


@app.command("get")
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
    except AttributeError:
        print_error(f"Unknown config key: {key!r}", prefix=False)
        raise typer.Exit(1)


# =============================================================================
# Command: devops config set
# =============================================================================


@app.command("set")
def set_value(
    key: Annotated[str, typer.Argument(help=HELP.config.key)],
    value: Annotated[str, typer.Argument(help=HELP.config.value)],
) -> None:
    """Set a configuration value. Tokens are stored in the OS keyring."""
    settings = load_settings()
    try:
        dotted_set(settings, key, value)
        save_settings(settings)
        if key in _SECRET_FIELDS:
            print_success(f"Secret '{key}' stored in keyring.", prefix=False)
        else:
            print_success(f"{key} = {value}", prefix=False)
    except SecretStorageError as exc:
        _render_secret_store_error(key, exc)
        raise typer.Exit(1)
    except (AttributeError, ValueError) as exc:
        print_error(f"Failed to set {key!r}: {exc}", prefix=False)
        raise typer.Exit(1)


# =============================================================================
# Command: devops config init
# =============================================================================


@app.command()
def init() -> None:
    """Interactive first-time setup wizard."""
    settings = load_settings()
    print_info("[bold]devops-cli setup wizard[/bold]\n", prefix=False)

    # ── GitHub ─────────────────────────────────────────────────────────────
    print_info("[cyan]GitHub[/cyan]", prefix=False)
    gh_path = shutil.which("gh")
    if gh_path:
        if not _gh_auth_status() and typer.confirm(
            "Authenticate with GitHub CLI now using 'gh auth login'?", default=True
        ):
            run_subprocess(
                ["gh", "auth", "login"],
                check=False,
                capture_output=False,
                timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS * 4,
            )

        gh_token = _gh_auth_token()
        if gh_token and typer.confirm("Import GitHub CLI token into devops keyring?", default=True):
            try:
                dotted_set(settings, opt.GITHUB_TOKEN, gh_token)
                print_success("GitHub token stored in keyring.")
            except SecretStorageError as exc:
                _render_secret_store_error(opt.GITHUB_TOKEN, exc)
        elif gh_token:
            print_success("Using GitHub CLI authentication via 'gh auth token'.")
        else:
            print_warning(
                "No GitHub CLI session found. You can run 'gh auth login' later.", prefix=False
            )
    else:
        token = typer.prompt("Personal Access Token (PAT)", hide_input=True, default="")
        if token:
            try:
                dotted_set(settings, opt.GITHUB_TOKEN, token)
                print_success("GitHub token stored in keyring.")
            except SecretStorageError as exc:
                _render_secret_store_error(opt.GITHUB_TOKEN, exc)

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
            validate_service_url(grafana_url, "Grafana", allow=settings.ai.allow_private_network)
            settings.grafana.url = grafana_url
        except ValueError as exc:
            print_error(f"{exc}", prefix=False)
        g_token = typer.prompt("Grafana API token", hide_input=True, default="")
        if g_token:
            try:
                dotted_set(settings, opt.GRAFANA_TOKEN, g_token)
            except SecretStorageError as exc:
                _render_secret_store_error(opt.GRAFANA_TOKEN, exc)

    # ── Prometheus ─────────────────────────────────────────────────────────
    print_info("\n[cyan]Prometheus[/cyan]", prefix=False)
    prom_url = typer.prompt("Prometheus URL (leave blank to skip)", default="")
    if prom_url:
        try:
            validate_service_url(prom_url, "Prometheus", allow=settings.ai.allow_private_network)
            settings.prometheus.url = prom_url
        except ValueError as exc:
            print_error(f"{exc}", prefix=False)

    # ── ArgoCD ─────────────────────────────────────────────────────────────
    print_info("\n[cyan]ArgoCD[/cyan]", prefix=False)
    argocd_url = typer.prompt("ArgoCD URL (leave blank to skip)", default="")
    if argocd_url:
        try:
            validate_service_url(argocd_url, "ArgoCD", allow=settings.ai.allow_private_network)
            settings.argocd.url = argocd_url
        except ValueError as exc:
            print_error(f"{exc}", prefix=False)
        a_token = typer.prompt("ArgoCD API token", hide_input=True, default="")
        if a_token:
            try:
                dotted_set(settings, opt.ARGOCD_TOKEN, a_token)
            except SecretStorageError as exc:
                _render_secret_store_error(opt.ARGOCD_TOKEN, exc)

    save_settings(settings)
    print_success("Configuration saved!")
    print_info(f"Config file: [dim]{CONST_CONFIG_PATH}[/dim]", prefix=False)


# =============================================================================
# Environment Variable Specification Helpers
# =============================================================================


def _resolve_env_spec_value(spec: EnvVarSpec, settings: Settings) -> tuple[object, bool]:
    """Return (value, is_from_env) for an environment variable specification."""
    env_val = os.environ.get(spec.env_var)
    if env_val is not None:
        return env_val, True

    if spec.option_key is None:
        return None, False

    if spec.is_secret:
        if spec.option_key == opt.GITHUB_TOKEN:
            return get_github_token(settings), False
        if spec.option_key == opt.GRAFANA_TOKEN:
            return get_grafana_token(settings), False
        if spec.option_key == opt.ARGOCD_TOKEN:
            return get_argocd_token(settings), False
        if spec.option_key == opt.AI_API_KEY:
            return get_ai_api_key(settings), False
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
def output_env_vars(
    export: Annotated[
        bool,
        typer.Option(
            "--export",
            "-e",
            help=HELP.config.export_env,
        ),
    ] = False,
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

    if json_output:
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
        write_stdout(format_json(data) + "\n")
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


# NOTE (Design Justification - v0.1.1 Prep): auth_headless provides the command stub
# for loading session tokens into ephemeral memory for headless Linux CI environments lacking DBus.
@app.command("auth-headless")
def auth_headless(
    key: Annotated[str, typer.Argument(help=HELP.config.secret_key)],
    token: Annotated[str, typer.Argument(help=HELP.config.secret_token)],
) -> None:
    """Load secret tokens into ephemeral memory for headless CI environments lacking DBus."""
    # TODO (v0.1.1 Feature): Implement memory-backed fallback secret storage for headless CI runners
    from devops_cli.config.options import KEYRING_KEYS
    from devops_cli.config.settings import _EPHEMERAL_CI_SECRETS

    if key not in KEYRING_KEYS:
        print_error(
            f"Invalid secret key '{key}'. Must be one of: {list(KEYRING_KEYS.keys())}",
            prefix=False,
        )
        raise typer.Exit(1)

    keyring_field = KEYRING_KEYS[key]
    _EPHEMERAL_CI_SECRETS[keyring_field] = token
    print_success(f"Ephemeral secret loaded into memory: {key}")


# =============================================================================
# Command: devops config audit-stream
# =============================================================================


@app.command("audit-stream")
def audit_stream(
    destination: Annotated[str, typer.Argument(help=HELP.config.destination)],
) -> None:
    """Stream stored audit records to SIEM destination URL."""
    from devops_cli.core.audit import stream_audit_records

    count = stream_audit_records(destination_url=destination)
    print_success(f"Streamed {count} audit record(s) → [bold]{destination}[/bold]")
