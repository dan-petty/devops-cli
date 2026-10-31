"""Test suite for Kubernetes HTTP transport keys and configuration caching."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from devops_cli.k8s.context import configured_context, reset_context_cache
from devops_cli.k8s.service import KubernetesService
from devops_cli.k8s.service_http import transport_key
from devops_cli.k8s.service_proxy import (
    kube_configuration,
    reset_configuration_cache,
)
from tests.support.fakes.kubernetes import FakeCluster


def test_the_proxy_client_key_ignores_the_request_path() -> None:
    """Every path on one host shares a connection."""
    assert transport_key("https://host:6443/a/b?q=1") == transport_key("https://host:6443/c")


def test_the_proxy_client_key_separates_hosts() -> None:
    """Two clusters do not share a connection."""
    assert transport_key("https://a:6443/x") != transport_key("https://b:6443/x")


def test_the_configured_context_is_cached_between_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The context recorded in settings is cached against the configuration file's modification time."""
    reset_context_cache()
    cfg = tmp_path / "config.yaml"
    cfg.write_text("k8s:\n  context: homelab-k3s\n")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg))

    first = configured_context()
    second = configured_context()
    reset_context_cache()
    assert (first, second) == ("homelab-k3s", "homelab-k3s")


def test_an_edited_configuration_changes_the_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An edited configuration file updates the cached context."""
    reset_context_cache()
    cfg = tmp_path / "config.yaml"
    cfg.write_text("k8s:\n  context: homelab-k3s\n")
    monkeypatch.setenv("DEVOPS_CLI_CONFIG", str(cfg))

    before = configured_context()
    now = time.time() + 10.0
    cfg.write_text("k8s:\n  context: staging\n")
    os.utime(cfg, (now, now))

    after = configured_context()
    reset_context_cache()
    assert (before, after) == ("homelab-k3s", "staging")


def test_the_client_configuration_is_cached_between_requests(cluster: FakeCluster) -> None:
    """The client configuration is reused between requests for the same context."""
    cluster.context_names.append("test-ctx")
    reset_configuration_cache()
    config1 = kube_configuration("test-ctx")
    config2 = kube_configuration("test-ctx")
    assert config1 is config2


def test_an_edited_kubeconfig_invalidates_the_cached_configuration(cluster: FakeCluster) -> None:
    """Resetting the service invalidates the cached configuration."""
    cluster.context_names.append("test-ctx")
    reset_configuration_cache()
    config1 = kube_configuration("test-ctx")
    KubernetesService.reset_instance()
    cluster2 = FakeCluster()
    cluster2.context_names.append("test-ctx")
    KubernetesService.install(cluster2)
    config2 = kube_configuration("test-ctx")
    assert config1 is not config2
