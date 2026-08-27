"""Argo command group: cd (ArgoCD REST), workflows (argo CLI), rollouts (argo-rollouts CLI).

Security & Input Validation:
- ArgoCD REST calls validate target server URL via `validate_service_url()`.
- Workflows and Rollouts arguments (`name`, `namespace`) are strictly validated against RFC 1123
  label regex before subprocess execution to eliminate command injection risk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import httpx2
import typer

from devops_cli.config import load_settings
from devops_cli.config.defaults import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.core.validation import validate_k8s_name
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.http.validation import validate_service_url
from devops_cli.lang import HELP, MESSAGES
from devops_cli.models.argo import ArgoCDApp
from devops_cli.output import (
    print_error,
    print_info,
    print_success,
    print_table,
)

app = new_typer(help=HELP.argo.app, no_args_is_help=True)

# ── Sub-groups ────────────────────────────────────────────────────────────────
cd_app = new_typer(help=HELP.argo.cd)
workflows_app = new_typer(help=HELP.argo.workflows)
rollouts_app = new_typer(help=HELP.argo.rollouts)

app.add_typer(cd_app, name="cd")
app.add_typer(workflows_app, name="workflows")
app.add_typer(rollouts_app, name="rollouts")

cd_apps_app = new_typer(help=HELP.argo.cd)
cd_app.add_typer(cd_apps_app, name="apps")


# =============================================================================
# ArgoCD Endpoint & Validation Helpers
# =============================================================================


def _validate_k8s_name(value: str, label: str, *, namespace: bool = False) -> None:
    """Raise typer.Exit if value is not a valid Kubernetes name."""
    validate_k8s_name(value, label, namespace=namespace)


def _argocd(settings: Any) -> tuple[str, dict[str, str]]:
    from devops_cli.config.settings import get_argocd_token

    if not settings.argocd.url:
        print_error(
            MESSAGES.argo.url_not_configured,
            prefix=False,
        )
        raise typer.Exit(1)
    try:
        validate_service_url(settings.argocd.url, "ArgoCD", allow=settings.ai.allow_private_network)
    except ValueError as exc:
        print_error(str(exc), prefix=False)
        raise typer.Exit(1)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    token = get_argocd_token(settings)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return settings.argocd.url.rstrip("/"), headers


# =============================================================================
# Command: devops argo cd apps list
# =============================================================================


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

    settings = load_settings()
    base, headers = _argocd(settings)

    with httpx2.Client() as c:
        resp = c.get(
            f"{base}/api/v1/applications",
            headers=headers,
            timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()

    rows: list[list[str]] = []
    data = resp.json()
    items = data.get("items", []) if isinstance(data, dict) else []
    for item in items:
        app_info = ArgoCDApp.from_api_item(item)
        sync_c = "green" if app_info.sync_status == "Synced" else "yellow"
        health_c = "green" if app_info.health_status == "Healthy" else "red"
        rows.append(
            [
                app_info.name,
                app_info.project,
                f"[{sync_c}]{app_info.sync_status}[/{sync_c}]",
                f"[{health_c}]{app_info.health_status}[/{health_c}]",
                app_info.repo_url,
            ]
        )
    print_table(
        title=MESSAGES.argo.table_title_apps,
        columns=[("Name", "cyan"), "Project", "Sync", "Health", ("Repo", "dim")],
        rows=rows,
    )


# =============================================================================
# Command: devops argo cd apps sync
# =============================================================================


@cd_apps_app.command("sync")
def cd_apps_sync(
    name: Annotated[str, typer.Argument(help=HELP.argo.app_name)],
    prune: Annotated[bool, typer.Option("--prune", help=HELP.argo.prune)] = False,
    force: Annotated[bool, typer.Option("--force", help=HELP.options.force)] = False,
) -> None:
    """Trigger a sync for an ArgoCD application."""
    _validate_k8s_name(name, "application name")
    settings = load_settings()
    base, headers = _argocd(settings)

    with httpx2.Client() as c:
        resp = c.post(
            f"{base}/api/v1/applications/{name}/sync",
            headers=headers,
            json={"sync": {"prune": prune, "force": force}},
            timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
    print_success(MESSAGES.argo.sync_triggered.format(name=name))


# =============================================================================
# Command: devops argo cd apps status
# =============================================================================


@cd_apps_app.command("status")
def cd_apps_status(
    name: Annotated[str, typer.Argument(help=HELP.argo.app_name)],
) -> None:
    """Show sync and health status for an ArgoCD application."""
    _validate_k8s_name(name, "application name")
    settings = load_settings()
    base, headers = _argocd(settings)

    with httpx2.Client() as c:
        resp = c.get(
            f"{base}/api/v1/applications/{name}",
            headers=headers,
            timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()

    data = resp.json()
    app_info = ArgoCDApp.from_api_item(data)

    print_info(f"[bold cyan]{app_info.name}[/bold cyan]", prefix=False)
    print_info(f"  Sync:     {app_info.sync_status}", prefix=False)
    print_info(f"  Health:   {app_info.health_status}", prefix=False)
    print_info(f"  Revision: {app_info.revision}", prefix=False)


# =============================================================================
# Command: devops argo workflows (list, submit, logs)
# =============================================================================


@workflows_app.command("list")
def workflows_list(
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = None,
) -> None:
    """List Argo Workflows."""
    if namespace:
        _validate_k8s_name(namespace, "namespace", namespace=True)
    cmd = ["argo", "list", "--output", "wide"]
    if namespace:
        cmd += ["--namespace", namespace]
    run_subprocess(
        cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS, capture_output=False
    )


@workflows_app.command("submit")
def workflows_submit(
    file: Annotated[Path, typer.Argument(help=HELP.argo.workflow_file)],
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = None,
    wait: Annotated[bool, typer.Option("--wait", "-w", help=HELP.argo.wait)] = False,
) -> None:
    """Submit an Argo Workflow from a YAML file."""
    if namespace:
        _validate_k8s_name(namespace, "namespace", namespace=True)
    cmd = ["argo", "submit", str(file)]
    if namespace:
        cmd += ["--namespace", namespace]
    if wait:
        cmd.append("--wait")
    run_subprocess(
        cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS, capture_output=False
    )


@workflows_app.command("logs")
def workflows_logs(
    name: Annotated[str, typer.Argument(help=HELP.argo.workflow_name)],
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = None,
    follow: Annotated[bool, typer.Option("--follow", "-f", help=HELP.argo.follow)] = False,
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
    run_subprocess(
        cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS, capture_output=False
    )


# =============================================================================
# Command: devops argo rollouts (list, status)
# =============================================================================


@rollouts_app.command("list")
def rollouts_list(
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = None,
) -> None:
    """List Argo Rollouts."""
    if namespace:
        _validate_k8s_name(namespace, "namespace", namespace=True)
    cmd = ["kubectl", "argo", "rollouts", "list"]
    if namespace:
        cmd += ["--namespace", namespace]
    run_subprocess(
        cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS, capture_output=False
    )


@rollouts_app.command("status")
def rollouts_status(
    name: Annotated[str, typer.Argument(help=HELP.argo.rollout_name)],
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = None,
    watch: Annotated[bool, typer.Option("--watch", "-w", help=HELP.argo.watch)] = False,
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
    run_subprocess(
        cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS, capture_output=False
    )
