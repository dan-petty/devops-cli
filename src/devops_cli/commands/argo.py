"""Argo command group: cd (ArgoCD REST), workflows and rollouts (native Argo CRDs).

Security & Input Validation:
- ArgoCD REST calls dial `argocd.url` through the egress factory at the configured level, which
  checks each address at the connect.
- Workflow and Rollout arguments (`name`, `namespace`) are strictly validated against the RFC 1123
  label regex before reaching the Kubernetes API.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import httpx2
import typer

from devops_cli.argo.crd import ArgoCRDService, get_argo_crd_service, is_not_found_error
from devops_cli.argo.credentials import argocd_api_request
from devops_cli.argo.helm_records import (
    HelmRelease,
    RetirementPlan,
    dry_run_helm_record_retirement,
    plan_helm_record_retirement,
    retire_helm_records,
)
from devops_cli.argo.image_pins import PinCheck, check_pins, kustomize_image_pins
from devops_cli.argo.sync import build_sync_request_body
from devops_cli.config.constants import (
    CONST_ARGO_DEFAULT_LOG_CONTAINER,
    CONST_ARGO_POD_NAME_V1,
    CONST_ARGO_WORKFLOW_FAILURE_PHASES,
    CONST_ARGO_WORKFLOW_TERMINAL_PHASES,
    CONST_OUTPUT_FORMAT_TABLE,
)
from devops_cli.config.defaults import (
    DEFAULT_ARGOCD_NAMESPACE,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    DEFAULT_K8S_NAMESPACE,
    DEFAULT_ROLLOUT_WATCH_INTERVAL_SECONDS,
    DEFAULT_TABLE_FORMAT,
    DEFAULT_WORKFLOW_POLL_INTERVAL_SECONDS,
    DEFAULT_WORKFLOW_WAIT_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import load_settings
from devops_cli.core.cli import new_typer
from devops_cli.core.validation import validate_k8s_name
from devops_cli.dry_run import dry_run_class, is_dry_run
from devops_cli.dry_run.requests import render_request_plan
from devops_cli.exceptions.argo import ArgoError
from devops_cli.http.client import new_http_client
from devops_cli.http.egress import EgressLevel, configured_level
from devops_cli.http.urls import service_base_url
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
from devops_cli.output.serialization import emit_serialized, resolve_format

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

# A refusal at the connect ends each command with its message and no traceback.
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
        raise typer.Exit(1) from exc

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
    """Return (base_url, headers) for Argo CD API requests.

    The URL check reads only the URL, and it runs before the token mint. A failed mint, also one
    whose address the egress level refused, ends the command with its cause. The client of
    `_argocd_client` checks the address at the connect.
    """
    from devops_cli.argo.credentials import resolve_argocd_server_and_token

    if not settings.argocd.url:
        print_error(
            MESSAGES.argo.url_not_configured,
            prefix=False,
        )
        raise typer.Exit(1)
    try:
        base = service_base_url(settings.argocd.url, "argocd.url")
    except ValueError as exc:
        print_error(str(exc), prefix=False)
        raise typer.Exit(1) from exc
    _, token = resolve_argocd_server_and_token(settings)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return base, headers


def _argocd_client(settings: Any) -> httpx2.Client:
    """An Argo CD client that dials the configured level: loopback, or private with the flag."""
    return new_http_client(level=configured_level(settings.ai))


# =============================================================================
# Command: devops argo cd apps list
# =============================================================================


@cd_apps_app.command("list")
@dry_run_class("request-plan")
def cd_apps_list(
    watch: Annotated[bool, typer.Option("--watch", "-w", help=HELP.argo.watch)] = False,
    interval: Annotated[float, typer.Option("--interval", "-i", help=HELP.argo.interval)] = 3.0,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """List all ArgoCD applications."""
    if dry_run or is_dry_run():
        from devops_cli.argo.argo_plans import plan_argocd_apps_list

        render_request_plan("Plan for listing Argo CD applications", plan_argocd_apps_list())
        return

    def _build_apps_table() -> TablePayload:
        settings = load_settings()
        base, headers = _argocd(settings)
        rows: list[list[str]] = []
        try:
            with _argocd_client(settings) as client:
                resp = argocd_api_request(
                    settings,
                    headers,
                    lambda sent: client.get(
                        f"{base}/api/v1/applications",
                        headers=sent,
                        timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
                    ),
                )
            data = resp.json()
            items = (data.get("items") or []) if isinstance(data, dict) else []
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
@dry_run_class("request-plan")
def cd_apps_sync(
    name: Annotated[str, typer.Argument(help=HELP.argo.app_name)],
    prune: Annotated[bool, typer.Option("--prune", help=HELP.argo.prune)] = False,
    force: Annotated[bool, typer.Option("--force", help=HELP.options.force)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Trigger a sync for an ArgoCD application."""
    _validate_k8s_name(name, "application name")
    if dry_run or is_dry_run():
        from devops_cli.argo.argo_plans import plan_argocd_apps_sync

        render_request_plan(
            f"Plan for syncing Argo CD application '{name}'",
            plan_argocd_apps_sync(name=name, prune=prune, force=force),
        )
        return
    settings = load_settings()
    base, headers = _argocd(settings)

    with _argocd_client(settings) as c:
        argocd_api_request(
            settings,
            headers,
            lambda sent: c.post(
                f"{base}/api/v1/applications/{name}/sync",
                headers=sent,
                json=build_sync_request_body(prune=prune, force=force),
                timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
            ),
        )
    print_success(MESSAGES.argo.sync_triggered.format(name=name))


# =============================================================================
# Command: devops argo cd apps status
# =============================================================================


@cd_apps_app.command("status")
@dry_run_class("request-plan")
def cd_apps_status(
    name: Annotated[str, typer.Argument(help=HELP.argo.app_name)],
    watch: Annotated[bool, typer.Option("--watch", "-w", help=HELP.argo.watch)] = False,
    interval: Annotated[float, typer.Option("--interval", "-i", help=HELP.argo.interval)] = 3.0,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Show the sync and health of an Argo CD application, and check each image it pins.

    An image the application pins as `<image>:<tag>@<digest>` in its kustomize images is checked
    against the digest its tag names in the registry now. Without --watch, the command exits 1
    when the status cannot be read, a tag names another digest, or a registry gives no digest.
    """
    _validate_k8s_name(name, "application name")
    if dry_run or is_dry_run():
        from devops_cli.argo.argo_plans import plan_argocd_apps_status

        render_request_plan(
            f"Plan for Argo CD application '{name}' status",
            plan_argocd_apps_status(name=name),
        )
        return

    def _build_status_panel() -> tuple[PanelPayload, bool]:
        settings = load_settings()
        base, headers = _argocd(settings)
        try:
            with _argocd_client(settings) as client:
                resp = argocd_api_request(
                    settings,
                    headers,
                    lambda sent: client.get(
                        f"{base}/api/v1/applications/{name}",
                        headers=sent,
                        timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
                    ),
                )
            item = resp.json()
            app_info = ArgoCDApp.from_api_item(item)
        except Exception as exc:
            panel = format_argo_app_status_panel(
                name=name, sync_status="", health_status="", revision="", error=str(exc)
            )
            return panel, False
        checks = _check_image_pins(item)
        panel = format_argo_app_status_panel(
            name=app_info.name,
            sync_status=app_info.sync_status,
            health_status=app_info.health_status,
            revision=app_info.revision,
            images=[_pin_check_line(check) for check in checks],
        )
        return panel, all(check.in_step for check in checks)

    if watch:
        from devops_cli.watchers.live_resource import LiveResourceWatcher

        LiveResourceWatcher(
            lambda: _build_status_panel()[0].render(),
            interval_seconds=interval,
            name="argo_app_status",
        ).watch()
        return
    panel, ok = _build_status_panel()
    print(panel)
    if not ok:
        raise typer.Exit(1)


def _check_image_pins(item: dict[str, Any]) -> list[PinCheck]:
    """Check each image the application pins against its public registry; none, no request."""
    pins = kustomize_image_pins(item)
    if not pins:
        return []
    with new_http_client(level=EgressLevel.PUBLIC) as client:
        return check_pins(pins, client, timeout=DEFAULT_HTTP_TIMEOUT_SECONDS)


def _short_digest(digest: str) -> str:
    algorithm, _, value = digest.partition(":")
    return f"{algorithm}:{value[:12]}" if value else digest


def _pin_check_line(check: PinCheck) -> tuple[bool, str]:
    """The panel line of one pin check, with whether it is in step."""
    pinned = _short_digest(check.pin.digest)
    if check.error is not None:
        text = MESSAGES.output.argo_image_unread.format(
            image=check.pin.image, pinned=pinned, error=check.error
        )
    elif check.in_step:
        text = MESSAGES.output.argo_image_in_step.format(image=check.pin.image, digest=pinned)
    else:
        text = MESSAGES.output.argo_image_moved.format(
            image=check.pin.image, pinned=pinned, current=_short_digest(check.current or "")
        )
    return check.in_step, text


# =============================================================================
# Command: devops argo cd apps bootstrap-gitops
# =============================================================================


@cd_apps_app.command("bootstrap-gitops")
@dry_run_class("request-plan")
def cd_apps_bootstrap_gitops(
    root_app_path: Annotated[
        Path,
        typer.Option(
            "--root-app",
            "-f",
            help=HELP.argo.app_of_apps_manifest,
        ),
    ] = Path("k8s/argocd/bootstrap/bootstrap.yaml"),
    context: Annotated[
        str | None,
        typer.Option("--context", "-c", help=HELP.options.context),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Apply the GitOps root Application to bootstrap local project orchestration."""
    if dry_run or is_dry_run():
        from devops_cli.argo.argo_plans import plan_argocd_bootstrap_gitops

        render_request_plan(
            "Plan for bootstrapping GitOps root application",
            plan_argocd_bootstrap_gitops(root_app_path, context=context),
        )
        return
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
        raise typer.Exit(1) from exc

    print_success(f"GitOps root Application '{applied.name}' applied from {root_app_path}")


# =============================================================================
# Command: devops argo cd apps retire-helm-records
# =============================================================================


def _print_retirement_plan(plan: RetirementPlan) -> None:
    """One row for each release that an Application renders, then what Argo CD did not apply."""
    m = MESSAGES.argo
    if plan.releases:
        print_table(
            m.helm_records_table_title,
            ["Release", "Namespace", "Application", "Result"],
            [
                [
                    release.name,
                    release.namespace,
                    release.application,
                    m.helm_records_qualifies.format(count=len(release.records))
                    if release.qualifies
                    else m.helm_records_refused.format(count=len(release.unapplied)),
                ]
                for release in plan.releases
            ],
        )
    else:
        print_info(m.helm_records_none, prefix=False)
    for release in plan.releases:
        for ref in release.unapplied:
            print_info(
                m.helm_records_unapplied.format(
                    release=release.name,
                    namespace=release.namespace,
                    object=ref,
                    application=release.application,
                ),
                prefix=False,
                safe=True,
            )
    if plan.kept:
        print_info(m.helm_records_kept.format(releases=", ".join(plan.kept)), prefix=False)


@cd_apps_app.command("retire-helm-records")
def cd_apps_retire_helm_records(
    confirm: Annotated[
        bool, typer.Option("--confirm", help=HELP.argo.retire_helm_records_confirm)
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.options.context)
    ] = None,
) -> None:
    """Delete the Helm release records of the charts that Argo CD renders.

    Helm then forgets those releases, and every object stays. A release qualifies when Argo CD
    applied each of its objects. Without --confirm the command prints the plan only.
    """
    from devops_cli.commands.k8s.cluster_runtime import resolve_effective_context
    from devops_cli.core.validation import validate_k8s_context_name

    effective_context = resolve_effective_context(context)
    if effective_context:
        validate_k8s_context_name(effective_context, "context")
    if dry_run or is_dry_run():
        render_request_plan(
            MESSAGES.argo.helm_records_dry_run_heading,
            dry_run_helm_record_retirement(effective_context),
            (MESSAGES.dry_run.placeholders_note,),
        )
        return
    plan = plan_helm_record_retirement(effective_context)
    _print_retirement_plan(plan)
    qualifying = plan.qualifying
    if not qualifying:
        return
    if not confirm:
        print_info(
            MESSAGES.argo.helm_records_confirm_hint.format(
                count=sum(len(release.records) for release in qualifying),
                releases=len(qualifying),
            ),
            prefix=False,
        )
        return

    def _retired(release: HelmRelease) -> None:
        print_success(
            MESSAGES.argo.helm_records_retired.format(
                count=len(release.records), release=release.name, namespace=release.namespace
            )
        )

    retired = retire_helm_records(plan, effective_context, progress=_retired)
    print_success(MESSAGES.argo.helm_records_done.format(releases=len(retired)))


# =============================================================================
# Command: devops argo workflows (list, submit, logs)
# =============================================================================


@workflows_app.command("list")
@dry_run_class("request-plan")
def workflows_list(
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """List Argo Workflows."""
    if dry_run or is_dry_run():
        from devops_cli.argo.argo_plans import plan_argo_workflows_list

        render_request_plan(
            "Plan for listing Argo Workflows",
            plan_argo_workflows_list(namespace=_namespace(namespace)),
        )
        return
    workflows = get_argo_crd_service().list_workflows(namespace=_namespace(namespace))
    print_table(
        title=MESSAGES.argo.table_title_workflows,
        columns=[("Name", "cyan"), "Phase", "Progress", "Started", "Finished"],
        rows=[
            [wf.name, wf.phase, wf.progress or "—", wf.started_at or "—", wf.finished_at or "—"]
            for wf in workflows
        ],
    )


@workflows_app.command("submit")
@dry_run_class("request-plan")
def workflows_submit(
    file: Annotated[Path, typer.Argument(help=HELP.argo.workflow_file)],
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = None,
    wait: Annotated[bool, typer.Option("--wait", "-w", help=HELP.argo.wait)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Submit an Argo Workflow from a YAML file."""
    target_ns = _namespace(namespace)
    if dry_run or is_dry_run():
        from devops_cli.argo.argo_plans import plan_argo_workflows_submit

        render_request_plan(
            f"Plan for submitting Argo Workflow from {file}",
            plan_argo_workflows_submit(file, namespace=target_ns),
        )
        return
    service = get_argo_crd_service()
    submitted = service.submit_workflow(_load_manifest(file.resolve()), namespace=target_ns)
    print_success(
        MESSAGES.argo.workflow_submitted.format(name=submitted.name, phase=submitted.phase)
    )
    if wait:
        final = _await_workflow(service, submitted.name, target_ns)
        print_info(MESSAGES.argo.workflow_finished.format(name=final.name, phase=final.phase))
        if final.phase in CONST_ARGO_WORKFLOW_FAILURE_PHASES:
            raise typer.Exit(1)


@workflows_app.command("logs")
@dry_run_class("request-plan")
def workflows_logs(
    name: Annotated[str, typer.Argument(help=HELP.argo.workflow_name)],
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = None,
    container: Annotated[
        str, typer.Option("--container", "-c", help=HELP.argo.container)
    ] = CONST_ARGO_DEFAULT_LOG_CONTAINER,
    follow: Annotated[bool, typer.Option("--follow", "-f", help=HELP.argo.follow)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Stream logs for an Argo Workflow."""
    target_ns = _namespace(namespace)
    if dry_run or is_dry_run():
        from devops_cli.argo.argo_plans import plan_argo_workflows_logs

        render_request_plan(
            f"Plan for streaming logs of Argo Workflow '{name}'",
            plan_argo_workflows_logs(name, namespace=target_ns, container=container),
        )
        return
    from devops_cli.k8s.service import KubernetesService

    target_ns = _namespace(namespace)
    crd_svc = get_argo_crd_service()
    pods = crd_svc.workflow_pod_names(name, namespace=target_ns)
    if not pods:
        print_info(MESSAGES.argo.workflow_no_pods.format(name=name), prefix=False)
        return

    service = KubernetesService.get_instance()
    try:
        stream = service.read_pod_logs(
            pods[0], namespace=target_ns, container=container, follow=follow
        )
    except Exception as exc:
        if is_not_found_error(exc):
            v1_pods = crd_svc.workflow_pod_names(
                name, namespace=target_ns, version=CONST_ARGO_POD_NAME_V1
            )
            if v1_pods and v1_pods != pods:
                pods = v1_pods
                stream = service.read_pod_logs(
                    pods[0], namespace=target_ns, container=container, follow=follow
                )
            else:
                raise
        else:
            raise

    for i, pod in enumerate(pods):
        print_info(f"── {pod} ──", prefix=False)
        pod_stream = (
            stream
            if i == 0
            else service.read_pod_logs(pod, namespace=target_ns, container=container, follow=follow)
        )
        for line in pod_stream:
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
@dry_run_class("request-plan")
def rollouts_list(
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """List Argo Rollouts."""
    if dry_run or is_dry_run():
        from devops_cli.argo.argo_plans import plan_argo_rollouts_list

        render_request_plan(
            "Plan for listing Argo Rollouts",
            plan_argo_rollouts_list(namespace=_namespace(namespace)),
        )
        return
    rollouts = get_argo_crd_service().list_rollouts(namespace=_namespace(namespace))
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
@dry_run_class("request-plan")
def rollouts_status(
    name: Annotated[str, typer.Argument(help=HELP.argo.rollout_name)],
    namespace: Annotated[
        str | None, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = None,
    watch: Annotated[bool, typer.Option("--watch", "-w", help=HELP.argo.watch)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Show status for an Argo Rollout."""
    target_ns = _namespace(namespace)
    if dry_run or is_dry_run():
        from devops_cli.argo.argo_plans import plan_argo_rollouts_status

        render_request_plan(
            f"Plan for Argo Rollout '{name}' status",
            plan_argo_rollouts_status(name, namespace=target_ns),
        )
        return
    service = get_argo_crd_service()

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
@dry_run_class("request-plan")
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
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help=HELP.options.json_output)
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Synchronize an application across a fleet of Kubernetes clusters with bounded concurrency."""
    _validate_k8s_name(app_name, "application name")
    cluster_list = [c.strip() for c in clusters.split(",") if c.strip()]
    for c in cluster_list:
        _validate_k8s_name(c, "cluster name")

    if dry_run or is_dry_run():
        from devops_cli.argo.argo_plans import plan_argo_fleet_sync
        from devops_cli.argo.fleet import resolve_cluster_app_name
        from devops_cli.models.argo import ArgoFleetAppTarget, ArgoFleetSyncResult

        planned = plan_argo_fleet_sync(
            app_name=app_name,
            clusters=cluster_list,
            prune=prune,
            force=force,
        )
        resolved = resolve_format(output_format, json_output=json_output)
        if resolved != CONST_OUTPUT_FORMAT_TABLE:
            result = ArgoFleetSyncResult(
                fleet_name=fleet_name,
                targets=[
                    ArgoFleetAppTarget(
                        app_name=resolve_cluster_app_name(app_name, c),
                        cluster=c,
                        status="DryRun",
                        message="Dry run simulation succeeded",
                    )
                    for c in cluster_list
                ],
                total_synced=len(cluster_list),
                total_failed=0,
                success=True,
                dry_run=True,
                requests=[r.__dict__ for r in planned],
            )
            emit_serialized(result.model_dump(), resolved)
            return
        render_request_plan(
            f"Plan for syncing fleet '{fleet_name}' application '{app_name}'",
            planned,
        )
        return

    from devops_cli.argo.fleet import render_fleet_sync_table, sync_fleet

    result = sync_fleet(
        app_name=app_name,
        clusters=cluster_list,
        fleet_name=fleet_name,
        prune=prune,
        force=force,
        max_concurrency=concurrency,
        dry_run=is_dry_run(),
    )

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(result.model_dump(), resolved)
    else:
        print(render_fleet_sync_table(result))

    if not result.success:
        raise typer.Exit(1)


@app.command("sync")
@dry_run_class("request-plan")
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
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help=HELP.options.json_output)
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
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
            output_format=output_format,
            json_output=json_output,
            dry_run=dry_run or is_dry_run(),
        )
    else:
        if dry_run or is_dry_run():
            from devops_cli.argo.argo_plans import plan_argocd_apps_sync

            planned = plan_argocd_apps_sync(name=name, prune=prune, force=force)
            resolved = resolve_format(output_format, json_output=json_output)
            if resolved != CONST_OUTPUT_FORMAT_TABLE:
                emit_serialized(
                    {"dry_run": True, "requests": [r.__dict__ for r in planned]}, resolved
                )
                return
            render_request_plan(f"Plan for syncing Argo CD application '{name}'", planned)
            return
        cd_apps_sync(name=name, prune=prune, force=force)


@rollouts_app.command("promote")
@dry_run_class("request-plan")
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
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Promote an in-progress Argo Rollout to the next progressive step or full release."""
    if dry_run or is_dry_run():
        from devops_cli.argo.argo_plans import plan_argo_rollouts_promote

        render_request_plan(
            f"Plan for promoting rollout '{name}'",
            plan_argo_rollouts_promote(name, namespace=namespace, full=full),
        )
        return
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
@dry_run_class("request-plan")
def rollouts_abort(
    name: Annotated[str, typer.Argument(help=HELP.argo.rollout_name)],
    namespace: Annotated[
        str, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = "default",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Abort an in-progress Argo Rollout and revert immediately to the stable replica set."""
    if dry_run or is_dry_run():
        from devops_cli.argo.argo_plans import plan_argo_rollouts_abort

        render_request_plan(
            f"Plan for aborting rollout '{name}'",
            plan_argo_rollouts_abort(name, namespace=namespace),
        )
        return
    from devops_cli.argo.rollouts import abort_rollout

    success = abort_rollout(name, namespace=namespace, dry_run=is_dry_run())
    if not success:
        print_error(f"Failed to abort rollout '{name}' in namespace '{namespace}'")
        raise typer.Exit(1)
    print_success(f"Successfully aborted rollout '{name}' in namespace '{namespace}'")


@rollouts_app.command("restart")
@dry_run_class("request-plan")
def rollouts_restart(
    name: Annotated[str, typer.Argument(help=HELP.argo.rollout_name)],
    namespace: Annotated[
        str, typer.Option("--namespace", "-n", help=HELP.options.namespace)
    ] = "default",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Perform a restart rollout across all pods in an Argo Rollout."""
    if dry_run or is_dry_run():
        from devops_cli.argo.argo_plans import plan_argo_rollouts_restart

        render_request_plan(
            f"Plan for restarting rollout '{name}'",
            plan_argo_rollouts_restart(name, namespace=namespace),
        )
        return
    from devops_cli.argo.rollouts import restart_rollout

    success = restart_rollout(name, namespace=namespace, dry_run=is_dry_run())
    if not success:
        print_error(f"Failed to restart rollout '{name}' in namespace '{namespace}'")
        raise typer.Exit(1)
    print_success(f"Successfully restarted rollout '{name}' in namespace '{namespace}'")


@rollouts_app.command("analyze")
@dry_run_class("request-plan")
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
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help=HELP.options.json_output)
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help=HELP.options.dry_run),
    ] = False,
) -> None:
    """Evaluate metric rollback gates and trigger automated rollback on threshold violation."""
    if dry_run or is_dry_run():
        from devops_cli.argo.argo_plans import plan_argo_rollouts_analyze
        from devops_cli.models.argo import RolloutAnalysisResult

        planned = plan_argo_rollouts_analyze(
            name=name,
            namespace=namespace,
            error_rate_threshold=error_rate_threshold,
            auto_abort=auto_abort,
        )
        resolved = resolve_format(output_format, json_output=json_output)
        if resolved != CONST_OUTPUT_FORMAT_TABLE:
            result = RolloutAnalysisResult(
                rollout_name=name,
                namespace=namespace,
                passed=True,
                metric_results=[],
                action_taken="promoted",
                reason="Dry run simulated rollout analysis",
                dry_run=True,
                requests=[r.__dict__ for r in planned],
            )
            emit_serialized(result.model_dump(), resolved)
            return
        render_request_plan(f"Plan for analyzing rollout '{name}'", planned)
        return
    from devops_cli.argo.rollouts import evaluate_rollout_gate, render_rollout_analysis_table
    from devops_cli.models.argo import RolloutMetricThreshold

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
        dry_run=dry_run or is_dry_run(),
    )

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(result.model_dump(), resolved)
    else:
        print(render_rollout_analysis_table(result))

    if not result.passed:
        if resolved == CONST_OUTPUT_FORMAT_TABLE:
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
    output_format: str = DEFAULT_TABLE_FORMAT,
    json_output: bool = False,
) -> None:
    """Execute a single-cycle manifest drift inspection and optional reconciliation."""
    from devops_cli.argo.gitops import (
        render_gitops_drift_table,
        render_gitops_sync_table,
    )
    from devops_cli.output import print_info

    drift = watcher.scan_drift(detect_cold_drift=True)
    sync_res = watcher.sync_now(drift) if drift else None

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        out = {
            "events": [e.model_dump() for e in drift],
            "synced": sync_res.model_dump() if sync_res else None,
        }
        emit_serialized(out, resolved)
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
@dry_run_class("request-plan")
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
    ] = "cluster",
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
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help=HELP.options.json_output)
    ] = False,
) -> None:
    """Monitor Kubernetes and Helm manifests for drift and trigger instant ArgoCD sync."""
    _validate_k8s_name(app_name, "application name")
    if mode not in ("api", "webhook"):
        print_error(f"Unsupported GitOps sync mode '{mode}'. Allowed: api, webhook")
        raise typer.Exit(1)

    if dry_run or is_dry_run():
        from devops_cli.argo.argo_plans import plan_argo_gitops_watch

        planned = plan_argo_gitops_watch(
            app_name=app_name,
            mode=mode,
            prune=prune,
            force=force,
        )
        resolved = resolve_format(output_format, json_output=json_output)
        if resolved != CONST_OUTPUT_FORMAT_TABLE:
            emit_serialized({"dry_run": True, "requests": [r.__dict__ for r in planned]}, resolved)
            return
        render_request_plan(f"Plan for GitOps watch on '{app_name}'", planned)
        return

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
        _handle_gitops_once(watcher, output_format, json_output)
    else:
        _handle_gitops_continuous(watcher, path, app_name, max_events, json_output)


@gitops_app.command("drift")
@dry_run_class("no-external-request")
def gitops_drift(
    path: Annotated[
        str,
        typer.Option(
            "--path",
            "-p",
            help="Comma-separated paths or directories of manifests to inspect",
        ),
    ] = "k8s",
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
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
    from devops_cli.output import print_info

    paths = _parse_manifest_paths(path)
    state = compute_manifest_state(paths)
    persisted = load_persisted_manifest_state(paths)

    if persisted is not None:
        drift = scan_manifest_drift(persisted, state)
    else:
        drift = inspect_git_manifest_drift(paths)

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        data = {"manifests": [e.model_dump() for e in drift]}
        emit_serialized(data, resolved)
    elif drift:
        print(render_gitops_drift_table(drift))
    else:
        print_info("No manifest drift detected across watched paths (working tree clean)")


@gitops_app.command("sync")
@dry_run_class("request-plan")
def gitops_sync(
    app_name: Annotated[
        str,
        typer.Option("--app-name", "-a", help=HELP.argo.app_name),
    ] = "cluster",
    mode: Annotated[
        str,
        typer.Option("--mode", "-m", help="Synchronization trigger mode ('api' or 'webhook')"),
    ] = "api",
    prune: Annotated[bool, typer.Option("--prune", help=HELP.argo.prune)] = False,
    force: Annotated[bool, typer.Option("--force", help=HELP.options.force)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[
        bool, typer.Option("--json", "-j", help=HELP.options.json_output)
    ] = False,
) -> None:
    """Trigger an immediate GitOps synchronization for an ArgoCD application."""
    _validate_k8s_name(app_name, "application name")
    if mode not in ("api", "webhook"):
        print_error(f"Unsupported GitOps sync mode '{mode}'. Allowed: api, webhook")
        raise typer.Exit(1)

    if dry_run or is_dry_run():
        from devops_cli.argo.argo_plans import plan_argo_gitops_sync
        from devops_cli.models.argo import GitOpsSyncTriggerResult

        planned = plan_argo_gitops_sync(
            app_name=app_name,
            mode=mode,
            prune=prune,
            force=force,
        )
        resolved = resolve_format(output_format, json_output=json_output)
        if resolved != CONST_OUTPUT_FORMAT_TABLE:
            result = GitOpsSyncTriggerResult(
                app_name=app_name,
                changed_files=[],
                status="DryRun",
                sync_mode=mode,
                message="Simulated GitOps synchronization trigger succeeded",
                duration_seconds=0.0,
                timestamp=0.0,
                success=True,
                dry_run=True,
                requests=[r.__dict__ for r in planned],
            )
            emit_serialized(result.model_dump(), resolved)
            return
        render_request_plan(f"Plan for GitOps sync on '{app_name}'", planned)
        return

    from devops_cli.argo.gitops import render_gitops_sync_table, trigger_argocd_sync

    result = trigger_argocd_sync(
        app_name=app_name,
        prune=prune,
        force=force,
        dry_run=is_dry_run(),
        sync_mode=mode,  # type: ignore[arg-type]
    )

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(result.model_dump(), resolved)
    else:
        print(render_gitops_sync_table([result]))

    if not result.success:
        raise typer.Exit(1)
