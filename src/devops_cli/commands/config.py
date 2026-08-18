"""Config command group: show, get, set, init."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.config import options as opt
from devops_cli.config.constants import CONST_CONFIG_PATH
from devops_cli.config.defaults import DEFAULT_GH_AUTH_TIMEOUT_SECONDS
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
from devops_cli.http.validation import validate_service_url

app = typer.Typer(help="Manage devops-cli configuration.", no_args_is_help=True)
console = Console()


def _render_secret_store_error(key: str, exc: SecretStorageError) -> None:
    from devops_cli.ai.review.sanitization import _mask_secrets_in_content

    env_var = env_var_for_option(key)
    masked_err = _mask_secrets_in_content(str(exc))
    rprint(f"[yellow]Could not store secret for {key}: {masked_err}[/yellow]")
    if env_var:
        rprint(f"[yellow]Use environment variable fallback: export {env_var}=<value>[/yellow]")


def _gh_auth_status() -> bool:
    from devops_cli.config.defaults import DEFAULT_GH_AUTH_TIMEOUT_SECONDS
    from devops_cli.core.process import run_subprocess

    try:
        result = run_subprocess(
            ["gh", "auth", "status"],
            quiet=True,
            timeout=DEFAULT_GH_AUTH_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _gh_auth_token() -> str | None:
    from devops_cli.config.defaults import DEFAULT_GH_AUTH_TIMEOUT_SECONDS
    from devops_cli.core.process import run_subprocess

    try:
        result = run_subprocess(
            ["gh", "auth", "token"],
            quiet=True,
            timeout=DEFAULT_GH_AUTH_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None
    token = result.stdout.strip()
    return token or None


@app.command()
def show() -> None:
    """Print all configuration values, masking secrets."""
    settings = load_settings()

    from devops_cli.lang import MESSAGES

    table = Table(title=MESSAGES.config.header, show_header=True, header_style="bold")
    table.add_column(MESSAGES.config.key_col, style="bold cyan", no_wrap=True)
    table.add_column(MESSAGES.config.val_col)

    def _row(key: str, value: object, secret: bool = False) -> None:
        not_set_str = f"[dim]{MESSAGES.config.not_set}[/dim]"
        if secret:
            display = "[green]set (****)[/green]" if value else not_set_str
        elif isinstance(value, list):
            display = ", ".join(str(v) for v in value) if value else not_set_str
        else:
            display = str(value) if value is not None else not_set_str
        table.add_row(key, display)

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

    console.print(table)
    console.print(f"\nConfig file: [dim]{get_active_config_path()}[/dim]")


@app.command("get")
def get_value(
    key: Annotated[str, typer.Argument(help="Dotted config key, e.g. github.default_org")],
) -> None:
    """Print a single configuration value."""
    if key in _SECRET_FIELDS:
        rprint("[yellow]Secret keys cannot be retrieved with 'get'. Use 'config show'.[/yellow]")
        raise typer.Exit(1)
    settings = load_settings()
    try:
        value = dotted_get(settings, key)
        rprint(str(value) if value is not None else "[dim](not set)[/dim]")
    except AttributeError:
        rprint(f"[red]Unknown config key: {key!r}[/red]")
        raise typer.Exit(1)


@app.command("set")
def set_value(
    key: Annotated[str, typer.Argument(help="Dotted config key, e.g. github.token")],
    value: Annotated[str, typer.Argument(help="Value to set")],
) -> None:
    """Set a configuration value. Tokens are stored in the OS keyring."""
    settings = load_settings()
    try:
        dotted_set(settings, key, value)
        save_settings(settings)
        if key in _SECRET_FIELDS:
            rprint(f"[green]Secret '{key}' stored in keyring.[/green]")
        else:
            rprint(f"[green]{key} = {value}[/green]")
    except SecretStorageError as exc:
        _render_secret_store_error(key, exc)
        raise typer.Exit(1)
    except (AttributeError, ValueError) as exc:
        rprint(f"[red]Failed to set {key!r}: {exc}[/red]")
        raise typer.Exit(1)


@app.command()
def init() -> None:
    """Interactive first-time setup wizard."""
    settings = load_settings()
    console.print("[bold]devops-cli setup wizard[/bold]\n")

    # ── GitHub ─────────────────────────────────────────────────────────────
    console.print("[cyan]GitHub[/cyan]")
    gh_path = shutil.which("gh")
    if gh_path:
        if not _gh_auth_status() and typer.confirm(
            "Authenticate with GitHub CLI now using 'gh auth login'?", default=True
        ):
            subprocess.run(
                ["gh", "auth", "login"],
                check=False,
                timeout=DEFAULT_GH_AUTH_TIMEOUT_SECONDS * 4,
            )

        gh_token = _gh_auth_token()
        if gh_token and typer.confirm("Import GitHub CLI token into devops keyring?", default=True):
            try:
                dotted_set(settings, opt.GITHUB_TOKEN, gh_token)
                rprint("  [green]✓[/green] GitHub token stored in keyring.")
            except SecretStorageError as exc:
                _render_secret_store_error(opt.GITHUB_TOKEN, exc)
        elif gh_token:
            rprint("  [green]✓[/green] Using GitHub CLI authentication via 'gh auth token'.")
        else:
            rprint(
                "  [yellow]No GitHub CLI session found. You can run 'gh auth login' later.[/yellow]"
            )
    else:
        token = typer.prompt("Personal Access Token (PAT)", hide_input=True, default="")
        if token:
            try:
                dotted_set(settings, opt.GITHUB_TOKEN, token)
                rprint("  [green]✓[/green] GitHub token stored in keyring.")
            except SecretStorageError as exc:
                _render_secret_store_error(opt.GITHUB_TOKEN, exc)

    default_org = typer.prompt("Default org (leave blank to skip)", default="")
    if default_org:
        settings.github.default_org = default_org

    # ── Repositories ───────────────────────────────────────────────────────
    console.print("\n[cyan]Repositories[/cyan]")
    base_dir = typer.prompt("Repos base directory", default=str(settings.repos.base_dir))
    settings.repos.base_dir = Path(base_dir)

    # ── Grafana ────────────────────────────────────────────────────────────
    console.print("\n[cyan]Grafana[/cyan]")
    grafana_url = typer.prompt("Grafana URL (leave blank to skip)", default="")
    if grafana_url:
        try:
            validate_service_url(grafana_url, "Grafana", allow=settings.ai.allow_private_network)
            settings.grafana.url = grafana_url
        except ValueError as exc:
            rprint(f"  [red]{exc}[/red]")
        g_token = typer.prompt("Grafana API token", hide_input=True, default="")
        if g_token:
            try:
                dotted_set(settings, opt.GRAFANA_TOKEN, g_token)
            except SecretStorageError as exc:
                _render_secret_store_error(opt.GRAFANA_TOKEN, exc)

    # ── Prometheus ─────────────────────────────────────────────────────────
    console.print("\n[cyan]Prometheus[/cyan]")
    prom_url = typer.prompt("Prometheus URL (leave blank to skip)", default="")
    if prom_url:
        try:
            validate_service_url(prom_url, "Prometheus", allow=settings.ai.allow_private_network)
            settings.prometheus.url = prom_url
        except ValueError as exc:
            rprint(f"  [red]{exc}[/red]")

    # ── ArgoCD ─────────────────────────────────────────────────────────────
    console.print("\n[cyan]ArgoCD[/cyan]")
    argocd_url = typer.prompt("ArgoCD URL (leave blank to skip)", default="")
    if argocd_url:
        try:
            validate_service_url(argocd_url, "ArgoCD", allow=settings.ai.allow_private_network)
            settings.argocd.url = argocd_url
        except ValueError as exc:
            rprint(f"  [red]{exc}[/red]")
        a_token = typer.prompt("ArgoCD API token", hide_input=True, default="")
        if a_token:
            try:
                dotted_set(settings, opt.ARGOCD_TOKEN, a_token)
            except SecretStorageError as exc:
                _render_secret_store_error(opt.ARGOCD_TOKEN, exc)

    save_settings(settings)
    console.print("\n[bold green]Configuration saved![/bold green]")
    console.print(f"Config file: [dim]{CONST_CONFIG_PATH}[/dim]")


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


@app.command("output")
@app.command("env")
@app.command("env-vars")
def output_env_vars(
    export: Annotated[
        bool,
        typer.Option(
            "--export",
            "-e",
            help="Print environment variables as shell export statements.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Print environment variables as JSON.",
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
        console.print(json.dumps(data, indent=2))
        return

    if export:
        import shlex

        console.print("# devops-cli environment variables export")
        for spec in specs:
            val, _ = _resolve_env_spec_value(spec, settings)
            if spec.is_secret:
                console.print(f'# export {spec.env_var}="****"  # secret (stored in OS keyring)')
            elif val is not None:
                quoted = shlex.quote(str(val))
                console.print(f"export {spec.env_var}={quoted}")
            else:
                console.print(f'# export {spec.env_var}=""  # {spec.description}')
        return

    table = Table(title="devops-cli environment variables", show_header=True, header_style="bold")
    table.add_column("Environment Variable", style="bold cyan", no_wrap=True)
    table.add_column("Config Key", style="dim", no_wrap=True)
    table.add_column("Current Value", overflow="fold")
    table.add_column("Description", overflow="fold")

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

        table.add_row(spec.env_var, key_display, val_display, spec.description)

    console.print(table)


# NOTE (Design Justification - v0.1.1 Prep): auth_headless provides the command stub
# for loading session tokens into ephemeral memory for headless Linux CI environments lacking DBus.
@app.command("auth-headless")
def auth_headless(
    key: Annotated[str, typer.Argument(help="Dotted secret key, e.g. github.token")],
    token: Annotated[str, typer.Argument(help="Secret token string")],
) -> None:
    """Load secret tokens into ephemeral memory for headless CI environments lacking DBus."""
    # TODO (v0.1.1 Feature): Implement memory-backed fallback secret storage for headless CI runners
    from devops_cli.config.options import KEYRING_KEYS
    from devops_cli.config.settings import _EPHEMERAL_CI_SECRETS

    if key not in KEYRING_KEYS:
        rprint(
            f"[red]Invalid secret key '{key}'. Must be one of: {list(KEYRING_KEYS.keys())}[/red]"
        )
        raise typer.Exit(1)

    keyring_field = KEYRING_KEYS[key]
    _EPHEMERAL_CI_SECRETS[keyring_field] = token
    rprint(f"[green]✓ Ephemeral secret loaded into memory: {key}[/green]")


@app.command("audit-stream")
def audit_stream(
    destination: Annotated[str, typer.Argument(help="Destination Syslog or HTTP URL")],
) -> None:
    """Stream stored audit records to SIEM destination URL."""
    from devops_cli.core.audit import stream_audit_records

    count = stream_audit_records(destination_url=destination)
    rprint(f"[green]✓ Streamed {count} audit record(s) → [bold]{destination}[/bold][/green]")
