"""Kubernetes stack credential discovery and secure OS Keyring synchronization."""

from __future__ import annotations

import base64

from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.config.settings import _keyring_set
from devops_cli.core.process import run_subprocess
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from devops_cli.telemetry.tracer import trace_span


def _decode_k8s_secret_field(raw_b64: str) -> str | None:
    """Safely decode base64 secret field into string."""
    cleaned = raw_b64.strip()
    if not cleaned:
        return None
    try:
        decoded_bytes = base64.b64decode(cleaned)
        return decoded_bytes.decode("utf-8").strip()
    except Exception:
        return None


def fetch_secret_data(
    secret_name: str,
    namespace: str,
    context: str | None = None,
) -> dict[str, str]:
    """Fetch and decode all data fields from a Kubernetes Secret in a single call."""
    import json

    cmd = [
        "kubectl",
        "get",
        "secret",
        secret_name,
        "-n",
        namespace,
        "-o=json",
    ]
    if context:
        cmd.extend(["--context", context])

    res = run_subprocess(cmd, quiet=True, timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS)
    if res.returncode != 0 or not res.stdout.strip():
        return {}

    try:
        payload = json.loads(res.stdout)
        data = payload.get("data", {})
        return {k: _decode_k8s_secret_field(v) or "" for k, v in data.items() if isinstance(v, str)}
    except Exception:
        return {}


def fetch_secret_field(
    secret_name: str,
    field: str,
    namespace: str,
    context: str | None = None,
) -> str | None:
    """Fetch and decode a specific field from a Kubernetes Secret."""
    data = fetch_secret_data(secret_name, namespace, context=context)
    val = data.get(field)
    return val if val else None


@trace_span("k8s.credentials.argocd")
def fetch_argocd_password(
    namespace: str = "argocd",
    context: str | None = None,
    save_to_keyring: bool = True,
) -> str | None:
    """Fetch initial ArgoCD admin password from Kubernetes and store in keyring."""
    pw = fetch_secret_field(
        secret_name="argocd-initial-admin-secret",
        field="password",
        namespace=namespace,
        context=context,
    )
    if pw and save_to_keyring:
        _keyring_set("argocd_password", pw)
        GLOBAL_METRICS.increment_counter(
            "k8s_credentials_synced_total", labels={"service": "argocd"}
        )
    return pw


@trace_span("k8s.credentials.grafana")
def fetch_grafana_password(
    namespaces: list[str] | None = None,
    context: str | None = None,
    save_to_keyring: bool = True,
) -> str | None:
    """Fetch Grafana admin password from Kubernetes and store in keyring."""
    candidate_namespaces = namespaces or ["monitoring", "grafana", "default"]
    candidate_secrets = ["kube-prometheus-stack-grafana", "grafana", "grafana-admin-credentials"]
    candidate_fields = ["admin-password", "admin_password", "password"]

    for ns in candidate_namespaces:
        for secret_name in candidate_secrets:
            data = fetch_secret_data(secret_name, ns, context=context)
            if not data:
                continue
            for field in candidate_fields:
                pw = data.get(field)
                if pw:
                    if save_to_keyring:
                        _keyring_set("grafana_password", pw)
                        GLOBAL_METRICS.increment_counter(
                            "k8s_credentials_synced_total", labels={"service": "grafana"}
                        )
                    return pw
    return None


@trace_span("k8s.credentials.sync")
def sync_k8s_credentials(
    context: str | None = None,
    stack: str = "infra",
    save_to_keyring: bool = True,
) -> dict[str, bool]:
    """Discover and synchronize Kubernetes stack credentials into OS Keyring."""
    results: dict[str, bool] = {}
    if stack in ("infra", "all"):
        argo_pw = fetch_argocd_password(context=context, save_to_keyring=save_to_keyring)
        results["argocd"] = argo_pw is not None

        grafana_pw = fetch_grafana_password(context=context, save_to_keyring=save_to_keyring)
        results["grafana"] = grafana_pw is not None

    return results
