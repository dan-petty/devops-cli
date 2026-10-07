"""Tests for Argo CD source parameter overrides generation and CLI command."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.argocd_source import (
    generate_argocd_source,
    render_argocd_source_content,
    render_ingress_argocd_source_content,
)

runner = CliRunner()

SAMPLE_TEMPLATE = """apiVersion: v1
kind: ConfigMap
metadata:
  name: devops-cli-config
  namespace: devops
data:
  devops-cli.yaml: |
    ai:
      provider: gateway
      model: devops-background
    service:
      repos:
        - owner/repo
      machine_account: devops-bot
"""

SAMPLE_INGRESS_ROUTES = """---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: open-webui-ingress
  namespace: llm
spec:
  rules:
    - host: chat.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: open-webui
                port:
                  number: 8080
---
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: traefik-dashboard
  namespace: kube-system
spec:
  routes:
    - match: Host(`traefik.example.com`)
      kind: Rule
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: roadmap-service
  namespace: devops
spec:
  rules:
    - host: hooks.example.com
"""


class DummyService:
    repos: ClassVar[list[str]] = ["custom/repo-a", "custom/repo-b"]
    machine_account = "test-bot"
    drain_timeout_seconds = 120
    poll_interval_seconds = 300


class DummyK8s:
    domain = "example.com"
    github_account = None


class DummySettings:
    service = DummyService()
    k8s = DummyK8s()
    cloudflare = None


def test_render_argocd_source_content_with_domain() -> None:
    """Verify render_argocd_source_content produces both ConfigMap and Ingress patches."""
    content = render_argocd_source_content(
        SAMPLE_TEMPLATE,
        settings=DummySettings(),
    )
    doc = yaml.safe_load(content)
    patches = doc["kustomize"]["patches"]
    patch_docs = [yaml.safe_load(p["patch"]) for p in patches]
    kinds = [d["kind"] for d in patch_docs]

    cm_doc = next(d for d in patch_docs if d["kind"] == "ConfigMap")
    ingress_doc = next(d for d in patch_docs if d["kind"] == "Ingress")

    inner_cfg = yaml.safe_load(cm_doc["data"]["devops-cli.yaml"])
    rule = ingress_doc["spec"]["rules"][0]

    assert (
        len(patches),
        kinds,
        inner_cfg["service"]["repos"],
        inner_cfg["service"]["machine_account"],
        inner_cfg["service"]["drain_timeout_seconds"],
        inner_cfg["service"]["poll_interval_seconds"],
        rule["host"],
    ) == (
        2,
        ["ConfigMap", "Ingress"],
        ["custom/repo-a", "custom/repo-b"],
        "test-bot",
        120,
        300,
        "hooks.example.com",
    )


def test_render_argocd_source_content_without_domain() -> None:
    """Verify render_argocd_source_content omits Ingress patch when domain is not configured."""

    class NoDomainSettings:
        service = DummyService()
        k8s = None
        cloudflare = None

    content = render_argocd_source_content(
        SAMPLE_TEMPLATE,
        settings=NoDomainSettings(),
    )
    doc = yaml.safe_load(content)
    patches = doc["kustomize"]["patches"]
    patch_docs = [yaml.safe_load(p["patch"]) for p in patches]

    assert (
        len(patches),
        patch_docs[0]["kind"],
        "Ingress" in [d["kind"] for d in patch_docs],
    ) == (1, "ConfigMap", False)


def test_render_argocd_source_content_invalid_template_raises() -> None:
    """Verify KubernetesContextError is raised if template is invalid."""
    with pytest.raises(KubernetesContextError, match="standard service configuration block"):
        render_argocd_source_content("apiVersion: v1\nkind: ConfigMap\n")


def test_render_ingress_argocd_source_content_with_domain() -> None:
    """Verify render_ingress_argocd_source_content patches Ingress and IngressRoute hosts."""
    content = render_ingress_argocd_source_content(
        SAMPLE_INGRESS_ROUTES,
        domain="example.org",
    )
    doc = yaml.safe_load(content)
    patches = doc["kustomize"]["patches"]
    patch_docs = [yaml.safe_load(p["patch"]) for p in patches]
    names = [d["metadata"]["name"] for d in patch_docs]

    ingress_doc = next(d for d in patch_docs if d["kind"] == "Ingress")
    route_doc = next(d for d in patch_docs if d["kind"] == "IngressRoute")

    assert (
        len(patches),
        "roadmap-service" in names,
        ingress_doc["spec"]["rules"][0]["host"],
        route_doc["spec"]["routes"][0]["match"],
    ) == (
        2,
        False,
        "chat.example.org",
        "Host(`traefik.example.org`)",
    )


def test_render_ingress_argocd_source_content_without_domain() -> None:
    """Verify render_ingress_argocd_source_content returns empty patch list when domain is omitted."""
    content = render_ingress_argocd_source_content(
        SAMPLE_INGRESS_ROUTES,
        domain=None,
        settings=None,
    )
    doc = yaml.safe_load(content)
    assert doc == {"kustomize": {"patches": []}}


def test_generate_argocd_source_writes_files(tmp_path: Path) -> None:
    """Verify generate_argocd_source writes .argocd-source.yaml to devops and ingress dirs."""
    k8s_dir = tmp_path / "k8s"
    devops_dir = k8s_dir / "devops"
    devops_overlay_dir = k8s_dir / "overlays" / "homelab" / "devops"
    ingress_dir = k8s_dir / "ingress"
    ingress_overlay_dir = k8s_dir / "overlays" / "homelab" / "ingress"

    for d in (devops_dir, devops_overlay_dir, ingress_dir, ingress_overlay_dir):
        d.mkdir(parents=True)

    (devops_dir / "configmap.yaml").write_text(SAMPLE_TEMPLATE, encoding="utf-8")
    (ingress_dir / "ingress-routes.yaml").write_text(SAMPLE_INGRESS_ROUTES, encoding="utf-8")

    generated = generate_argocd_source(
        k8s_dir=k8s_dir,
        settings=DummySettings(),
    )

    expected_devops_overlay = devops_overlay_dir / ".argocd-source.yaml"
    expected_devops = devops_dir / ".argocd-source.yaml"
    expected_ingress_overlay = ingress_overlay_dir / ".argocd-source.yaml"
    expected_ingress = ingress_dir / ".argocd-source.yaml"

    assert (
        len(generated),
        expected_devops_overlay in generated,
        expected_devops in generated,
        expected_ingress_overlay in generated,
        expected_ingress in generated,
        "hooks.example.com" in expected_devops_overlay.read_text(encoding="utf-8"),
        "chat.example.com" in expected_ingress_overlay.read_text(encoding="utf-8"),
    ) == (4, True, True, True, True, True, True)


def test_generate_argocd_source_missing_template_raises(tmp_path: Path) -> None:
    """Verify FileNotFoundError raised if no configmap template exists."""
    with pytest.raises(FileNotFoundError, match="DevOps ConfigMap template not found"):
        generate_argocd_source(k8s_dir=tmp_path)


def test_argocd_source_cli_dry_run(tmp_path: Path) -> None:
    """Verify argocd-source --dry-run prints yaml to stdout without creating files."""
    k8s_dir = tmp_path / "k8s"
    devops_dir = k8s_dir / "devops"
    devops_dir.mkdir(parents=True)
    (devops_dir / "configmap.yaml").write_text(SAMPLE_TEMPLATE, encoding="utf-8")

    res = runner.invoke(app, ["argocd-source", "--k8s-dir", str(k8s_dir), "--dry-run"])

    assert (
        res.exit_code,
        "kustomize:" in res.output,
        "devops-cli-config" in res.output,
        (devops_dir / ".argocd-source.yaml").exists(),
    ) == (0, True, True, False)


def test_argocd_source_cli_generates_files(tmp_path: Path) -> None:
    """Verify argocd-source CLI generates files and prints success message."""
    k8s_dir = tmp_path / "k8s"
    devops_dir = k8s_dir / "devops"
    devops_dir.mkdir(parents=True)
    (devops_dir / "configmap.yaml").write_text(SAMPLE_TEMPLATE, encoding="utf-8")

    res = runner.invoke(
        app,
        ["argocd-source", "--k8s-dir", str(k8s_dir), "--domain", "example.com"],
    )

    target_file = devops_dir / ".argocd-source.yaml"
    assert (
        res.exit_code,
        "Generated" in res.output,
        target_file.is_file(),
        "hooks.example.com" in target_file.read_text(encoding="utf-8"),
    ) == (0, True, True, True)


def test_argocd_source_cli_missing_template_exits_nonzero(tmp_path: Path) -> None:
    """Verify argocd-source CLI exits with code 1 if template is missing."""
    res = runner.invoke(app, ["argocd-source", "--k8s-dir", str(tmp_path)])
    assert (
        res.exit_code,
        "Failed to generate Argo CD source overrides" in res.output,
    ) == (1, True)
