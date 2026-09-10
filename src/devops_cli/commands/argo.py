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
from devops_cli.dry_run import dry_run_command, is_dry_run
from devops_cli.http.validation import validate_service_url
from devops_cli.lang import HELP, MESSAGES
from devops_cli.models.argo import ArgoCDApp
from devops_cli.output import (
    PanelPayload,
    TablePayload,
    format_argo_app_status_panel,
    format_argo_apps_table,
    print,
    print_error,
    print_success,
)

app = new_typer(help=HELP.argo.app, no_args_is_help=True)

# ── Sub-groups ────────────────────────────────────────────────────────────────
cd_app = new_typer(help=HELP.argo.cd)
workflows_app = new_typer(help=HELP.argo.workflows)
rollouts_app = new_typer(help=HELP.argo.rollouts)
fleet_app = new_typer(help="Multi-cluster ArgoCD fleet synchronization")

app.add_typer(cd_app, name="cd")
app.add_typer(workflows_app, name="workflows")
app.add_typer(rollouts_app, name="rollouts")
app.add_typer(fleet_app, name="fleet")
cd_app.add_typer(fleet_app, name="fleet")

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
@dry_run_command(
    command="devops argo cd apps list",
    action="list_argocd_apps",
    detail_params=["watch"],
)
def cd_apps_list(
    watch: Annotated[bool, typer.Option("--watch", "-w", help=HELP.argo.watch)] = False,
    interval: Annotated[float, typer.Option("--interval", "-i", help=HELP.argo.interval)] = 3.0,
) -> None:
    """List all ArgoCD applications."""

    def _build_apps_table() -> TablePayload:
        settings = load_settings()
        base, headers = _argocd(settings)
        rows: list[list[str]] = []
        try:
            with httpx2.Client() as client:
                resp = client.get(
                    f"{base}/api/v1/applications",
                    headers=headers,
                    timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
                )
                resp.raise_for_status()
            data = resp.json()
            items = data.get("items", []) if isinstance(data, dict) else []
        except Exception as exc:
            rows.append([f"[red]Error: {exc}[/red]", "—", "—", "—", "—"])
            return format_argo_apps_table(rows)
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
        return format_argo_apps_table(rows)

    if watch:
        from devops_cli.watchers.live_resource import LiveResourceWatcher

        LiveResourceWatcher(
            lambda: _build_apps_table().render(), interval_seconds=interval, name="argo_apps_list"
        ).watch()
    else:
        print(_build_apps_table())


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
    watch: Annotated[bool, typer.Option("--watch", "-w", help=HELP.argo.watch)] = False,
    interval: Annotated[float, typer.Option("--interval", "-i", help=HELP.argo.interval)] = 3.0,
) -> None:
    """Show sync and health status for an ArgoCD application."""
    _validate_k8s_name(name, "application name")

    def _build_status_panel() -> PanelPayload:
        settings = load_settings()
        base, headers = _argocd(settings)
        try:
            with httpx2.Client() as client:
                resp = client.get(
                    f"{base}/api/v1/applications/{name}",
                    headers=headers,
                    timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
                )
                resp.raise_for_status()
            app_info = ArgoCDApp.from_api_item(resp.json())
        except Exception as exc:
            return format_argo_app_status_panel(
                name=name, sync_status="", health_status="", revision="", error=str(exc)
            )
        return format_argo_app_status_panel(
            name=app_info.name,
            sync_status=app_info.sync_status,
            health_status=app_info.health_status,
            revision=app_info.revision,
        )

    if watch:
        from devops_cli.watchers.live_resource import LiveResourceWatcher

        LiveResourceWatcher(
            lambda: _build_status_panel().render(),
            interval_seconds=interval,
            name="argo_app_status",
        ).watch()
    else:
        print(_build_status_panel())


# =============================================================================
# Command: devops argo cd apps bootstrap-gitops
# =============================================================================


@cd_apps_app.command("bootstrap-gitops")
@dry_run_command(
    command="devops argo cd apps bootstrap-gitops",
    action="bootstrap_argocd_gitops",
    target_param="root_app_path",
    detail_params=["context"],
)
def cd_apps_bootstrap_gitops(
    root_app_path: Annotated[
        Path,
        typer.Option(
            "--root-app",
            "-f",
            help=HELP.argo.app_of_apps_manifest,
        ),
    ] = Path("k8s/argocd/apps/root-app.yaml"),
    context: Annotated[
        str | None,
        typer.Option("--context", "-c", help=HELP.options.context),
    ] = None,
) -> None:
    """Bootstrap local GitOps project orchestration via ArgoCD and the Git daemon."""
    resolved_manifest = root_app_path.resolve()
    if not resolved_manifest.exists() or not resolved_manifest.is_file():
        print_error(f"Root app manifest not found or not a file: {root_app_path}", prefix=False)
        raise typer.Exit(1)

    if resolved_manifest.suffix.lower() not in (".yaml", ".yml"):
        print_error(
            f"Invalid root app manifest format '{root_app_path}'; expected .yaml or .yml",
            prefix=False,
        )
        raise typer.Exit(1)

    import tempfile

    from devops_cli.core.repo import find_repo_root

    repo_root = find_repo_root().resolve()
    cwd_root = Path.cwd().resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if not (
        resolved_manifest.is_relative_to(repo_root)
        or resolved_manifest.is_relative_to(cwd_root)
        or resolved_manifest.is_relative_to(temp_root)
    ):
        print_error(
            f"Root app manifest '{root_app_path}' resolves outside allowed workspace or temporary directory",
            prefix=False,
        )
        raise typer.Exit(1)

    cmd = ["kubectl", "apply", "-f", str(resolved_manifest)]
    if context:
        cmd.extend(["--context", context])

    res = run_subprocess(
        cmd,
        check=False,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        capture_output=True,
    )
    if res.returncode != 0:
        print_error(f"Failed to bootstrap GitOps root app: {res.stderr}", prefix=False)
        raise typer.Exit(res.returncode)

    print_success(f"GitOps root Application applied from {root_app_path}")


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


@fleet_app.command("sync")
@dry_run_command(
    command="devops argo fleet sync",
    action="sync_argo_fleet",
    target_param="app_name",
    detail_params=["clusters", "fleet_name", "concurrency"],
)
def fleet_sync(
    app_name: Annotated[str, typer.Argument(help=HELP.argo.app_name)],
    clusters: Annotated[
        str,
        typer.Option(
            "--clusters",
            "-c",
            help="Comma-separated list of target cluster names (e.g. dev,staging,prod)",
        ),
    ] = "dev,staging,prod",
    fleet_name: Annotated[
        str, typer.Option("--fleet", help="Fleet identifier group name")
    ] = "default-fleet",
    concurrency: Annotated[
        int,
        typer.Option(
            "--concurrency",
            "-p",
            help="Maximum concurrent cluster synchronization workers",
        ),
    ] = 3,
    prune: Annotated[bool, typer.Option("--prune", help=HELP.argo.prune)] = False,
    force: Annotated[bool, typer.Option("--force", help=HELP.options.force)] = False,
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help=HELP.options.json_output)
    ] = False,
) -> None:
    """Synchronize an application across a fleet of Kubernetes clusters with bounded concurrency."""
    _validate_k8s_name(app_name, "application name")
    from devops_cli.argo.fleet import render_fleet_sync_table, sync_fleet
    from devops_cli.output import write_stdout

    cluster_list = [c.strip() for c in clusters.split(",") if c.strip()]
    for c in cluster_list:
        _validate_k8s_name(c, "cluster name")

    result = sync_fleet(
        app_name=app_name,
        clusters=cluster_list,
        fleet_name=fleet_name,
        prune=prune,
        force=force,
        max_concurrency=concurrency,
        dry_run=is_dry_run(),
    )

    if json_output:
        write_stdout(result.model_dump_json(indent=2) + "\n")
    else:
        print(render_fleet_sync_table(result))

    if not result.success:
        raise typer.Exit(1)


@app.command("sync")
def argo_sync_cmd(
    name: Annotated[str, typer.Argument(help=HELP.argo.app_name)],
    fleet: Annotated[
        bool,
        typer.Option(
            "--fleet",
            help="Synchronize application across multi-cluster fleet",
        ),
    ] = False,
    clusters: Annotated[
        str,
        typer.Option(
            "--clusters",
            "-c",
            help="Comma-separated list of target cluster names (e.g. dev,staging,prod)",
        ),
    ] = "dev,staging,prod",
    fleet_name: Annotated[
        str, typer.Option("--fleet-name", help="Fleet identifier group name")
    ] = "default-fleet",
    concurrency: Annotated[
        int,
        typer.Option(
            "--concurrency",
            "-p",
            help="Maximum concurrent cluster synchronization workers",
        ),
    ] = 3,
    prune: Annotated[bool, typer.Option("--prune", help=HELP.argo.prune)] = False,
    force: Annotated[bool, typer.Option("--force", help=HELP.options.force)] = False,
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help=HELP.options.json_output)
    ] = False,
) -> None:
    """Synchronize an ArgoCD application (or multi-cluster fleet when --fleet is passed)."""
    if fleet:
        fleet_sync(
            app_name=name,
            clusters=clusters,
            fleet_name=fleet_name,
            concurrency=concurrency,
            prune=prune,
            force=force,
            json_output=json_output,
        )
    else:
        cd_apps_sync(name=name, prune=prune, force=force)


@rollouts_app.command("promote")
@dry_run_command(
    command="devops argo rollouts promote",
    action="promote_argo_rollout",
    target_param="name",
    detail_params=["namespace", "full"],
)
def rollouts_promote(
    name: Annotated[str, typer.Argument(help=HELP.argo.rollout_name)],
    namespace: Annotated[
        str, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = "default",
    full: Annotated[
        bool,
        typer.Option(
            "--full", help="Skip all remaining steps and promote directly to full release"
        ),
    ] = False,
) -> None:
    """Promote an in-progress Argo Rollout to the next progressive step or full release."""
    from devops_cli.argo.rollouts import promote_rollout

    success = promote_rollout(name, namespace=namespace, full=full, dry_run=is_dry_run())
    if not success:
        print_error(f"Failed to promote rollout '{name}' in namespace '{namespace}'")
        raise typer.Exit(1)
    target_mode = "full release" if full else "next step"
    print_success(
        f"Successfully promoted rollout '{name}' ({target_mode}) in namespace '{namespace}'"
    )


@rollouts_app.command("abort")
@dry_run_command(
    command="devops argo rollouts abort",
    action="abort_argo_rollout",
    target_param="name",
    detail_params=["namespace"],
)
def rollouts_abort(
    name: Annotated[str, typer.Argument(help=HELP.argo.rollout_name)],
    namespace: Annotated[
        str, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = "default",
) -> None:
    """Abort an in-progress Argo Rollout and revert immediately to the stable replica set."""
    from devops_cli.argo.rollouts import abort_rollout

    success = abort_rollout(name, namespace=namespace, dry_run=is_dry_run())
    if not success:
        print_error(f"Failed to abort rollout '{name}' in namespace '{namespace}'")
        raise typer.Exit(1)
    print_success(f"Successfully aborted rollout '{name}' in namespace '{namespace}'")


@rollouts_app.command("restart")
@dry_run_command(
    command="devops argo rollouts restart",
    action="restart_argo_rollout",
    target_param="name",
    detail_params=["namespace"],
)
def rollouts_restart(
    name: Annotated[str, typer.Argument(help=HELP.argo.rollout_name)],
    namespace: Annotated[
        str, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = "default",
) -> None:
    """Perform a restart rollout across all pods in an Argo Rollout."""
    from devops_cli.argo.rollouts import restart_rollout

    success = restart_rollout(name, namespace=namespace, dry_run=is_dry_run())
    if not success:
        print_error(f"Failed to restart rollout '{name}' in namespace '{namespace}'")
        raise typer.Exit(1)
    print_success(f"Successfully restarted rollout '{name}' in namespace '{namespace}'")


@rollouts_app.command("analyze")
def rollouts_analyze(
    name: Annotated[str, typer.Argument(help=HELP.argo.rollout_name)],
    namespace: Annotated[
        str, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = "default",
    error_rate_threshold: Annotated[
        float,
        typer.Option(
            "--error-rate-threshold",
            "-e",
            help="Maximum allowable HTTP 5xx error rate percentage before triggering automated rollback",
        ),
    ] = 1.0,
    auto_abort: Annotated[
        bool,
        typer.Option(
            "--auto-abort/--no-auto-abort",
            help="Automatically trigger rollout abort when metric analysis violates threshold",
        ),
    ] = True,
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help=HELP.options.json_output)
    ] = False,
) -> None:
    """Evaluate metric rollback gates and trigger automated rollback on threshold violation."""
    from devops_cli.argo.rollouts import evaluate_rollout_gate, render_rollout_analysis_table
    from devops_cli.models.argo import RolloutMetricThreshold
    from devops_cli.output import write_stdout

    thresholds = [
        RolloutMetricThreshold(
            metric_name="http_error_rate_percentage",
            query=f'sum(rate(http_requests_total{{status=~"5..",app="{name}"}}[2m])) / sum(rate(http_requests_total{{app="{name}"}}[2m])) * 100',
            threshold=error_rate_threshold,
            operator="lte",
        )
    ]

    result = evaluate_rollout_gate(
        rollout_name=name,
        namespace=namespace,
        thresholds=thresholds,
        auto_abort=auto_abort,
        dry_run=is_dry_run(),
    )

    if json_output:
        write_stdout(result.model_dump_json(indent=2) + "\n")
    else:
        print(render_rollout_analysis_table(result))

    if not result.passed:
        if not json_output:
            print_error(f"Rollout metric analysis failed: {result.reason}")
        raise typer.Exit(1)
