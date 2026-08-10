"""Config command group: show, get, set, init."""

from __future__ import annotations

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
from devops_cli.config.env import env_var_for_option
from devops_cli.config.settings import (
    _SECRET_FIELDS,
    SecretStorageError,
    dotted_get,
    dotted_set,
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
    env_var = env_var_for_option(key)
    rprint(f"[yellow]Could not store secret for {key}: {exc}[/yellow]")
    if env_var:
        rprint(f"[yellow]Use environment variable fallback: export {env_var}=<value>[/yellow]")


def _gh_auth_status() -> bool:
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except OSError, subprocess.SubprocessError:
        return False
    return result.returncode == 0


def _gh_auth_token() -> str | None:
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except OSError, subprocess.SubprocessError:
        return None
    if result.returncode != 0:
        return None
    token = result.stdout.strip()
    return token or None


@app.command()
def show() -> None:
    """Print all configuration values, masking secrets."""
    settings = load_settings()

    table = Table(title="devops-cli configuration", show_header=True, header_style="bold")
    table.add_column("Key", style="bold cyan", no_wrap=True)
    table.add_column("Value")

    def _row(key: str, value: object, secret: bool = False) -> None:
        if secret:
            display = "[green]set (****)[/green]" if value else "[dim]not set[/dim]"
        else:
            display = str(value) if value is not None else "[dim]not set[/dim]"
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
    _row(opt.AI_OLLAMA_URL, settings.ai.ollama_url)
    _row(opt.AI_API_BASE_URL, settings.ai.api_base_url)
    _row(opt.AI_API_KEY, get_ai_api_key(settings), secret=True)

    console.print(table)
    console.print(f"\nConfig file: [dim]{CONST_CONFIG_PATH}[/dim]")


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
            subprocess.run(["gh", "auth", "login"], check=False)

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
