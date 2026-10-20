"""Live Argo CD diff and override reporting at release cut (#1343)."""

from __future__ import annotations

import json
import logging
import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from devops_cli.argo.credentials import (
    resolve_argocd_server_address,
    resolve_argocd_server_and_token,
)
from devops_cli.config.constants import (
    CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS,
    CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS_BY_STACK,
    CONST_MAX_ERROR_DETAIL_LENGTH,
)
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.k8s import KubernetesError
from devops_cli.k8s.argocd_gate import (
    _get_repo_origin,
    _normalize_git_url,
    discover_argocd_applications,
)
from devops_cli.k8s.argocd_overrides import _host_fields
from devops_cli.k8s.template import build_manifest_path, holds_template_domain_value
from devops_cli.output import print_info, print_warning

logger = logging.getLogger(__name__)


def _find_repo_source_position(sources: list[dict[str, Any]], expected_origin: str) -> int | None:
    """Find 1-based source position in spec.sources corresponding to the target repository."""
    norm_expected = _normalize_git_url(expected_origin)
    for pos, s in enumerate(sources, start=1):
        if not isinstance(s, dict) or "chart" in s:
            continue
        repo_url = s.get("repoURL")
        if repo_url and _normalize_git_url(repo_url) == norm_expected:
            return pos
    # Fallback: first source with path and no chart
    for pos, s in enumerate(sources, start=1):
        if isinstance(s, dict) and "chart" not in s and "path" in s:
            return pos
    return None


def _extract_patch_ops(patch_val: Any) -> list[dict[str, Any]]:
    """Parse patch payload into a list of operation dictionaries."""
    if isinstance(patch_val, str):
        try:
            parsed = json.loads(patch_val)
            return parsed if isinstance(parsed, list) else []
        except ValueError, TypeError:
            return []
    return patch_val if isinstance(patch_val, list) else []


def _extract_tested_hosts_from_patch(patch_def: Any) -> set[str]:
    """Extract tested host values from a single kustomize patch definition."""
    if not isinstance(patch_def, dict):
        return set()
    ops = _extract_patch_ops(patch_def.get("patch"))
    tested: set[str] = set()
    for op in ops:
        if isinstance(op, dict) and op.get("op") == "test":
            val = str(op.get("value", "")).strip()
            if val:
                tested.add(val)
    return tested


def extract_live_tested_hosts(app_data: dict[str, Any]) -> set[str]:
    """Extract set of host values tested by JSON patches in an Argo CD Application."""
    tested_hosts: set[str] = set()
    spec = app_data.get("spec", {})
    sources: list[dict[str, Any]] = (
        spec.get("sources", []) if "sources" in spec else [spec.get("source", {})]
    )

    for s in sources:
        if not isinstance(s, dict):
            continue
        patches = s.get("kustomize", {}).get("patches", [])
        for p in patches:
            tested_hosts.update(_extract_tested_hosts_from_patch(p))

    return tested_hosts


def _resolve_homelab_stack(app_name: str) -> str:
    """Determine the deploy-stack name for a homelab application."""
    for stack, apps in CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS_BY_STACK.items():
        if app_name in apps:
            return stack
    return "devops"


def _extract_tip_placeholders(docs: list[Any]) -> set[str]:
    """Find all placeholder template domain host values across rendered manifests."""
    placeholders: set[str] = set()
    for d in docs:
        if not isinstance(d, dict):
            continue
        for _ptr, val in _host_fields(d):
            if holds_template_domain_value(val):
                placeholders.add(val)
    return placeholders


def _check_homelab_placeholder_hosts(
    app_name: str,
    doc: dict[str, Any],
    root: Path,
    server: str,
    runner: Callable[..., Any],
    env: dict[str, str],
) -> list[str]:
    """Check if homelab application has placeholder hosts at tip without live test operations."""
    cmd = ["argocd", "app", "get", app_name, "--server", server, "--grpc-web", "-o", "json"]
    try:
        proc = runner(cmd, env=env, capture_output=True, text=True, check=False)
        if proc.returncode != 0 or not proc.stdout:
            return []
        app_data = json.loads(proc.stdout)
    except (OSError, ValueError, TypeError) as exc:
        logger.debug("Failed to retrieve live application %s: %s", app_name, exc)
        return []

    live_tested = extract_live_tested_hosts(app_data)
    path_str = doc.get("spec", {}).get("source", {}).get("path")
    if not path_str:
        return []

    target_path = root / path_str
    if not target_path.exists():
        return []

    try:
        rendered = build_manifest_path(target_path)
        docs = list(yaml.safe_load_all(rendered))
    except KubernetesError, OSError, yaml.YAMLError:
        return []

    tip_placeholders = _extract_tip_placeholders(docs)
    uncovered = sorted(tip_placeholders - live_tested)
    stack = _resolve_homelab_stack(app_name)
    return [
        f"Placeholder host '{host}' in application '{app_name}' has no live override. "
        f"Run 'devops k8s deploy-stack --stack {stack}'."
        for host in uncovered
    ]


def _diff_application(
    app_name: str,
    doc: dict[str, Any],
    server: str,
    sha: str,
    expected_origin: str,
    runner: Callable[..., Any],
    env: dict[str, str],
) -> str | None:
    """Execute argocd app diff for a single application at target SHA revision."""
    spec = doc.get("spec", {})
    sources = spec.get("sources")

    if isinstance(sources, list):
        pos = _find_repo_source_position(sources, expected_origin)
        if pos is None:
            return None
        cmd = [
            "argocd",
            "app",
            "diff",
            app_name,
            "--server",
            server,
            "--grpc-web",
            "--source-positions",
            str(pos),
            "--revisions",
            sha,
        ]
    else:
        source = spec.get("source", {})
        if not source or (not source.get("repoURL") and not source.get("path")):
            return None
        cmd = [
            "argocd",
            "app",
            "diff",
            app_name,
            "--server",
            server,
            "--grpc-web",
            "--revision",
            sha,
        ]

    try:
        proc = runner(cmd, env=env, capture_output=True, text=True, check=False)
        if proc.returncode == 0:
            return f"{app_name}: clean"
        if proc.returncode == 1:
            return f"{app_name}: differs"
        err = (str(proc.stderr or "") or str(proc.stdout or "")).strip()[
            :CONST_MAX_ERROR_DETAIL_LENGTH
        ]
        return f"{app_name}: failed: {err}"
    except OSError as exc:
        err = str(exc)[:CONST_MAX_ERROR_DETAIL_LENGTH]
        return f"{app_name}: failed: {err}"


def _resolve_target_sha(root: Path, ref: str | None, sha: str | None) -> str:
    """Resolve git commit SHA for diff comparisons."""
    if sha:
        return sha.strip()
    target_ref = ref or "HEAD"
    proc = run_subprocess(
        ["git", "-C", str(root), "rev-parse", target_ref],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0 and proc.stdout and proc.stdout.strip():
        return proc.stdout.strip()
    return target_ref


def _check_argocd_prerequisites() -> tuple[str, str] | None:
    """Verify argocd binary, URL and token, returning (server_address, token) or None."""
    if shutil.which("argocd") is None:
        print_warning("argocd binary is not installed, skipping live Argo CD report.", prefix=False)
        return None

    url, token = resolve_argocd_server_and_token()
    if not url:
        print_warning("argocd.url is not configured, skipping live Argo CD report.", prefix=False)
        return None
    if not token:
        print_warning(
            "Argo CD token is not configured, skipping live Argo CD report.", prefix=False
        )
        return None

    return resolve_argocd_server_address(url), token


def _print_report_summary(report_lines: list[str]) -> None:
    """Print formatted summary lines for the live Argo CD report."""
    if not report_lines:
        return
    print_info(f"Argo CD live report ({len(report_lines)} item(s)):", prefix=False)
    for line in report_lines:
        if "differs" in line or "failed" in line or "has no live override" in line:
            print_warning(f"  - {line}", prefix=False)
        else:
            print_info(f"  - {line}", prefix=False)


def report_argocd_live_diff(
    root: Path,
    *,
    ref: str | None = None,
    sha: str | None = None,
    runner: Callable[..., Any] | None = None,
) -> list[str]:
    """Execute live non-blocking Argo CD application diff and override report (#1343).

    Checks whether the argocd CLI binary, server URL, and token exist. If any are missing,
    emits a single warning and returns without blocking.
    """
    prereqs = _check_argocd_prerequisites()
    if prereqs is None:
        return []

    server, token = prereqs
    runner_fn = runner or run_subprocess
    target_sha = _resolve_target_sha(root, ref, sha)
    expected_origin = _get_repo_origin(root)
    apps = discover_argocd_applications(root)
    if not apps:
        return []

    env = dict(os.environ)
    env["ARGOCD_AUTH_TOKEN"] = token

    report_lines: list[str] = []

    for app_name, doc in sorted(apps.items()):
        diff_res = _diff_application(
            app_name, doc, server, target_sha, expected_origin, runner_fn, env
        )
        if diff_res:
            report_lines.append(diff_res)

        if app_name in CONST_K8S_ARGOCD_HOMELAB_APPLICATIONS:
            placeholder_warnings = _check_homelab_placeholder_hosts(
                app_name, doc, root, server, runner_fn, env
            )
            report_lines.extend(placeholder_warnings)

    _print_report_summary(report_lines)
    return report_lines
