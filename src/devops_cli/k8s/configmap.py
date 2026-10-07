"""Kubernetes ConfigMap generation and dynamic synchronization for cluster devops-cli jobs."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from devops_cli.config.defaults import DEFAULT_K8S_DIR
from devops_cli.config.settings import Settings, load_settings
from devops_cli.exceptions.k8s import KubernetesContextError

_SERVICE_BLOCK_PATTERN = re.compile(
    r"(    service:\s*\n      repos:\s*\n)(?:        - [^\n]+\s*\n)+(\s*machine_account:\s*)[^\n]+",
    re.MULTILINE,
)

DEFAULT_PLACEHOLDER_REPO = "owner/repo"
DEFAULT_PLACEHOLDER_ACCOUNT = "devops-bot"


def _format_repo_items(repos: Sequence[str]) -> str:
    """Format repository names as YAML list elements indented for devops-cli.yaml."""
    clean_repos = [r.strip() for r in repos if r and r.strip()]
    if not clean_repos:
        clean_repos = [DEFAULT_PLACEHOLDER_REPO]
    return "\n".join(f"        - {repo}" for repo in clean_repos)


def render_devops_configmap_content(
    template_content: str,
    repos: Sequence[str] | None = None,
    machine_account: str | None = None,
    drain_timeout_seconds: int | None = None,
    poll_interval_seconds: int | None = None,
) -> str:
    """Substitute service target repositories and machine account into ConfigMap template."""
    m = _SERVICE_BLOCK_PATTERN.search(template_content)
    if not m:
        raise KubernetesContextError(
            "Could not locate standard service configuration block in devops ConfigMap template."
        )

    formatted_repos = _format_repo_items(repos or [])
    account = (machine_account or "").strip() or DEFAULT_PLACEHOLDER_ACCOUNT
    extra_lines = ""
    if drain_timeout_seconds is not None:
        extra_lines += f"\n      drain_timeout_seconds: {drain_timeout_seconds}"
    if poll_interval_seconds is not None:
        extra_lines += f"\n      poll_interval_seconds: {poll_interval_seconds}"
    replacement = f"{m.group(1)}{formatted_repos}\n{m.group(2)}{account}{extra_lines}"
    rendered = _SERVICE_BLOCK_PATTERN.sub(replacement, template_content, count=1)

    parsed_cm = yaml.safe_load(rendered)
    if not isinstance(parsed_cm, dict) or "data" not in parsed_cm:
        raise KubernetesContextError("Rendered ConfigMap is not a valid Kubernetes resource.")
    inner_raw = yaml.safe_load(parsed_cm["data"].get("devops-cli.yaml", ""))
    Settings.model_validate(inner_raw)

    return rendered


def _extract_existing_service_params(target_path: Path) -> tuple[list[str], str | None]:
    """Extract existing repositories and machine account from target ConfigMap if present."""
    if not target_path.is_file():
        return [], None
    try:
        raw_doc = yaml.safe_load(target_path.read_text(encoding="utf-8"))
        inner = yaml.safe_load(raw_doc["data"]["devops-cli.yaml"])
        svc = inner.get("service") or {}
        repos = [r for r in svc.get("repos", []) if r and r != DEFAULT_PLACEHOLDER_REPO]
        account = svc.get("machine_account")
        return repos, account
    except Exception:
        return [], None


def _resolve_effective_repos(
    settings: Any,
    existing_repos: list[str],
) -> list[str]:
    """Determine effective repository list from settings, existing file, or defaults."""
    cfg_repos = getattr(getattr(settings, "service", None), "repos", None)
    if cfg_repos:
        return list(cfg_repos)
    if existing_repos:
        return existing_repos
    return [DEFAULT_PLACEHOLDER_REPO]


def _resolve_effective_account(
    settings: Any,
    existing_account: str | None,
) -> str:
    """Determine effective machine account from service settings, k8s account, or defaults."""
    svc_account = getattr(getattr(settings, "service", None), "machine_account", None)
    if svc_account and str(svc_account).strip():
        return str(svc_account).strip()
    k8s_account = getattr(getattr(settings, "k8s", None), "github_account", None)
    if k8s_account and str(k8s_account).strip():
        return str(k8s_account).strip()
    if existing_account and existing_account.strip():
        return existing_account.strip()
    return DEFAULT_PLACEHOLDER_ACCOUNT


def ensure_devops_configmap(
    k8s_dir: Path | None = None,
    settings: Any = None,
    target_path: Path | None = None,
    force: bool = False,
) -> Path:
    """Ensure k8s/devops/configmap.yaml exists and is synchronized from active configuration."""
    base_dir = k8s_dir or DEFAULT_K8S_DIR
    template_path = base_dir / "devops" / "configmap.example.yaml"
    dest_path = target_path or (base_dir / "devops" / "configmap.yaml")

    if not template_path.is_file():
        raise FileNotFoundError(
            f"DevOps ConfigMap template not found at {template_path}. "
            "Ensure k8s/devops/configmap.example.yaml exists."
        )

    if dest_path.is_file() and not force:
        return dest_path

    active_settings = settings if settings is not None else load_settings()
    existing_repos, existing_account = _extract_existing_service_params(dest_path)

    effective_repos = _resolve_effective_repos(active_settings, existing_repos)
    effective_account = _resolve_effective_account(active_settings, existing_account)

    svc = getattr(active_settings, "service", None)
    drain_timeout = getattr(svc, "drain_timeout_seconds", None)
    poll_interval = getattr(svc, "poll_interval_seconds", None)

    template_text = template_path.read_text(encoding="utf-8")
    rendered = render_devops_configmap_content(
        template_text,
        repos=effective_repos,
        machine_account=effective_account,
        drain_timeout_seconds=drain_timeout,
        poll_interval_seconds=poll_interval,
    )

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(rendered, encoding="utf-8")
    return dest_path


def render_active_devops_configmap(
    k8s_dir: Path | None = None,
    settings: Any = None,
) -> str:
    """Render devops ConfigMap with active settings without modifying tracked files on disk."""
    base_dir = k8s_dir or DEFAULT_K8S_DIR
    template_path = base_dir / "devops" / "configmap.example.yaml"

    if not template_path.is_file():
        raise FileNotFoundError(
            f"DevOps ConfigMap template not found at {template_path}. "
            "Ensure k8s/devops/configmap.example.yaml exists."
        )

    active_settings = settings if settings is not None else load_settings()
    effective_repos = _resolve_effective_repos(active_settings, [])
    effective_account = _resolve_effective_account(active_settings, None)

    svc = getattr(active_settings, "service", None)
    drain_timeout = getattr(svc, "drain_timeout_seconds", None)
    poll_interval = getattr(svc, "poll_interval_seconds", None)

    template_text = template_path.read_text(encoding="utf-8")
    return render_devops_configmap_content(
        template_text,
        repos=effective_repos,
        machine_account=effective_account,
        drain_timeout_seconds=drain_timeout,
        poll_interval_seconds=poll_interval,
    )
