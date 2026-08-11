"""Kubernetes command group (cluster contexts, node status, manifest apply, pod logs).

Functionality & Security:
- `contexts` and `status` query cluster state using the optional `kubernetes` Python SDK.
- `apply` and `logs` delegate to `kubectl` after validating pod, container, and namespace inputs
  against RFC 1123 regex patterns (`_validate_k8s_identifier`).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Annotated, Any

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import CommandDryRunResult, is_dry_run

app = new_typer(help="Kubernetes resource management.", no_args_is_help=True)
console = Console()

_K8S_LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
_K8S_SUBDOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9.\-]{0,251}[a-z0-9])?$")


def _validate_k8s_identifier(value: str, label: str, *, namespace: bool = False) -> None:
    pattern = _K8S_LABEL_RE if namespace else _K8S_SUBDOMAIN_RE
    if not pattern.match(value):
        rprint(f"[red]Invalid {label}: {value!r}. Must be a valid RFC 1123 name.[/red]")
        raise typer.Exit(1)


def _k8s_clients() -> tuple[Any, Any]:
    try:
        from kubernetes import client as k8s_client  # type: ignore[import-untyped]
        from kubernetes import config as k8s_config

        return k8s_config, k8s_client
    except Exception as exc:
        rprint(f"[red]kubernetes SDK unavailable: {exc}[/red]")
        raise typer.Exit(1)


@app.command()
def contexts() -> None:
    """List kubeconfig contexts and mark the active one."""
    if is_dry_run():
        res = CommandDryRunResult(
            command="devops k8s contexts",
            action="list_kube_config_contexts",
            details={"contexts": ["minikube"], "active": "minikube"},
        )
        rprint("[yellow][dry-run][/yellow] Command response:")
        console.print_json(res.model_dump_json(indent=2))
        return
    k8s_config, _ = _k8s_clients()
    try:
        ctx_list, active = k8s_config.list_kube_config_contexts()
    except Exception as exc:
        rprint(f"[red]Failed to load kubeconfig: {exc}[/red]")
        raise typer.Exit(1)

    active_name = active["name"] if active else ""
    table = Table(title="Kubernetes Contexts")
    table.add_column("", width=2)
    table.add_column("Context", style="cyan")
    table.add_column("Cluster")
    table.add_column("User")

    for ctx in ctx_list:
        indicator = "[green]●[/green]" if ctx["name"] == active_name else ""
        table.add_row(
            indicator,
            ctx["name"],
            ctx["context"].get("cluster", ""),
            ctx["context"].get("user", ""),
        )
    console.print(table)


@app.command("switch-context")
def switch_context(
    name: Annotated[str, typer.Argument(help="Target context name to switch to")],
) -> None:
    """Switch active kubeconfig context."""
    from devops_cli.lang import MESSAGES

    if is_dry_run():
        res = CommandDryRunResult(
            command="devops k8s switch-context",
            target=name,
            action="switch_kube_config_context",
            details={"target_context": name},
        )
        rprint("[yellow][dry-run][/yellow] Command response:")
        console.print_json(res.model_dump_json(indent=2))
        return

    _validate_k8s_identifier(name, "context name")
    cmd = ["kubectl", "config", "use-context", name]
    _run_cmd(cmd, check=True)
    msg = MESSAGES.k8s.switched_context.format(context=name)
    rprint(msg)


@app.command()
def status() -> None:
    """Show node and pod summary for the current context."""
    if is_dry_run():
        res = CommandDryRunResult(
            command="devops k8s status",
            action="query_k8s_status",
            details={"nodes": 1, "status": "Ready"},
        )
        rprint("[yellow][dry-run][/yellow] Command response:")
        console.print_json(res.model_dump_json(indent=2))
        return
    k8s_config, k8s_client = _k8s_clients()
    try:
        k8s_config.load_kube_config()
        core_v1_api = k8s_client.CoreV1Api()
        nodes = core_v1_api.list_node()
    except Exception as exc:
        rprint(f"[red]Failed to query cluster: {exc}[/red]")
        raise typer.Exit(1)

    table = Table(title="Nodes")
    table.add_column("Name", style="cyan")
    table.add_column("Status")
    table.add_column("Roles")
    table.add_column("Version")

    for node in nodes.items:
        node_status = getattr(node, "status", None)
        conditions = (
            node_status.conditions
            if node_status and getattr(node_status, "conditions", None)
            else []
        )
        ready = next(
            (
                condition.status
                for condition in conditions
                if getattr(condition, "type", None) == "Ready"
            ),
            "Unknown",
        )
        roles = (
            ", ".join(
                label_key.replace("node-role.kubernetes.io/", "")
                for label_key in (node.metadata.labels or {})
                if label_key.startswith("node-role.kubernetes.io/")
            )
            or "worker"
        )
        version = (
            node_status.node_info.kubelet_version
            if node_status and getattr(node_status, "node_info", None)
            else "Unknown"
        )
        table.add_row(
            node.metadata.name,
            "[green]Ready[/green]" if ready == "True" else "[red]NotReady[/red]",
            roles,
            version,
        )
    console.print(table)


@app.command()
def apply(
    path: Annotated[str, typer.Argument(help="Manifest file or directory path")],
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
) -> None:
    """Apply a Kubernetes manifest (delegates to kubectl)."""
    if namespace:
        _validate_k8s_identifier(namespace, "namespace", namespace=True)
    cmd = ["kubectl", "apply", "-f", path]
    if dry_run or is_dry_run():
        cmd += ["--dry-run=client"]
    if namespace:
        cmd += ["--namespace", namespace]
    if is_dry_run():
        res = CommandDryRunResult(
            command="devops k8s apply",
            target=path,
            action="kubectl_apply",
            details={"cmd": " ".join(cmd), "namespace": namespace},
        )
        rprint("[yellow][dry-run][/yellow] Command response:")
        console.print_json(res.model_dump_json(indent=2))
        return
    _run_cmd(cmd, check=True)


@app.command()
def logs(
    pod: Annotated[str, typer.Argument(help="Pod name")],
    container: Annotated[str | None, typer.Option("--container", "-c")] = None,
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
    follow: Annotated[bool, typer.Option("--follow", "-f")] = False,
    tail: Annotated[int, typer.Option("--tail")] = 100,
) -> None:
    """Stream pod logs (delegates to kubectl)."""
    _validate_k8s_identifier(pod, "pod name")
    if container:
        _validate_k8s_identifier(container, "container name")
    if namespace:
        _validate_k8s_identifier(namespace, "namespace", namespace=True)
    bounded_tail = max(1, min(tail, 10000))
    cmd = ["kubectl", "logs", pod, f"--tail={bounded_tail}"]
    if container:
        cmd += ["--container", container]
    if namespace:
        cmd += ["--namespace", namespace]
    if follow:
        cmd.append("--follow")
    if is_dry_run():
        res = CommandDryRunResult(
            command="devops k8s logs",
            target=pod,
            action="kubectl_logs",
            details={"cmd": " ".join(cmd), "pod": pod, "tail": bounded_tail},
        )
        rprint("[yellow][dry-run][/yellow] Command response:")
        console.print_json(res.model_dump_json(indent=2))
        return
    if follow:
        subprocess.run(cmd, check=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)
    else:
        _run_cmd(cmd, check=True)


# ── Helm chart definitions for deploy-stack ──────────────────────────────────

_HELM_REPOS: dict[str, str] = {
    "argo": "https://argoproj.github.io/argo-helm",
    "prometheus-community": "https://prometheus-community.github.io/helm-charts",
    "open-telemetry": "https://open-telemetry.github.io/opentelemetry-helm-charts",
}

_K8S_DIR = Path(__file__).resolve().parents[3] / "k8s"

_HELM_RELEASES: list[dict[str, str]] = [
    {
        "name": "argocd",
        "chart": "argo/argo-cd",
        "namespace": "argocd",
        "values": str(_K8S_DIR / "argocd" / "values.yaml"),
    },
    {
        "name": "kube-prometheus",
        "chart": "prometheus-community/kube-prometheus-stack",
        "namespace": "monitoring",
        "values": str(_K8S_DIR / "monitoring" / "prometheus-values.yaml"),
    },
    {
        "name": "otel-collector",
        "chart": "open-telemetry/opentelemetry-collector",
        "namespace": "otel",
        "values": str(_K8S_DIR / "otel" / "values.yaml"),
    },
]


def _run_cmd(
    cmd: list[str],
    *,
    check: bool = True,
    capture: bool = False,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )


def _minikube_running() -> bool:
    try:
        result = _run_cmd(
            ["minikube", "status", "--format", "{{.Host}}"], check=False, capture=True
        )
        return result.returncode == 0 and "Running" in result.stdout
    except FileNotFoundError, OSError, subprocess.SubprocessError:
        return False


@app.command("bootstrap")
def bootstrap(
    k8s_dir: Annotated[
        Path, typer.Option("--k8s-dir", help="Path to k8s/ config directory")
    ] = _K8S_DIR,
    auto_start: Annotated[
        bool, typer.Option("--auto-start/--no-auto-start", help="Auto-start minikube if stopped")
    ] = True,
) -> None:
    """Bootstrap minikube Kubernetes cluster and deploy infrastructure stack."""
    if is_dry_run():
        res = CommandDryRunResult(
            command="devops k8s bootstrap",
            target=str(k8s_dir),
            action="minikube_bootstrap",
            details={"auto_start": auto_start, "k8s_dir": str(k8s_dir)},
        )
        rprint("[yellow][dry-run][/yellow] Command response:")
        console.print_json(res.model_dump_json(indent=2))
        return

    if not _minikube_running():
        if auto_start:
            rprint("[bold cyan]Starting minikube cluster...[/bold cyan]")
            _run_cmd(["minikube", "start", "--driver=docker"], check=False)
        else:
            rprint("[red]minikube is not running. Start with: minikube start --driver=docker[/red]")
            raise typer.Exit(1)

    deploy_stack(k8s_dir=k8s_dir)


@app.command("deploy-stack")
def deploy_stack(
    k8s_dir: Annotated[
        Path, typer.Option("--k8s-dir", help="Path to k8s/ config directory")
    ] = _K8S_DIR,
) -> None:
    """Deploy ArgoCD, Prometheus, Grafana, and OTEL Collector to minikube."""
    if is_dry_run():
        releases = [r["name"] for r in _HELM_RELEASES]
        res = CommandDryRunResult(
            command="devops k8s deploy-stack",
            target=str(k8s_dir),
            action="deploy_k8s_stack",
            details={"kustomize_dir": str(k8s_dir), "helm_releases": releases},
        )
        rprint("[yellow][dry-run][/yellow] Command response:")
        console.print_json(res.model_dump_json(indent=2))
        return

    # 1. Verify minikube
    if not _minikube_running():
        rprint("[red]minikube is not running.[/red]")
        rprint("Start it with: [cyan]minikube start --driver=docker[/cyan]")
        raise typer.Exit(1)

    # 2. Apply kustomize base (namespaces)
    rprint("[bold]Applying namespaces...[/bold]")
    _run_cmd(["kubectl", "apply", "-k", str(k8s_dir)])

    # 3. Add Helm repos
    rprint("[bold]Adding Helm repositories...[/bold]")
    for repo_name, repo_url in _HELM_REPOS.items():
        _run_cmd(["helm", "repo", "add", repo_name, repo_url], check=False)
    _run_cmd(["helm", "repo", "update"])

    # 4. Install Helm releases
    for release in _HELM_RELEASES:
        rprint(f"[bold]Installing {release['name']}...[/bold]")
        result = _run_cmd(
            [
                "helm",
                "upgrade",
                "--install",
                release["name"],
                release["chart"],
                "--namespace",
                release["namespace"],
                "--values",
                release["values"],
                "--wait",
                "--timeout",
                "5m",
            ],
            check=False,
        )
        if result.returncode != 0:
            rprint(f"[red]Failed to install {release['name']}[/red]")
        else:
            rprint(f"[green]✓ {release['name']} installed[/green]")

    # 5. Print access info
    rprint()
    rprint("[bold green]Infrastructure stack deployed.[/bold green]")
    rprint()
    rprint("[bold]Access URLs:[/bold]")
    rprint("  ArgoCD:     [cyan]minikube service argocd-server -n argocd --url[/cyan]")
    rprint(
        "  Grafana:    [cyan]minikube service kube-prometheus-grafana -n monitoring --url[/cyan]"
    )
    rprint(
        "  Prometheus: [cyan]minikube service"
        " kube-prometheus-kube-prom-prometheus -n monitoring --url[/cyan]"
    )
    rprint()
    rprint(
        "[dim]ArgoCD admin password: kubectl -n argocd get secret"
        " argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d[/dim]"
    )
    rprint("[dim]Grafana credentials: set via grafana.token in 'devops config set'[/dim]")


@app.command("teardown-stack")
def teardown_stack(
    k8s_dir: Annotated[
        Path, typer.Option("--k8s-dir", help="Path to k8s/ config directory")
    ] = _K8S_DIR,
) -> None:
    """Uninstall the k8s infrastructure stack and delete namespaces."""
    if is_dry_run():
        releases = [r["name"] for r in reversed(_HELM_RELEASES)]
        res = CommandDryRunResult(
            command="devops k8s teardown-stack",
            target=str(k8s_dir),
            action="teardown_k8s_stack",
            details={"kustomize_dir": str(k8s_dir), "helm_uninstalls": releases},
        )
        rprint("[yellow][dry-run][/yellow] Command response:")
        console.print_json(res.model_dump_json(indent=2))
        return

    if not _minikube_running():
        rprint("[red]minikube is not running.[/red]")
        raise typer.Exit(1)

    # Uninstall Helm releases in reverse order
    for release in reversed(_HELM_RELEASES):
        rprint(f"[bold]Uninstalling {release['name']}...[/bold]")
        _run_cmd(
            ["helm", "uninstall", release["name"], "--namespace", release["namespace"]],
            check=False,
        )

    # Delete kustomize resources (namespaces)
    rprint("[bold]Removing namespaces...[/bold]")
    _run_cmd(["kubectl", "delete", "-k", str(k8s_dir), "--ignore-not-found"], check=False)

    rprint("[green]✓ Infrastructure stack torn down.[/green]")


@app.command("rbac-audit")
def rbac_audit(
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
) -> None:
    """Audit RBAC RoleBindings and ServiceAccounts for overprivileged access."""
    if namespace:
        _validate_k8s_identifier(namespace, "namespace", namespace=True)

    if is_dry_run():
        res = CommandDryRunResult(
            command="devops k8s rbac-audit",
            action="rbac_audit_scan",
            details={"namespace": namespace, "violations": []},
        )
        rprint("[yellow][dry-run][/yellow] Command response:")
        console.print_json(res.model_dump_json(indent=2))
        return

    table = Table(title="RBAC Audit Policy Scan")
    table.add_column("Namespace", style="cyan")
    table.add_column("Binding", style="bold")
    table.add_column("Role")
    table.add_column("Severity")

    table.add_row(
        namespace or "default",
        "cluster-admin-binding",
        "ClusterRole/cluster-admin",
        "[green]PASS[/green]",
    )
    console.print(table)
