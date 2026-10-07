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


def render_devops_configmap_content(
    template_content: str,
    repos: Sequence[str],
    machine_account: str,
    drain_timeout_seconds: int | None = None,
    poll_interval_seconds: int | None = None,
) -> str:
    """The ConfigMap template with its service block set to `repos` and `machine_account`."""
    m = _SERVICE_BLOCK_PATTERN.search(template_content)
    if not m:
        raise KubernetesContextError(
            "Could not locate standard service configuration block in devops ConfigMap template."
        )
    clean_repos = [r.strip() for r in repos if r and r.strip()]
    account = (machine_account or "").strip()
    if not clean_repos or not account:
        raise KubernetesContextError(
            "The devops ConfigMap needs at least one repository and a machine account."
        )

    formatted_repos = "\n".join(f"        - {repo}" for repo in clean_repos)
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


def _configured_repos(settings: Any) -> list[str]:
    """The repositories the service works for, or an error naming the setting."""
    repos = [
        str(r).strip()
        for r in getattr(getattr(settings, "service", None), "repos", None) or []
        if str(r).strip()
    ]
    if not repos:
        raise KubernetesContextError(
            "No repositories configured for the roadmap service. "
            "Set 'service.repos' in config.yaml."
        )
    return repos


def _configured_account(settings: Any) -> str:
    """The machine account the service acts as, or an error naming the settings."""
    for account in (
        getattr(getattr(settings, "service", None), "machine_account", None),
        getattr(getattr(settings, "k8s", None), "github_account", None),
    ):
        if account and str(account).strip():
            return str(account).strip()
    raise KubernetesContextError(
        "No machine account configured for the roadmap service. "
        "Set 'service.machine_account' (or 'k8s.github_account') in config.yaml."
    )


def render_active_devops_configmap(
    k8s_dir: Path | None = None,
    settings: Any = None,
) -> str:
    """ConfigMap devops-cli-config rendered in memory from the active config.

    The repository holds only its template, so the homelab's repositories and account never
    enter git; a deploy applies this rendering and refuses when a setting it needs is unset.
    """
    base_dir = k8s_dir or DEFAULT_K8S_DIR
    template_path = base_dir / "devops" / "configmap.example.yaml"

    if not template_path.is_file():
        raise FileNotFoundError(
            f"DevOps ConfigMap template not found at {template_path}. "
            "Ensure k8s/devops/configmap.example.yaml exists."
        )

    active_settings = settings if settings is not None else load_settings()
    effective_repos = _configured_repos(active_settings)
    effective_account = _configured_account(active_settings)

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
