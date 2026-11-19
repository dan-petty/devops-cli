"""Argo CD trial environment lifecycle (#1082).

Deploys transient trial workloads from internal Gitea branches into fenced cluster namespaces
using Argo CD.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from devops_cli.argo.crd import get_argo_crd_service
from devops_cli.config.commands import build_kubectl_cmd
from devops_cli.config.constants import CONST_ARGO_PLURAL_APPLICATIONS
from devops_cli.config.defaults import DEFAULT_ARGOCD_NAMESPACE
from devops_cli.config.settings import get_gitea_token, load_settings
from devops_cli.core.clock import sleep
from devops_cli.core.process import run_subprocess
from devops_cli.core.validation import validate_k8s_name
from devops_cli.exceptions.argo import ArgoError, ArgoResourceNotFoundError
from devops_cli.gitea.client import GiteaClient
from devops_cli.gitea.exceptions import GiteaAccessBlocked, GiteaError
from devops_cli.output import format_timestamp_age

logger = logging.getLogger(__name__)

DEFAULT_TRIAL_REPO = "dan-petty/devops-cli"
TRIAL_PROJECT = "trial"
TRIAL_WAIT_TIMEOUT_SECONDS = 120.0
TRIAL_POLL_INTERVAL_SECONDS = 2.0


def branch_to_dns_label(branch: str) -> str:
    """Convert a git branch name into a valid RFC 1123 DNS label."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", branch.lower()).strip("-")
    cleaned = cleaned[:57].rstrip("-")
    if not cleaned:
        cleaned = "trial"
    return cleaned


def normalize_trial_name(name: str) -> str:
    """Normalize and validate a trial name, ensuring it starts with 'trial-'."""
    trial_name = name if name.startswith("trial-") else f"trial-{name}"
    validate_k8s_name(trial_name, "trial name", namespace=True)
    return trial_name


def build_trial_namespace_manifest(name: str) -> dict[str, Any]:
    """Build the Kubernetes Namespace manifest for a trial."""
    ns_name = normalize_trial_name(name)
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": ns_name,
            "labels": {
                "app.kubernetes.io/managed-by": "devops-cli",
                "pod-security.kubernetes.io/enforce": "restricted",
                "pod-security.kubernetes.io/warn": "restricted",
                "pod-security.kubernetes.io/audit": "restricted",
            },
        },
    }


def build_trial_application_manifest(
    name: str,
    *,
    branch: str,
    path: str,
    repo: str = DEFAULT_TRIAL_REPO,
) -> dict[str, Any]:
    """Build the ArgoCD Application manifest for a trial."""
    app_name = normalize_trial_name(name)
    repo_url = f"http://gitea-http.gitea.svc.cluster.local:3000/{repo}.git"
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {
            "name": app_name,
            "namespace": DEFAULT_ARGOCD_NAMESPACE,
            "finalizers": ["resources-finalizer.argocd.argoproj.io"],
        },
        "spec": {
            "project": TRIAL_PROJECT,
            "source": {
                "repoURL": repo_url,
                "targetRevision": branch,
                "path": path,
            },
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": app_name,
            },
            "syncPolicy": {
                "automated": {
                    "prune": True,
                    "selfHeal": True,
                },
            },
        },
    }


def apply_trial_namespace(name: str, context: str | None = None) -> None:
    """Server-side apply a trial Namespace with restricted Pod Security."""
    manifest = build_trial_namespace_manifest(name)
    ns_name = manifest["metadata"]["name"]
    payload = json.dumps(manifest)
    cmd = build_kubectl_cmd(
        [
            "apply",
            "--server-side",
            "--field-manager=devops-cli",
            "--force-conflicts",
            "-f",
            "-",
        ],
        context=context,
    )
    result = run_subprocess(cmd, input=payload, quiet=True, timeout=30.0)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise ArgoError(f"Failed to apply Namespace '{ns_name}': {detail}")


def delete_trial_namespace(name: str, context: str | None = None) -> None:
    """Delete a trial Namespace, ensuring it starts with 'trial-'."""
    ns_name = normalize_trial_name(name)
    cmd = build_kubectl_cmd(
        ["delete", "namespace", ns_name, "--ignore-not-found"],
        context=context,
    )
    result = run_subprocess(cmd, quiet=True, timeout=60.0)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise ArgoError(f"Failed to delete Namespace '{ns_name}': {detail}")


def check_gitea_branch_and_path(
    branch: str,
    path: str,
    repo: str = DEFAULT_TRIAL_REPO,
) -> None:
    """Validate that branch and path exist on Gitea repository.

    Fails with message naming #1081 if Gitea is not configured or reachable.
    """
    settings = load_settings()
    url = settings.gitea.url
    token = get_gitea_token(settings)
    if not url or not token:
        raise ArgoError(
            "Gitea URL or token is not configured. The Gitea stack (#1081) is required for trials."
        )

    owner, sep, repo_name = repo.partition("/")
    if not sep or not owner or not repo_name:
        raise ArgoError(f"Invalid repository '{repo}'. Expected format 'owner/repo'.")

    try:
        with GiteaClient(url, token) as client:
            branch_info = client.branch(owner, repo_name, branch)
            if branch_info is None:
                raise ArgoError(f"Branch '{branch}' does not exist on Gitea repository '{repo}'.")
            contents = client.contents(owner, repo_name, path, ref=branch)
            if contents is None:
                raise ArgoError(
                    f"Path '{path}' does not exist on branch '{branch}' in Gitea repository '{repo}'."
                )
    except GiteaAccessBlocked:
        raise
    except GiteaError as exc:
        raise ArgoError(f"Gitea error while inspecting '{repo}': {exc}") from exc
    except Exception as exc:
        raise ArgoError(
            f"Failed to connect to Gitea at {url}. The Gitea stack (#1081) is required: {exc}"
        ) from exc


def start_trial(
    *,
    branch: str,
    path: str,
    repo: str = DEFAULT_TRIAL_REPO,
    name: str | None = None,
    context: str | None = None,
    dry_run: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Start a trial application and namespace, checking Gitea first."""
    check_gitea_branch_and_path(branch, path, repo=repo)

    resolved_name = name or branch_to_dns_label(branch)
    ns_manifest = build_trial_namespace_manifest(resolved_name)
    app_manifest = build_trial_application_manifest(
        resolved_name, branch=branch, path=path, repo=repo
    )

    if not dry_run:
        apply_trial_namespace(resolved_name, context=context)
        get_argo_crd_service(context=context).apply_application(
            app_manifest, namespace=DEFAULT_ARGOCD_NAMESPACE
        )

    return ns_manifest, app_manifest


def end_trial(
    name: str,
    *,
    context: str | None = None,
    dry_run: bool = False,
    timeout_seconds: float = TRIAL_WAIT_TIMEOUT_SECONDS,
) -> str:
    """End a trial application and remove its namespace."""
    app_name = normalize_trial_name(name)

    if not dry_run:
        crd = get_argo_crd_service(context=context)
        try:
            crd.delete_application(app_name, namespace=DEFAULT_ARGOCD_NAMESPACE)
        except ArgoResourceNotFoundError:
            pass

        # Wait for Application removal
        start_time = time.monotonic()
        while time.monotonic() - start_time < timeout_seconds:
            try:
                crd.get_resource(
                    CONST_ARGO_PLURAL_APPLICATIONS, app_name, namespace=DEFAULT_ARGOCD_NAMESPACE
                )
                sleep(TRIAL_POLL_INTERVAL_SECONDS)
            except ArgoResourceNotFoundError:
                break
        else:
            raise ArgoError(f"Timed out waiting for Application '{app_name}' to be deleted.")

        delete_trial_namespace(app_name, context=context)

    return app_name


def list_trials(context: str | None = None) -> list[list[str]]:
    """List all Argo CD applications in project 'trial'."""
    crd = get_argo_crd_service(context=context)
    raw_apps = crd.list_resources(
        CONST_ARGO_PLURAL_APPLICATIONS, namespace=DEFAULT_ARGOCD_NAMESPACE
    )
    rows: list[list[str]] = []
    for app in raw_apps:
        spec = app.get("spec", {})
        if spec.get("project") != TRIAL_PROJECT:
            continue
        meta = app.get("metadata", {})
        name = str(meta.get("name", ""))
        source = spec.get("source", {})
        branch = str(source.get("targetRevision", ""))
        path = str(source.get("path", ""))
        status = app.get("status", {})
        sync = str(status.get("sync", {}).get("status", "Unknown"))
        health = str(status.get("health", {}).get("status", "Unknown"))
        created_at = str(meta.get("creationTimestamp", ""))
        age = format_timestamp_age(created_at) if created_at else ""
        rows.append([name, branch, path, sync, health, age])
    return rows
