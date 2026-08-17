"""Argo command group: cd (ArgoCD REST), workflows (argo CLI), rollouts (argo-rollouts CLI).

Security & Input Validation:
- ArgoCD REST calls validate target server URL via `validate_service_url()`.
- Workflows and Rollouts arguments (`name`, `namespace`) are strictly validated against RFC 1123
  label regex before subprocess execution to eliminate command injection risk.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated, Any

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.config.constants import CONST_K8S_LABEL_RE, CONST_K8S_SUBDOMAIN_RE
from devops_cli.config.defaults import (
    DEFAULT_HTTP_LONG_TIMEOUT_SECONDS,
    DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.http.validation import validate_service_url
from devops_cli.models.argo import ArgoCDApp

app = new_typer(help="Argo CD, Workflows, and Rollouts management.", no_args_is_help=True)
console = Console()

# ── Sub-groups ────────────────────────────────────────────────────────────────
cd_app = new_typer(help="ArgoCD application management.")
workflows_app = new_typer(help="Argo Workflows management.")
rollouts_app = new_typer(help="Argo Rollouts management.")

app.add_typer(cd_app, name="cd")
app.add_typer(workflows_app, name="workflows")
app.add_typer(rollouts_app, name="rollouts")

cd_apps_app = new_typer(help="Manage ArgoCD applications.")
cd_app.add_typer(cd_apps_app, name="apps")

# RFC 1123 label (namespaces, simple names) and subdomain (resource names) patterns
_K8S_LABEL_RE = CONST_K8S_LABEL_RE
_K8S_SUBDOMAIN_RE = CONST_K8S_SUBDOMAIN_RE


def _validate_k8s_name(value: str, label: str, *, namespace: bool = False) -> None:
    """Raise typer.Exit if value is not a valid Kubernetes name."""
    pattern = CONST_K8S_LABEL_RE if namespace else CONST_K8S_SUBDOMAIN_RE
    if not pattern.match(value):
        rprint(f"[red]Invalid {label}: {value!r}. Must be a valid RFC 1123 name.[/red]")
        raise typer.Exit(1)


def _argocd(settings: Any) -> tuple[str, dict[str, str]]:
    from devops_cli.config.settings import get_argocd_token

    if not settings.argocd.url:
        rprint("[red]ArgoCD URL not configured. Run: devops config set argocd.url <url>[/red]")
        raise typer.Exit(1)
    try:
        validate_service_url(settings.argocd.url, "ArgoCD", allow=settings.ai.allow_private_network)
    except ValueError as exc:
        rprint(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    token = get_argocd_token(settings)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return settings.argocd.url.rstrip("/"), headers


# ── ArgoCD: apps ──────────────────────────────────────────────────────────────


@cd_apps_app.command("list")
def cd_apps_list() -> None:
    """List all ArgoCD applications."""
    if is_dry_run():
        render_dry_run_result(
            command="devops argo cd apps list",
            action="list_argocd_apps",
            details={"apps": []},
        )
        return

    import httpx2

    from devops_cli.config import load_settings

    settings = load_settings()
    base, headers = _argocd(settings)

    with httpx2.Client() as c:
        resp = c.get(
            f"{base}/api/v1/applications",
            headers=headers,
            timeout=DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()

    table = Table(title="ArgoCD Applications")
    table.add_column("Name", style="cyan")
    table.add_column("Project")
    table.add_column("Sync")
    table.add_column("Health")
    table.add_column("Repo", style="dim")

    for item in resp.json().get("items", []):
        app_info = ArgoCDApp.from_api_item(item)
        sync_c = "green" if app_info.sync_status == "Synced" else "yellow"
        health_c = "green" if app_info.health_status == "Healthy" else "red"
        table.add_row(
            app_info.name,
            app_info.project,
            f"[{sync_c}]{app_info.sync_status}[/{sync_c}]",
            f"[{health_c}]{app_info.health_status}[/{health_c}]",
            app_info.repo_url,
        )
    console.print(table)


@cd_apps_app.command("sync")
def cd_apps_sync(
    name: Annotated[str, typer.Argument(help="Application name")],
    prune: Annotated[bool, typer.Option("--prune")] = False,
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Trigger a sync for an ArgoCD application."""
    _validate_k8s_name(name, "application name")
    import httpx2

    from devops_cli.config import load_settings

    settings = load_settings()
    base, headers = _argocd(settings)

    with httpx2.Client() as c:
        resp = c.post(
            f"{base}/api/v1/applications/{name}/sync",
            headers=headers,
            json={"sync": {"prune": prune, "force": force}},
            timeout=DEFAULT_HTTP_LONG_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
    rprint(f"[green]Sync triggered:[/green] {name}")


@cd_apps_app.command("status")
def cd_apps_status(
    name: Annotated[str, typer.Argument(help="Application name")],
) -> None:
    """Show sync and health status for an ArgoCD application."""
    _validate_k8s_name(name, "application name")
    import httpx2

    from devops_cli.config import load_settings

    settings = load_settings()
    base, headers = _argocd(settings)

    with httpx2.Client() as c:
        resp = c.get(
            f"{base}/api/v1/applications/{name}",
            headers=headers,
            timeout=DEFAULT_HTTP_REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()

    data = resp.json()
    app_info = ArgoCDApp.from_api_item(data)

    rprint(f"[bold cyan]{app_info.name}[/bold cyan]")
    rprint(f"  Sync:     {app_info.sync_status}")
    rprint(f"  Health:   {app_info.health_status}")
    rprint(f"  Revision: {app_info.revision}")


# ── Argo Workflows (argo CLI) ─────────────────────────────────────────────────


@workflows_app.command("list")
def workflows_list(
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
) -> None:
    """List Argo Workflows."""
    if namespace:
        _validate_k8s_name(namespace, "namespace", namespace=True)
    cmd = ["argo", "list", "--output", "wide"]
    if namespace:
        cmd += ["--namespace", namespace]
    subprocess.run(cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)


@workflows_app.command("submit")
def workflows_submit(
    file: Annotated[Path, typer.Argument(help="Workflow YAML file")],
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
    wait: Annotated[bool, typer.Option("--wait", "-w")] = False,
) -> None:
    """Submit an Argo Workflow from a YAML file."""
    if namespace:
        _validate_k8s_name(namespace, "namespace", namespace=True)
    cmd = ["argo", "submit", str(file)]
    if namespace:
        cmd += ["--namespace", namespace]
    if wait:
        cmd.append("--wait")
    subprocess.run(cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)


@workflows_app.command("logs")
def workflows_logs(
    name: Annotated[str, typer.Argument(help="Workflow name")],
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
    follow: Annotated[bool, typer.Option("--follow", "-f")] = False,
) -> None:
    """Stream logs for an Argo Workflow."""
    _validate_k8s_name(name, "workflow name")
    if namespace:
        _validate_k8s_name(namespace, "namespace", namespace=True)
    cmd = ["argo", "logs", name]
    if namespace:
        cmd += ["--namespace", namespace]
    if follow:
        cmd.append("--follow")
        subprocess.run(cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)
    else:
        subprocess.run(cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)


# ── Argo Rollouts (kubectl argo rollouts plugin) ──────────────────────────────


@rollouts_app.command("list")
def rollouts_list(
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
) -> None:
    """List Argo Rollouts."""
    if namespace:
        _validate_k8s_name(namespace, "namespace", namespace=True)
    cmd = ["kubectl", "argo", "rollouts", "list"]
    if namespace:
        cmd += ["--namespace", namespace]
    subprocess.run(cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)


@rollouts_app.command("status")
def rollouts_status(
    name: Annotated[str, typer.Argument(help="Rollout name")],
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
    watch: Annotated[bool, typer.Option("--watch", "-w")] = False,
) -> None:
    """Show status for an Argo Rollout."""
    _validate_k8s_name(name, "rollout name")
    if namespace:
        _validate_k8s_name(namespace, "namespace", namespace=True)
    cmd = ["kubectl", "argo", "rollouts", "status", name]
    if namespace:
        cmd += ["--namespace", namespace]
    if watch:
        cmd.append("--watch")
        subprocess.run(cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)
    else:
        subprocess.run(cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)
