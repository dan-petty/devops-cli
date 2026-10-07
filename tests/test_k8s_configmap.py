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
    ensure_devops_configmap,
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


def test_ensure_devops_configmap_creates_from_example(tmp_path: Path) -> None:
    """Verify ensure_devops_configmap writes target when missing."""
    k8s_dir = tmp_path / "k8s"
    devops_dir = k8s_dir / "devops"
    devops_dir.mkdir(parents=True)
    (devops_dir / "configmap.example.yaml").write_text(SAMPLE_TEMPLATE, encoding="utf-8")

    class DummySettings:
        service = type(
            "DummyService", (), {"repos": ["test/repo"], "machine_account": "bot-user"}
        )()
        k8s = type("DummyK8s", (), {"github_account": None})()

    target = ensure_devops_configmap(k8s_dir=k8s_dir, settings=DummySettings())

    assert (
        target.is_file(),
        "test/repo" in target.read_text(encoding="utf-8"),
        "bot-user" in target.read_text(encoding="utf-8"),
    ) == (True, True, True)


def test_ensure_devops_configmap_preserves_existing_repos_if_settings_empty(
    tmp_path: Path,
) -> None:
    """Verify existing repos in target are preserved when active settings provide none."""
    k8s_dir = tmp_path / "k8s"
    devops_dir = k8s_dir / "devops"
    devops_dir.mkdir(parents=True)
    (devops_dir / "configmap.example.yaml").write_text(SAMPLE_TEMPLATE, encoding="utf-8")

    existing_target = devops_dir / "configmap.yaml"
    initial = render_devops_configmap_content(
        SAMPLE_TEMPLATE,
        repos=["persisted/repo"],
        machine_account="persisted-bot",
    )
    existing_target.write_text(initial, encoding="utf-8")

    class EmptySettings:
        service = type("DummyService", (), {"repos": [], "machine_account": None})()
        k8s = type("DummyK8s", (), {"github_account": None})()

    res = ensure_devops_configmap(k8s_dir=k8s_dir, settings=EmptySettings(), force=True)
    content = res.read_text(encoding="utf-8")

    assert (
        "persisted/repo" in content,
        "persisted-bot" in content,
    ) == (True, True)


def test_ensure_devops_configmap_missing_template_raises(tmp_path: Path) -> None:
    """Verify FileNotFoundError is raised if template does not exist."""
    with pytest.raises(
        FileNotFoundError, match=r"Ensure k8s/devops/configmap\.example\.yaml exists"
    ):
        ensure_devops_configmap(k8s_dir=tmp_path)
