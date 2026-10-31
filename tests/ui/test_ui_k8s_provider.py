"""Tests for the dashboard Kubernetes data provider using the KubernetesService fake."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from devops_cli.k8s.service import KubernetesService
from devops_cli.ui.data_providers import (
    DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS,
    K8sSummary,
    fetch_k8s_status,
)
from devops_cli.ui.projections import k8s_banner
from tests.support.fakes.kubernetes import (
    FakeCluster,
    FakeCoreV1,
    api_exception,
    crashlooping_pod,
    healthy_pod,
    node,
)


@pytest.fixture
def serve_k8s(config: Callable[..., Path]) -> Iterator[Callable[[FakeCoreV1], FakeCoreV1]]:
    """Install FakeCluster with a configured 'lab' context."""
    config(k8s={"context": "lab"})
    installed: list[FakeCluster] = []

    def _serve(core: FakeCoreV1) -> FakeCoreV1:
        fake = FakeCluster(core=core, contexts=("lab",), current="lab")
        KubernetesService.install(fake)
        installed.append(fake)
        return core

    try:
        yield _serve
    finally:
        KubernetesService.reset_instance()


def test_fetch_k8s_status_reads_pods_and_nodes_on_one_bounded_client(
    serve_k8s: Callable[[FakeCoreV1], FakeCoreV1],
) -> None:
    """Pods become typed records, nodes are counted Ready, and neither call can hang."""
    core = serve_k8s(
        FakeCoreV1(
            pods=[
                healthy_pod("api-0", "shop"),
                crashlooping_pod("exporter-0", "monitoring"),
            ],
            nodes=[
                node("worker-1"),
                node("worker-2"),
                node("worker-3"),
                node("worker-4", "False"),
            ],
        ),
    )
    summary = fetch_k8s_status()
    assert (
        summary.connected,
        summary.context,
        [(pod.name, pod.status, pod.ready_containers) for pod in summary.pods],
        (summary.nodes_ready, summary.nodes_total),
        [(method, kwargs.get("_request_timeout")) for method, kwargs in core.calls],
        "3/4 nodes Ready" in k8s_banner(summary),
    ) == (
        True,
        "lab",
        [("api-0", "Running", "1/1"), ("exporter-0", "CrashLoopBackOff", "0/1")],
        (3, 4),
        [
            ("list_pod_for_all_namespaces", DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS),
            ("list_node", DEFAULT_K8S_CONNECT_TIMEOUT_SECONDS),
        ],
        True,
    )


def test_pods_still_render_when_the_node_list_fails(
    serve_k8s: Callable[[FakeCoreV1], FakeCoreV1],
) -> None:
    """Listing nodes needs a cluster-scoped permission listing pods does not."""
    serve_k8s(
        FakeCoreV1(
            pods=[healthy_pod("api-0")],
            nodes=api_exception(403, "Forbidden"),
        ),
    )
    summary = fetch_k8s_status()
    assert (summary.connected, len(summary.pods), summary.nodes_error) == (
        True,
        1,
        "403 Forbidden",
    )
    assert "nodes: unavailable (403 Forbidden)" in k8s_banner(summary)


def test_a_failed_pod_list_reports_the_context_and_the_masked_error(
    serve_k8s: Callable[[FakeCoreV1], FakeCoreV1],
) -> None:
    """The banner names the cluster it tried, and a token in the error is not echoed."""
    serve_k8s(FakeCoreV1(pods=ConnectionError("refused, token=ghp_" + "a" * 36)))
    summary = fetch_k8s_status()
    banner = k8s_banner(summary)
    assert (
        summary.connected,
        "Disconnected | context lab — ConnectionError: refused" in banner,
        "ghp_" + "a" * 36 in banner,
    ) == (False, True, False)


def test_fetch_k8s_status_failure() -> None:
    """fetch_k8s_status gracefully returns disconnected summary on client failure."""
    fake = FakeCluster().unreachable()
    KubernetesService.install(fake)
    try:
        summary = fetch_k8s_status()
        assert isinstance(summary, K8sSummary)
        assert summary.connected is False
        assert summary.pods == []
    finally:
        KubernetesService.reset_instance()


def test_the_kubernetes_snapshot_runs_no_subprocess(
    serve_k8s: Callable[[FakeCoreV1], FakeCoreV1],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A banner badge ran a CLI on every refresh, with a timeout of half an hour."""
    import subprocess

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the Kubernetes provider started a subprocess")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    serve_k8s(FakeCoreV1(pods=[healthy_pod("api-0")], nodes=[node("worker-1")]))
    assert fetch_k8s_status().connected is True


@pytest.mark.parametrize(
    ("configured", "kubeconfig", "in_pod", "expected"),
    [
        ("lab", ("ambient",), False, "lab"),
        (None, ("ambient",), False, "ambient"),
        (None, (), False, ""),
        (None, ("ambient",), True, "ambient"),
        (None, (), True, "in-cluster"),
        ("lab", (), True, "lab"),
    ],
)
def test_the_context_named_is_the_configured_one_or_kubectls_current_one(
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
    configured: str | None,
    kubeconfig: tuple[str, ...],
    in_pod: bool,
    expected: str,
) -> None:
    """The banner names the cluster the dashboard actually connects to.

    Only a pod with no kubeconfig context to name connects with its service account.
    """
    if in_pod:
        monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "example.com")
        monkeypatch.setenv("KUBERNETES_SERVICE_PORT", "443")
    else:
        monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
        monkeypatch.delenv("KUBERNETES_SERVICE_PORT", raising=False)

    config(k8s={"context": configured or ""})
    current = kubeconfig[0] if kubeconfig else None
    fake = FakeCluster(contexts=kubeconfig, current=current)
    KubernetesService.install(fake)
    try:
        assert fetch_k8s_status().context == expected
    finally:
        KubernetesService.reset_instance()


@pytest.mark.parametrize("in_pod", [False, True])
def test_a_context_missing_from_the_kubeconfig_is_reported_as_missing(
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
    in_pod: bool,
) -> None:
    """A context missing from the kubeconfig is reported as disconnected naming the context."""
    if in_pod:
        monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "example.com")
        monkeypatch.setenv("KUBERNETES_SERVICE_PORT", "443")
    else:
        monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
        monkeypatch.delenv("KUBERNETES_SERVICE_PORT", raising=False)

    config(k8s={"context": "lab"})
    fake = FakeCluster(contexts=("other",), current="other").unreachable()
    KubernetesService.install(fake)
    try:
        summary = fetch_k8s_status()
        banner = k8s_banner(summary)
        assert summary.connected is False
        assert "context lab" in banner
        assert "Service host/port is not set" not in banner
    finally:
        KubernetesService.reset_instance()


def test_the_dashboard_reads_the_configured_cluster(config: Callable[..., Path]) -> None:
    """The dashboard must report on the same cluster as every other command."""
    config(k8s={"context": "homelab-k3s"})
    fake = FakeCluster(contexts=("homelab-k3s",), current="homelab-k3s")
    KubernetesService.install(fake)
    try:
        summary = fetch_k8s_status()
        assert summary.context == "homelab-k3s"
    finally:
        KubernetesService.reset_instance()


def test_the_dashboard_falls_back_to_in_cluster_configuration(
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running the dashboard inside the cluster must still work."""
    config(k8s={"context": ""})
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "example.com")
    fake = FakeCluster(contexts=(), current=None)
    KubernetesService.install(fake)
    try:
        summary = fetch_k8s_status()
        assert summary.context == "in-cluster"
    finally:
        KubernetesService.reset_instance()


def test_the_dashboard_outside_a_pod_reports_the_kubeconfig_error(
    config: Callable[..., Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Outside a pod a missing cluster is reported in the summary."""
    config(k8s={"context": "lab"})
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
    fake = FakeCluster(contexts=(), current=None).unreachable()
    KubernetesService.install(fake)
    try:
        summary = fetch_k8s_status()
        assert summary.connected is False
        assert "lab" in summary.context
    finally:
        KubernetesService.reset_instance()
