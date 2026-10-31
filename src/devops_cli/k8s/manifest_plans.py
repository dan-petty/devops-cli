"""Planned request builders for Kubernetes manifest, stack, and kustomize commands.

A dry run makes zero external requests and returns the ordered PlannedRequest items.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from devops_cli.config.commands import (
    BIN_KUBECTL,
    build_helm_diff_cmd,
    build_kubectl_cmd,
    build_kustomize_build_cmd,
)
from devops_cli.config.constants import (
    CONST_SERVER_CERT_NAME,
    CONST_SERVER_KEY_NAME,
)
from devops_cli.dry_run.requests import PlannedRequest


def plan_k8s_apply(
    path: str | Path,
    namespace: str | None = None,
    template: bool = False,
    domain: str | None = None,
) -> list[PlannedRequest]:
    """Plan manifest apply via kubectl."""
    if template or domain is not None:
        cmd = [BIN_KUBECTL, "apply", "-f", "-"]
        if namespace:
            cmd.extend(["--namespace", namespace])
        return [
            PlannedRequest(
                method="kubectl",
                target="apply",
                argv=tuple(cmd),
                stdin="<rendered-manifest>",
            )
        ]
    cmd = [BIN_KUBECTL, "apply", "-f", str(path)]
    if namespace:
        cmd.extend(["--namespace", namespace])
    return [
        PlannedRequest(
            method="kubectl",
            target="apply",
            argv=tuple(cmd),
        )
    ]


def plan_k8s_render(
    path: str | Path,
    domain: str | None = None,
) -> list[PlannedRequest]:
    """Plan manifest or kustomization rendering."""
    cmd = [BIN_KUBECTL, "kustomize", str(path)]
    return [
        PlannedRequest(
            method="kubectl",
            target="kustomize",
            argv=tuple(cmd),
        )
    ]


def plan_k8s_bootstrap(
    k8s_dir: Path | str,
    stack: str = "all",
    auto_start: bool = True,
) -> list[PlannedRequest]:
    """Plan cluster bootstrapping with Minikube, stack deployment, and ingress routing."""
    requests: list[PlannedRequest] = [
        PlannedRequest(
            method="minikube",
            target="status",
            argv=("minikube", "status"),
        )
    ]
    if auto_start:
        requests.append(
            PlannedRequest(
                method="minikube",
                target="start",
                argv=("minikube", "start", "--driver=docker"),
            )
        )
    requests.extend(
        [
            PlannedRequest(
                method="minikube",
                target="update-context",
                argv=("minikube", "update-context"),
            ),
            PlannedRequest(
                method="k8s",
                target=f"deploy-stack/{stack}",
                argv=(
                    "devops",
                    "k8s",
                    "deploy-stack",
                    "--stack",
                    stack,
                    "--k8s-dir",
                    str(k8s_dir),
                ),
            ),
            PlannedRequest(
                method="k8s",
                target=f"configure-urls/{stack}",
                argv=(
                    "devops",
                    "k8s",
                    "configure-urls",
                    "--stack",
                    stack,
                    "--context",
                    "minikube",
                ),
            ),
        ]
    )
    return requests


def plan_k8s_bootstrap_openwebui(
    email: str,
    name: str,
    context: str | None = None,
) -> list[PlannedRequest]:
    """Plan Open-WebUI admin user bootstrapping via pod discovery and exec."""
    ctx_args = ["--context", context] if context else []
    pod_cmd = [
        BIN_KUBECTL,
        "get",
        "pods",
        "-n",
        "llm",
        "-l",
        "app.kubernetes.io/name=open-webui",
        "-o",
        "jsonpath={.items[0].metadata.name}",
        *ctx_args,
    ]
    exec_cmd = [
        BIN_KUBECTL,
        "exec",
        "-i",
        "-n",
        "llm",
        "<open-webui-pod>",
        *ctx_args,
        "--",
        "python3",
        "-c",
        "<bootstrap-script>",
    ]
    return [
        PlannedRequest(
            method="kubectl",
            target="pods",
            argv=tuple(pod_cmd),
        ),
        PlannedRequest(
            method="kubectl",
            target="exec",
            argv=tuple(exec_cmd),
            stdin="<bootstrap-script>",
        ),
    ]


def plan_k8s_bootstrap_mattermost(
    team: str = "homelab",
    context: str | None = None,
    push_secrets: bool = True,
) -> list[PlannedRequest]:
    """Plan Mattermost team, channels, webhooks, and slash command bootstrapping via pod discovery and exec."""
    ctx_args = ["--context", context] if context else []
    pod_cmd = [
        BIN_KUBECTL,
        "get",
        "pods",
        "-n",
        "mattermost",
        "-l",
        "app.kubernetes.io/name=mattermost",
        "-o",
        "jsonpath={.items[0].metadata.name}",
        *ctx_args,
    ]
    exec_cmd = [
        BIN_KUBECTL,
        "exec",
        "-n",
        "mattermost",
        "<mattermost-pod>",
        *ctx_args,
        "--",
        "mmctl",
        "--local",
        "<bootstrap-subcommand>",
    ]
    requests = [
        PlannedRequest(
            method="kubectl",
            target="pods",
            argv=tuple(pod_cmd),
        ),
        PlannedRequest(
            method="kubectl",
            target="exec",
            argv=tuple(exec_cmd),
        ),
    ]
    if push_secrets:
        push_cmd = [
            "devops",
            "k8s",
            "push-secrets",
            "--only",
            "monitoring/alertmanager-mattermost,argocd/argocd-notifications-secret,devops/devops-cli",
            *ctx_args,
        ]
        requests.append(
            PlannedRequest(
                method="devops",
                target="secrets",
                argv=tuple(push_cmd),
            )
        )
    return requests


def plan_k8s_chaos(
    experiment: str = "pod-kill",
    deployment: str = "sample-app",
    namespace: str = "default",
    duration: int = 30,
) -> list[PlannedRequest]:
    """Plan chaos pod deletion and rollout monitoring requests."""
    get_cmd = build_kubectl_cmd(
        ["get", "pods", "-n", namespace, "-l", f"app={deployment}", "-o", "name"]
    )
    del_cmd = build_kubectl_cmd(["delete", f"pod/{deployment}-<hash>", "-n", namespace, "--now"])
    status_cmd = build_kubectl_cmd(
        ["rollout", "status", f"deployment/{deployment}", "-n", namespace, f"--timeout={duration}s"]
    )
    return [
        PlannedRequest(
            method="kubectl",
            target="pods",
            argv=tuple(get_cmd),
        ),
        PlannedRequest(
            method="kubectl",
            target="pod",
            argv=tuple(del_cmd),
        ),
        PlannedRequest(
            method="kubectl",
            target="deployment",
            argv=tuple(status_cmd),
        ),
    ]


def plan_k8s_check_deprecated(target: Path | str) -> list[PlannedRequest]:
    """Plan Pluto deprecation scan on local manifests or charts."""
    cmd = ["pluto", "detect-files", "-d", str(target)]
    return [
        PlannedRequest(
            method="pluto",
            target="deprecation",
            argv=tuple(cmd),
        )
    ]


def plan_k8s_configure_urls(
    stack: str,
    context: str | None = None,
    addressing: str | None = None,
) -> list[PlannedRequest]:
    """Plan cluster ingress discovery and host resolution."""
    ctx_args = ["--context", context] if context else []
    cmd = [BIN_KUBECTL, "get", "ingress", "-A", "-o", "json", *ctx_args]
    plans = [
        PlannedRequest(
            method="kubectl",
            target="ingress",
            argv=tuple(cmd),
        )
    ]
    if addressing == "node-port":
        node_cmd = [
            BIN_KUBECTL,
            "get",
            "nodes",
            "-o",
            'jsonpath={.items[0].status.addresses[?(@.type=="InternalIP")].address}',
            *ctx_args,
        ]
        plans.append(
            PlannedRequest(
                method="kubectl",
                target="nodes",
                argv=tuple(node_cmd),
            )
        )
    return plans


def plan_k8s_create_tls_secret(
    secret_name: str,
    namespace: str,
    cert_path: Path | str,
    key_path: Path | str,
    context: str | None = None,
) -> list[PlannedRequest]:
    """Plan namespace check and TLS secret creation via kubectl."""
    ctx_args = ["--context", context] if context else []
    ns_cmd = [BIN_KUBECTL, "get", "namespace", namespace, *ctx_args]
    secret_cmd = [
        BIN_KUBECTL,
        "create",
        "secret",
        "tls",
        secret_name,
        f"--cert={cert_path}",
        f"--key={key_path}",
        "-n",
        namespace,
        *ctx_args,
    ]
    return [
        PlannedRequest(
            method="kubectl",
            target=f"namespace/{namespace}",
            argv=tuple(ns_cmd),
        ),
        PlannedRequest(
            method="kubectl",
            target=f"secret/{secret_name}",
            argv=tuple(secret_cmd),
        ),
    ]


def plan_k8s_diff_helm(
    release_name: str,
    chart_path: Path | str,
    namespace: str | None = None,
    values: Sequence[Path | str] | None = None,
) -> list[PlannedRequest]:
    """Plan helm-diff execution between cluster release and chart."""
    cmd = build_helm_diff_cmd(
        release_name=release_name,
        chart_path=Path(chart_path),
        namespace=namespace,
        values_files=[Path(v) for v in values] if values else None,
    )
    return [
        PlannedRequest(
            method="helm",
            target="diff",
            argv=tuple(cmd),
        )
    ]


def plan_k8s_enable_tls(
    stack: str,
    tls_dir: Path | str,
    secret_name: str,
    context: str | None = None,
    overwrite: bool = False,
) -> list[PlannedRequest]:
    """Plan TLS secret deployments across stack namespaces."""
    ctx_args = ["--context", context] if context else []
    namespaces = ["default"]
    normalized = stack.lower()
    if "infra" in normalized or normalized == "all":
        namespaces.extend(["argocd", "monitoring", "otel"])
    if "llm" in normalized or normalized == "all":
        namespaces.extend(["llm"])

    cert_path = Path(tls_dir) / CONST_SERVER_CERT_NAME
    key_path = Path(tls_dir) / CONST_SERVER_KEY_NAME

    plans: list[PlannedRequest] = []
    for ns in namespaces:
        plans.append(
            PlannedRequest(
                method="kubectl",
                target=f"namespace/{ns}",
                argv=tuple([BIN_KUBECTL, "get", "namespace", ns, *ctx_args]),
            )
        )
        action = "apply" if overwrite else "create"
        plans.append(
            PlannedRequest(
                method="kubectl",
                target=f"secret/{secret_name}",
                argv=tuple(
                    [
                        BIN_KUBECTL,
                        action,
                        "secret",
                        "tls",
                        secret_name,
                        f"--cert={cert_path}",
                        f"--key={key_path}",
                        "-n",
                        ns,
                        *ctx_args,
                    ]
                ),
            )
        )
    return plans


def plan_k8s_sync_secrets(
    stack: str = "infra",
    context: str | None = None,
) -> list[PlannedRequest]:
    """Plan secret synchronization from cluster to local credentials."""
    ctx_args = ["--context", context] if context else []
    cmd = [
        BIN_KUBECTL,
        "get",
        "secret",
        "argocd-initial-admin-secret",
        "-n",
        "argocd",
        "-o",
        "jsonpath={.data.password}",
        *ctx_args,
    ]
    return [
        PlannedRequest(
            method="kubectl",
            target="secret/argocd-initial-admin-secret",
            argv=tuple(cmd),
        )
    ]


def plan_k8s_teardown_stack(
    k8s_dir: Path | str,
    stack: str = "infra",
    context: str | None = None,
) -> list[PlannedRequest]:
    """Plan stack uninstall and resource deletions."""
    ctx_args = ["--context", context] if context else []
    return [
        PlannedRequest(
            method="kubectl",
            target="apps",
            argv=tuple(
                [BIN_KUBECTL, "get", "application", "-n", "argocd", "-o", "name", *ctx_args]
            ),
        ),
        PlannedRequest(
            method="kubectl",
            target="teardown",
            argv=tuple(
                [BIN_KUBECTL, "delete", "-k", str(k8s_dir), "--ignore-not-found", *ctx_args]
            ),
        ),
    ]


def plan_k8s_validate(
    manifest_path: Path | str,
    k8s_version: str = "1.32.0",
    strict: bool = True,
) -> list[PlannedRequest]:
    """Plan Kubeconform schema validation invocation."""
    cmd = ["kubeconform", "-kubernetes-version", k8s_version]
    if strict:
        cmd.append("-strict")
    cmd.append(str(manifest_path))
    return [
        PlannedRequest(
            method="kubeconform",
            target="validate",
            argv=tuple(cmd),
        )
    ]


def plan_kustomize_apply(
    path: Path | str,
    namespace: str | None = None,
    template: bool = False,
    domain: str | None = None,
) -> list[PlannedRequest]:
    """Plan kustomization apply via kubectl."""
    if template or domain is not None:
        k_args = ["apply", "-f", "-"]
        if namespace:
            k_args.extend(["--namespace", namespace])
        cmd = build_kubectl_cmd(k_args)
        return [
            PlannedRequest(
                method="kubectl",
                target="apply",
                argv=tuple(cmd),
                stdin="<rendered-manifest>",
            )
        ]
    k_args = ["apply", "-k", str(path)]
    if namespace:
        k_args.extend(["--namespace", namespace])
    cmd = build_kubectl_cmd(k_args)
    return [
        PlannedRequest(
            method="kubectl",
            target="apply",
            argv=tuple(cmd),
        )
    ]


def plan_kustomize_build(
    path: Path | str,
    output: str | None = None,
) -> list[PlannedRequest]:
    """Plan kustomize build invocation."""
    cmd = build_kustomize_build_cmd(Path(path))
    if output:
        cmd.extend(["--output", output])
    return [
        PlannedRequest(
            method="kustomize",
            target="build",
            argv=tuple(cmd),
        )
    ]


def plan_kustomize_diff(path: Path | str) -> list[PlannedRequest]:
    """Plan kubectl diff -k invocation."""
    cmd = build_kubectl_cmd(["diff", "-k", str(path)])
    return [
        PlannedRequest(
            method="kubectl",
            target="diff",
            argv=tuple(cmd),
        )
    ]
