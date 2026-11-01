"""The Kubernetes API's fake: the SDK's API objects, faked behind the service's source (#1315).

`KubernetesService` takes its API objects from a `KubernetesApiSource` (`devops_cli.k8s.api`).
`FakeCluster` is that source for tests: it names its kubeconfig contexts and connects every
context to one `FakeCoreV1`, one `FakeCustomObjects` and one `FakeVersion`. The `cluster` fixture
installs it as the process's service, so the service's caching, context resolution and
projections run as they do against a real cluster.

The objects are the SDK's own models, so code under test reads them exactly as it reads a real
API response. A missing object is answered with the SDK's `ApiException` and its status, as the
API server answers it. `FakeCluster.unreachable()` makes every call raise what the client raises
when no server listens. Each fake records its calls in `calls`, as `(method, arguments)`.
`tests/k8s/test_kubernetes_contract.py` holds the fake to the real client over recorded API
responses. Names are generic, as SECURITY.md requires of fixtures.
"""

from __future__ import annotations

import copy
import datetime
import json
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from devops_cli.exceptions.k8s import KubernetesContextError


class _LazyKubernetesClient:
    """Lazily load kubernetes.client so importing test fixtures does not cost ~600ms."""

    def __getattr__(self, name: str) -> Any:
        from kubernetes import client as k8s_client

        val = getattr(k8s_client, name)
        globals()["client"] = k8s_client
        return val


client: Any = _LazyKubernetesClient()

NOW = datetime.datetime(2026, 10, 1, 12, 0, tzinfo=datetime.UTC)

FAKE_CONTEXT = "fake"


def running() -> Any:
    """A container state that is running."""
    return client.V1ContainerState(running=client.V1ContainerStateRunning(started_at=NOW))


def waiting(reason: str) -> Any:
    """A container state waiting for the given reason."""
    return client.V1ContainerState(waiting=client.V1ContainerStateWaiting(reason=reason))


def terminated(exit_code: int, reason: str | None = None, signal: int | None = None) -> Any:
    """A container state that has terminated."""
    return client.V1ContainerState(
        terminated=client.V1ContainerStateTerminated(
            exit_code=exit_code, reason=reason, signal=signal
        )
    )


def status(
    name: str,
    state: Any,
    *,
    ready: bool = False,
    restarts: int = 0,
    started: bool | None = None,
    last: Any = None,
) -> Any:
    """A container status as the kubelet reports it."""
    return client.V1ContainerStatus(
        name=name,
        image=f"example.com/{name}:1",
        image_id="",
        ready=ready,
        restart_count=restarts,
        started=started,
        state=state,
        last_state=last,
    )


def ready_app(name: str = "app") -> Any:
    """A running, ready app container status."""
    return status(name, running(), ready=True)


def pod(
    name: str = "web-0",
    namespace: str = "default",
    *,
    phase: str = "Running",
    containers: tuple[str, ...] = ("app",),
    statuses: list[Any] | None = None,
    init_containers: tuple[str, ...] = (),
    sidecars: tuple[str, ...] = (),
    init_statuses: list[Any] | None = None,
    reason: str | None = None,
    conditions: dict[str, str] | None = None,
    annotations: dict[str, str] | None = None,
    deleted: bool = False,
    node_name: str | None = None,
    finalizers: list[str] | None = None,
    creation_timestamp: datetime.datetime | None = None,
    deletion_timestamp: datetime.datetime | None = None,
) -> Any:
    """A pod. `sidecars` names the init containers whose restart policy is Always."""
    spec_inits = [
        client.V1Container(
            name=init,
            image=f"example.com/{init}:1",
            restart_policy="Always" if init in sidecars else None,
        )
        for init in init_containers
    ]
    del_ts = deletion_timestamp or (NOW if deleted else None)
    return client.V1Pod(
        metadata=client.V1ObjectMeta(
            name=name,
            namespace=namespace,
            uid=f"uid-{namespace}-{name}",
            annotations=annotations,
            creation_timestamp=creation_timestamp or NOW,
            deletion_timestamp=del_ts,
            finalizers=finalizers,
        ),
        spec=client.V1PodSpec(
            node_name=node_name,
            containers=[
                client.V1Container(name=container, image=f"example.com/{container}:1")
                for container in containers
            ],
            init_containers=spec_inits or None,
        ),
        status=client.V1PodStatus(
            phase=phase,
            reason=reason,
            conditions=[
                client.V1PodCondition(type=kind, status=value)
                for kind, value in (conditions or {}).items()
            ]
            or None,
            container_statuses=statuses,
            init_container_statuses=init_statuses,
        ),
    )


def healthy_pod(name: str, namespace: str = "default", *, node_name: str | None = None) -> Any:
    """A running pod whose one container is ready."""
    return pod(
        name, namespace, node_name=node_name, statuses=[ready_app()], conditions={"Ready": "True"}
    )


def crashlooping_pod(
    name: str,
    namespace: str = "default",
    *,
    node_name: str | None = None,
    restarts: int = 86,
) -> Any:
    """A pod in phase Running whose container waits in CrashLoopBackOff."""
    return pod(
        name,
        namespace,
        node_name=node_name,
        statuses=[
            status(
                "app",
                waiting("CrashLoopBackOff"),
                restarts=restarts,
                last=terminated(1, "Error"),
            )
        ],
        conditions={"Ready": "False"},
    )


def node(
    name: str,
    ready: str = "True",
    unschedulable: bool = False,
    addresses: dict[str, str] | None = None,
) -> Any:
    """A node whose Ready condition holds the given status, with its addresses by type."""
    return client.V1Node(
        metadata=client.V1ObjectMeta(name=name),
        spec=client.V1NodeSpec(unschedulable=unschedulable),
        status=client.V1NodeStatus(
            conditions=[client.V1NodeCondition(type="Ready", status=ready)],
            addresses=[
                client.V1NodeAddress(type=kind, address=address)
                for kind, address in (addresses or {}).items()
            ]
            or None,
        ),
    )


def service(
    name: str,
    namespace: str = "default",
    *,
    port: int = 80,
    node_port: int | None = None,
    load_balancer: str | None = None,
    port_name: str | None = None,
    ports: list[tuple[int, str | None]] | None = None,
) -> Any:
    """A Service with one port, or the `(number, name)` `ports` given, and the address of its
    load balancer when it has one."""
    ingress = [client.V1LoadBalancerIngress(ip=load_balancer)] if load_balancer else None
    if ports is None:
        spec_ports = [client.V1ServicePort(name=port_name, port=port, node_port=node_port)]
    else:
        spec_ports = [client.V1ServicePort(name=pname, port=number) for number, pname in ports]
    return client.V1Service(
        metadata=client.V1ObjectMeta(name=name, namespace=namespace),
        spec=client.V1ServiceSpec(ports=spec_ports),
        status=client.V1ServiceStatus(load_balancer=client.V1LoadBalancerStatus(ingress=ingress)),
    )


def event(
    reason: str,
    *,
    last: datetime.datetime | None = None,
    event_time: datetime.datetime | None = None,
    first: datetime.datetime | None = None,
    created: datetime.datetime | None = None,
    count: int | None = None,
    series_count: int | None = None,
    kind: str = "Normal",
    message: str = "",
    involved_kind: str = "Pod",
    involved_name: str = "web-0",
    involved_namespace: str | None = None,
) -> Any:
    """A core/v1 event. One written through events.k8s.io/v1 has only event_time and series."""
    return client.CoreV1Event(
        metadata=client.V1ObjectMeta(name=f"evt-{reason}", creation_timestamp=created),
        involved_object=client.V1ObjectReference(
            kind=involved_kind, name=involved_name, namespace=involved_namespace
        ),
        reason=reason,
        message=message or f"{reason} happened",
        type=kind,
        count=count,
        last_timestamp=last,
        event_time=event_time,
        first_timestamp=first,
        series=client.CoreV1EventSeries(count=series_count) if series_count else None,
    )


def api_exception(status_code: int, reason: str) -> Exception:
    """The SDK's `ApiException`, with the status and reason the API server sends."""
    from kubernetes.client.rest import ApiException

    return ApiException(status=status_code, reason=reason)


def not_found() -> Exception:
    """The SDK's answer to a read of an object the API server does not hold."""
    return api_exception(404, "Not Found")


def connection_refused(url: str = "/") -> Exception:
    """What the client raises when no API server listens: urllib3's `MaxRetryError`."""
    from urllib3.exceptions import MaxRetryError, NewConnectionError

    reason = NewConnectionError(None, "Failed to establish a new connection: Connection refused")  # type: ignore[arg-type]
    return MaxRetryError(None, url, reason=reason)  # type: ignore[arg-type]


def from_wire(data: Any, kind: str) -> Any:
    """Deserialize an API response body into the SDK's model `kind`, as the client does."""
    from kubernetes import client as k8s_client

    return k8s_client.ApiClient().deserialize(SimpleNamespace(data=json.dumps(data)), kind)


class _FakeStreamResponse:
    """A streamed HTTP response: watch lines or log chunks, in order.

    A chunk that is an exception is raised when the reader reaches it, as a connection that
    drops in the middle of a body raises.
    """

    def __init__(self, chunks: list[Any]) -> None:
        self._chunks = chunks

    def stream(self, amt: Any = None, decode_content: bool = False) -> Iterator[Any]:
        for chunk in self._chunks:
            if isinstance(chunk, BaseException):
                raise chunk
            yield chunk

    def close(self) -> None:
        pass

    def release_conn(self) -> None:
        pass

    def shutdown(self) -> None:
        pass


class _FakeApi:
    """What every fake API object shares: the call log and the unreachable state."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.refused = False

    def _record(self, method: str, kwargs: dict[str, Any]) -> None:
        self.calls.append((method, kwargs))
        if self.refused:
            raise connection_refused(method)


class FakeCoreV1(_FakeApi):
    """A CoreV1Api stand-in that records every call and answers from fixed data.

    A list call answers with the given items, or raises the given exception instead. A read
    of a service, persistent volume or claim that the fake does not hold raises 404.
    """

    def __init__(
        self,
        pods: list[Any] | Exception | None = None,
        nodes: list[Any] | Exception | None = None,
        events: list[Any] | Exception | None = None,
        logs: dict[tuple[str, str], str | bytes | list[Any]]
        | str
        | bytes
        | list[Any]
        | Exception
        | None = None,
        watch_events: list[dict[str, Any]] | Exception | None = None,
        services: list[Any] | Exception | None = None,
        pvs: dict[str, Any] | None = None,
        pvcs: dict[tuple[str, str], Any] | None = None,
    ) -> None:
        super().__init__()
        self.watch_events = watch_events
        self.answers = {
            "list_pod_for_all_namespaces": pods if pods is not None else [],
            "list_namespaced_pod": pods if pods is not None else [],
            "list_node": nodes if nodes is not None else [],
            "list_namespaced_event": events if events is not None else [],
            "list_event_for_all_namespaces": events if events is not None else [],
            "read_namespaced_pod_log": logs if logs is not None else "",
            "list_namespaced_service": services if services is not None else [],
        }
        self.pvs: dict[str, Any] = dict(pvs or {})
        self.pvcs: dict[tuple[str, str], Any] = dict(pvcs or {})

    def _answer(self, method: str, kwargs: dict[str, Any]) -> Any:
        self._record(method, kwargs)
        if kwargs.get("watch"):
            if isinstance(self.watch_events, Exception):
                raise self.watch_events
            if self.watch_events is not None:
                lines = [f"{json.dumps(ev)}\n" for ev in self.watch_events]
                return _FakeStreamResponse(lines)
        answer = self.answers[method]
        if isinstance(answer, Exception):
            raise answer
        if method == "read_namespaced_pod_log":
            return _log_answer(answer, kwargs)
        items = [item for item in answer if _in_namespace(item, kwargs.get("namespace"))]
        if kwargs.get("watch"):
            lines = []
            for item in items:
                raw_item = (
                    item
                    if isinstance(item, dict)
                    else client.ApiClient().sanitize_for_serialization(item)
                )
                lines.append(f"{json.dumps({'type': 'ADDED', 'object': raw_item})}\n")
            return _FakeStreamResponse(lines)
        return _Items(items)

    def list_pod_for_all_namespaces(self, **kwargs: Any) -> Any:
        """:rtype: V1PodList"""
        return self._answer("list_pod_for_all_namespaces", kwargs)

    def list_namespaced_pod(self, namespace: str, **kwargs: Any) -> Any:
        """:rtype: V1PodList"""
        return self._answer("list_namespaced_pod", {"namespace": namespace, **kwargs})

    def list_node(self, **kwargs: Any) -> Any:
        """:rtype: V1NodeList"""
        return self._answer("list_node", kwargs)

    def list_namespaced_event(self, namespace: str, **kwargs: Any) -> Any:
        """:rtype: CoreV1EventList"""
        return self._answer("list_namespaced_event", {"namespace": namespace, **kwargs})

    def list_event_for_all_namespaces(self, **kwargs: Any) -> Any:
        """:rtype: CoreV1EventList"""
        return self._answer("list_event_for_all_namespaces", kwargs)

    def read_namespaced_pod_log(self, name: str, namespace: str, **kwargs: Any) -> Any:
        """:rtype: str"""
        return self._answer(
            "read_namespaced_pod_log", {"name": name, "namespace": namespace, **kwargs}
        )

    def list_namespaced_service(self, namespace: str, **kwargs: Any) -> Any:
        """:rtype: V1ServiceList"""
        return self._answer("list_namespaced_service", {"namespace": namespace, **kwargs})

    def read_namespaced_service(self, name: str, namespace: str, **kwargs: Any) -> Any:
        """:rtype: V1Service"""
        self._record("read_namespaced_service", {"name": name, "namespace": namespace, **kwargs})
        services = self.answers["list_namespaced_service"]
        if isinstance(services, Exception):
            raise services
        for item in services:
            meta = item.metadata
            if meta.name == name and (meta.namespace or "default") == namespace:
                return item
        raise not_found()

    def read_persistent_volume(self, name: str, **kwargs: Any) -> Any:
        """:rtype: V1PersistentVolume"""
        self._record("read_persistent_volume", {"name": name, **kwargs})
        if name not in self.pvs:
            raise not_found()
        return self.pvs[name]

    def patch_persistent_volume(self, name: str, body: Any, **kwargs: Any) -> Any:
        """:rtype: V1PersistentVolume"""
        self._record("patch_persistent_volume", {"name": name, "body": body, **kwargs})
        if name not in self.pvs:
            raise not_found()
        finalizers = (
            (body.get("metadata") or {}).get("finalizers") if isinstance(body, dict) else None
        )
        if finalizers is not None:
            self.pvs[name].metadata.finalizers = list(finalizers) or None
        return self.pvs[name]

    def delete_persistent_volume(self, name: str, **kwargs: Any) -> Any:
        """:rtype: V1PersistentVolume"""
        self._record("delete_persistent_volume", {"name": name, **kwargs})
        if name not in self.pvs:
            raise not_found()
        return self.pvs.pop(name)

    def read_namespaced_persistent_volume_claim(
        self, name: str, namespace: str, **kwargs: Any
    ) -> Any:
        """:rtype: V1PersistentVolumeClaim"""
        self._record(
            "read_namespaced_persistent_volume_claim",
            {"name": name, "namespace": namespace, **kwargs},
        )
        claim = self.pvcs.get((namespace, name))
        if claim is None:
            raise not_found()
        return claim


def _log_bytes(answer: Any) -> bytes:
    """The bytes a pod wrote: an answer that is `bytes`, or text, or a list of chunks."""
    if isinstance(answer, bytes):
        return answer
    if isinstance(answer, list):
        return b"".join(c for c in answer if isinstance(c, bytes))
    return str(answer).encode()


def _log_answer(answer: Any, kwargs: dict[str, Any]) -> Any:
    """A pod's log as the client answers it.

    The answer is what the pod wrote: text, `bytes`, or a list of byte chunks (and exceptions)
    to stream as they are. A dict holds one of those for each `(namespace, pod)`, and a pod it
    does not hold is a 404.

    A read that asks not to preload the body gets the stream of the bytes. A plain read gets what
    `kubernetes` 36.0.3 gives: the response type of `read_namespaced_pod_log` is `str`, so the
    client skips the decode and `deserialize` ends in `str(bytes)`, the escaped `b'...'` text.
    """
    if isinstance(answer, dict):
        key = (kwargs.get("namespace", ""), kwargs.get("name", ""))
        if key not in answer:
            raise not_found()
        answer = answer[key]
    if kwargs.get("_preload_content") is False:
        if isinstance(answer, list):
            return _FakeStreamResponse(answer)
        return _FakeStreamResponse([_log_bytes(answer)] if answer else [])
    return str(_log_bytes(answer))


def _in_namespace(item: Any, namespace: str | None) -> bool:
    """Whether a listed object belongs to `namespace`; a list for all namespaces keeps all."""
    if namespace is None or isinstance(item, dict):
        return True
    meta = getattr(item, "metadata", None)
    item_namespace = getattr(meta, "namespace", None)
    return item_namespace is None or item_namespace == namespace


def _equality_selector(selector: str | None) -> dict[str, str]:
    """The labels of an equality label selector, `a=b,c=d`, the one form devops-cli sends. A
    selector of another form is refused, so a test cannot pass on a filter the fake ignores."""
    pairs = [pair.split("=") for pair in (selector or "").split(",") if pair]
    if any(len(pair) != 2 or not pair[0] or "!" in pair[0] for pair in pairs):
        raise ValueError(f"The fake takes only equality label selectors, not {selector!r}")
    return {key: value for key, value in pairs}


def _merge(target: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Apply a JSON merge patch (RFC 7386): a null deletes a key, a mapping merges."""
    merged = copy.deepcopy(target)
    for key, value in patch.items():
        if value is None:
            merged.pop(key, None)
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


class FakeCustomObjects(_FakeApi):
    """A CustomObjectsApi stand-in that holds custom objects as the API server's dicts.

    `objects` maps `(group, version, plural)` to the objects of that resource. A read or patch
    of an object the fake does not hold raises 404, and a create of one it holds raises 409.
    """

    def __init__(self, objects: dict[tuple[str, str, str], list[dict[str, Any]]] | None = None):
        super().__init__()
        self.objects: dict[tuple[str, str, str], list[dict[str, Any]]] = {
            key: [copy.deepcopy(obj) for obj in items] for key, items in (objects or {}).items()
        }

    def _find(
        self, group: str, version: str, namespace: str, plural: str, name: str
    ) -> dict[str, Any]:
        for obj in self.objects.get((group, version, plural), []):
            meta = obj.get("metadata") or {}
            if meta.get("name") == name and meta.get("namespace") == namespace:
                return obj
        raise not_found()

    def list_namespaced_custom_object(
        self, group: str, version: str, namespace: str, plural: str, **kwargs: Any
    ) -> Any:
        """:rtype: object"""
        self._record(
            "list_namespaced_custom_object",
            {
                "group": group,
                "version": version,
                "namespace": namespace,
                "plural": plural,
                **kwargs,
            },
        )
        wanted = _equality_selector(kwargs.get("label_selector"))
        items = [
            copy.deepcopy(obj)
            for obj in self.objects.get((group, version, plural), [])
            if (obj.get("metadata") or {}).get("namespace") == namespace
            and wanted.items() <= ((obj.get("metadata") or {}).get("labels") or {}).items()
        ]
        return {"apiVersion": f"{group}/{version}", "items": items, "metadata": {}}

    def get_namespaced_custom_object(
        self, group: str, version: str, namespace: str, plural: str, name: str, **kwargs: Any
    ) -> Any:
        """:rtype: object"""
        self._record(
            "get_namespaced_custom_object",
            {
                "group": group,
                "version": version,
                "namespace": namespace,
                "plural": plural,
                "name": name,
                **kwargs,
            },
        )
        return copy.deepcopy(self._find(group, version, namespace, plural, name))

    def create_namespaced_custom_object(
        self, group: str, version: str, namespace: str, plural: str, body: Any, **kwargs: Any
    ) -> Any:
        """:rtype: object"""
        self._record(
            "create_namespaced_custom_object",
            {
                "group": group,
                "version": version,
                "namespace": namespace,
                "plural": plural,
                "body": body,
                **kwargs,
            },
        )
        name = (body.get("metadata") or {}).get("name")
        try:
            self._find(group, version, namespace, plural, str(name))
        except Exception:
            created = _merge(copy.deepcopy(body), {"metadata": {"namespace": namespace}})
            self.objects.setdefault((group, version, plural), []).append(created)
            return copy.deepcopy(created)
        raise api_exception(409, "Conflict")

    def patch_namespaced_custom_object(
        self,
        group: str,
        version: str,
        namespace: str,
        plural: str,
        name: str,
        body: Any,
        **kwargs: Any,
    ) -> Any:
        """:rtype: object"""
        self._record(
            "patch_namespaced_custom_object",
            {
                "group": group,
                "version": version,
                "namespace": namespace,
                "plural": plural,
                "name": name,
                "body": body,
                **kwargs,
            },
        )
        return self._patch(group, version, namespace, plural, name, body)

    def patch_namespaced_custom_object_status(
        self,
        group: str,
        version: str,
        namespace: str,
        plural: str,
        name: str,
        body: Any,
        **kwargs: Any,
    ) -> Any:
        """:rtype: object"""
        self._record(
            "patch_namespaced_custom_object_status",
            {
                "group": group,
                "version": version,
                "namespace": namespace,
                "plural": plural,
                "name": name,
                "body": body,
                **kwargs,
            },
        )
        return self._patch(
            group, version, namespace, plural, name, {"status": (body or {}).get("status")}
        )

    def _patch(
        self, group: str, version: str, namespace: str, plural: str, name: str, body: Any
    ) -> dict[str, Any]:
        current = self._find(group, version, namespace, plural, name)
        patched = _merge(current, body or {})
        items = self.objects[(group, version, plural)]
        items[items.index(current)] = patched
        return copy.deepcopy(patched)


class FakeVersion(_FakeApi):
    """A VersionApi stand-in that answers `get_code` with one server version."""

    def __init__(self, git_version: str = "v1.34.1") -> None:
        super().__init__()
        self.git_version = git_version

    def get_code(self, **kwargs: Any) -> Any:
        """:rtype: VersionInfo"""
        self._record("get_code", kwargs)
        major, minor = self.git_version.lstrip("v").split(".")[:2]
        return client.VersionInfo(
            build_date="2026-10-01T00:00:00Z",
            compiler="gc",
            git_commit="0" * 40,
            git_tree_state="clean",
            git_version=self.git_version,
            go_version="go1.25.1",
            major=major,
            minor=minor,
            platform="linux/amd64",
        )


class FakeCluster:
    """The Kubernetes API, faked: a `KubernetesApiSource` over the fake API objects.

    It names `contexts` as a kubeconfig does, with `current` as its current context, and
    connects every context it names to the same API objects. A context it does not name is
    refused with `KubernetesContextError`, as the real source refuses a context that neither
    the kubeconfig nor a service account gives. `connects` records each context asked for.
    """

    def __init__(
        self,
        core: FakeCoreV1 | None = None,
        custom_objects: FakeCustomObjects | None = None,
        version: FakeVersion | None = None,
        contexts: tuple[str, ...] = (FAKE_CONTEXT,),
        current: str | None = FAKE_CONTEXT,
        configuration: Any = None,
    ) -> None:
        from types import SimpleNamespace

        self.core = core or FakeCoreV1()
        self.custom_objects = custom_objects or FakeCustomObjects()
        self.version = version or FakeVersion()
        self.context_names = list(contexts)
        self.current = current
        self.configuration = (
            configuration
            if configuration is not None
            else SimpleNamespace(
                host="https://cluster.example.com:6443",
                ssl_ca_cert=None,
                verify_ssl=True,
                cert_file=None,
                key_file=None,
                api_key={},
                api_key_prefix={},
                refresh_api_key_hook=None,
            )
        )
        self.connects: list[str | None] = []

    def unreachable(self) -> FakeCluster:
        """Refuse every API call as a cluster whose API server does not listen refuses it."""
        for api in (self.core, self.custom_objects, self.version):
            api.refused = True
        return self

    def contexts(self) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """The contexts and the current one, shaped as `list_kube_config_contexts` gives them."""
        listed = [
            {"name": name, "context": {"cluster": name, "user": name}}
            for name in self.context_names
        ]
        active = next((ctx for ctx in listed if ctx["name"] == self.current), None)
        return listed, active

    def connect(self, context: str | None) -> Any:
        """The API objects of `context`, else of the current context."""
        from devops_cli.k8s.api import KubernetesApis

        self.connects.append(context)
        name = context or self.current
        if name not in self.context_names:
            raise KubernetesContextError(
                f"No kubeconfig context named '{name}', and no service account", context=name
            )
        return KubernetesApis(
            core=self.core,
            custom_objects=self.custom_objects,
            version=self.version,
            configuration=self.configuration,
        )


class _Items:
    """A list response: `items` and `metadata` are read."""

    def __init__(self, items: list[Any], resource_version: str = "100") -> None:
        self.items = items
        self.metadata = SimpleNamespace(resource_version=resource_version)


@pytest.fixture
def cluster(config: Callable[..., Path]) -> Iterator[FakeCluster]:
    """The Kubernetes API, faked for the process's `KubernetesService`.

    The fixture installs a `FakeCluster` through `KubernetesService.install` and returns it, so
    a test seeds its API objects (`cluster.core`, `cluster.custom_objects`, `cluster.version`)
    and reads their `calls`. The configured context (`k8s.context`) is the fake's, so a call
    that names no context reaches it. `KubernetesService.reset_instance` removes it at teardown.
    """
    from devops_cli.k8s.service import KubernetesService

    config(k8s={"context": FAKE_CONTEXT})
    fake = FakeCluster()
    KubernetesService.install(fake)
    try:
        yield fake
    finally:
        KubernetesService.reset_instance()
