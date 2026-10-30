"""Kubernetes ConfigMap generation and dynamic synchronization for cluster devops-cli jobs."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from devops_cli.config.defaults import DEFAULT_K8S_DIR
from devops_cli.config.settings import GitHubAppConfig, Settings, load_settings
from devops_cli.exceptions.k8s import KubernetesContextError

_CONFIG_KEY = "devops-cli.yaml"


class _BlockDumper(yaml.SafeDumper):
    """YAML that writes a multi-line string as a literal block, as the template holds its config."""


def _represent_text(dumper: yaml.SafeDumper, text: str) -> yaml.ScalarNode:
    style = "|" if "\n" in text else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", text, style=style)


_BlockDumper.add_representer(str, _represent_text)


def _service_block(
    repos: Sequence[str],
    github_app: GitHubAppConfig,
    drain_timeout_seconds: int | None,
    poll_interval_seconds: int | None,
    github_requests_per_hour: int | None,
) -> dict[str, Any]:
    """The ConfigMap's `service` section: the repositories, the GitHub App the Service acts as,
    and the timings and the hourly request budget when set."""
    clean_repos = [r.strip() for r in repos if r and r.strip()]
    if not clean_repos or _missing_app_settings(github_app):
        raise KubernetesContextError(
            "The devops ConfigMap needs at least one repository and the GitHub App's ID, "
            "installation ID and slug."
        )
    service: dict[str, Any] = {
        "repos": clean_repos,
        # The Service names no single repository for its tokens: the Job it makes does (#2667).
        "github_app": github_app.model_dump(mode="json", exclude={"token_repository"}),
    }
    optional = {
        "drain_timeout_seconds": drain_timeout_seconds,
        "poll_interval_seconds": poll_interval_seconds,
        "github_requests_per_hour": github_requests_per_hour,
    }
    service.update({key: value for key, value in optional.items() if value is not None})
    return service


def render_devops_configmap_content(
    template_content: str,
    repos: Sequence[str],
    github_app: GitHubAppConfig,
    drain_timeout_seconds: int | None = None,
    poll_interval_seconds: int | None = None,
    github_requests_per_hour: int | None = None,
) -> str:
    """The ConfigMap template with its service section set to `repos` and `github_app`.

    The template's config is read as YAML and written again, so the applied ConfigMap does not
    keep the template's comments.
    """
    manifest = yaml.safe_load(template_content)
    data = manifest.get("data") if isinstance(manifest, dict) else None
    if not isinstance(data, dict):
        data = {}
    config = yaml.safe_load(data.get(_CONFIG_KEY) or "")
    if not isinstance(config, dict) or not isinstance(config.get("service"), dict):
        raise KubernetesContextError(
            "Could not locate standard service configuration block in devops ConfigMap template."
        )
    config["service"] = _service_block(
        repos, github_app, drain_timeout_seconds, poll_interval_seconds, github_requests_per_hour
    )
    Settings.model_validate(config)
    data[_CONFIG_KEY] = yaml.dump(config, Dumper=_BlockDumper, sort_keys=False)
    return yaml.dump(manifest, Dumper=_BlockDumper, sort_keys=False)


def _configured_repos(settings: Settings) -> list[str]:
    """The repositories the service works for, or an error naming the setting."""
    repos = [str(r).strip() for r in settings.service.repos if str(r).strip()]
    if not repos:
        raise KubernetesContextError(
            "No repositories configured for the roadmap service. "
            "Set 'service.repos' in config.yaml."
        )
    return repos


def _missing_app_settings(github_app: GitHubAppConfig) -> list[str]:
    """The App settings that are not set."""
    wanted = (
        ("service.github_app.app_id", github_app.app_id),
        ("service.github_app.installation_id", github_app.installation_id),
        ("service.github_app.slug", github_app.slug),
    )
    return [option for option, value in wanted if not value]


def _configured_app(settings: Settings) -> GitHubAppConfig:
    """The GitHub App the service acts as, or an error naming each setting that is not set."""
    github_app = settings.service.github_app
    missing = _missing_app_settings(github_app)
    if missing:
        raise KubernetesContextError(
            "The roadmap service acts as a GitHub App, so set "
            + ", ".join(f"'{option}'" for option in missing)
            + " in config.yaml."
        )
    return github_app


def render_active_devops_configmap(
    k8s_dir: Path | None = None,
    settings: Settings | None = None,
) -> str:
    """ConfigMap devops-cli-config rendered in memory from the active config.

    The repository holds only its template, so the homelab's repositories and App never enter
    git; a deploy applies this rendering and refuses when a setting it needs is unset.
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
    github_app = _configured_app(active_settings)

    drain_timeout = active_settings.service.drain_timeout_seconds
    poll_interval = active_settings.service.poll_interval_seconds
    # The Service keeps its own default unless a source sets the budget: the ConfigMap copies no
    # default into the cluster (#2755).
    budget = (
        active_settings.service.github_requests_per_hour
        if "github_requests_per_hour" in active_settings.service.model_fields_set
        else None
    )

    template_text = template_path.read_text(encoding="utf-8")
    return render_devops_configmap_content(
        template_text,
        repos=effective_repos,
        github_app=github_app,
        drain_timeout_seconds=drain_timeout,
        poll_interval_seconds=poll_interval,
        github_requests_per_hour=budget,
    )
