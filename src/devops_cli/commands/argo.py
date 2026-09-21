"""Argo command group: cd (ArgoCD REST), workflows and rollouts (native Argo CRDs).

Security & Input Validation:
- ArgoCD REST calls validate target server URL via `validate_service_url()`.
- Workflow and Rollout arguments (`name`, `namespace`) are strictly validated against the RFC 1123
  label regex before reaching the Kubernetes API.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import httpx2
import typer

from devops_cli.argo.crd import ArgoCRDService, get_argo_crd_service
from devops_cli.config import load_settings
from devops_cli.config.constants import (
    CONST_ARGO_WORKFLOW_FAILURE_PHASES,
    CONST_ARGO_WORKFLOW_TERMINAL_PHASES,
)
from devops_cli.config.defaults import (
    DEFAULT_ARGOCD_NAMESPACE,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_K8S_NAMESPACE,
    DEFAULT_ROLLOUT_WATCH_INTERVAL_SECONDS,
    DEFAULT_WORKFLOW_POLL_INTERVAL_SECONDS,
    DEFAULT_WORKFLOW_WAIT_TIMEOUT_SECONDS,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.validation import validate_k8s_name
from devops_cli.dry_run import dry_run_command, is_dry_run
from devops_cli.exceptions.argo import ArgoError
from devops_cli.http.validation import validate_service_url
from devops_cli.lang import HELP, MESSAGES
from devops_cli.models.argo import ArgoCDApp, ArgoRolloutState, ArgoWorkflowState
from devops_cli.output import (
    PanelPayload,
    TablePayload,
    format_argo_app_status_panel,
    format_argo_apps_table,
    print,
    print_error,
    print_info,
    print_success,
    print_table,
    write_stdout,
)

app = new_typer(help=HELP.argo.app, no_args_is_help=True)

# ── Sub-groups ────────────────────────────────────────────────────────────────
cd_app = new_typer(help=HELP.argo.cd)
workflows_app = new_typer(help=HELP.argo.workflows)
rollouts_app = new_typer(help=HELP.argo.rollouts)
fleet_app = new_typer(help="Multi-cluster ArgoCD fleet synchronization")
gitops_app = new_typer(help="Automated GitOps drift detection and webhook synchronization")

app.add_typer(cd_app, name="cd")
app.add_typer(workflows_app, name="workflows")
app.add_typer(rollouts_app, name="rollouts")
app.add_typer(fleet_app, name="fleet")
cd_app.add_typer(fleet_app, name="fleet")
app.add_typer(gitops_app, name="gitops")
cd_app.add_typer(gitops_app, name="gitops")

cd_apps_app = new_typer(help=HELP.argo.cd)
cd_app.add_typer(cd_apps_app, name="apps")


# =============================================================================
# ArgoCD Endpoint & Validation Helpers
# =============================================================================


def _validate_k8s_name(value: str, label: str, *, namespace: bool = False) -> None:
    """Raise typer.Exit if value is not a valid Kubernetes name."""
    validate_k8s_name(value, label, namespace=namespace)


def _namespace(namespace: str | None) -> str:
    """Resolve the effective namespace, validating any caller-supplied override."""
    if namespace is None:
        return DEFAULT_K8S_NAMESPACE
    _validate_k8s_name(namespace, "namespace", namespace=True)
    return namespace


def _crd(context: str | None = None) -> ArgoCRDService:
    """Construct the native Argo custom resource service for a kubeconfig context."""
    return get_argo_crd_service(context=context)


def _load_manifest(path: Path) -> dict[str, Any]:
    """Load and validate a single-document Argo custom resource manifest."""
    import yaml

    if not path.exists() or not path.is_file():
        print_error(f"Manifest not found or not a file: {path}", prefix=False)
        raise typer.Exit(1)
    if path.suffix.lower() not in (".yaml", ".yml"):
        print_error(f"Invalid manifest format '{path}'; expected .yaml or .yml", prefix=False)
        raise typer.Exit(1)

    try:
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print_error(f"Failed parsing manifest '{path}': {exc}", prefix=False)
        raise typer.Exit(1)

    if not isinstance(manifest, dict):
        print_error(f"Manifest '{path}' must contain a single resource document", prefix=False)
        raise typer.Exit(1)
    return manifest


def _await_workflow(service: ArgoCRDService, name: str, namespace: str) -> ArgoWorkflowState:
    """Poll a Workflow until it reaches a terminal phase or the wait budget expires."""
    import time

    deadline = time.monotonic() + DEFAULT_WORKFLOW_WAIT_TIMEOUT_SECONDS
    state = service.get_workflow(name, namespace)
    while state.phase not in CONST_ARGO_WORKFLOW_TERMINAL_PHASES:
        if time.monotonic() >= deadline:
            print_error(
                MESSAGES.argo.workflow_wait_timeout.format(
                    name=name, seconds=DEFAULT_WORKFLOW_WAIT_TIMEOUT_SECONDS
                ),
                prefix=False,
            )
            raise typer.Exit(1)
        time.sleep(DEFAULT_WORKFLOW_POLL_INTERVAL_SECONDS)
        state = service.get_workflow(name, namespace)
    return state


def _rollout_status_table(state: ArgoRolloutState) -> TablePayload:
    """Render a single Rollout's progressive delivery state as a Rich table."""
    rows: list[list[Any]] = [
        ["Name", state.name],
        ["Namespace", state.namespace],
        ["Strategy", state.strategy or "—"],
        ["Phase", state.phase],
        [
            "Step",
            "—" if state.current_step is None else f"{state.current_step}/{state.total_steps}",
        ],
        ["Replicas (ready/desired)", f"{state.ready_replicas}/{state.desired_replicas}"],
        ["Updated", str(state.updated_replicas)],
        ["Available", str(state.available_replicas)],
        ["Paused", "yes" if state.paused else "no"],
        ["Aborted", "yes" if state.aborted else "no"],
        ["Message", state.message or "—"],
    ]
    return TablePayload(
        title=MESSAGES.argo.table_title_rollout_status.format(name=state.name),
        columns=[("Field", "cyan"), "Value"],
        rows=rows,
    )


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

    manifest = _load_manifest(resolved_manifest)
    namespace = str(
        (manifest.get("metadata") or {}).get("namespace", "") or DEFAULT_ARGOCD_NAMESPACE
    )

    try:
        applied = get_argo_crd_service(context=context).apply_application(
            manifest, namespace=namespace
        )
    except ArgoError as exc:
        print_error(f"Failed to bootstrap GitOps root app: {exc}", prefix=False)
        raise typer.Exit(1)

    print_success(f"GitOps root Application '{applied.name}' applied from {root_app_path}")


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
    workflows = _crd(namespace).list_workflows(namespace=_namespace(namespace))
    print_table(
        title=MESSAGES.argo.table_title_workflows,
        columns=[("Name", "cyan"), "Phase", "Progress", "Started", "Finished"],
        rows=[
            [wf.name, wf.phase, wf.progress or "—", wf.started_at or "—", wf.finished_at or "—"]
            for wf in workflows
        ],
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
    target_ns = _namespace(namespace)
    submitted = _crd(namespace).submit_workflow(_load_manifest(file.resolve()), namespace=target_ns)
    print_success(
        MESSAGES.argo.workflow_submitted.format(name=submitted.name, phase=submitted.phase)
    )
    if wait:
        final = _await_workflow(_crd(namespace), submitted.name, target_ns)
        print_info(MESSAGES.argo.workflow_finished.format(name=final.name, phase=final.phase))
        if final.phase in CONST_ARGO_WORKFLOW_FAILURE_PHASES:
            raise typer.Exit(1)


@workflows_app.command("logs")
def workflows_logs(
    name: Annotated[str, typer.Argument(help=HELP.argo.workflow_name)],
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = None,
    follow: Annotated[bool, typer.Option("--follow", "-f", help=HELP.argo.follow)] = False,
) -> None:
    """Stream logs for an Argo Workflow."""
    from devops_cli.k8s.service import KubernetesService

    target_ns = _namespace(namespace)
    pods = _crd(namespace).workflow_pod_names(name, namespace=target_ns)
    if not pods:
        print_info(MESSAGES.argo.workflow_no_pods.format(name=name), prefix=False)
        return

    service = KubernetesService.get_instance()
    for pod in pods:
        print_info(f"── {pod} ──", prefix=False)
        for line in service.read_pod_logs(pod, namespace=target_ns, follow=follow):
            write_stdout(line if line.endswith("\n") else f"{line}\n")


# =============================================================================
# Command: devops argo rollouts (list, status)
# =============================================================================


def _rollout_step(state: ArgoRolloutState) -> str:
    """Render a Rollout's canary step position for terminal display."""
    if state.current_step is None:
        return "—"
    return f"{state.current_step}/{state.total_steps}"


@rollouts_app.command("list")
def rollouts_list(
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = None,
) -> None:
    """List Argo Rollouts."""
    rollouts = _crd(namespace).list_rollouts(namespace=_namespace(namespace))
    print_table(
        title=MESSAGES.argo.table_title_rollouts,
        columns=[("Name", "cyan"), "Strategy", "Phase", "Step", "Ready", "Updated"],
        rows=[
            [
                state.name,
                state.strategy or "—",
                state.phase,
                _rollout_step(state),
                f"{state.ready_replicas}/{state.desired_replicas}",
                str(state.updated_replicas),
            ]
            for state in rollouts
        ],
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
    target_ns = _namespace(namespace)
    service = _crd(namespace)

    if watch:
        from devops_cli.watchers.live_resource import LiveResourceWatcher

        LiveResourceWatcher(
            lambda: _rollout_status_table(service.get_rollout(name, target_ns)).render(),
            interval_seconds=DEFAULT_ROLLOUT_WATCH_INTERVAL_SECONDS,
            name="argo_rollout_status",
        ).watch()
        return

    from devops_cli.output import print as print_renderable

    print_renderable(_rollout_status_table(service.get_rollout(name, target_ns)))


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


# =============================================================================
# GitOps Automation: drift detection, continuous watch, and webhook synchronization
# =============================================================================


def _parse_manifest_paths(path: str) -> list[str]:
    """Parse comma-separated manifest paths into a sanitized path list."""
    return [p.strip() for p in path.split(",") if p.strip()] or ["k8s"]


def _handle_gitops_once(
    watcher: Any,
    json_output: bool,
) -> None:
    """Execute a single-cycle manifest drift inspection and optional reconciliation."""
    from devops_cli.argo.gitops import (
        render_gitops_drift_table,
        render_gitops_sync_table,
    )
    from devops_cli.output import print_info, write_stdout

    drift = watcher.scan_drift(detect_cold_drift=True)
    sync_res = watcher.sync_now(drift) if drift else None

    if json_output:
        out = {
            "events": [e.model_dump() for e in drift],
            "synced": sync_res.model_dump() if sync_res else None,
        }
        write_stdout(json.dumps(out, indent=2) + "\n")
    elif drift:
        print(render_gitops_drift_table(drift))
        if sync_res:
            print(render_gitops_sync_table([sync_res]))
    else:
        print_info("No manifest drift detected across watched paths")

    if sync_res and not sync_res.success:
        raise typer.Exit(1)


def _handle_gitops_continuous(
    watcher: Any,
    path: str,
    app_name: str,
    max_events: int | None,
    json_output: bool,
) -> None:
    """Run the continuous watcher loop and print live reconciliation updates."""
    from devops_cli.argo.gitops import render_gitops_sync_table
    from devops_cli.output import print_info, write_stdout

    if not json_output:
        print_info(f"Watching manifests in '{path}' for application '{app_name}'...")

    all_drift_events: list[Any] = []

    def _on_drift(events: list[Any]) -> None:
        all_drift_events.extend(events)

    def _on_sync(res: Any) -> None:
        if not json_output:
            print(render_gitops_sync_table([res]))

    watcher.on_drift = _on_drift
    watcher.on_sync = _on_sync
    results = watcher.watch(max_events=max_events)

    if json_output:
        out = {
            "events": [e.model_dump() for e in all_drift_events],
            "synced": [r.model_dump() for r in results],
        }
        write_stdout(json.dumps(out, indent=2) + "\n")


@gitops_app.command("watch")
@dry_run_command(
    command="devops argo gitops watch",
    action="watch_gitops_drift",
    detail_params=["path", "app_name", "debounce_ms", "interval", "mode"],
)
def gitops_watch(
    path: Annotated[
        str,
        typer.Option(
            "--path",
            "-p",
            help="Comma-separated paths or directories of manifests to monitor",
        ),
    ] = "k8s",
    app_name: Annotated[
        str,
        typer.Option("--app-name", "-a", help=HELP.argo.app_name),
    ] = "root-app",
    debounce_ms: Annotated[
        int,
        typer.Option(
            "--debounce-ms",
            help="Debounce delay in milliseconds to aggregate rapid modifications",
        ),
    ] = 500,
    interval: Annotated[
        float,
        typer.Option("--interval", "-i", help="Watch polling interval in seconds"),
    ] = 1.0,
    max_events: Annotated[
        int | None,
        typer.Option("--max-events", help="Maximum change events to process before exiting"),
    ] = None,
    once: Annotated[
        bool,
        typer.Option(
            "--once",
            help="Check manifest drift once, trigger sync if drifted, and exit immediately",
        ),
    ] = False,
    mode: Annotated[
        str,
        typer.Option("--mode", "-m", help="Synchronization trigger mode ('api' or 'webhook')"),
    ] = "api",
    prune: Annotated[bool, typer.Option("--prune", help=HELP.argo.prune)] = False,
    force: Annotated[bool, typer.Option("--force", help=HELP.options.force)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help=HELP.options.json_output)
    ] = False,
) -> None:
    """Monitor Kubernetes and Helm manifests for drift and trigger instant ArgoCD sync."""
    _validate_k8s_name(app_name, "application name")
    if mode not in ("api", "webhook"):
        print_error(f"Unsupported GitOps sync mode '{mode}'. Allowed: api, webhook")
        raise typer.Exit(1)

    from devops_cli.argo.gitops import GitOpsWatcher

    paths = _parse_manifest_paths(path)
    watcher = GitOpsWatcher(
        paths=paths,
        app_name=app_name,
        debounce_ms=debounce_ms,
        poll_interval_seconds=interval,
        dry_run=is_dry_run(),
        prune=prune,
        force=force,
        sync_mode=mode,  # type: ignore[arg-type]
    )

    if once:
        _handle_gitops_once(watcher, json_output)
    else:
        _handle_gitops_continuous(watcher, path, app_name, max_events, json_output)


@gitops_app.command("drift")
def gitops_drift(
    path: Annotated[
        str,
        typer.Option(
            "--path",
            "-p",
            help="Comma-separated paths or directories of manifests to inspect",
        ),
    ] = "k8s",
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help=HELP.options.json_output)
    ] = False,
) -> None:
    """Inspect and report local manifest state and detect any unstaged or modified files."""
    from devops_cli.argo.gitops import (
        compute_manifest_state,
        inspect_git_manifest_drift,
        load_persisted_manifest_state,
        render_gitops_drift_table,
        scan_manifest_drift,
    )
    from devops_cli.output import print_info, write_stdout

    paths = _parse_manifest_paths(path)
    state = compute_manifest_state(paths)
    persisted = load_persisted_manifest_state(paths)

    if persisted is not None:
        drift = scan_manifest_drift(persisted, state)
    else:
        drift = inspect_git_manifest_drift(paths)

    if json_output:
        data = {"manifests": [e.model_dump() for e in drift]}
        write_stdout(json.dumps(data, indent=2) + "\n")
    elif drift:
        print(render_gitops_drift_table(drift))
    else:
        print_info("No manifest drift detected across watched paths (working tree clean)")


@gitops_app.command("sync")
@dry_run_command(
    command="devops argo gitops sync",
    action="trigger_gitops_sync",
    target_param="app_name",
    detail_params=["mode"],
)
def gitops_sync(
    app_name: Annotated[
        str,
        typer.Option("--app-name", "-a", help=HELP.argo.app_name),
    ] = "root-app",
    mode: Annotated[
        str,
        typer.Option("--mode", "-m", help="Synchronization trigger mode ('api' or 'webhook')"),
    ] = "api",
    prune: Annotated[bool, typer.Option("--prune", help=HELP.argo.prune)] = False,
    force: Annotated[bool, typer.Option("--force", help=HELP.options.force)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help=HELP.options.json_output)
    ] = False,
) -> None:
    """Trigger an immediate GitOps synchronization for an ArgoCD application."""
    _validate_k8s_name(app_name, "application name")
    if mode not in ("api", "webhook"):
        print_error(f"Unsupported GitOps sync mode '{mode}'. Allowed: api, webhook")
        raise typer.Exit(1)

    from devops_cli.argo.gitops import render_gitops_sync_table, trigger_argocd_sync
    from devops_cli.output import write_stdout

    result = trigger_argocd_sync(
        app_name=app_name,
        prune=prune,
        force=force,
        dry_run=is_dry_run(),
        sync_mode=mode,  # type: ignore[arg-type]
    )

    if json_output:
        write_stdout(result.model_dump_json(indent=2) + "\n")
    else:
        print(render_gitops_sync_table([result]))

    if not result.success:
        raise typer.Exit(1)
