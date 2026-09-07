"""Kubernetes command group (cluster contexts, node status, manifest apply, pod logs, stack lifecycle, TLS, auditing, and diagnostics)."""

from __future__ import annotations

import shutil

from devops_cli.commands.k8s.bootstrap import bootstrap
from devops_cli.commands.k8s.cluster_context import (
    apply,
    contexts,
    logs,
    status,
    switch_context,
)
from devops_cli.commands.k8s.cluster_runtime import (
    _cluster_reachable,
    _k8s_clients,
    _minikube_running,
    _run_cmd,
    _validate_k8s_identifier,
)
from devops_cli.commands.k8s.diagnostics import (
    chaos_cmd,
    diff_helm_cmd,
    pods_cmd,
    stream_logs_cmd,
)
from devops_cli.commands.k8s.networking import (
    _detect_service_url,
    _extract_first_node_ip,
    _parse_minikube_service_url,
    _resolve_accessible_url,
    _resolve_k8s_node_port_url,
    _resolve_stacks,
    _verify_url_reachability,
    configure_urls,
    port_forward,
    port_forward_status,
    port_forward_stop,
)
from devops_cli.commands.k8s.security_audit import (
    k8s_audit,
    k8s_check_deprecated,
    k8s_lint,
    k8s_validate,
    rbac_audit,
    validate_policy_cmd,
)
from devops_cli.commands.k8s.stack_lifecycle import (
    _HELM_RELEASES,
    _HELM_RELEASES_BY_STACK,
    _HELM_REPOS,
    _HELM_REPOS_BY_STACK,
    _MANIFESTS_BY_STACK,
    VALID_STACKS,
    _adopt_helm_resource_if_conflict,
    _bootstrap_openwebui_account,
    _ensure_qdrant_api_key_secret,
    bootstrap_openwebui,
    deploy_stack,
    sync_secrets,
    teardown_stack,
)
from devops_cli.commands.k8s.tls_management import (
    create_tls_secret,
    enable_tls_stack,
)
from devops_cli.core.cli import new_typer
from devops_cli.core.process import run_subprocess
from devops_cli.lang import HELP

app = new_typer(help=HELP.k8s.app, no_args_is_help=True)

# Register subcommands
app.command()(contexts)
app.command("switch-context")(switch_context)
app.command()(status)
app.command()(apply)
app.command()(logs)
app.command("bootstrap")(bootstrap)
app.command("bootstrap-openwebui")(bootstrap_openwebui)
app.command("deploy-stack")(deploy_stack)
app.command("sync-secrets")(sync_secrets)
app.command("configure-urls")(configure_urls)
app.command("port-forward")(port_forward)
app.command("port-forward-status")(port_forward_status)
app.command("port-forward-stop")(port_forward_stop)
app.command("teardown-stack")(teardown_stack)
app.command("rbac-audit")(rbac_audit)
app.command("lint")(k8s_lint)
app.command("audit")(k8s_audit)
app.command("check-deprecated")(k8s_check_deprecated)
app.command("create-tls-secret")(create_tls_secret)
app.command("enable-tls")(enable_tls_stack)
app.command("validate")(k8s_validate)
app.command(name="validate-policy")(validate_policy_cmd)
app.command(name="stream-logs")(stream_logs_cmd)
app.command(name="diff-helm")(diff_helm_cmd)
app.command(name="chaos")(chaos_cmd)
app.command(name="pods")(pods_cmd)

__all__ = [
    "app",
    "apply",
    "bootstrap",
    "bootstrap_openwebui",
    "chaos_cmd",
    "configure_urls",
    "contexts",
    "create_tls_secret",
    "deploy_stack",
    "diff_helm_cmd",
    "enable_tls_stack",
    "k8s_audit",
    "k8s_check_deprecated",
    "k8s_lint",
    "k8s_validate",
    "logs",
    "port_forward",
    "pods_cmd",
    "rbac_audit",
    "run_subprocess",
    "shutil",
    "status",
    "stream_logs_cmd",
    "switch_context",
    "sync_secrets",
    "teardown_stack",
    "validate_policy_cmd",
    "_adopt_helm_resource_if_conflict",
    "_bootstrap_openwebui_account",
    "_ensure_qdrant_api_key_secret",
    "_cluster_reachable",
    "_detect_service_url",
    "_extract_first_node_ip",
    "_HELM_RELEASES",
    "_HELM_RELEASES_BY_STACK",
    "_HELM_REPOS",
    "_HELM_REPOS_BY_STACK",
    "_k8s_clients",
    "_MANIFESTS_BY_STACK",
    "_minikube_running",
    "_parse_minikube_service_url",
    "_resolve_accessible_url",
    "_resolve_k8s_node_port_url",
    "_resolve_stacks",
    "_run_cmd",
    "_validate_k8s_identifier",
    "_verify_url_reachability",
    "VALID_STACKS",
]
