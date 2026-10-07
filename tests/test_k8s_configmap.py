"""Tests for Kubernetes devops ConfigMap rendering and dynamic synchronization."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from devops_cli.config.settings import Settings
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.configmap import (
    DEFAULT_PLACEHOLDER_ACCOUNT,
    DEFAULT_PLACEHOLDER_REPO,
    render_active_devops_configmap,
    render_devops_configmap_content,
)

SAMPLE_TEMPLATE = """apiVersion: v1
kind: ConfigMap
metadata:
  name: devops-cli-config
  namespace: devops
data:
  devops-cli.yaml: |
    ai:
      provider: gateway
      gateway_url: http://llm-gateway.llm.svc.cluster.local:4000/v1
      allow_private_network: true
      model: devops-background
      tasks:
        analysis:
          model: devops-background
          context_window: 65536
        chat:
          model: devops-background
        embedding:
          model: bge-m3:latest
    telemetry:
      enabled: true
      endpoint: http://otel-collector-opentelemetry-collector.otel.svc.cluster.local:4318
    service:
      repos:
        - owner/repo
      machine_account: devops-bot
"""


def test_render_devops_configmap_substitutes_repos_and_account() -> None:
    """Verify render_devops_configmap_content substitutes repos and machine account."""
    rendered = render_devops_configmap_content(
        SAMPLE_TEMPLATE,
        repos=["example-org/repo-one", "example-org/repo-two"],
        machine_account="custom-bot",
    )
    doc = yaml.safe_load(rendered)
    inner = yaml.safe_load(doc["data"]["devops-cli.yaml"])
    settings = Settings.model_validate(inner)

    assert (
        settings.service.repos,
        settings.service.machine_account,
        settings.ai.provider,
        settings.telemetry.enabled,
    ) == (
        ["example-org/repo-one", "example-org/repo-two"],
        "custom-bot",
        "gateway",
        True,
    )


def test_render_devops_configmap_falls_back_to_defaults() -> None:
    """Verify default placeholders used when repos or account are empty."""
    rendered = render_devops_configmap_content(SAMPLE_TEMPLATE, repos=[], machine_account=None)
    doc = yaml.safe_load(rendered)
    inner = yaml.safe_load(doc["data"]["devops-cli.yaml"])
    settings = Settings.model_validate(inner)

    assert (
        settings.service.repos,
        settings.service.machine_account,
    ) == (
        [DEFAULT_PLACEHOLDER_REPO],
        DEFAULT_PLACEHOLDER_ACCOUNT,
    )


def test_render_devops_configmap_invalid_template_raises() -> None:
    """Verify KubernetesContextError is raised if service block is missing."""
    with pytest.raises(KubernetesContextError, match="standard service configuration block"):
        render_devops_configmap_content("apiVersion: v1\nkind: ConfigMap\n")


def test_render_devops_configmap_with_timeouts_and_poll() -> None:
    """Verify render_devops_configmap_content formats drain_timeout_seconds and poll_interval_seconds."""
    rendered = render_devops_configmap_content(
        SAMPLE_TEMPLATE,
        repos=["example/repo"],
        machine_account="bot",
        drain_timeout_seconds=90,
        poll_interval_seconds=180,
    )
    doc = yaml.safe_load(rendered)
    inner = yaml.safe_load(doc["data"]["devops-cli.yaml"])
    settings = Settings.model_validate(inner)

    assert (
        settings.service.drain_timeout_seconds,
        settings.service.poll_interval_seconds,
    ) == (90, 180)


def test_render_active_devops_configmap_success(tmp_path: Path) -> None:
    """Verify render_active_devops_configmap renders content in memory without creating files."""
    devops_dir = tmp_path / "devops"
    devops_dir.mkdir(parents=True)
    (devops_dir / "configmap.example.yaml").write_text(SAMPLE_TEMPLATE, encoding="utf-8")

    class DummySettings:
        service = type(
            "Service",
            (),
            {
                "repos": ["active/repo"],
                "machine_account": "active-bot",
                "drain_timeout_seconds": 75,
                "poll_interval_seconds": 150,
            },
        )()

    rendered = render_active_devops_configmap(k8s_dir=tmp_path, settings=DummySettings())

    assert (
        "active/repo" in rendered,
        "active-bot" in rendered,
        "drain_timeout_seconds: 75" in rendered,
        "poll_interval_seconds: 150" in rendered,
        (devops_dir / "configmap.yaml").exists(),
    ) == (True, True, True, True, False)


def test_render_active_devops_configmap_missing_template_raises(tmp_path: Path) -> None:
    """Verify render_active_devops_configmap raises FileNotFoundError when template is missing."""
    with pytest.raises(
        FileNotFoundError, match=r"Ensure k8s/devops/configmap\.example\.yaml exists"
    ):
        render_active_devops_configmap(k8s_dir=tmp_path)


def _template_dir(tmp_path: Path) -> Path:
    devops_dir = tmp_path / "devops"
    devops_dir.mkdir(parents=True)
    (devops_dir / "configmap.example.yaml").write_text(SAMPLE_TEMPLATE, encoding="utf-8")
    return tmp_path


def _settings(repos: list[str], account: str | None, github_account: str | None = None) -> object:
    class _Settings:
        service = type("Service", (), {"repos": repos, "machine_account": account})()
        k8s = type("K8s", (), {"github_account": github_account})()

    return _Settings()


def test_the_active_config_map_without_repositories_is_refused_naming_the_setting(
    tmp_path: Path,
) -> None:
    """A deploy never ships the template's placeholder repository."""
    with pytest.raises(KubernetesContextError, match=r"service\.repos"):
        render_active_devops_configmap(
            k8s_dir=_template_dir(tmp_path), settings=_settings([], "bot")
        )


def test_the_active_config_map_without_an_account_is_refused_naming_the_settings(
    tmp_path: Path,
) -> None:
    """A deploy never ships the template's placeholder machine account."""
    with pytest.raises(
        KubernetesContextError, match=r"service\.machine_account.*k8s\.github_account"
    ):
        render_active_devops_configmap(
            k8s_dir=_template_dir(tmp_path), settings=_settings(["owner/repo"], None)
        )


def test_the_machine_account_falls_back_to_the_configured_github_account(tmp_path: Path) -> None:
    rendered = render_active_devops_configmap(
        k8s_dir=_template_dir(tmp_path), settings=_settings(["owner/repo"], None, "devops-bot")
    )
    inner = yaml.safe_load(yaml.safe_load(rendered)["data"]["devops-cli.yaml"])
    assert (inner["service"]["repos"], inner["service"]["machine_account"]) == (
        ["owner/repo"],
        "devops-bot",
    )
