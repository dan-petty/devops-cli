"""The contract of the Kubernetes API's fake: it answers the service as the real client does (#1315).

Each case runs twice through `KubernetesService`. The `fake` side is `FakeCluster`, seeded with the
objects of the recording. The `real` side is the official client, which `KubernetesClientSource`
connects through a kubeconfig in `tmp_path` to a loopback server the test owns; the server replays
`tests/fixtures/kubernetes/recorded_responses.json` for each request's method, path and watch flag,
offline. Both sides must give the same expected result or the same error; where they differ, the
fake is wrong.

Covered: each call on the seam's Protocols (`devops_cli.k8s.api`), list and read results, a 404
and a 403 as the SDK's `ApiException` with the same status, a watch stream through the informer,
a context the kubeconfig does not name, and an API server that does not listen, which the
`refusing_port` double stands in for.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from devops_cli.exceptions.k8s import KubernetesContextError
from devops_cli.k8s.api import KubernetesClientSource
from devops_cli.k8s.informer import ResourceInformer
from devops_cli.k8s.service import KubernetesService
from tests.support.fakes.kubernetes import (
    FakeCluster,
    FakeCoreV1,
    FakeCustomObjects,
    FakeVersion,
    api_exception,
    from_wire,
)
from tests.support.paths import FIXTURES

CONTEXT = "contract"
ARGO = ("argoproj.io", "v1alpha1", "argocd", "applications")


def _recording() -> list[dict[str, Any]]:
    data = json.loads((FIXTURES / "kubernetes" / "recorded_responses.json").read_text("utf-8"))
    responses: list[dict[str, Any]] = data["responses"]
    return responses


def _recorded(method: str, path: str, *, watch: bool = False) -> dict[str, Any]:
    return next(
        entry
        for entry in _recording()
        if (entry["method"], entry["path"], entry["watch"]) == (method, path, watch)
    )


def _body(path: str) -> Any:
    return _recorded("GET", path)["body"]


def _seeded_cluster(*, contexts: tuple[str, ...] = (CONTEXT,)) -> FakeCluster:
    """A fake cluster that holds the objects the recording answers with."""
    body = _body
    core = FakeCoreV1(
        pods=from_wire(body("/api/v1/pods"), "V1PodList").items,
        nodes=from_wire(body("/api/v1/nodes"), "V1NodeList").items,
        events=from_wire(body("/api/v1/namespaces/default/events"), "CoreV1EventList").items,
        logs={
            ("default", "web-0"): _recorded("GET", "/api/v1/namespaces/default/pods/web-0/log")[
                "text"
            ]
        },
        watch_events=_recorded("GET", "/api/v1/namespaces/default/pods", watch=True)["lines"],
        services=from_wire(body("/api/v1/namespaces/default/services"), "V1ServiceList").items,
        pvs={"pv-a": from_wire(body("/api/v1/persistentvolumes/pv-a"), "V1PersistentVolume")},
    )
    core.answers["list_event_for_all_namespaces"] = api_exception(403, "Forbidden")
    applications = body("/apis/argoproj.io/v1alpha1/namespaces/argocd/applications")["items"]
    return FakeCluster(
        core=core,
        custom_objects=FakeCustomObjects({ARGO[0:2] + ARGO[3:]: applications}),
        version=FakeVersion(git_version=body("/version/")["gitVersion"]),
        contexts=contexts,
        current=CONTEXT,
    )


class _Replay(BaseHTTPRequestHandler):
    """Answers each request with the recorded response for its method, path and watch flag."""

    def _answer(self) -> None:
        parts = urlsplit(self.path)
        watch = parse_qs(parts.query).get("watch", [""])[0].lower() == "true"
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        try:
            entry = _recorded(self.command, parts.path, watch=watch)
        except StopIteration:
            entry = {"status": 599, "text": f"no recorded answer for {self.command} {self.path}"}
        if "lines" in entry:
            payload = "".join(json.dumps(line) + "\n" for line in entry["lines"]).encode()
            content_type = "application/json"
        elif "text" in entry:
            payload, content_type = entry["text"].encode(), "text/plain"
        else:
            payload, content_type = json.dumps(entry["body"]).encode(), "application/json"
        self.send_response(entry["status"])
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        self._answer()

    def do_POST(self) -> None:
        self._answer()

    def do_PATCH(self) -> None:
        self._answer()

    def do_DELETE(self) -> None:
        self._answer()

    def log_message(self, format: str, *args: Any) -> None:
        """Keep the replay quiet."""


def _kubeconfig(path: Path, server: str) -> Path:
    path.write_text(
        "apiVersion: v1\n"
        "kind: Config\n"
        f"clusters:\n- name: {CONTEXT}\n  cluster:\n    server: {server}\n"
        f"contexts:\n- name: {CONTEXT}\n  context:\n    cluster: {CONTEXT}\n    user: {CONTEXT}\n"
        f"current-context: {CONTEXT}\n"
        f"users:\n- name: {CONTEXT}\n  user:\n    token: placeholder-token\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def replay_server() -> Iterator[str]:
    """The loopback server that replays the recording, as `http://127.0.0.1:<port>`."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Replay)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _real_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, server: str
) -> KubernetesService:
    monkeypatch.setenv("KUBECONFIG", str(_kubeconfig(tmp_path / "kubeconfig", server)))
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
    return KubernetesService(KubernetesClientSource())


@pytest.fixture
def contract_context(config: Callable[..., Path]) -> str:
    """The configured context of both sides, which a call without a context resolves to."""
    config(k8s={"context": CONTEXT})
    return CONTEXT


@pytest.fixture(params=["fake", "real"])
def service(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    contract_context: str,
) -> KubernetesService:
    """The service over each side: the seeded fake, or the real client over the replay."""
    if request.param == "fake":
        return KubernetesService(_seeded_cluster())
    server = request.getfixturevalue("replay_server")
    return _real_service(tmp_path, monkeypatch, server)


@pytest.fixture(params=["fake", "real"])
def down_service(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    contract_context: str,
) -> KubernetesService:
    """The service over each side when no API server listens."""
    if request.param == "fake":
        return KubernetesService(_seeded_cluster().unreachable())
    port = request.getfixturevalue("refusing_port")
    return _real_service(tmp_path, monkeypatch, f"http://127.0.0.1:{port}")


def _outcome(call: Callable[[], Any]) -> Any:
    """The call's result, or the error it raised as `(type, status, reason)` or `(type, cause)`."""
    from kubernetes.client.rest import ApiException

    try:
        return call()
    except ApiException as exc:
        return ("ApiException", exc.status, exc.reason)
    except KubernetesContextError as exc:
        return ("KubernetesContextError", type(exc.__cause__).__name__)


def test_contexts_name_the_kubeconfig_contexts_and_the_current_one(
    service: KubernetesService,
) -> None:
    contexts, active = service.list_contexts()

    assert ([ctx["name"] for ctx in contexts], (active or {}).get("name")) == (
        [CONTEXT],
        CONTEXT,
    )


def test_a_context_the_kubeconfig_does_not_name_does_not_connect(
    service: KubernetesService,
) -> None:
    assert (service.load_config("other"), service.is_cluster_reachable("other")) == (False, False)


def test_nodes_are_listed_with_their_ready_status_and_addresses(service: KubernetesService) -> None:
    nodes = service.list_nodes()

    assert [
        (
            n.metadata.name,
            [c.status for c in n.status.conditions if c.type == "Ready"],
            [(a.type, a.address) for a in n.status.addresses],
        )
        for n in nodes
    ] == [
        ("node-a", ["True"], [("InternalIP", "192.0.2.10"), ("Hostname", "node-a")]),
        ("node-b", ["False"], [("InternalIP", "192.0.2.11"), ("Hostname", "node-b")]),
    ]


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (
            {"namespace": "default"},
            [("default", "web-0", "Running"), ("default", "web-1", "Pending")],
        ),
        (
            {"all_namespaces": True},
            [
                ("default", "web-0", "Running"),
                ("default", "web-1", "Pending"),
                ("data", "db-0", "Running"),
            ],
        ),
    ],
)
def test_pods_are_listed_for_one_namespace_or_all(
    service: KubernetesService, kwargs: dict[str, Any], expected: list[tuple[str, str, str]]
) -> None:
    pods = service.list_pods(**kwargs)

    assert [(p.metadata.namespace, p.metadata.name, p.status.phase) for p in pods] == expected


def test_a_pod_log_is_read_line_by_line(service: KubernetesService) -> None:
    assert list(service.read_pod_logs("web-0", namespace="default")) == ["line one", "line two"]


@pytest.mark.parametrize(
    ("name", "expected"),
    [("web", "http://192.0.2.50"), ("api", "http://192.0.2.10:30080"), ("missing", None)],
)
def test_a_service_endpoint_comes_from_its_load_balancer_or_a_node_port(
    service: KubernetesService, name: str, expected: str | None
) -> None:
    assert service.resolve_service_endpoint(name, namespace="default") == expected


def test_services_are_listed_and_a_missing_one_is_a_404(service: KubernetesService) -> None:
    core = service.core_api()

    assert (
        [s.metadata.name for s in core.list_namespaced_service(namespace="default").items],
        _outcome(lambda: core.read_namespaced_service(name="missing", namespace="default")),
    ) == (["web", "api"], ("ApiException", 404, "Not Found"))


def test_events_are_listed_and_a_forbidden_list_is_a_403(service: KubernetesService) -> None:
    core = service.core_api()

    assert (
        [
            (e.reason, e.involved_object.name)
            for e in core.list_namespaced_event(namespace="default").items
        ],
        _outcome(core.list_event_for_all_namespaces),
    ) == ([("Pulled", "web-0")], ("ApiException", 403, "Forbidden"))


def test_a_persistent_volume_is_read_and_a_missing_one_is_a_404(
    service: KubernetesService,
) -> None:
    core = service.core_api()
    volume = core.read_persistent_volume(name="pv-a")

    assert (
        (volume.metadata.name, volume.status.phase, volume.metadata.finalizers),
        _outcome(lambda: core.read_persistent_volume(name="pv-gone")),
        _outcome(
            lambda: core.read_namespaced_persistent_volume_claim(name="db-data", namespace="data")
        ),
    ) == (
        ("pv-a", "Released", ["kubernetes.io/pv-protection"]),
        ("ApiException", 404, "Not Found"),
        ("ApiException", 404, "Not Found"),
    )


def test_a_persistent_volume_loses_its_finalizers_by_patch_and_is_deleted(
    service: KubernetesService,
) -> None:
    core = service.core_api()
    patched = core.patch_persistent_volume(name="pv-a", body={"metadata": {"finalizers": []}})
    deleted = core.delete_persistent_volume(name="pv-a")

    assert ((patched.metadata.name, patched.metadata.finalizers), deleted.metadata.name) == (
        ("pv-a", None),
        "pv-a",
    )


def test_custom_objects_are_listed_read_and_a_missing_one_is_a_404(
    service: KubernetesService,
) -> None:
    api = service.custom_objects_api()
    group, version, namespace, plural = ARGO

    listed = api.list_namespaced_custom_object(group, version, namespace, plural)
    read = api.get_namespaced_custom_object(group, version, namespace, plural, "web")

    assert (
        [(o["metadata"]["name"], o["status"]["sync"]["status"]) for o in listed["items"]],
        (read["kind"], read["metadata"]["name"]),
        _outcome(
            lambda: api.get_namespaced_custom_object(group, version, namespace, plural, "missing")
        ),
    ) == ([("web", "Synced")], ("Application", "web"), ("ApiException", 404, "Not Found"))


def test_a_custom_object_is_patched(service: KubernetesService) -> None:
    api = service.custom_objects_api()
    group, version, namespace, plural = ARGO
    refresh = {"metadata": {"annotations": {"argocd.argoproj.io/refresh": "normal"}}}

    annotated = api.patch_namespaced_custom_object(
        group, version, namespace, plural, "web", refresh
    )

    assert annotated["metadata"]["annotations"] == {"argocd.argoproj.io/refresh": "normal"}


def test_a_custom_object_status_is_patched(service: KubernetesService) -> None:
    api = service.custom_objects_api()
    group, version, namespace, plural = ARGO
    body = {"status": {"sync": {"status": "OutOfSync"}}}

    patched = api.patch_namespaced_custom_object_status(
        group, version, namespace, plural, "web", body
    )

    assert (patched["status"]["sync"]["status"], patched["status"]["health"]["status"]) == (
        "OutOfSync",
        "Healthy",
    )


def test_a_custom_object_is_created_in_its_namespace(service: KubernetesService) -> None:
    api = service.custom_objects_api()
    group, version, namespace, plural = ARGO
    body = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {"name": "api"},
        "spec": {"project": "default"},
    }

    created = api.create_namespaced_custom_object(group, version, namespace, plural, body)

    assert (created["kind"], created["metadata"]["name"], created["metadata"]["namespace"]) == (
        "Application",
        "api",
        "argocd",
    )


def test_the_server_version_is_read_and_the_cluster_is_reachable(
    service: KubernetesService,
) -> None:
    assert (service.is_cluster_reachable(), service.server_version()) == (True, "v1.34.1")


def test_a_pod_watch_streams_typed_events_through_the_informer(service: KubernetesService) -> None:
    informer = ResourceInformer(service=service, namespace="default")

    events = list(informer.stream_events(timeout_seconds=1))

    assert [(e.event_type, e.namespace, e.name, e.status) for e in events] == [
        ("ADDED", "default", "web-0", "Running"),
        ("MODIFIED", "default", "web-1", "ContainerCreating"),
    ]


def test_an_api_server_that_does_not_listen_refuses_every_call(
    down_service: KubernetesService,
) -> None:
    assert (
        down_service.is_cluster_reachable(),
        _outcome(down_service.list_nodes),
        _outcome(lambda: down_service.list_pods(namespace="default")),
    ) == (
        False,
        ("KubernetesContextError", "MaxRetryError"),
        ("KubernetesContextError", "MaxRetryError"),
    )
