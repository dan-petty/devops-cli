"""Argo command group: cd (ArgoCD REST), workflows (CLI), rollouts (CLI)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated, Any

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.cli import new_typer

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


def _argocd(settings: Any) -> tuple[str, dict[str, str]]:
    from devops_cli.config import get_argocd_token

    if not settings.argocd.url:
        rprint("[red]ArgoCD URL not configured. Run: devops config set argocd.url <url>[/red]")
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
    import httpx2

    from devops_cli.config import load_settings

    settings = load_settings()
    base, headers = _argocd(settings)

    with httpx2.Client() as c:
        resp = c.get(f"{base}/api/v1/applications", headers=headers, timeout=30)
        resp.raise_for_status()

    table = Table(title="ArgoCD Applications")
    table.add_column("Name", style="cyan")
    table.add_column("Project")
    table.add_column("Sync")
    table.add_column("Health")
    table.add_column("Repo", style="dim")

    for item in resp.json().get("items", []):
        meta = item["metadata"]
        st = item.get("status", {})
        sync_s = st.get("sync", {}).get("status", "Unknown")
        health_s = st.get("health", {}).get("status", "Unknown")
        repo = item.get("spec", {}).get("source", {}).get("repoURL", "")
        project = item.get("spec", {}).get("project", "")

        sync_c = "green" if sync_s == "Synced" else "yellow"
        health_c = "green" if health_s == "Healthy" else "red"

        table.add_row(
            meta["name"],
            project,
            f"[{sync_c}]{sync_s}[/{sync_c}]",
            f"[{health_c}]{health_s}[/{health_c}]",
            repo,
        )
    console.print(table)


@cd_apps_app.command("sync")
def cd_apps_sync(
    name: Annotated[str, typer.Argument(help="Application name")],
    prune: Annotated[bool, typer.Option("--prune")] = False,
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """Trigger a sync for an ArgoCD application."""
    import httpx2

    from devops_cli.config import load_settings

    settings = load_settings()
    base, headers = _argocd(settings)

    with httpx2.Client() as c:
        resp = c.post(
            f"{base}/api/v1/applications/{name}/sync",
            headers=headers,
            json={"prune": prune, "force": force},
            timeout=60,
        )
        resp.raise_for_status()
    rprint(f"[green]Sync triggered:[/green] {name}")


@cd_apps_app.command("status")
def cd_apps_status(
    name: Annotated[str, typer.Argument(help="Application name")],
) -> None:
    """Show sync and health status for an ArgoCD application."""
    import httpx2

    from devops_cli.config import load_settings

    settings = load_settings()
    base, headers = _argocd(settings)

    with httpx2.Client() as c:
        resp = c.get(f"{base}/api/v1/applications/{name}", headers=headers, timeout=30)
        resp.raise_for_status()

    data = resp.json()
    st = data.get("status", {})
    sync_s = st.get("sync", {}).get("status", "Unknown")
    health_s = st.get("health", {}).get("status", "Unknown")
    revision = st.get("sync", {}).get("revision", "Unknown")[:8]

    rprint(f"[bold cyan]{name}[/bold cyan]")
    rprint(f"  Sync:     {sync_s}")
    rprint(f"  Health:   {health_s}")
    rprint(f"  Revision: {revision}")


# ── Argo Workflows (argo CLI) ─────────────────────────────────────────────────


@workflows_app.command("list")
def workflows_list(
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
) -> None:
    """List Argo Workflows."""
    cmd = ["argo", "list", "--output", "wide"]
    if namespace:
        cmd += ["--namespace", namespace]
    subprocess.run(cmd, check=True)


@workflows_app.command("submit")
def workflows_submit(
    file: Annotated[Path, typer.Argument(help="Workflow YAML file")],
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
    wait: Annotated[bool, typer.Option("--wait", "-w")] = False,
) -> None:
    """Submit an Argo Workflow from a YAML file."""
    cmd = ["argo", "submit", str(file)]
    if namespace:
        cmd += ["--namespace", namespace]
    if wait:
        cmd.append("--wait")
    subprocess.run(cmd, check=True)


@workflows_app.command("logs")
def workflows_logs(
    name: Annotated[str, typer.Argument(help="Workflow name")],
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
    follow: Annotated[bool, typer.Option("--follow", "-f")] = False,
) -> None:
    """Stream logs for an Argo Workflow."""
    cmd = ["argo", "logs", name]
    if namespace:
        cmd += ["--namespace", namespace]
    if follow:
        cmd.append("--follow")
    subprocess.run(cmd, check=True)


# ── Argo Rollouts (kubectl argo rollouts plugin) ──────────────────────────────


@rollouts_app.command("list")
def rollouts_list(
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
) -> None:
    """List Argo Rollouts."""
    cmd = ["kubectl", "argo", "rollouts", "list", "rollouts"]
    if namespace:
        cmd += ["--namespace", namespace]
    subprocess.run(cmd, check=True)


@rollouts_app.command("status")
def rollouts_status(
    name: Annotated[str, typer.Argument(help="Rollout name")],
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
    watch: Annotated[bool, typer.Option("--watch", "-w")] = False,
) -> None:
    """Show status for an Argo Rollout."""
    cmd = ["kubectl", "argo", "rollouts", "status", name]
    if namespace:
        cmd += ["--namespace", namespace]
    if watch:
        cmd.append("--watch")
    subprocess.run(cmd, check=True)
