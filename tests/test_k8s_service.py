"""Tests for native KubernetesService and ResourceInformer subsystems."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.config.constants import (
    CONST_K8S_EVENT_ADDED,
    CONST_K8S_EVENT_DELETED,
)
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.informer import ResourceInformer
from devops_cli.k8s.service import KubernetesService


@pytest.fixture(autouse=True)
def reset_k8s_service() -> None:
    """Ensure clean KubernetesService singleton state for every test."""
    KubernetesService.reset_instance()


def test_k8s_service_singleton() -> None:
    """Verify singleton pattern consistency."""
    svc1 = KubernetesService.get_instance()
    svc2 = KubernetesService.get_instance()
    assert (svc1 is svc2, svc1._config_loaded) == (True, False)


def test_k8s_service_load_config_success() -> None:
    """Verify load_config initializes core client interfaces."""
    svc = KubernetesService.get_instance()
    with (
        patch("kubernetes.config.load_incluster_config", side_effect=Exception("not in cluster")),
        patch("kubernetes.config.load_kube_config") as mock_kube_config,
        patch("kubernetes.client.ApiClient"),
        patch("kubernetes.client.CoreV1Api"),
        patch("kubernetes.client.AppsV1Api"),
        patch("kubernetes.client.VersionApi"),
    ):
        result = svc.load_config(context="dev-cluster")
        assert (result, svc._config_loaded, svc._active_context) == (True, True, "dev-cluster")
        mock_kube_config.assert_called_once_with(context="dev-cluster")


def test_k8s_service_load_config_failure() -> None:
    """Verify load_config failure handling returns False."""
    svc = KubernetesService.get_instance()
    with (
        patch("kubernetes.config.load_incluster_config", side_effect=Exception("fail")),
        patch("kubernetes.config.load_kube_config", side_effect=Exception("fail")),
    ):
        result = svc.load_config()
        assert (result, svc._config_loaded) == (False, False)


def test_k8s_service_reachability() -> None:
    """Verify in-process cluster reachability probing and caching."""
    svc = KubernetesService.get_instance()
    with patch.object(svc, "load_config", return_value=True):
        mock_version_api = MagicMock()
        mock_version_api.get_code.return_value = SimpleNamespace(git_version="v1.30.0")
        svc._version_api = mock_version_api

        reachable = svc.is_cluster_reachable(context="test-ctx")
        cached_probe = svc.is_cluster_reachable(context="test-ctx")
        assert (reachable, cached_probe, mock_version_api.get_code.call_count) == (True, True, 1)


def test_k8s_service_reachability_failure() -> None:
    """Verify reachability returns False on probe exception."""
    svc = KubernetesService.get_instance()
    with patch.object(svc, "load_config", return_value=True):
        mock_version_api = MagicMock()
        mock_version_api.get_code.side_effect = Exception("connection refused")
        svc._version_api = mock_version_api

        assert (svc.is_cluster_reachable(context="fail-ctx"),) == (False,)


def test_k8s_service_list_contexts() -> None:
    """Verify list_contexts extraction from kubeconfig."""
    svc = KubernetesService.get_instance()
    mock_contexts = ([{"name": "ctx1"}, {"name": "ctx2"}], {"name": "ctx1"})
    with patch("kubernetes.config.list_kube_config_contexts", return_value=mock_contexts):
        ctx_list, active = svc.list_contexts()
        active_name = active["name"] if active else ""
        assert (len(ctx_list), active_name) == (2, "ctx1")


def test_k8s_service_switch_context(tmp_path: Path) -> None:
    """Verify switch_context updates kubeconfig file atomically."""
    kubeconfig_file = tmp_path / "config"
    kubeconfig_file.write_text(
        "apiVersion: v1\ncurrent-context: default\ncontexts:\n  - name: default\n  - name: prod\n",
        encoding="utf-8",
    )
    svc = KubernetesService.get_instance()
    with (
        patch.object(svc, "_get_kubeconfig_path", return_value=kubeconfig_file),
        patch.object(svc, "load_config", return_value=True),
    ):
        svc.switch_context("prod")
        updated_content = kubeconfig_file.read_text(encoding="utf-8")
        assert ("current-context: prod" in updated_content,) == (True,)


def test_k8s_service_switch_context_not_found(tmp_path: Path) -> None:
    """Verify switch_context raises KubernetesContextError for unknown context."""
    kubeconfig_file = tmp_path / "config"
    kubeconfig_file.write_text("apiVersion: v1\ncontexts:\n  - name: default\n", encoding="utf-8")
    svc = KubernetesService.get_instance()
    with patch.object(svc, "_get_kubeconfig_path", return_value=kubeconfig_file):
        with pytest.raises(KubernetesContextError, match="does not exist"):
            svc.switch_context("nonexistent")


def test_k8s_service_list_nodes() -> None:
    """Verify list_nodes queries API and caches results."""
    svc = KubernetesService.get_instance()
    mock_node = SimpleNamespace(metadata=SimpleNamespace(name="node-1"))
    mock_core = MagicMock()
    mock_core.list_node.return_value = SimpleNamespace(items=[mock_node])

    with patch.object(svc, "load_config", return_value=True):
        svc._core_v1 = mock_core
        nodes_first = svc.list_nodes()
        nodes_cached = svc.list_nodes()
        assert (len(nodes_first), len(nodes_cached), mock_core.list_node.call_count) == (1, 1, 1)


def test_k8s_service_list_pods() -> None:
    """Verify list_pods supports namespaced and all-namespace queries."""
    svc = KubernetesService.get_instance()
    mock_pod = SimpleNamespace(metadata=SimpleNamespace(name="pod-1"))
    mock_core = MagicMock()
    mock_core.list_namespaced_pod.return_value = SimpleNamespace(items=[mock_pod])
    mock_core.list_pod_for_all_namespaces.return_value = SimpleNamespace(items=[mock_pod, mock_pod])

    with patch.object(svc, "load_config", return_value=True):
        svc._core_v1 = mock_core
        ns_pods = svc.list_pods(namespace="custom")
        all_pods = svc.list_pods(all_namespaces=True)
        assert (len(ns_pods), len(all_pods)) == (1, 2)


def test_k8s_service_read_pod_logs() -> None:
    """Verify read_pod_logs invokes CoreV1Api with bounded tail."""
    svc = KubernetesService.get_instance()
    mock_core = MagicMock()
    mock_core.read_namespaced_pod_log.return_value = "log-line-1\nlog-line-2"

    with patch.object(svc, "load_config", return_value=True):
        svc._core_v1 = mock_core
        output = svc.read_pod_logs("pod-1", namespace="default", tail_lines=50)
        assert (output, mock_core.read_namespaced_pod_log.call_count) == (
            "log-line-1\nlog-line-2",
            1,
        )


def test_k8s_service_resolve_service_endpoint_load_balancer() -> None:
    """Verify resolve_service_endpoint returns LoadBalancer endpoint when present."""
    svc = KubernetesService.get_instance()
    mock_svc = SimpleNamespace(
        status=SimpleNamespace(
            load_balancer=SimpleNamespace(
                ingress=[SimpleNamespace(ip="203.0.113.10", hostname=None)]
            )
        ),
        spec=SimpleNamespace(ports=[SimpleNamespace(port=8080, node_port=None)]),
    )
    mock_core = MagicMock()
    mock_core.read_namespaced_service.return_value = mock_svc

    with patch.object(svc, "load_config", return_value=True):
        svc._core_v1 = mock_core
        url = svc.resolve_service_endpoint("web-svc", namespace="default")
        assert (url,) == ("http://203.0.113.10:8080",)


def test_resource_informer_event_normalization() -> None:
    """Verify ResourceInformer normalizes Watch event dictionaries."""
    mock_svc = MagicMock()
    informer = ResourceInformer(resource_kind="Pod", namespace="default", service=mock_svc)

    mock_obj = SimpleNamespace(
        metadata=SimpleNamespace(name="agent-pod", namespace="default"),
        status=SimpleNamespace(phase="Running"),
    )
    raw_event = {"type": CONST_K8S_EVENT_ADDED, "object": mock_obj}
    event = informer._normalize_event(raw_event)

    assert (event.event_type, event.name, event.namespace, event.status) == (
        CONST_K8S_EVENT_ADDED,
        "agent-pod",
        "default",
        "Running",
    )


def test_resource_informer_cache_lifecycle() -> None:
    """Verify ResourceInformer in-memory state updates on event stream."""
    mock_svc = MagicMock()
    informer = ResourceInformer(resource_kind="Pod", namespace="test-ns", service=mock_svc)

    mock_obj = SimpleNamespace(
        metadata=SimpleNamespace(name="worker", namespace="test-ns"),
        status=SimpleNamespace(phase="Running"),
    )
    ev_add = informer._normalize_event({"type": CONST_K8S_EVENT_ADDED, "object": mock_obj})
    informer._update_cache(ev_add, mock_obj)

    state_after_add = informer.get_state()
    cached = informer.get_cached_resources()

    ev_del = informer._normalize_event({"type": CONST_K8S_EVENT_DELETED, "object": mock_obj})
    informer._update_cache(ev_del, mock_obj)
    state_after_del = informer.get_state()

    assert (
        state_after_add.resource_count,
        state_after_add.synced,
        "test-ns/worker" in cached,
        state_after_del.resource_count,
    ) == (1, True, True, 0)


def test_resource_informer_stream_events() -> None:
    """Verify stream_events yields events using mock Watch."""
    mock_svc = MagicMock()
    mock_svc.load_config.return_value = True
    informer = ResourceInformer(resource_kind="Pod", namespace="default", service=mock_svc)

    mock_obj = SimpleNamespace(
        metadata=SimpleNamespace(name="streamed-pod", namespace="default"),
        status=SimpleNamespace(phase="Running"),
    )
    mock_watch = MagicMock()
    mock_watch.stream.return_value = [
        {"type": CONST_K8S_EVENT_ADDED, "object": mock_obj},
        {"type": CONST_K8S_EVENT_DELETED, "object": mock_obj},
    ]

    with patch("kubernetes.watch.Watch", return_value=mock_watch):
        events = list(informer.stream_events(timeout_seconds=5.0))
        assert (len(events), events[0].name, events[1].event_type) == (
            2,
            "streamed-pod",
            CONST_K8S_EVENT_DELETED,
        )


def test_resource_informer_stream_events_all_namespaces() -> None:
    """Verify stream_events handles all-namespace selector."""
    mock_svc = MagicMock()
    mock_svc.load_config.return_value = True
    informer = ResourceInformer(resource_kind="Pod", namespace="", service=mock_svc)

    mock_watch = MagicMock()
    mock_watch.stream.return_value = []
    with patch("kubernetes.watch.Watch", return_value=mock_watch):
        events = list(informer.stream_events(timeout_seconds=2.0))
        assert (len(events),) == (0,)


def test_resource_informer_start_and_stop() -> None:
    """Verify start initiates background thread and stop terminates it."""
    mock_svc = MagicMock()
    mock_svc.load_config.return_value = True
    informer = ResourceInformer(resource_kind="Pod", namespace="default", service=mock_svc)

    received: list[any] = []
    with patch.object(informer, "stream_events", return_value=[]):
        informer.start(on_event=received.append)
        is_running_init = informer._running
        informer.start()  # Idempotent second call
        informer.stop()
        assert (is_running_init, informer._running) == (True, False)


def test_k8s_service_read_pod_logs_follow() -> None:
    """Verify read_pod_logs returns stream iterator when follow=True."""
    svc = KubernetesService.get_instance()
    mock_resp = MagicMock()
    mock_resp.stream.return_value = [b"stream-1\n", b"stream-2\n"]
    mock_core = MagicMock()
    mock_core.read_namespaced_pod_log.return_value = mock_resp

    with patch.object(svc, "load_config", return_value=True):
        svc._core_v1 = mock_core
        stream_iter = svc.read_pod_logs("pod-1", follow=True)
        lines = list(stream_iter)
        assert (lines, mock_core.read_namespaced_pod_log.call_count) == (
            ["stream-1\n", "stream-2\n"],
            1,
        )


def test_k8s_service_read_pod_logs_failure() -> None:
    """Verify read_pod_logs raises KubernetesContextError on API failure."""
    svc = KubernetesService.get_instance()
    mock_core = MagicMock()
    mock_core.read_namespaced_pod_log.side_effect = Exception("not found")

    with patch.object(svc, "load_config", return_value=True):
        svc._core_v1 = mock_core
        with pytest.raises(KubernetesContextError, match="Failed to read pod logs"):
            svc.read_pod_logs("missing-pod")


def test_k8s_service_resolve_service_endpoint_node_port() -> None:
    """Verify resolve_service_endpoint falls back to NodePort and node IP."""
    svc = KubernetesService.get_instance()
    mock_svc = SimpleNamespace(
        status=SimpleNamespace(load_balancer=None),
        spec=SimpleNamespace(ports=[SimpleNamespace(port=80, node_port=30080)]),
    )
    mock_node = SimpleNamespace(
        status=SimpleNamespace(
            addresses=[
                SimpleNamespace(type="InternalIP", address="192.0.2.10"),
            ]
        )
    )
    mock_core = MagicMock()
    mock_core.read_namespaced_service.return_value = mock_svc

    with (
        patch.object(svc, "load_config", return_value=True),
        patch.object(svc, "list_nodes", return_value=[mock_node]),
    ):
        svc._core_v1 = mock_core
        url = svc.resolve_service_endpoint("internal-svc", namespace="default")
        assert (url,) == ("http://192.0.2.10:30080",)


def test_k8s_service_resolve_service_endpoint_not_found() -> None:
    """Verify resolve_service_endpoint returns None on lookup error."""
    svc = KubernetesService.get_instance()
    mock_core = MagicMock()
    mock_core.read_namespaced_service.side_effect = Exception("no such service")

    with patch.object(svc, "load_config", return_value=True):
        svc._core_v1 = mock_core
        assert (svc.resolve_service_endpoint("bad-svc"),) == (None,)


def test_k8s_service_kubeconfig_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify _get_kubeconfig_path respects KUBECONFIG environment variable."""
    override = tmp_path / "custom_kubeconfig"
    override.write_text("apiVersion: v1\n", encoding="utf-8")
    monkeypatch.setenv("KUBECONFIG", str(override))

    svc = KubernetesService.get_instance()
    resolved = svc._get_kubeconfig_path()
    assert (resolved,) == (override.resolve(),)


def test_k8s_service_cache_expiration() -> None:
    """Verify _get_cached invalidates entries after TTL."""
    svc = KubernetesService.get_instance()
    svc._cache_ttl = 0.01
    svc._set_cached("test-key", "test-val")
    val_immediate = svc._get_cached("test-key")

    import time

    time.sleep(0.02)
    val_expired = svc._get_cached("test-key")
    assert (val_immediate, val_expired) == ("test-val", None)


def test_k8s_service_list_exceptions() -> None:
    """Verify list_nodes and list_pods raise KubernetesContextError on exception."""
    svc = KubernetesService.get_instance()
    mock_core = MagicMock()
    mock_core.list_node.side_effect = Exception("api down")
    mock_core.list_namespaced_pod.side_effect = Exception("api down")

    with patch.object(svc, "load_config", return_value=True):
        svc._core_v1 = mock_core
        with pytest.raises(KubernetesContextError, match="Failed to query cluster nodes"):
            svc.list_nodes()
        with pytest.raises(KubernetesContextError, match="Failed to query pods"):
            svc.list_pods()
