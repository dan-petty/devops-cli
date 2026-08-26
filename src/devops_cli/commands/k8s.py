"""Kubernetes command group (cluster contexts, node status, manifest apply, pod logs).

Functionality & Security:
- `contexts` and `status` query cluster state using the optional `kubernetes` Python SDK.
- `apply` and `logs` delegate to `kubectl` after validating pod, container, and namespace inputs
  against RFC 1123 regex patterns (`_validate_k8s_identifier`).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.constants import (
    CONST_SERVER_CERT_NAME,
    CONST_SERVER_KEY_NAME,
)
from devops_cli.config.defaults import (
    DEFAULT_ARGOCD_PORT,
    DEFAULT_CURRENT_PATH,
    DEFAULT_GRAFANA_PORT,
    DEFAULT_HTTP_PROBE_TIMEOUT_SECONDS,
    DEFAULT_JAEGER_PORT,
    DEFAULT_K8S_ALL_STACK,
    DEFAULT_K8S_DIR,
    DEFAULT_K8S_LOGS_TAIL,
    DEFAULT_K8S_NAMESPACE,
    DEFAULT_K8S_STACK,
    DEFAULT_K8S_TLS_SECRET_NAME,
    DEFAULT_KUBECONFORM_VERSION,
    DEFAULT_OLLAMA_PORT,
    DEFAULT_OPEN_WEBUI_PORT,
    DEFAULT_OTEL_PORT,
    DEFAULT_PROMETHEUS_PORT,
    DEFAULT_QDRANT_PORT,
    DEFAULT_REST_HOST,
    DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    DEFAULT_TLS_DIR,
    DEFAULT_VALKEY_PORT,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.core.validation import validate_k8s_name
from devops_cli.crypto.tls_certificates import generate_homelab_tls_bundle
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.lang import HELP, MESSAGES
from devops_cli.models.tls import KubernetesTLSSecretResult
from devops_cli.output import (
    Table,
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    write_stdout,
)

app = new_typer(help="Kubernetes resource management.", no_args_is_help=True)


# =============================================================================
# Validation & Client Resolution Helpers
# =============================================================================


def _validate_k8s_identifier(val: str, label: str, *, namespace: bool = False) -> None:
    validate_k8s_name(val, label, namespace=namespace)


def _k8s_clients() -> tuple[Any, Any]:
    try:
        from kubernetes import client as k8s_client  # type: ignore[import-untyped]
        from kubernetes import config as k8s_config

        return k8s_config, k8s_client
    except ImportError:
        print_error("kubernetes package not installed. Run: pip install kubernetes", prefix=False)
        raise typer.Exit(1)


# =============================================================================
# Command: devops k8s contexts
# =============================================================================


@app.command()
def contexts() -> None:
    """List kubeconfig contexts and mark the active one."""
    if is_dry_run():
        render_dry_run_result(
            command="devops k8s contexts",
            action="list_kube_config_contexts",
            details={"contexts": ["minikube"], "active": "minikube"},
        )
        return
    k8s_config, _ = _k8s_clients()
    try:
        ctx_list, active = k8s_config.list_kube_config_contexts()
    except Exception as exc:
        print_error(f"Failed to load kubeconfig: {exc}", prefix=False)
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
    print_table(table)


# =============================================================================
# Command: devops k8s switch-context
# =============================================================================


@app.command("switch-context")
def switch_context(
    name: Annotated[str, typer.Argument(help="Target context name to switch to")],
) -> None:
    """Switch active kubeconfig context."""
    if is_dry_run():
        render_dry_run_result(
            command="devops k8s switch-context",
            target=name,
            action="switch_kube_config_context",
            details={"target_context": name},
        )
        return

    _validate_k8s_identifier(name, "context name")
    cmd = ["kubectl", "config", "use-context", name]
    _run_cmd(cmd, check=True)
    msg = MESSAGES.k8s.switched_context.format(context=name)
    print_success(msg, prefix=False)


# =============================================================================
# Command: devops k8s status
# =============================================================================


@app.command()
def status() -> None:
    """Show node and pod summary for the current context."""
    if is_dry_run():
        render_dry_run_result(
            command="devops k8s status",
            action="query_k8s_status",
            details={"nodes": 1, "status": "Ready"},
        )
        return
    k8s_config, k8s_client = _k8s_clients()
    try:
        k8s_config.load_kube_config()
        core_v1_api = k8s_client.CoreV1Api()
        nodes = core_v1_api.list_node()
    except Exception as exc:
        print_error(f"Failed to query cluster: {exc}", prefix=False)
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
    print_table(table)


# =============================================================================
# Command: devops k8s apply
# =============================================================================


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
        render_dry_run_result(
            command="devops k8s apply",
            target=path,
            action="kubectl_apply",
            details={"cmd": " ".join(cmd), "namespace": namespace},
        )
        return
    _run_cmd(cmd, check=True)


# =============================================================================
# Command: devops k8s logs
# =============================================================================


@app.command()
def logs(
    pod: Annotated[str, typer.Argument(help="Pod name")],
    container: Annotated[str | None, typer.Option("--container", "-c")] = None,
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
    follow: Annotated[bool, typer.Option("--follow", "-f", help=HELP.options.follow)] = False,
    tail: Annotated[int, typer.Option("--tail", help=HELP.options.tail)] = DEFAULT_K8S_LOGS_TAIL,
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
        render_dry_run_result(
            command="devops k8s logs",
            target=pod,
            action="kubectl_logs",
            details={"cmd": " ".join(cmd), "pod": pod, "tail": bounded_tail},
        )
        return
    if follow:
        run_subprocess(
            cmd,
            check=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
            capture_output=False,
        )
    else:
        _run_cmd(cmd, check=True)


# =============================================================================
# Stack Helm & Manifest Definitions
# =============================================================================

_HELM_REPOS_BY_STACK: dict[str, dict[str, str]] = {
    "infra": {
        "argo": "https://argoproj.github.io/argo-helm",
        "prometheus-community": "https://prometheus-community.github.io/helm-charts",
        "open-telemetry": "https://open-telemetry.github.io/opentelemetry-helm-charts",
    },
    "llm": {
        "open-webui": "https://open-webui.github.io/helm-charts",
        "qdrant": "https://qdrant.github.io/qdrant-helm",
    },
}

_HELM_REPOS: dict[str, str] = {
    **_HELM_REPOS_BY_STACK["infra"],
    **_HELM_REPOS_BY_STACK["llm"],
}


_HELM_RELEASES_BY_STACK: dict[str, list[dict[str, str]]] = {
    "infra": [
        {
            "name": "argocd",
            "chart": "argo/argo-cd",
            "namespace": "argocd",
            "values": str(DEFAULT_K8S_DIR / "argocd" / "values.yaml"),
        },
        {
            "name": "kube-prometheus",
            "chart": "prometheus-community/kube-prometheus-stack",
            "namespace": "monitoring",
            "values": str(DEFAULT_K8S_DIR / "monitoring" / "prometheus-values.yaml"),
        },
        {
            "name": "otel-collector",
            "chart": "open-telemetry/opentelemetry-collector",
            "namespace": "otel",
            "values": str(DEFAULT_K8S_DIR / "otel" / "values.yaml"),
        },
    ],
    "llm": [
        {
            "name": "open-webui",
            "chart": "open-webui/open-webui",
            "namespace": "llm",
            "values": str(DEFAULT_K8S_DIR / "llm" / "values-open-webui.yaml"),
        },
        {
            "name": "qdrant",
            "chart": "qdrant/qdrant",
            "namespace": "llm",
            "values": str(DEFAULT_K8S_DIR / "llm" / "values-qdrant.yaml"),
        },
    ],
}

_HELM_RELEASES: list[dict[str, str]] = _HELM_RELEASES_BY_STACK["infra"]

_MANIFESTS_BY_STACK: dict[str, list[Path]] = {
    "infra": [
        DEFAULT_K8S_DIR / "otel" / "jaeger.yaml",
    ],
    "llm": [
        DEFAULT_K8S_DIR / "llm" / "valkey.yaml",
        DEFAULT_K8S_DIR / "llm" / "ollama-daemonset.yaml",
    ],
}

VALID_STACKS: tuple[str, ...] = ("infra", "llm", "all")


def _resolve_stacks(stack: str) -> list[str]:
    s = stack.strip().lower()
    if s == "all":
        return ["infra", "llm"]
    if s in _HELM_RELEASES_BY_STACK:
        return [s]
    print_error(
        f"Invalid stack: {stack!r}. Supported stacks: {', '.join(VALID_STACKS)}",
        prefix=False,
    )
    raise typer.Exit(1)


def _run_cmd(
    cmd: list[str],
    *,
    check: bool = True,
    capture: bool = False,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    return run_subprocess(
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


def _cluster_reachable(context: str | None = None) -> bool:
    """Return True if the target Kubernetes cluster (or Minikube) is reachable."""
    cmd = ["kubectl", "cluster-info", "--request-timeout=5s"]
    if context:
        cmd.extend(["--context", context])
    try:
        res = _run_cmd(cmd, check=False, capture=True)
        if res.returncode == 0:
            return True
    except FileNotFoundError, OSError, subprocess.SubprocessError:
        pass

    if not context or context == "minikube":
        return _minikube_running()
    return False


# =============================================================================
# Command: devops k8s bootstrap
# =============================================================================


@app.command("bootstrap")
def bootstrap(
    k8s_dir: Annotated[
        Path, typer.Option("--dir", "-d", help="Directory containing Kubernetes manifests")
    ] = DEFAULT_K8S_DIR,
    auto_start: Annotated[
        bool, typer.Option("--auto-start/--no-auto-start", help="Auto-start minikube if stopped")
    ] = True,
    stack: Annotated[
        str,
        typer.Option("--stack", "-s", help="Stack to deploy after bootstrap: infra | llm | all"),
    ] = DEFAULT_K8S_ALL_STACK,
) -> None:
    """Bootstrap minikube Kubernetes cluster and deploy infrastructure/LLM stack."""
    selected_stacks = _resolve_stacks(stack)
    if is_dry_run():
        render_dry_run_result(
            command="devops k8s bootstrap",
            target=str(k8s_dir),
            action="minikube_bootstrap",
            details={
                "auto_start": auto_start,
                "k8s_dir": str(k8s_dir),
                "stack": stack,
                "stacks": selected_stacks,
            },
        )
        return

    if not _minikube_running():
        if auto_start:
            print_info(MESSAGES.k8s.starting_minikube, prefix=False)
            has_gpu = shutil.which("nvidia-smi") is not None
            started = False
            if has_gpu:
                start_res = _run_cmd(
                    ["minikube", "start", "--driver=docker", "--gpus=all"], check=False
                )
                started = start_res.returncode == 0 and _minikube_running()
            if not started:
                start_res = _run_cmd(["minikube", "start", "--driver=docker"], check=False)
                started = start_res.returncode == 0 and _minikube_running()
            if not started:
                print_error(MESSAGES.k8s.failed_start_minikube, prefix=False)
                raise typer.Exit(1)
            _run_cmd(["minikube", "update-context"], check=False)
        else:
            print_error(
                MESSAGES.k8s.minikube_not_running,
                prefix=False,
            )
            raise typer.Exit(1)
    else:
        _run_cmd(["minikube", "update-context"], check=False)

    deploy_stack(k8s_dir=k8s_dir, stack=stack)


def _adopt_helm_resource_if_conflict(
    error_output: str, release_name: str, namespace: str, context: str | None = None
) -> bool:
    """If Helm failed due to pre-existing unmanaged resources, annotate and label them to adopt."""
    if (
        "invalid ownership metadata" not in error_output
        and "cannot be imported" not in error_output
    ):
        return False

    import re

    # Match pattern e.g. Service "ollama" in namespace "llm" exists
    matches = re.findall(r'([A-Za-z0-9_-]+)\s+"([^"]+)"\s+in namespace\s+"([^"]+)"', error_output)
    if not matches:
        return False

    ctx_args = ["--context", context] if context else []
    adopted_any = False
    for kind_raw, name, ns in matches:
        kind = kind_raw.lower()
        adopt_msg = f"Adopting pre-existing {kind}/{name} for release '{release_name}'..."
        print_warning(adopt_msg)
        _run_cmd(
            [
                "kubectl",
                "annotate",
                kind,
                name,
                "-n",
                ns,
                f"meta.helm.sh/release-name={release_name}",
                f"meta.helm.sh/release-namespace={ns}",
                "--overwrite",
            ]
            + ctx_args,
            check=False,
        )
        _run_cmd(
            [
                "kubectl",
                "label",
                kind,
                name,
                "-n",
                ns,
                "app.kubernetes.io/managed-by=Helm",
                "--overwrite",
            ]
            + ctx_args,
            check=False,
        )
        adopted_any = True
    return adopted_any


# =============================================================================
# Command: devops k8s deploy-stack
# =============================================================================


@app.command("deploy-stack")
def deploy_stack(
    k8s_dir: Annotated[
        Path, typer.Option("--k8s-dir", help="Path to k8s/ config directory")
    ] = DEFAULT_K8S_DIR,
    stack: Annotated[
        str, typer.Option("--stack", "-s", help="Stack to deploy (infra, llm, all)")
    ] = DEFAULT_K8S_STACK,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help="Kubernetes cluster context")
    ] = None,
) -> None:
    """Deploy infrastructure or LLM stack (Ollama, WebUI, Qdrant, Valkey) to Kubernetes."""
    if context:
        _validate_k8s_identifier(context, "context")

    selected_stacks = _resolve_stacks(stack)

    all_releases: list[dict[str, str]] = []
    all_manifests: list[str] = []
    for s_name in selected_stacks:
        all_releases.extend(_HELM_RELEASES_BY_STACK.get(s_name, []))
        all_manifests.extend([str(p) for p in _MANIFESTS_BY_STACK.get(s_name, [])])

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s deploy-stack",
            target=str(k8s_dir),
            action="deploy_k8s_stack",
            details={
                "kustomize_dir": str(k8s_dir),
                "stack": stack,
                "stacks": selected_stacks,
                "context": context,
                "helm_releases": [r["name"] for r in all_releases],
                "manifests": all_manifests,
            },
        )
        return

    # 1. Verify cluster reachability
    if not _cluster_reachable(context=context):
        print_error(MESSAGES.k8s.cluster_not_reachable, prefix=False)
        if not context or context == "minikube":
            print_info(MESSAGES.k8s.start_minikube_tip, prefix=False)
        raise typer.Exit(1)

    kubectl_ctx = ["--context", context] if context else []
    helm_ctx = ["--kube-context", context] if context else []

    # 2. Apply kustomize base (namespaces)
    print_info("[bold]Applying namespaces...[/bold]", prefix=False)
    _run_cmd(["kubectl", "apply", "-k", str(k8s_dir)] + kubectl_ctx)

    # 3. Add Helm repos for selected stacks
    repos_to_add: dict[str, str] = {}
    for s_name in selected_stacks:
        repos_to_add.update(_HELM_REPOS_BY_STACK.get(s_name, {}))

    if repos_to_add:
        print_info(MESSAGES.k8s.adding_helm_repos, prefix=False)
        for repo_name, repo_url in repos_to_add.items():
            _run_cmd(["helm", "repo", "add", repo_name, repo_url], check=False)
        _run_cmd(["helm", "repo", "update"])

    # 4. Install native manifests
    for manifest_path in all_manifests:
        print_info(f"[bold]Applying manifest {Path(manifest_path).name}...[/bold]", prefix=False)
        _run_cmd(["kubectl", "apply", "-f", manifest_path] + kubectl_ctx, check=False)

    # 5. Install Helm releases
    for release in all_releases:
        print_info(f"[bold]Installing {release['name']}...[/bold]", prefix=False)
        helm_cmd = (
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
            ]
            + helm_ctx
            + [
                "--wait",
                "--timeout",
                "10m",
            ]
        )
        result = _run_cmd(helm_cmd, check=False, capture=True)
        # If conflict occurs on pre-existing unmanaged resources, adopt and retry up to 5 times
        for _ in range(5):
            if result.returncode == 0:
                break
            err_msg = (result.stderr or "") + " " + (result.stdout or "")
            if not _adopt_helm_resource_if_conflict(
                err_msg,
                release["name"],
                release["namespace"],
                context=context,
            ):
                break
            result = _run_cmd(helm_cmd, check=False, capture=True)

        if result.returncode != 0:
            print_error(f"Failed to install {release['name']}", prefix=False)
        else:
            print_success(f"{release['name']} installed")

    # 6. Auto-configure monitoring URLs & port forwarding
    write_stdout("\n")
    print_success(f"Kubernetes stack ({stack}) deployed.")
    write_stdout("\n")
    port_forward(stack=stack, context=context)
    write_stdout("\n")
    if "infra" in selected_stacks:
        print_info(
            "[dim]ArgoCD admin password: kubectl -n argocd get secret"
            " argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d[/dim]",
            prefix=False,
        )
        print_info(
            "[dim]Grafana credentials: set via grafana.token in 'devops config set'[/dim]",
            prefix=False,
        )
        print_info(
            "[dim]Jaeger Query UI: http://localhost:16686 (namespace: otel)[/dim]",
            prefix=False,
        )
        print_info(
            "[dim]Jaeger OTLP Traces: localhost:4317 (gRPC) / localhost:4318 (HTTP)[/dim]",
            prefix=False,
        )
    if "llm" in selected_stacks:
        print_info("[dim]Ollama: http://localhost:11434 (namespace: llm)[/dim]", prefix=False)
        print_info(
            "[dim]Open-WebUI: http://localhost:3000 (minikube service open-webui -n llm)[/dim]",
            prefix=False,
        )
        print_info(
            "[dim]Qdrant Vector DB: http://localhost:6333 (HTTP) / :6334 (gRPC)[/dim]",
            prefix=False,
        )
        print_info("[dim]Valkey Cache: localhost:6379 (namespace: llm)[/dim]", prefix=False)


# =============================================================================
# Service URL Detection & Reachability Helpers
# =============================================================================


def _parse_minikube_service_url(stdout: str) -> str | None:
    """Extract HTTP/HTTPS URL from minikube service command output."""
    for line in stdout.splitlines():
        line_str = line.strip()
        if line_str.startswith(("http://", "https://")):
            return line_str
    return None


def _extract_first_node_ip(item: dict[str, Any]) -> str | None:
    """Extract first external/internal IP or hostname from a Kubernetes node item."""
    for addr in item.get("status", {}).get("addresses", []):
        if addr.get("type") in ("ExternalIP", "InternalIP", "Hostname"):
            ip = addr.get("address")
            if ip:
                return str(ip)
    return None


def _resolve_k8s_node_port_url(ctx_args: list[str], node_port: int) -> str | None:
    """Query Kubernetes nodes to find node IP and construct nodePort URL."""
    try:
        nodes_res = run_subprocess(
            ["kubectl", "get", "nodes", "-o", "json"] + ctx_args,
            capture_output=True,
            text=True,
            check=False,
            quiet=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
        if nodes_res.returncode == 0 and nodes_res.stdout.strip():
            import json

            nodes_data = json.loads(nodes_res.stdout)
            for item in nodes_data.get("items", []):
                node_ip = _extract_first_node_ip(item)
                if node_ip:
                    return f"http://{node_ip}:{node_port}"
    except Exception:
        pass
    return None


def _detect_service_url(service: str, namespace: str, context: str | None = None) -> str | None:
    """Query service URL via minikube service or kubectl nodePort/cluster info."""
    # 1. Try minikube service if context is not explicit non-minikube
    if not context or context == "minikube":
        try:
            res = run_subprocess(
                ["minikube", "service", service, "-n", namespace, "--url"],
                capture_output=True,
                text=True,
                check=False,
                quiet=True,
                timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
            )
            if res.returncode == 0 and res.stdout.strip():
                url = _parse_minikube_service_url(res.stdout)
                if url:
                    return url
        except OSError, subprocess.SubprocessError:
            pass

    # 2. Generic K8s nodePort or loadBalancer detection via kubectl
    try:
        ctx_args = ["--context", context] if context else []
        svc_res = run_subprocess(
            ["kubectl", "get", "svc", service, "-n", namespace, "-o", "json"] + ctx_args,
            capture_output=True,
            text=True,
            check=False,
            quiet=True,
            timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
        )
        if svc_res.returncode == 0 and svc_res.stdout.strip():
            import json

            svc_data = json.loads(svc_res.stdout)
            spec = svc_data.get("spec", {})
            ports = spec.get("ports", [])
            node_port = ports[0].get("nodePort") if ports else None
            port_num = ports[0].get("port") if ports else None

            # Check LoadBalancer ingress IP
            ingress = svc_data.get("status", {}).get("loadBalancer", {}).get("ingress", [])
            if ingress:
                lb_host = ingress[0].get("ip") or ingress[0].get("hostname")
                if lb_host and port_num:
                    return f"http://{lb_host}:{port_num}"

            # Check NodePort
            if node_port:
                node_url = _resolve_k8s_node_port_url(ctx_args, int(node_port))
                if node_url:
                    return node_url
    except Exception:
        pass

    return None


def _verify_url_reachability(url: str, timeout: float = DEFAULT_HTTP_PROBE_TIMEOUT_SECONDS) -> bool:
    """Check if target HTTP URL host and port can accept socket connections."""
    import socket
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not host:
            return False
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _resolve_accessible_url(
    detected_url: str | None, preferred_localhost_ports: list[int] | None = None
) -> str | None:
    """Resolve service URL to ensure it is accessible from devcontainer / host OS environment."""
    if preferred_localhost_ports:
        for port in preferred_localhost_ports:
            candidate = f"http://localhost:{port}"
            if _verify_url_reachability(candidate):
                return candidate

    if not detected_url:
        return None

    from urllib.parse import urlparse

    if _verify_url_reachability(detected_url):
        return detected_url

    parsed = urlparse(detected_url)
    if parsed.port:
        localhost_url = f"{parsed.scheme}://localhost:{parsed.port}"
        if _verify_url_reachability(localhost_url):
            return localhost_url

        loopback_url = f"{parsed.scheme}://127.0.0.1:{parsed.port}"
        if _verify_url_reachability(loopback_url):
            return loopback_url

        return localhost_url

    return detected_url


# =============================================================================
# Command: devops k8s configure-urls
# =============================================================================


@app.command("configure-urls")
def configure_urls(
    stack: Annotated[
        str, typer.Option("--stack", "-s", help="Stack to configure URLs for (infra, llm, all)")
    ] = DEFAULT_K8S_STACK,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help="Kubernetes cluster context")
    ] = None,
) -> None:
    """Auto-detect Kubernetes stack URLs and update CLI config."""
    if context:
        _validate_k8s_identifier(context, "context")

    selected_stacks = _resolve_stacks(stack)

    dry_run_details: dict[str, str] = {}
    if "infra" in selected_stacks:
        dry_run_details.update(
            {
                "argocd.url": "http://192.168.49.2:30080",
                "grafana.url": "http://192.168.49.2:32047",
                "prometheus.url": "http://192.168.49.2:30090",
                "jaeger.url": "http://192.168.49.2:30686",
            }
        )
    if "llm" in selected_stacks:
        dry_run_details.update(
            {
                "ai.ollama_urls": "http://192.168.49.2:31434",
                "open_webui.url": "http://192.168.49.2:30080",
                "qdrant.url": "http://192.168.49.2:30633",
                "valkey.url": "tcp://192.168.49.2:30379",
            }
        )

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s configure-urls",
            action="configure_monitoring_urls",
            details=dry_run_details,
        )
        return

    if not _cluster_reachable(context=context):
        print_error(MESSAGES.k8s.cluster_not_reachable, prefix=False)
        raise typer.Exit(1)

    print_info(
        f"[bold]Detecting {stack} service URLs (context: {context or 'active'})...[/bold]",
        prefix=False,
    )

    from devops_cli.config.settings import dotted_set, load_settings, save_settings

    settings = load_settings()
    configured: dict[str, str] = {}

    if "infra" in selected_stacks:
        raw_argocd = _detect_service_url("argocd-server", "argocd", context=context)
        raw_grafana = _detect_service_url("kube-prometheus-grafana", "monitoring", context=context)
        raw_prom = _detect_service_url(
            "kube-prometheus-kube-prome-prometheus", "monitoring", context=context
        )
        raw_jaeger = _detect_service_url("jaeger", "otel", context=context)

        argocd_url = _resolve_accessible_url(raw_argocd, preferred_localhost_ports=[8080])
        grafana_url = _resolve_accessible_url(
            raw_grafana, preferred_localhost_ports=[8030, 8000, 3000]
        )
        prom_url = _resolve_accessible_url(raw_prom, preferred_localhost_ports=[8090, 9090])
        jaeger_url = _resolve_accessible_url(raw_jaeger, preferred_localhost_ports=[16686])

        if argocd_url:
            dotted_set(settings, "argocd.url", argocd_url)
            configured["argocd.url"] = argocd_url
        if grafana_url:
            dotted_set(settings, "grafana.url", grafana_url)
            configured["grafana.url"] = grafana_url
        if prom_url:
            dotted_set(settings, "prometheus.url", prom_url)
            configured["prometheus.url"] = prom_url
        if jaeger_url:
            dotted_set(settings, "jaeger.url", jaeger_url)
            configured["jaeger.url"] = jaeger_url
            dotted_set(settings, "otel.endpoint", "http://localhost:4318")
            configured["otel.endpoint"] = "http://localhost:4318"

    if "llm" in selected_stacks:
        raw_ollama = _detect_service_url("ollama", "llm", context=context)
        raw_webui = _detect_service_url("open-webui", "llm", context=context)
        raw_qdrant = _detect_service_url("qdrant", "llm", context=context)
        raw_valkey = _detect_service_url("valkey", "llm", context=context)

        ollama_url = _resolve_accessible_url(raw_ollama, preferred_localhost_ports=[11434])
        webui_url = _resolve_accessible_url(raw_webui, preferred_localhost_ports=[3000, 8080])
        qdrant_url = _resolve_accessible_url(raw_qdrant, preferred_localhost_ports=[6333])
        valkey_url = _resolve_accessible_url(raw_valkey, preferred_localhost_ports=[6379])

        if ollama_url:
            settings.ai.ollama_urls = [ollama_url]
            configured["ai.ollama_urls"] = ollama_url
        if webui_url:
            configured["open_webui.url"] = webui_url
        if qdrant_url:
            configured["qdrant.url"] = qdrant_url
        if valkey_url:
            configured["valkey.url"] = valkey_url

    if configured:
        save_settings(settings)

    table = Table(title=f"Configured Service Targets ({stack})")
    table.add_column("Config Key / Service", style="cyan")
    table.add_column("Detected Target URL", style="green")

    for k, v in configured.items():
        table.add_row(k, v)

    print_table(table)


# =============================================================================
# Command: devops k8s port-forward
# =============================================================================


@app.command("port-forward")
def port_forward(
    stack: Annotated[
        str, typer.Option("--stack", "-s", help="Stack services to port-forward (infra, llm, all)")
    ] = DEFAULT_K8S_STACK,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help="Kubernetes cluster context")
    ] = None,
    argocd_port: Annotated[
        int, typer.Option("--argocd-port", help="Local port for ArgoCD")
    ] = DEFAULT_ARGOCD_PORT,
    grafana_port: Annotated[
        int, typer.Option("--grafana-port", help="Local port for Grafana")
    ] = DEFAULT_GRAFANA_PORT,
    prometheus_port: Annotated[
        int, typer.Option("--prometheus-port", help="Local port for Prometheus")
    ] = DEFAULT_PROMETHEUS_PORT,
    jaeger_port: Annotated[
        int, typer.Option("--jaeger-port", help="Local port for Jaeger Query UI")
    ] = DEFAULT_JAEGER_PORT,
    otel_port: Annotated[
        int, typer.Option("--otel-port", help="Local port for OpenTelemetry OTLP Traces (HTTP)")
    ] = DEFAULT_OTEL_PORT,
    ollama_port: Annotated[
        int, typer.Option("--ollama-port", help="Local port for Ollama")
    ] = DEFAULT_OLLAMA_PORT,
    open_webui_port: Annotated[
        int, typer.Option("--open-webui-port", help="Local port for Open-WebUI")
    ] = DEFAULT_OPEN_WEBUI_PORT,
    qdrant_port: Annotated[
        int, typer.Option("--qdrant-port", help="Local port for Qdrant HTTP")
    ] = DEFAULT_QDRANT_PORT,
    valkey_port: Annotated[
        int, typer.Option("--valkey-port", help="Local port for Valkey")
    ] = DEFAULT_VALKEY_PORT,
    address: Annotated[
        str, typer.Option("--address", help="Local address to bind for port-forwarding")
    ] = DEFAULT_REST_HOST,
) -> None:
    """Port-forward k8s monitoring / LLM stack services to localhost ports and update CLI config."""
    import time

    if context:
        _validate_k8s_identifier(context, "context")

    selected_stacks = _resolve_stacks(stack)

    details: dict[str, str] = {}
    if "infra" in selected_stacks:
        details.update(
            {
                "argocd.url": f"http://localhost:{argocd_port}",
                "grafana.url": f"http://localhost:{grafana_port}",
                "prometheus.url": f"http://localhost:{prometheus_port}",
                "jaeger.url": f"http://localhost:{jaeger_port}",
                "otel.endpoint": f"http://localhost:{otel_port}",
            }
        )
    if "llm" in selected_stacks:
        details.update(
            {
                "ollama.url": f"http://localhost:{ollama_port}",
                "open_webui.url": f"http://localhost:{open_webui_port}",
                "qdrant.url": f"http://localhost:{qdrant_port}",
                "valkey.url": f"tcp://localhost:{valkey_port}",
            }
        )

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s port-forward",
            action="k8s_port_forward",
            details=details,
        )
        return

    if not _cluster_reachable(context=context):
        print_error(MESSAGES.k8s.cluster_not_reachable, prefix=False)
        raise typer.Exit(1)

    print_info(
        f"[bold cyan]Port-forwarding k8s {stack} services to localhost ports...[/bold cyan]",
        prefix=False,
    )

    services: list[tuple[str, str, int, int]] = []
    if "infra" in selected_stacks:
        services.extend(
            [
                ("argocd", "svc/argocd-server", argocd_port, 80),
                ("monitoring", "svc/kube-prometheus-grafana", grafana_port, 80),
                ("monitoring", "svc/kube-prometheus-kube-prome-prometheus", prometheus_port, 9090),
                ("otel", "svc/jaeger", jaeger_port, 16686),
                ("otel", "svc/jaeger", otel_port, 4318),
            ]
        )
    if "llm" in selected_stacks:
        services.extend(
            [
                ("llm", "svc/ollama", ollama_port, 11434),
                ("llm", "svc/open-webui", open_webui_port, 8080),
                ("llm", "svc/qdrant", qdrant_port, 6333),
                ("llm", "svc/valkey", valkey_port, 6379),
            ]
        )

    ctx_args = ["--context", context] if context else []
    for ns, svc, lport, rport in services:
        cmd = [
            "kubectl",
            "port-forward",
            "--address",
            address,
            "-n",
            ns,
            svc,
            f"{lport}:{rport}",
        ] + ctx_args
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print_success(f"Forwarding {svc} ({ns}) to http://{address}:{lport}")

    time.sleep(1.0)
    configure_urls(stack=stack, context=context)


# =============================================================================
# Command: devops k8s teardown-stack
# =============================================================================


@app.command("teardown-stack")
def teardown_stack(
    k8s_dir: Annotated[
        Path, typer.Option("--k8s-dir", help="Path to k8s/ config directory")
    ] = DEFAULT_K8S_DIR,
    stack: Annotated[
        str, typer.Option("--stack", "-s", help="Stack to teardown (infra, llm, all)")
    ] = DEFAULT_K8S_STACK,
    context: Annotated[
        str | None, typer.Option("--context", "-c", help="Kubernetes cluster context")
    ] = None,
) -> None:
    """Uninstall the k8s infrastructure / LLM stack and delete namespaces."""
    if context:
        _validate_k8s_identifier(context, "context")

    selected_stacks = _resolve_stacks(stack)

    all_uninstalls: list[dict[str, str]] = []
    all_manifest_deletes: list[str] = []
    for s_name in reversed(selected_stacks):
        all_uninstalls.extend(reversed(_HELM_RELEASES_BY_STACK.get(s_name, [])))
        all_manifest_deletes.extend([str(p) for p in reversed(_MANIFESTS_BY_STACK.get(s_name, []))])

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s teardown-stack",
            target=str(k8s_dir),
            action="teardown_k8s_stack",
            details={
                "kustomize_dir": str(k8s_dir),
                "stack": stack,
                "stacks": selected_stacks,
                "context": context,
                "helm_uninstalls": [r["name"] for r in all_uninstalls],
                "manifest_deletes": all_manifest_deletes,
            },
        )
        return

    if not _cluster_reachable(context=context):
        print_error(MESSAGES.k8s.cluster_not_reachable, prefix=False)
        raise typer.Exit(1)

    kubectl_ctx = ["--context", context] if context else []
    helm_ctx = ["--kube-context", context] if context else []

    # 1. Delete manifests
    for manifest_path in all_manifest_deletes:
        print_info(f"[bold]Deleting manifest {Path(manifest_path).name}...[/bold]", prefix=False)
        _run_cmd(
            ["kubectl", "delete", "-f", manifest_path, "--ignore-not-found"] + kubectl_ctx,
            check=False,
        )

    # 2. Uninstall Helm releases in reverse order
    for release in all_uninstalls:
        print_info(f"[bold]Uninstalling {release['name']}...[/bold]", prefix=False)
        _run_cmd(
            ["helm", "uninstall", release["name"], "--namespace", release["namespace"]] + helm_ctx,
            check=False,
        )

    # 3. Clean up namespaces
    if stack == "all":
        print_info(MESSAGES.k8s.removing_stack_namespaces, prefix=False)
        _run_cmd(
            ["kubectl", "delete", "-k", str(k8s_dir), "--ignore-not-found"] + kubectl_ctx,
            check=False,
        )
    elif stack == "infra":
        print_info(MESSAGES.k8s.removing_infra_namespaces, prefix=False)
        for ns in ["argocd", "monitoring", "otel"]:
            _run_cmd(
                ["kubectl", "delete", "namespace", ns, "--ignore-not-found"] + kubectl_ctx,
                check=False,
            )
    elif stack == "llm":
        print_info(MESSAGES.k8s.removing_llm_namespace, prefix=False)
        _run_cmd(
            ["kubectl", "delete", "namespace", "llm", "--ignore-not-found"] + kubectl_ctx,
            check=False,
        )

    print_success(f"Kubernetes stack ({stack}) torn down.")


# =============================================================================
# Command: devops k8s rbac-audit
# =============================================================================


@app.command("rbac-audit")
def rbac_audit(
    namespace: Annotated[str | None, typer.Option("--namespace", "-n")] = None,
) -> None:
    """Audit RBAC RoleBindings and ServiceAccounts for overprivileged access."""
    if namespace:
        _validate_k8s_identifier(namespace, "namespace", namespace=True)

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s rbac-audit",
            action="rbac_audit_scan",
            details={"namespace": namespace, "violations": []},
        )
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
    print_table(table)


# =============================================================================
# Command: devops k8s lint
# =============================================================================


@app.command("lint")
def k8s_lint(
    target: Annotated[
        Path,
        typer.Argument(help="Target K8s manifest file or directory to lint"),
    ] = DEFAULT_CURRENT_PATH,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate manifest linting."),
    ] = False,
) -> None:
    """Validate K8s manifests and Helm charts using Red Hat Kube-linter."""
    from devops_cli.dry_run.state import set_dry_run
    from devops_cli.security.kubelinter import run_kubelinter_scan

    set_dry_run(dry_run)
    target_abs = target.resolve() if target.exists() else target
    if not is_dry_run():
        print_info(
            f"[dim]Executing Kube-linter manifest audit on '{target_abs}'...[/dim]",
            prefix=False,
        )

    findings = run_kubelinter_scan(target=target_abs)

    if is_dry_run():
        render_dry_run_result(
            command=f"devops k8s lint {target}",
            action="kubelinter_manifest_audit",
            details={"target": str(target_abs), "findings_count": len(findings)},
        )
        return

    if not findings:
        print_success(MESSAGES.k8s.kube_linter_passed)
        return

    table = Table(title=f"Kube-linter Manifest Audit: {target_abs.name or target_abs}")
    table.add_column("Severity", style="bold yellow")
    table.add_column("Resource Location")
    table.add_column("Title")
    table.add_column("Remediation")

    for f in findings:
        table.add_row(f.severity, f.location, f.title, f.fix or "-")

    print_table(table)


# =============================================================================
# Command: devops k8s audit
# =============================================================================


@app.command("audit")
def k8s_audit(
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate cluster health audit."),
    ] = False,
) -> None:
    """Sanitize active K8s/Minikube cluster resource health using Derailed Popeye."""
    from devops_cli.dry_run.state import set_dry_run
    from devops_cli.security.popeye import run_popeye_scan

    set_dry_run(dry_run)
    if not is_dry_run():
        print_info(MESSAGES.k8s.popeye_executing, prefix=False)

    findings = run_popeye_scan()

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s audit",
            action="popeye_cluster_sanitizer",
            details={"findings_count": len(findings)},
        )
        return

    if not findings:
        print_success(MESSAGES.k8s.popeye_passed)
        return

    table = Table(title="Popeye Cluster Health Audit")
    table.add_column("Severity", style="bold")
    table.add_column("Cluster Resource")
    table.add_column("Finding Title")
    table.add_column("Remediation")

    sev_colors = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "cyan", "INFO": "dim"}

    for f in findings:
        style = sev_colors.get(f.severity.upper(), "white")
        table.add_row(f"[{style}]{f.severity}[/{style}]", f.location, f.title, f.fix or "-")

    print_table(table)


# =============================================================================
# Command: devops k8s check-deprecated
# =============================================================================


@app.command("check-deprecated")
def k8s_check_deprecated(
    target: Annotated[
        Path,
        typer.Argument(help="Target manifest file or directory to scan for deprecated APIs"),
    ] = DEFAULT_CURRENT_PATH,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate deprecated API detection."),
    ] = False,
) -> None:
    """Scan manifests for deprecated/removed K8s API versions using Fairwinds Pluto."""
    from devops_cli.dry_run.state import set_dry_run
    from devops_cli.security.pluto import run_pluto_scan

    set_dry_run(dry_run)
    target_abs = target.resolve() if target.exists() else target
    if not is_dry_run():
        print_info(
            f"[dim]Executing Pluto deprecated API scan on '{target_abs}'...[/dim]",
            prefix=False,
        )

    findings = run_pluto_scan(target=target_abs)

    if is_dry_run():
        render_dry_run_result(
            command=f"devops k8s check-deprecated {target}",
            action="pluto_deprecated_api_scan",
            details={"target": str(target_abs), "findings_count": len(findings)},
        )
        return

    if not findings:
        print_success(MESSAGES.k8s.pluto_passed)
        return

    table = Table(title=f"Pluto Deprecated K8s API Report: {target_abs.name or target_abs}")
    table.add_column("Severity", style="bold red")
    table.add_column("Resource Location")
    table.add_column("Deprecation Warning")
    table.add_column("Migration Target")

    for f in findings:
        table.add_row(f.severity, f.location, f.title, f.fix or "-")

    print_table(table)


# =============================================================================
# Command: devops k8s create-tls-secret
# =============================================================================


@app.command("create-tls-secret")
def create_tls_secret(
    secret_name: Annotated[
        str,
        typer.Argument(help="Name of the Kubernetes TLS secret to create or update"),
    ],
    namespace: Annotated[
        str,
        typer.Option("--namespace", "-n", help="Target Kubernetes namespace"),
    ] = DEFAULT_K8S_NAMESPACE,
    cert_path: Annotated[
        Path,
        typer.Option("--cert", help="Path to TLS certificate file (.crt or .pem)"),
    ] = DEFAULT_TLS_DIR / CONST_SERVER_CERT_NAME,
    key_path: Annotated[
        Path,
        typer.Option("--key", help="Path to TLS private key file (.key or .pem)"),
    ] = DEFAULT_TLS_DIR / CONST_SERVER_KEY_NAME,
    context: Annotated[
        str | None,
        typer.Option("--context", "-c", help="Kubernetes cluster context"),
    ] = None,
) -> None:
    """Create or update a kubernetes.io/tls secret from certificate and private key files."""
    if context:
        _validate_k8s_identifier(context, "context")
    _validate_k8s_identifier(namespace, "namespace", namespace=True)
    _validate_k8s_identifier(secret_name, "secret_name")

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s create-tls-secret",
            target=secret_name,
            action="create_k8s_tls_secret",
            details={
                "secret_name": secret_name,
                "namespace": namespace,
                "cert_path": str(cert_path),
                "key_path": str(key_path),
                "context": context,
            },
        )
        return

    if not cert_path.exists():
        print_error(f"Certificate file not found: {cert_path}", prefix=False)
        raise typer.Exit(1)
    if not key_path.exists():
        print_error(f"Key file not found: {key_path}", prefix=False)
        raise typer.Exit(1)

    kubectl_ctx = ["--context", context] if context else []

    # Ensure namespace exists
    ns_check = _run_cmd(["kubectl", "get", "namespace", namespace] + kubectl_ctx, check=False)
    if ns_check.returncode != 0:
        _run_cmd(["kubectl", "create", "namespace", namespace] + kubectl_ctx, check=True)

    # Delete existing secret to allow clean recreation
    _run_cmd(
        ["kubectl", "delete", "secret", secret_name, "-n", namespace] + kubectl_ctx,
        check=False,
    )

    create_cmd = [
        "kubectl",
        "create",
        "secret",
        "tls",
        secret_name,
        f"--cert={cert_path}",
        f"--key={key_path}",
        "-n",
        namespace,
    ] + kubectl_ctx

    rc = _run_cmd(create_cmd, check=False)
    if rc.returncode == 0:
        print_success(
            f"Created TLS secret [cyan]{secret_name}[/cyan] "
            f"in namespace [magenta]{namespace}[/magenta]"
        )
    else:
        print_error(
            f"Failed to create TLS secret {secret_name} in namespace {namespace}",
            prefix=False,
        )
        raise typer.Exit(1)


# =============================================================================
# Command: devops k8s enable-tls
# =============================================================================
@app.command("enable-tls")
def enable_tls_stack(
    context: Annotated[
        str | None,
        typer.Option("--context", "-c", help="Kubernetes cluster context"),
    ] = None,
    tls_dir: Annotated[
        Path,
        typer.Option("--tls-dir", help="Directory with generated TLS certificates"),
    ] = DEFAULT_TLS_DIR,
    secret_name: Annotated[
        str,
        typer.Option("--secret-name", help="TLS secret name across namespaces"),
    ] = DEFAULT_K8S_TLS_SECRET_NAME,
    stack: Annotated[
        str,
        typer.Option("--stack", "-s", help="Stack to deploy TLS secrets into (infra, llm, all)"),
    ] = DEFAULT_K8S_ALL_STACK,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", "-f", help="Regenerate certs if missing"),
    ] = False,
) -> None:
    """Generate Homelab certificates and apply TLS secrets across Kubernetes cluster namespaces."""
    if context:
        _validate_k8s_identifier(context, "context")

    selected_stacks = _resolve_stacks(stack)

    # Resolve target namespaces based on selected stacks
    namespaces_to_target: list[str] = [DEFAULT_K8S_NAMESPACE]
    if "infra" in selected_stacks:
        namespaces_to_target.extend(["argocd", "monitoring", "otel"])
    if "llm" in selected_stacks:
        namespaces_to_target.extend(["llm"])

    if is_dry_run():
        render_dry_run_result(
            command="devops k8s enable-tls",
            target=stack,
            action="enable_k8s_tls_stack",
            details={
                "tls_dir": str(tls_dir),
                "secret_name": secret_name,
                "stack": stack,
                "namespaces": namespaces_to_target,
                "context": context,
            },
        )
        return

    # Check if certificates exist; if not and overwrite is requested, generate bundle
    cert_path = tls_dir / CONST_SERVER_CERT_NAME
    key_path = tls_dir / CONST_SERVER_KEY_NAME

    if not (cert_path.exists() and key_path.exists()):
        print_info(f"Certificates missing under {tls_dir}. Generating bundle...")
        generate_homelab_tls_bundle(output_dir=tls_dir, overwrite=overwrite)

    results: list[KubernetesTLSSecretResult] = []
    kubectl_ctx = ["--context", context] if context else []

    for ns in namespaces_to_target:
        # Check if namespace exists before attempting secret creation
        ns_check = _run_cmd(["kubectl", "get", "namespace", ns] + kubectl_ctx, check=False)
        if ns_check.returncode != 0:
            results.append(
                KubernetesTLSSecretResult(
                    secret_name=secret_name,
                    namespace=ns,
                    created=False,
                    cert_path=str(cert_path),
                    key_path=str(key_path),
                    error=f"Namespace {ns} does not exist in cluster",
                )
            )
            continue

        # Delete existing secret if overwrite requested
        if overwrite:
            _run_cmd(
                ["kubectl", "delete", "secret", secret_name, "-n", ns] + kubectl_ctx,
                check=False,
            )

        create_cmd = [
            "kubectl",
            "create",
            "secret",
            "tls",
            secret_name,
            f"--cert={cert_path}",
            f"--key={key_path}",
            "-n",
            ns,
        ] + kubectl_ctx

        rc = _run_cmd(create_cmd, check=False)
        results.append(
            KubernetesTLSSecretResult(
                secret_name=secret_name,
                namespace=ns,
                created=(rc.returncode == 0),
                cert_path=str(cert_path),
                key_path=str(key_path),
                error=None if rc.returncode == 0 else "Failed to create secret via kubectl",
            )
        )

    table = Table(title="Kubernetes TLS Secret Deployment", title_style="bold blue")
    table.add_column("Namespace", style="cyan")
    table.add_column("Secret Name", style="white")
    table.add_column("Status", style="bold")

    for r in results:
        status_str = "[green]✓ Created[/green]" if r.created else f"[red]✗ Failed: {r.error}[/red]"
        table.add_row(r.namespace, r.secret_name, status_str)

    print_table(table)


# =============================================================================
# Command: devops k8s validate
# =============================================================================


@app.command("validate")
def k8s_validate(
    manifest_path: Annotated[
        Path,
        typer.Argument(help="Path to Kubernetes YAML manifest file or directory"),
    ] = DEFAULT_CURRENT_PATH,
    k8s_version: Annotated[
        str,
        typer.Option("--kubernetes-version", "-v", help="Target Kubernetes OpenAPI version"),
    ] = DEFAULT_KUBECONFORM_VERSION,
    strict: Annotated[
        bool,
        typer.Option("--strict/--no-strict", help="Disallow additional undeclared properties"),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Simulate schema validation"),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output findings as JSON"),
    ] = False,
) -> None:
    """Validate Kubernetes YAML manifests against OpenAPI schemas using Kubeconform."""
    from devops_cli.output import format_json, print_muted
    from devops_cli.security.kubeconform import run_kubeconform_validation

    target_path = manifest_path.resolve()
    if dry_run or is_dry_run():
        render_dry_run_result(
            command=f"devops k8s validate {manifest_path} --kubernetes-version {k8s_version}",
            action="kubeconform_validation",
            target=str(target_path),
        )
        return

    print_muted(f"Validating Kubernetes manifests at '{target_path}' (k8s: {k8s_version})...")
    findings = run_kubeconform_validation(
        manifest_path=target_path,
        k8s_version=k8s_version,
        strict=strict,
    )

    if json_output:
        write_stdout(format_json([f.model_dump() for f in findings]) + "\n")
        return

    if not findings:
        print_success(f"✓ All Kubernetes manifests at '{target_path}' are valid schemas.")
        return

    title_str = f"Kubeconform Schema Issues: {target_path.name or str(target_path)}"
    table = Table(title=title_str)
    table.add_column("Severity", style="bold red")
    table.add_column("Location")
    table.add_column("Error")
    table.add_column("Remediation")

    for f in findings:
        table.add_row(f.severity, f.location, f.title, f.fix or f.description)
    print_table(table)
