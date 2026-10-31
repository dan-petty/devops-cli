"""Tests for Kubernetes manifest template substitution and CLI rendering."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.template import (
    normalize_domain,
    render_manifest_path,
    render_manifest_template,
    resolve_template_domain,
)
from tests.support.fakes.process import ProcessAnswer, ProcessFake


def test_normalize_domain_valid() -> None:
    """Normalize whitespace, uppercase, and leading dots on valid domains."""
    res_a = normalize_domain("  EXAMPLE.COM  ")
    res_b = normalize_domain(".example.com")
    res_c = normalize_domain("example.com.")
    assert (res_a, res_b, res_c) == ("example.com", "example.com", "example.com")


def test_normalize_domain_invalid_raises() -> None:
    """Invalid characters or empty strings raise KubernetesContextError."""
    with pytest.raises(KubernetesContextError, match="Invalid domain name"):
        normalize_domain("invalid domain with spaces!")

    with pytest.raises(KubernetesContextError, match="Invalid domain name"):
        normalize_domain("")


def test_resolve_template_domain_precedence(config: Callable[..., Path]) -> None:
    """CLI override takes precedence over config and environment."""
    cli_result = resolve_template_domain("custom.org")
    assert cli_result == "custom.org"

    config(k8s={"domain": "example.com"}, cloudflare={"domain": "cloudflare.org"})
    cfg_result = resolve_template_domain(None)
    assert cfg_result == "example.com"

    config(k8s={"domain": None}, cloudflare={"domain": "cloudflare.org"})
    cf_result = resolve_template_domain(None)
    assert cf_result == "cloudflare.org"


def test_resolve_template_domain_env_and_missing(
    config: Callable[..., Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Environment variables are used when config is unset, otherwise raises."""
    config(k8s={"domain": None}, cloudflare={"domain": None})

    monkeypatch.setenv("DEVOPS_CLI_K8S_DOMAIN", "example.com")
    env_result = resolve_template_domain(None)
    assert env_result == "example.com"

    monkeypatch.delenv("DEVOPS_CLI_K8S_DOMAIN", raising=False)
    monkeypatch.delenv("DEVOPS_CLI_DOMAIN", raising=False)
    with pytest.raises(KubernetesContextError, match="No domain configured"):
        resolve_template_domain(None)


def test_render_manifest_template_substitutions(snapshot: SnapshotAssertion) -> None:
    """Substitute example.com, ${DOMAIN}, $DOMAIN, ${K8S_DOMAIN}, and extra variables."""
    raw = (
        "host: chat.example.com\n"
        "other: ai.${DOMAIN}\n"
        "legacy: api.$DOMAIN\n"
        "k8s: app.${K8S_DOMAIN}\n"
        "extra: ${CUSTOM_ENV}\n"
    )
    rendered = render_manifest_template(
        raw,
        domain="example.com",
        extra_vars={"CUSTOM_ENV": "production"},
    )
    assert rendered == snapshot


def test_render_manifest_path_file(tmp_path: Path) -> None:
    """Render single manifest template file."""
    manifest = tmp_path / "route.yaml"
    manifest.write_text("host: chat.example.com", encoding="utf-8")

    result = render_manifest_path(manifest, domain="example.com")
    assert result == "host: chat.example.com"


def test_render_manifest_path_kustomize_dir(tmp_path: Path, process_fake: ProcessFake) -> None:
    """Render directory containing kustomization using kubectl kustomize output."""
    k_dir = tmp_path / "k_pkg"
    k_dir.mkdir()
    (k_dir / "kustomization.yaml").write_text("resources: []", encoding="utf-8")

    process_fake.answer(
        ["kubectl", "kustomize", str(k_dir)],
        ProcessAnswer(stdout="host: chat.example.com"),
    )
    rendered = render_manifest_path(k_dir, domain="example.com")
    assert rendered == "host: chat.example.com"


def test_render_manifest_path_kustomize_failure_raises(
    tmp_path: Path, process_fake: ProcessFake
) -> None:
    """Failing kubectl kustomize command raises KubernetesContextError."""
    k_dir = tmp_path / "k_pkg"
    k_dir.mkdir()
    (k_dir / "kustomization.yaml").write_text("resources: []", encoding="utf-8")

    process_fake.answer(
        ["kubectl", "kustomize", str(k_dir)],
        ProcessAnswer(returncode=1, stderr="kustomize error"),
    )
    with pytest.raises(KubernetesContextError, match="Kustomize build failed"):
        render_manifest_path(k_dir, domain="example.com")


def test_render_manifest_path_plain_yaml_dir(tmp_path: Path) -> None:
    """Render directory containing multiple yaml files without kustomization."""
    y_dir = tmp_path / "yamls"
    y_dir.mkdir()
    (y_dir / "01.yaml").write_text("host: chat.example.com", encoding="utf-8")
    (y_dir / "02.yaml").write_text("host: ai.example.com", encoding="utf-8")

    rendered = render_manifest_path(y_dir, domain="example.com")
    assert "host: chat.example.com\n---\nhost: ai.example.com" in rendered


def test_render_manifest_path_empty_dir_raises(tmp_path: Path) -> None:
    """Empty directory with no YAML files raises KubernetesContextError."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(KubernetesContextError, match="No YAML manifests found"):
        render_manifest_path(empty_dir, domain="example.com")


def test_render_manifest_path_missing_raises() -> None:
    """Non-existent path raises KubernetesContextError."""
    with pytest.raises(KubernetesContextError, match="Manifest path not found"):
        render_manifest_path("non_existent_file.yaml", domain="example.com")


def test_k8s_apply_cli_template_dry_run(tmp_path: Path, cli: Callable[..., Any]) -> None:
    """devops k8s apply --template --dry-run renders the preview and starts no kubectl child."""
    manifest = tmp_path / "ingress.yaml"
    manifest.write_text("host: chat.example.com", encoding="utf-8")

    result = cli(
        "k8s",
        "apply",
        str(manifest),
        "--template",
        "--domain",
        "example.com",
        "--dry-run",
    )
    assert result.exit_code == 0, result.output
    assert "devops k8s apply" in result.output
    assert "kubectl_apply_template" in result.output


def test_k8s_apply_cli_template_global_dry_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cli: Callable[..., Any]
) -> None:
    """devops k8s apply --template in global dry-run renders dry-run output."""
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "1")
    manifest = tmp_path / "ingress.yaml"
    manifest.write_text("host: chat.example.com", encoding="utf-8")

    result = cli(
        "k8s",
        "apply",
        str(manifest),
        "--template",
        "--domain",
        "example.com",
    )
    assert (result.exit_code, "kubectl_apply_template" in result.output) == (0, True)


def test_k8s_apply_cli_template_live(
    tmp_path: Path, process_fake: ProcessFake, cli: Callable[..., Any]
) -> None:
    """devops k8s apply --template pipes rendered input to kubectl apply -f -."""
    manifest = tmp_path / "ingress.yaml"
    manifest.write_text("host: chat.example.com", encoding="utf-8")

    process_fake.answer(
        ["kubectl", "apply"],
        ProcessAnswer(stdout="applied"),
    )
    result = cli(
        "k8s",
        "apply",
        str(manifest),
        "--domain",
        "example.com",
        "--namespace",
        "test-ns",
    )
    assert result.exit_code == 0
    call = next(
        c
        for c in process_fake.calls
        if c.argv == ("kubectl", "apply", "-f", "-", "--namespace", "test-ns")
    )
    assert call.stdin == "host: chat.example.com"


def test_k8s_render_cli(tmp_path: Path, cli: Callable[..., Any]) -> None:
    """devops k8s render prints substituted manifest content to stdout."""
    manifest = tmp_path / "ingress.yaml"
    manifest.write_text("host: chat.example.com\nai: ${DOMAIN}", encoding="utf-8")

    result = cli("k8s", "render", str(manifest), "--domain", "example.com")
    assert (
        result.exit_code,
        "host: chat.example.com\nai: example.com\n" in result.output,
    ) == (0, True)


def test_kustomize_apply_template_cli(
    tmp_path: Path, process_fake: ProcessFake, cli: Callable[..., Any]
) -> None:
    """devops kustomize apply --template renders and applies manifests."""
    k_dir = tmp_path / "k_dir"
    k_dir.mkdir()
    (k_dir / "app.yaml").write_text("host: chat.example.com", encoding="utf-8")

    process_fake.answer(
        ["kubectl", "apply"],
        ProcessAnswer(stdout="applied"),
    )
    result = cli(
        "kustomize",
        "apply",
        str(k_dir),
        "--template",
        "--domain",
        "example.com",
    )
    assert result.exit_code == 0
    call = next(c for c in process_fake.calls if c.argv == ("kubectl", "apply", "-f", "-"))
    assert call.stdin == "host: chat.example.com"
