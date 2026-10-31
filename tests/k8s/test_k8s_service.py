"""Tests for native KubernetesService and ResourceInformer subsystems.

The service reaches the Kubernetes API only through its source: the `cluster` fixture's fake,
or the real client over a kubeconfig and a service account under `tmp_path`, which loads a
configuration and connects to nothing.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.config.constants import (
    CONST_K8S_EVENT_ADDED,
    CONST_K8S_EVENT_DELETED,
)
from devops_cli.config.defaults import DEFAULT_LOG_MAX_LINE_CHARS
from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.api import KubernetesClientSource
from devops_cli.k8s.informer import ResourceInformer
from devops_cli.k8s.service import KubernetesService, PodLogStream
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.kubernetes import (
    FAKE_CONTEXT,
    FakeCluster,
    FakeCoreV1,
    node,
    pod,
    service,
)
from tests.support.waits import THREAD_HANDOFF_BOUND_SECONDS


def _kubeconfig(path: Path, servers: dict[str, str], current: str) -> Path:
    """A kubeconfig with one context, cluster and user for each name in `servers`."""
    clusters = "".join(f"- name: {n}\n  cluster:\n    server: {s}\n" for n, s in servers.items())
    contexts = "".join(
        f"- name: {n}\n  context:\n    cluster: {n}\n    user: {n}\n" for n in servers
    )
    users = "".join(f"- name: {n}\n  user:\n    token: placeholder-{n}\n" for n in servers)
    path.write_text(
        "apiVersion: v1\nkind: Config\n"
        f"clusters:\n{clusters}contexts:\n{contexts}current-context: {current}\nusers:\n{users}",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def service_account(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A pod's service account under `tmp_path`, with the API server's address in the env."""
    directory = tmp_path / "serviceaccount"
    directory.mkdir()
    (directory / "token").write_text("sa-token", encoding="utf-8")
    (directory / "ca.crt").write_text("placeholder certificate", encoding="utf-8")
    monkeypatch.setenv("KUBERNETES_SERVICE_HOST", "192.0.2.1")
    monkeypatch.setenv("KUBERNETES_SERVICE_PORT", "6443")
    return directory


def _host(apis: Any) -> str:
    return str(apis.core.api_client.configuration.host)


def test_the_process_service_is_one_instance_until_install_and_reset() -> None:
    """`install` replaces the process's service, and `reset_instance` removes what it gave."""
    first = KubernetesService.get_instance()
    fake = FakeCluster()
    installed = KubernetesService.install(fake)
    while_installed = KubernetesService.get_instance()
    KubernetesService.reset_instance()
    after_reset = KubernetesService.get_instance()
    after_reset.load_config(FAKE_CONTEXT)

    assert (
        first is KubernetesService.get_instance(),
        while_installed is installed,
        after_reset is installed,
        fake.connects,
    ) == (False, True, False, [])


def test_the_cluster_fixture_serves_the_process_service(cluster: FakeCluster) -> None:
    cluster.core.answers["list_node"] = [node("node-a")]

    nodes = KubernetesService.get_instance().list_nodes()

    assert ([n.metadata.name for n in nodes], cluster.core.calls, cluster.connects) == (
        ["node-a"],
        [("list_node", {})],
        [FAKE_CONTEXT],
    )


def test_a_kubeconfig_context_wins_over_a_service_account(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service_account: Path
) -> None:
    servers = {"dev": "https://dev.example.com:6443"}
    monkeypatch.setenv("KUBECONFIG", str(_kubeconfig(tmp_path / "config", servers, "dev")))

    apis = KubernetesClientSource(service_account_dir=service_account).connect("dev")

    assert _host(apis) == "https://dev.example.com:6443"


def test_without_a_kubeconfig_context_the_service_account_connects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service_account: Path
) -> None:
    servers = {"dev": "https://dev.example.com:6443"}
    monkeypatch.setenv("KUBECONFIG", str(_kubeconfig(tmp_path / "config", servers, "dev")))

    apis = KubernetesClientSource(service_account_dir=service_account).connect("other")

    assert (
        _host(apis),
        apis.core.api_client.configuration.api_key["BearerToken"],
    ) == ("https://192.0.2.1:6443", "bearer sa-token")


def test_without_a_kubeconfig_context_or_service_account_the_connection_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    servers = {"dev": "https://dev.example.com:6443"}
    monkeypatch.setenv("KUBECONFIG", str(_kubeconfig(tmp_path / "config", servers, "dev")))
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)

    with pytest.raises(KubernetesContextError, match="No kubeconfig context named 'other'"):
        KubernetesClientSource(service_account_dir=tmp_path / "none").connect("other")


def test_a_connection_leaves_the_global_default_configuration_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, service_account: Path
) -> None:
    from kubernetes import client

    servers = {"dev": "https://dev.example.com:6443"}
    monkeypatch.setenv("KUBECONFIG", str(_kubeconfig(tmp_path / "config", servers, "dev")))
    before = client.Configuration.get_default_copy().host
    source = KubernetesClientSource(service_account_dir=service_account)

    source.connect("dev")
    source.connect("other")

    assert client.Configuration.get_default_copy().host == before


def test_every_kubeconfig_entry_is_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _kubeconfig(tmp_path / "first", {"dev": "https://dev.example.com:6443"}, "dev")
    second = _kubeconfig(tmp_path / "second", {"prod": "https://prod.example.com:6443"}, "prod")
    monkeypatch.setenv("KUBECONFIG", f"{first}:{second}")
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
    source = KubernetesClientSource()

    contexts, _ = source.contexts()

    assert ([ctx["name"] for ctx in contexts], _host(source.connect("prod"))) == (
        ["dev", "prod"],
        "https://prod.example.com:6443",
    )


def test_a_switch_points_the_clients_at_the_context_and_leaves_the_kubeconfig_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    servers = {"dev": "https://dev.example.com:6443", "prod": "https://prod.example.com:6443"}
    kubeconfig = _kubeconfig(tmp_path / "config", servers, "dev")
    kubeconfig.write_text("# kept by the switch\n" + kubeconfig.read_text("utf-8"), "utf-8")
    monkeypatch.setenv("KUBECONFIG", str(kubeconfig))
    before = kubeconfig.read_bytes()
    svc = KubernetesService(KubernetesClientSource())

    svc.switch_context("prod")

    assert (
        kubeconfig.read_bytes() == before,
        svc.core_api("prod").api_client.configuration.host,
    ) == (
        True,
        "https://prod.example.com:6443",
    )


def test_a_switch_connects_to_the_context_and_drops_cached_answers() -> None:
    fake = FakeCluster(contexts=("dev", "prod"), current="dev")
    svc = KubernetesService(fake)
    fake.core.answers["list_node"] = [node("node-a")]
    svc.list_nodes("prod")

    svc.switch_context("prod")
    svc.list_nodes("prod")

    assert (fake.connects, [call for call, _ in fake.core.calls]) == (
        ["prod", "prod"],
        ["list_node", "list_node"],
    )


def test_a_switch_to_a_context_the_kubeconfig_does_not_name_fails() -> None:
    svc = KubernetesService(FakeCluster(contexts=("dev",), current="dev"))

    with pytest.raises(KubernetesContextError, match="does not exist"):
        svc.switch_context("nonexistent")


def test_load_config_connects_once_for_each_context(cluster: FakeCluster) -> None:
    svc = KubernetesService.get_instance()

    results = (
        svc.load_config(FAKE_CONTEXT),
        svc.load_config(FAKE_CONTEXT),
        svc.load_config("other"),
    )

    assert (results, cluster.connects) == ((True, True, False), [FAKE_CONTEXT, "other"])


def test_k8s_service_reachability_is_probed_once_and_cached(cluster: FakeCluster) -> None:
    svc = KubernetesService.get_instance()

    reachable = svc.is_cluster_reachable()
    cached_probe = svc.is_cluster_reachable()

    assert (reachable, cached_probe, svc.server_version(), len(cluster.version.calls)) == (
        True,
        True,
        "v1.34.1",
        1,
    )


def test_k8s_service_reports_unreachable_on_connection_error(cluster: FakeCluster) -> None:
    cluster.unreachable()

    assert KubernetesService.get_instance().is_cluster_reachable() is False


def test_k8s_service_list_contexts(cluster: FakeCluster) -> None:
    ctx_list, active = KubernetesService.get_instance().list_contexts()

    assert ([ctx["name"] for ctx in ctx_list], (active or {}).get("name")) == (
        [FAKE_CONTEXT],
        FAKE_CONTEXT,
    )


def test_k8s_service_list_nodes_caches_the_answer(cluster: FakeCluster) -> None:
    cluster.core.answers["list_node"] = [node("node-1")]
    svc = KubernetesService.get_instance()

    nodes_first = svc.list_nodes()
    nodes_cached = svc.list_nodes()

    assert (len(nodes_first), len(nodes_cached), len(cluster.core.calls)) == (1, 1, 1)


def test_k8s_service_list_pods(cluster: FakeCluster) -> None:
    pods = [pod("pod-1", "custom"), pod("pod-2", "other")]
    cluster.core.answers["list_namespaced_pod"] = pods
    cluster.core.answers["list_pod_for_all_namespaces"] = pods
    svc = KubernetesService.get_instance()

    ns_pods = svc.list_pods(namespace="custom", label_selector="app=web")
    all_pods = svc.list_pods(all_namespaces=True)

    assert ([p.metadata.name for p in ns_pods], len(all_pods), cluster.core.calls) == (
        ["pod-1"],
        2,
        [
            ("list_namespaced_pod", {"namespace": "custom", "label_selector": "app=web"}),
            ("list_pod_for_all_namespaces", {}),
        ],
    )


def test_k8s_service_read_pod_logs(cluster: FakeCluster) -> None:
    """read_pod_logs asks for a bounded tail as a stream and frames it into lines."""
    cluster.core.answers["read_namespaced_pod_log"] = {
        ("default", "pod-1"): "log-line-1\nlog-line-2\n"
    }

    lines = list(KubernetesService.get_instance().read_pod_logs("pod-1", tail_lines=50))

    assert (lines, cluster.core.calls) == (
        ["log-line-1", "log-line-2"],
        [
            (
                "read_namespaced_pod_log",
                {
                    "name": "pod-1",
                    "namespace": "default",
                    "tail_lines": 50,
                    "follow": False,
                    "_preload_content": False,
                },
            )
        ],
    )


def test_k8s_service_read_pod_logs_follow(cluster: FakeCluster) -> None:
    cluster.core.answers["read_namespaced_pod_log"] = "stream-1\nstream-2\n"

    lines = list(KubernetesService.get_instance().read_pod_logs("pod-1", follow=True))

    assert (lines, cluster.core.calls[0][1]["follow"]) == (["stream-1", "stream-2"], True)


def test_k8s_service_read_pod_logs_raises_on_error(cluster: FakeCluster) -> None:
    cluster.core.answers["read_namespaced_pod_log"] = RuntimeError("not found")

    with pytest.raises(KubernetesContextError, match="Failed to read pod logs"):
        KubernetesService.get_instance().read_pod_logs("missing-pod")


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("web-svc", "http://203.0.113.10:8080"),
        ("internal-svc", "http://192.0.2.10:30080"),
        ("bad-svc", None),
    ],
)
def test_k8s_service_resolve_service_endpoint(
    cluster: FakeCluster, name: str, expected: str | None
) -> None:
    """The endpoint is the load balancer's address, else a node's address at the node port."""
    cluster.core.answers["list_namespaced_service"] = [
        service("web-svc", port=8080, load_balancer="203.0.113.10"),
        service("internal-svc", port=80, node_port=30080),
    ]
    cluster.core.answers["list_node"] = [node("node-a", addresses={"InternalIP": "192.0.2.10"})]

    assert KubernetesService.get_instance().resolve_service_endpoint(name) == expected


def test_k8s_service_list_exceptions(cluster: FakeCluster) -> None:
    cluster.core.answers["list_node"] = RuntimeError("api down")
    cluster.core.answers["list_namespaced_pod"] = RuntimeError("api down")
    svc = KubernetesService.get_instance()

    with pytest.raises(KubernetesContextError, match="Failed to query cluster nodes"):
        svc.list_nodes()
    with pytest.raises(KubernetesContextError, match="Failed to query pods"):
        svc.list_pods()


def test_k8s_service_cache_expiration(clock: ClockFake) -> None:
    """Verify _get_cached invalidates entries after TTL."""
    svc = KubernetesService(FakeCluster())
    svc._set_cached("test-key", "test-val")
    val_immediate = svc._get_cached("test-key")

    clock.shift(301.0)
    val_expired = svc._get_cached("test-key")
    assert (val_immediate, val_expired) == ("test-val", None)


def test_cache_honours_per_entry_ttl() -> None:
    """A short negative-result TTL expires independently of the default cache TTL.

    Reachability probes cache failures for ~2s so they retry promptly; previously the
    ttl argument was accepted and silently ignored, pinning failures for the full TTL.
    """
    svc = KubernetesService(FakeCluster())

    svc._set_cached("short", "negative", ttl=0.0)
    svc._set_cached("long", "positive")

    assert (svc._get_cached("short"), svc._get_cached("long")) == (None, "positive")


def test_resource_informer_event_normalization(cluster: FakeCluster) -> None:
    """Verify ResourceInformer normalizes Watch event dictionaries."""
    informer = ResourceInformer(resource_kind="Pod", namespace="default")

    obj = SimpleNamespace(
        metadata=SimpleNamespace(name="agent-pod", namespace="default"),
        status=SimpleNamespace(phase="Running"),
    )
    event = informer._normalize_event({"type": CONST_K8S_EVENT_ADDED, "object": obj})

    assert (event.event_type, event.name, event.namespace, event.status) == (
        CONST_K8S_EVENT_ADDED,
        "agent-pod",
        "default",
        "Running",
    )


def test_resource_informer_dict_normalization(cluster: FakeCluster) -> None:
    """Verify ResourceInformer normalizes raw dictionary event objects."""
    informer = ResourceInformer(resource_kind="Pod", namespace="default")
    raw_dict = {
        "metadata": {"name": "dict-pod", "namespace": "custom-ns"},
        "status": {"phase": "Running"},
    }
    event = informer._normalize_event({"type": CONST_K8S_EVENT_ADDED, "object": raw_dict})

    assert (event.event_type, event.name, event.namespace, event.status) == (
        CONST_K8S_EVENT_ADDED,
        "dict-pod",
        "custom-ns",
        "Running",
    )


def test_resource_informer_cache_lifecycle(cluster: FakeCluster) -> None:
    """Verify ResourceInformer in-memory state updates on event stream."""
    informer = ResourceInformer(resource_kind="Pod", namespace="test-ns")

    obj = SimpleNamespace(
        metadata=SimpleNamespace(name="worker", namespace="test-ns"),
        status=SimpleNamespace(phase="Running"),
    )
    ev_add = informer._normalize_event({"type": CONST_K8S_EVENT_ADDED, "object": obj})
    informer._update_cache(ev_add, obj)

    state_after_add = informer.get_state()
    cached = informer.get_cached_resources()

    ev_del = informer._normalize_event({"type": CONST_K8S_EVENT_DELETED, "object": obj})
    informer._update_cache(ev_del, obj)
    state_after_del = informer.get_state()

    assert (
        state_after_add.resource_count,
        state_after_add.synced,
        "test-ns/worker" in cached,
        state_after_del.resource_count,
    ) == (1, True, True, 0)


def _raw_pod(name: str, namespace: str = "default", phase: str = "Running") -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": name, "namespace": namespace, "resourceVersion": "7"},
        "status": {"phase": phase},
    }


def test_resource_informer_stream_events(cluster: FakeCluster) -> None:
    """stream_events yields each event of the watch, through the SDK's own Watch."""
    cluster.core.watch_events = [
        {"type": CONST_K8S_EVENT_ADDED, "object": _raw_pod("streamed-pod")},
        {"type": CONST_K8S_EVENT_DELETED, "object": _raw_pod("streamed-pod")},
    ]
    informer = ResourceInformer(resource_kind="Pod", namespace="default")

    events = list(informer.stream_events(timeout_seconds=5.0))

    assert [(e.event_type, e.name) for e in events] == [
        (CONST_K8S_EVENT_ADDED, "streamed-pod"),
        (CONST_K8S_EVENT_DELETED, "streamed-pod"),
    ]


def test_resource_informer_stream_events_all_namespaces(cluster: FakeCluster) -> None:
    """An all-namespace informer watches every namespace."""
    informer = ResourceInformer(resource_kind="Pod", namespace="")

    events = list(informer.stream_events(timeout_seconds=2.0))

    assert (events, [call for call, _ in cluster.core.calls]) == (
        [],
        ["list_pod_for_all_namespaces"],
    )


def test_watch_streams_yield_typed_v1_pods_from_fake_cluster(cluster: FakeCluster) -> None:
    """Namespaced and all-namespace watches yield typed V1Pod objects from the fake cluster."""
    from kubernetes.client import V1Pod

    cluster.core.answers["list_namespaced_pod"] = [pod(name="worker-0", namespace="prod")]
    cluster.core.answers["list_pod_for_all_namespaces"] = [pod(name="worker-0", namespace="prod")]

    informer_ns = ResourceInformer(resource_kind="Pod", namespace="prod")
    events_ns = list(informer_ns.stream_events(timeout_seconds=1.0))
    cached_ns = informer_ns.get_cached_resources()

    informer_all = ResourceInformer(resource_kind="Pod", namespace="*")
    events_all = list(informer_all.stream_events(timeout_seconds=1.0))
    cached_all = informer_all.get_cached_resources()

    assert (
        type(cached_ns["prod/worker-0"]),
        type(cached_all["prod/worker-0"]),
        [e.name for e in events_ns],
        [e.name for e in events_all],
    ) == (V1Pod, V1Pod, ["worker-0"], ["worker-0"])


def test_stream_events_publishes_watcher_for_interruption(cluster: FakeCluster) -> None:
    """The active Watch is published so stop() can interrupt the blocking stream.

    Previously the Watch stayed local to stream_events, leaving `_watcher` as None so
    stop() could not interrupt the stream and the worker thread ran until the next
    server-side resync timeout.
    """
    from kubernetes import watch

    cluster.core.watch_events = [{"type": CONST_K8S_EVENT_ADDED, "object": _raw_pod("p")}]
    informer = ResourceInformer(resource_kind="Pod", namespace="default")

    stream = informer.stream_events(timeout_seconds=1.0)
    next(stream)
    while_streaming = informer._watcher
    list(stream)

    assert (type(while_streaming), informer._watcher) == (watch.Watch, None)


def test_resource_informer_start_and_stop(cluster: FakeCluster) -> None:
    """Verify start initiates background thread and stop terminates it."""
    informer = ResourceInformer(resource_kind="Pod", namespace="default")

    received: list[Any] = []
    with patch.object(informer, "stream_events", return_value=[]):
        informer.start(on_event=received.append)
        is_running_init = informer._running
        informer.start()  # Idempotent second call
        informer.stop()
        assert (is_running_init, informer._running) == (True, False)


def test_informer_reconnect_loop_passes_last_resource_version_and_backs_off(
    cluster: FakeCluster,
) -> None:
    """A persistent watch error backs off instead of looping, and reconnect passes last resourceVersion."""
    informer = ResourceInformer(resource_kind="Pod", namespace="default")
    informer._resource_version = "42"
    informer._running = True

    calls: list[str | None] = []
    waits: list[float] = []

    def fake_stream(
        *, timeout_seconds: float = 30.0, resource_version: str | None = None
    ) -> Iterator[Any]:
        calls.append(resource_version)
        if len(calls) == 1:
            raise RuntimeError("transient connection drop")
        informer._running = False
        return iter([])

    def fake_sleep(duration: float) -> None:
        waits.append(duration)

    with (
        patch.object(informer, "stream_events", side_effect=fake_stream),
        patch.object(informer, "_sleep_with_stop", side_effect=fake_sleep),
    ):
        informer._run_watch_loop(on_event=None)

    assert (calls, len(waits) > 0) == (["42", "42"], True)


def test_informer_reconnect_loop_relists_on_410_gone(cluster: FakeCluster) -> None:
    """Encountering 410 Gone triggers relisting to acquire fresh resourceVersion."""
    from kubernetes.client.rest import ApiException

    cluster.core.answers["list_namespaced_pod"] = [pod("relisted-pod", "default")]
    informer = ResourceInformer(resource_kind="Pod", namespace="default")
    informer._resource_version = "10"
    informer._running = True

    calls: list[str | None] = []

    def fake_stream(
        *, timeout_seconds: float = 30.0, resource_version: str | None = None
    ) -> Iterator[Any]:
        calls.append(resource_version)
        if len(calls) == 1:
            raise ApiException(status=410, reason="Gone")
        informer._running = False
        return iter([])

    with (
        patch.object(informer, "stream_events", side_effect=fake_stream),
        patch.object(informer, "_sleep_with_stop", return_value=None),
    ):
        informer._run_watch_loop(on_event=None)

    cached = informer.get_cached_resources()
    assert (calls, informer._resource_version, "default/relisted-pod" in cached) == (
        ["10", "100"],
        "100",
        True,
    )


def test_stop_interrupts_watcher_and_joins_thread(cluster: FakeCluster) -> None:
    """stop() interrupts the active watch and joins the background worker thread."""
    informer = ResourceInformer()

    mock_watch = MagicMock()
    mock_thread = MagicMock()
    mock_thread.is_alive.return_value = False
    informer._watcher = mock_watch
    informer._watch_thread = mock_thread

    informer.stop(timeout=0.5)

    assert (informer._running, informer._watch_thread, mock_watch.stop.call_count) == (
        False,
        None,
        1,
    )


def test_stop_survives_watcher_exception(cluster: FakeCluster) -> None:
    """A watcher that refuses to stop does not prevent the informer from shutting down."""
    informer = ResourceInformer()
    mock_watch = MagicMock()
    mock_watch.stop.side_effect = RuntimeError("stream already closed")
    informer._watcher = mock_watch

    informer.stop(timeout=0.1)
    assert informer._running is False


def test_informer_cache_is_bounded(cluster: FakeCluster) -> None:
    """The resource cache evicts oldest entries instead of growing without bound."""
    from devops_cli.config.defaults import DEFAULT_K8S_INFORMER_CACHE_MAX_ENTRIES

    informer = ResourceInformer(namespace="default")
    overflow = DEFAULT_K8S_INFORMER_CACHE_MAX_ENTRIES + 25

    for index in range(overflow):
        obj = SimpleNamespace(
            metadata=SimpleNamespace(name=f"pod-{index}", namespace="default"),
            status=SimpleNamespace(phase="Running"),
        )
        event = informer._normalize_event({"type": CONST_K8S_EVENT_ADDED, "object": obj})
        informer._update_cache(event, obj)

    cached = informer.get_cached_resources()
    assert (
        len(cached),
        "default/pod-0" in cached,
        f"default/pod-{overflow - 1}" in cached,
    ) == (DEFAULT_K8S_INFORMER_CACHE_MAX_ENTRIES, False, True)


class _QuietResponse:
    """A followed log response: one line, then a read blocked until its socket is shut.

    A container that stops writing leaves the read of its followed log blocked like this.
    """

    def __init__(self) -> None:
        self.shut = threading.Event()
        self.calls: list[str] = []
        self.ended_by_shutdown: bool | None = None

    def stream(self) -> Iterator[bytes]:
        yield b"first\n"
        # Whether the shut socket ended the read, not the bound running out on its own.
        self.ended_by_shutdown = self.shut.wait(timeout=THREAD_HANDOFF_BOUND_SECONDS)

    def shutdown(self) -> None:
        self.calls.append("shutdown")
        self.shut.set()

    def close(self) -> None:
        self.calls.append("close")

    def release_conn(self) -> None:
        self.calls.append("release_conn")


def test_closing_a_followed_log_ends_a_read_blocked_on_a_quiet_container() -> None:
    """Stopping the reader of a quiet container left its connection open for good.

    Closing shuts the socket for reading, which ends the blocked read from any thread;
    the reader then closes the response and returns its connection.
    """
    response = _QuietResponse()
    stream = PodLogStream(response)
    lines: list[str] = []
    reader = threading.Thread(target=lambda: lines.extend(stream), daemon=True)
    reader.start()
    stream.close()
    reader.join(timeout=THREAD_HANDOFF_BOUND_SECONDS)
    assert (reader.is_alive(), response.ended_by_shutdown, lines, response.calls) == (
        False,
        True,
        ["first"],
        ["shutdown", "close", "release_conn"],
    )


def test_closing_a_followed_log_that_already_ended_is_harmless() -> None:
    """urllib3 refuses to shut a socket it has closed; there is nothing left to stop."""
    response = MagicMock()
    response.stream.return_value = [b"only\n"]
    response.shutdown.side_effect = ValueError("Cannot shutdown socket")
    stream = PodLogStream(response)
    lines = list(stream)
    stream.close()
    assert (lines, response.close.call_count, response.release_conn.call_count) == (
        ["only"],
        1,
        1,
    )


@pytest.mark.parametrize(
    ("chunks", "expected_lines", "cap"),
    [
        ([b"a\nb", b"c\n"], ["a", "bc"], DEFAULT_LOG_MAX_LINE_CHARS),
        ([b"a\n", b"tail"], ["a", "tail"], DEFAULT_LOG_MAX_LINE_CHARS),
        ([b"caf\xc3", b"\xa9\n"], ["café"], DEFAULT_LOG_MAX_LINE_CHARS),
        ([b"\xff\nok\n"], ["\ufffd", "ok"], DEFAULT_LOG_MAX_LINE_CHARS),
        ([b"x" * 15], ["x" * 10, "x" * 5], 10),
        ([b"x" * 10, b"\n"], ["x" * 10], 10),
        ([b"a\x0cb\n"], ["a\x0cb"], DEFAULT_LOG_MAX_LINE_CHARS),
    ],
)
def test_pod_log_stream_framing_scenarios(
    chunks: list[bytes], expected_lines: list[str], cap: int
) -> None:
    """Verify incremental line framing across chunk boundaries, splits, and caps."""
    mock_resp = MagicMock()
    mock_resp.stream.return_value = chunks
    stream = PodLogStream(mock_resp, max_line_chars=cap)
    lines = list(stream)
    assert (lines, mock_resp.close.call_count, mock_resp.release_conn.call_count) == (
        expected_lines,
        1,
        1,
    )


def test_a_fake_core_api_object_records_and_refuses_like_the_real_one() -> None:
    """The fake answers a missing read with 404, records each call, and refuses when down."""
    from kubernetes.client.rest import ApiException
    from urllib3.exceptions import MaxRetryError

    core = FakeCoreV1()
    with pytest.raises(ApiException) as missing:
        core.read_persistent_volume(name="pv-gone")
    FakeCluster(core=core).unreachable()
    with pytest.raises(MaxRetryError) as raised:
        core.list_node()
    assert raised.value is not None

    assert (missing.value.status, core.calls) == (
        404,
        [("read_persistent_volume", {"name": "pv-gone"}), ("list_node", {})],
    )
