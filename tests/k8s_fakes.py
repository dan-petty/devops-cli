"""Kubernetes API objects and a fake CoreV1 client for tests that must not reach a cluster.

The objects are the SDK's own models, so code under test reads them exactly as it reads a
real API response. Names are generic, as AGENTS.md requires of fixtures.
"""

from __future__ import annotations

import datetime
from typing import Any

from kubernetes import client  # type: ignore[import-untyped]

NOW = datetime.datetime(2026, 10, 1, 12, 0, tzinfo=datetime.UTC)


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
    return client.V1Pod(
        metadata=client.V1ObjectMeta(
            name=name,
            namespace=namespace,
            uid=f"uid-{namespace}-{name}",
            annotations=annotations,
            creation_timestamp=NOW,
            deletion_timestamp=NOW if deleted else None,
        ),
        spec=client.V1PodSpec(
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


def healthy_pod(name: str, namespace: str = "default") -> Any:
    """A running pod whose one container is ready."""
    return pod(name, namespace, statuses=[ready_app()], conditions={"Ready": "True"})


def crashlooping_pod(name: str, namespace: str = "default") -> Any:
    """A pod in phase Running whose container waits in CrashLoopBackOff."""
    return pod(
        name,
        namespace,
        statuses=[
            status(
                "app",
                waiting("CrashLoopBackOff"),
                restarts=86,
                last=terminated(1, "Error"),
            )
        ],
        conditions={"Ready": "False"},
    )


def node(name: str, ready: str = "True") -> Any:
    """A node whose Ready condition holds the given status."""
    return client.V1Node(
        metadata=client.V1ObjectMeta(name=name),
        status=client.V1NodeStatus(conditions=[client.V1NodeCondition(type="Ready", status=ready)]),
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
) -> Any:
    """A core/v1 event. One written through events.k8s.io/v1 has only event_time and series."""
    return client.CoreV1Event(
        metadata=client.V1ObjectMeta(name=f"evt-{reason}", creation_timestamp=created),
        involved_object=client.V1ObjectReference(kind="Pod", name="web-0"),
        reason=reason,
        message=message or f"{reason} happened",
        type=kind,
        count=count,
        last_timestamp=last,
        event_time=event_time,
        first_timestamp=first,
        series=client.CoreV1EventSeries(count=series_count) if series_count else None,
    )


class FakeCoreV1:
    """A CoreV1Api stand-in that records every call and answers from fixed data.

    A list call answers with the given items, or raises the given exception instead.
    """

    def __init__(
        self,
        pods: list[Any] | Exception | None = None,
        nodes: list[Any] | Exception | None = None,
        events: list[Any] | Exception | None = None,
    ) -> None:
        self.answers = {
            "list_pod_for_all_namespaces": pods if pods is not None else [],
            "list_node": nodes if nodes is not None else [],
            "list_namespaced_event": events if events is not None else [],
        }
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def _answer(self, method: str, kwargs: dict[str, Any]) -> Any:
        self.calls.append((method, kwargs))
        answer = self.answers[method]
        if isinstance(answer, Exception):
            raise answer
        return _Items(answer)

    def list_pod_for_all_namespaces(self, **kwargs: Any) -> Any:
        return self._answer("list_pod_for_all_namespaces", kwargs)

    def list_node(self, **kwargs: Any) -> Any:
        return self._answer("list_node", kwargs)

    def list_namespaced_event(self, namespace: str, **kwargs: Any) -> Any:
        return self._answer("list_namespaced_event", {"namespace": namespace, **kwargs})


class _Items:
    """A list response: only `items` is read."""

    def __init__(self, items: list[Any]) -> None:
        self.items = items
