"""The node steps and the health gate of `devops infra apply` (#5125).

Each step is one `kubectl` command of the kube context of the infra repo, started through the
process runner with a request bound below its process bound:

- **Read**: `kubectl get nodes -o json` and `kubectl get node <node> -o json`.
- **Drain check**: `kubectl drain <node> --dry-run=server`. The API server checks each eviction
  against the PodDisruptionBudgets and changes nothing, so a drain that a budget blocks stops the
  apply before the node is cordoned.
- **Drain**: `kubectl drain <node> --ignore-daemonsets --delete-emptydir-data`, with no `--force`:
  a pod that no controller owns, and a budget, stop the drain. The drain cordons the node first.
  Its bound is `infra.drain_timeout_seconds`, or the longest grace period of a pod that it evicts
  and a margin, when that is longer (`kubectl get pods --field-selector spec.nodeName=<node>`).
- **Uncordon**: `kubectl uncordon <node>`.

The health gate reads every node of the cluster except the nodes of the hosts out of service:
each is Ready and has no memory, disk or PID pressure. When `prometheus.url` is set, no alert with
`severity="critical"` fires. A read that fails is a problem, not an error: the waits read again
until their time ends, so they go on through the short gap in which the API server of a
control-plane node restarts.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from devops_cli.config.defaults import (
    DEFAULT_INFRA_DRAIN_CHECK_TIMEOUT_SECONDS,
    DEFAULT_INFRA_DRAIN_MARGIN_SECONDS,
    DEFAULT_INFRA_KUBECTL_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_INFRA_KUBECTL_TIMEOUT_SECONDS,
    DEFAULT_INFRA_NODE_POLL_SECONDS,
)
from devops_cli.config.settings import Settings
from devops_cli.core import clock
from devops_cli.core.process import run_subprocess
from devops_cli.infra.status import gpu_total, memory_bytes
from devops_cli.lang import MESSAGES
from devops_cli.models.infra import NodeState
from devops_cli.security.sanitizer import mask_secrets

KUBECTL: Final[str] = "kubectl"
GET_NODES_ARGS: Final[tuple[str, ...]] = ("get", "nodes", "-o", "json")
# The query of the health gate: the critical alerts that fire.
CRITICAL_ALERTS_QUERY: Final[str] = 'ALERTS{alertstate="firing",severity="critical"}'
_READY: Final[str] = "Ready"
_TRUE: Final[str] = "True"
_UNKNOWN: Final[str] = "Unknown"
_PRESSURE: Final[tuple[str, ...]] = ("MemoryPressure", "DiskPressure", "PIDPressure")
_DRAIN_OPTIONS: Final[tuple[str, ...]] = ("--ignore-daemonsets", "--delete-emptydir-data")
_SERVER_DRY_RUN: Final[str] = "--dry-run=server"
# A wait ends when its read finds no problem this many times in a row, one poll interval apart.
_CLEAR_READS: Final[int] = 2


def kubectl_argv(context: str, *args: str) -> list[str]:
    """`kubectl` of the kube context `context`, with the request bound, then `args`."""
    return [
        KUBECTL,
        "--context",
        context,
        f"--request-timeout={DEFAULT_INFRA_KUBECTL_REQUEST_TIMEOUT_SECONDS}s",
        *args,
    ]


def get_node_args(node: str) -> tuple[str, ...]:
    """The read of one node as JSON."""
    return ("get", "node", node, "-o", "json")


def drain_args(node: str, timeout_seconds: int, *, check: bool) -> tuple[str, ...]:
    """The drain of `node` with no `--force`; with `check`, the server dry run of the drain."""
    args = ("drain", node, *_DRAIN_OPTIONS, f"--timeout={timeout_seconds}s")
    return (*args, _SERVER_DRY_RUN) if check else args


def pods_args(node: str) -> tuple[str, ...]:
    """The read of the pods of `node` as JSON."""
    return (
        "get",
        "pods",
        "--all-namespaces",
        "--field-selector",
        f"spec.nodeName={node}",
        "-o",
        "json",
    )


# The grace period of a pod that sets none (the Kubernetes default), in seconds.
_DEFAULT_GRACE_SECONDS: Final[int] = 30
_DAEMON_SET: Final[str] = "DaemonSet"
_MIRROR: Final[str] = "kubernetes.io/config.mirror"
_ENDED: Final[frozenset[str]] = frozenset({"Succeeded", "Failed"})


def is_evicted(item: Mapping[str, Any]) -> bool:
    """Whether a drain with `--ignore-daemonsets` evicts the pod: not a pod of a DaemonSet, not a
    mirror pod of the kubelet, and not a pod that ended."""
    metadata = item.get("metadata") or {}
    owners = metadata.get("ownerReferences") or ()
    if any(owner.get("kind") == _DAEMON_SET for owner in owners):
        return False
    if _MIRROR in (metadata.get("annotations") or {}):
        return False
    return (item.get("status") or {}).get("phase") not in _ENDED


def grace_period(item: Mapping[str, Any]) -> int:
    """The grace period of a pod in seconds."""
    value = (item.get("spec") or {}).get("terminationGracePeriodSeconds")
    return int(value) if value is not None else _DEFAULT_GRACE_SECONDS


def uncordon_args(node: str) -> tuple[str, ...]:
    """Let the scheduler put new pods on `node` again."""
    return ("uncordon", node)


def parse_node(item: Mapping[str, Any]) -> NodeState:
    """The state of a node of `kubectl get node -o json`."""
    status = item.get("status") or {}
    info = status.get("nodeInfo") or {}
    allocatable = status.get("allocatable") or {}
    return NodeState(
        name=str((item.get("metadata") or {}).get("name") or ""),
        ready=_condition(item, _READY) or _UNKNOWN,
        cordoned=bool((item.get("spec") or {}).get("unschedulable")),
        kernel=info.get("kernelVersion") or None,
        kubelet=info.get("kubeletVersion") or None,
        memory_capacity_bytes=memory_bytes(status.get("capacity")),
        memory_allocatable_bytes=memory_bytes(allocatable),
        gpu_allocatable=gpu_total(allocatable),
    )


def _condition(item: Mapping[str, Any], kind: str) -> str | None:
    conditions = (item.get("status") or {}).get("conditions") or ()
    return next((str(c.get("status")) for c in conditions if c.get("type") == kind), None)


def node_problems(item: Mapping[str, Any]) -> list[str]:
    """What makes a node unhealthy: it is not Ready, or it has memory, disk or PID pressure."""
    texts = MESSAGES.infra
    state = parse_node(item)
    problems = []
    if state.ready != _TRUE:
        problems.append(texts.apply_node_not_ready.format(node=state.name, ready=state.ready))
    problems += [
        texts.apply_node_pressure.format(node=state.name, condition=kind)
        for kind in _PRESSURE
        if _condition(item, kind) == _TRUE
    ]
    return problems


@dataclass(frozen=True)
class Read:
    """What a `kubectl` read gave: the JSON document, or the problem that stopped the read."""

    document: dict[str, Any] | None
    problem: str | None


@dataclass(frozen=True)
class Cluster:
    """The cluster of an infra repo: its kube context, the nodes of its hosts out of service,
    which the health gate does not read, and the settings of the bounds and of Prometheus."""

    context: str
    settings: Settings
    offline_nodes: frozenset[str] = frozenset()

    def _kubectl(self, args: tuple[str, ...], timeout: float) -> Read:
        result = run_subprocess(kubectl_argv(self.context, *args), quiet=True, timeout=timeout)
        if result.returncode != 0:
            detail = _last_line(result.stderr or result.stdout)
            return Read(
                None,
                MESSAGES.infra.apply_kubectl_failed.format(
                    command=" ".join(args), code=result.returncode, detail=detail
                ),
            )
        try:
            document = json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError:
            return Read({}, None)
        return Read(document if isinstance(document, dict) else {}, None)

    def node(self, name: str) -> Read:
        """The JSON of the node `name`."""
        return self._kubectl(get_node_args(name), DEFAULT_INFRA_KUBECTL_TIMEOUT_SECONDS)

    def health(self) -> list[str]:
        """The problems of the cluster: each node that is not Ready or has pressure, except the
        nodes out of service, and each critical alert that fires."""
        read = self._kubectl(GET_NODES_ARGS, DEFAULT_INFRA_KUBECTL_TIMEOUT_SECONDS)
        if read.problem is not None:
            return [read.problem]
        items = (read.document or {}).get("items") or ()
        problems = [
            problem
            for item in items
            if parse_node(item).name not in self.offline_nodes
            for problem in node_problems(item)
        ]
        return problems + critical_alerts(self.settings)

    def drain_check(self, node: str) -> str | None:
        """The problem that would stop the drain of `node`, from a server dry run that changes
        nothing; none when the drain would finish."""
        timeout = DEFAULT_INFRA_DRAIN_CHECK_TIMEOUT_SECONDS
        args = drain_args(node, timeout, check=True)
        return self._kubectl(args, timeout + DEFAULT_INFRA_DRAIN_MARGIN_SECONDS).problem

    def drain_bound(self, node: str) -> int:
        """The bound of the drain of `node` in seconds: `infra.drain_timeout_seconds`, or the
        longest grace period of a pod that the drain evicts and the margin, when that is longer.
        The drain waits for each pod to stop in its own grace period, so a shorter bound stops a
        drain that goes as it should. A read that fails gives the setting."""
        setting = self.settings.infra.drain_timeout_seconds
        read = self._kubectl(pods_args(node), DEFAULT_INFRA_KUBECTL_TIMEOUT_SECONDS)
        items = (read.document or {}).get("items") or ()
        graces = [grace_period(item) for item in items if is_evicted(item)]
        longest = max(graces, default=0)
        return max(setting, longest + DEFAULT_INFRA_DRAIN_MARGIN_SECONDS if longest else 0)

    def drain(self, node: str) -> str | None:
        """Cordon and drain `node` within its drain bound; the problem when the drain does not
        finish."""
        timeout = self.drain_bound(node)
        args = drain_args(node, timeout, check=False)
        return self._kubectl(args, timeout + DEFAULT_INFRA_DRAIN_MARGIN_SECONDS).problem

    def uncordon(self, node: str) -> list[str]:
        """Uncordon `node`, and try again through a gap of the API server until the wait for a
        node ends; the last problem when it does not finish."""

        def attempt() -> list[str]:
            read = self._kubectl(uncordon_args(node), DEFAULT_INFRA_KUBECTL_TIMEOUT_SECONDS)
            return [read.problem] if read.problem else []

        return self._wait(attempt, reads=1, first_wait=False)

    def wait_ready(self, node: str, gpus: int | None) -> list[str]:
        """Wait until `node` is Ready, has no pressure and has the GPUs `gpus` that it had before,
        on two reads one poll interval apart; the problems of the last read when the time ends."""

        def check() -> list[str]:
            read = self.node(node)
            if read.problem is not None:
                return [read.problem]
            item = read.document or {}
            problems = node_problems(item)
            now = parse_node(item).gpu_allocatable
            if now != gpus:
                problems.append(
                    MESSAGES.infra.apply_gpu_differs.format(node=node, now=now, before=gpus)
                )
            return problems

        return self._wait(check)

    def wait_healthy(self) -> list[str]:
        """Wait until the health gate finds no problem on two reads one poll interval apart; the
        problems of the last read when the time ends."""
        return self._wait(self.health)

    def _wait(
        self, read: Callable[[], list[str]], *, reads: int = _CLEAR_READS, first_wait: bool = True
    ) -> list[str]:
        """Run `read` once each poll interval until it finds no problem `reads` times in a row, or
        `infra.node_ready_timeout_seconds` ends."""
        deadline = clock.monotonic() + self.settings.infra.node_ready_timeout_seconds
        clear = 0
        wait = first_wait
        while True:
            if wait:
                clock.sleep(DEFAULT_INFRA_NODE_POLL_SECONDS)
            wait = True
            problems = read()
            clear = 0 if problems else clear + 1
            if clear >= reads:
                return []
            if problems and clock.monotonic() >= deadline:
                return problems


def critical_alerts(settings: Settings) -> list[str]:
    """Each critical alert that fires, when `prometheus.url` is set. A query that gets no answer is
    a problem: the gate does not pass on a read that it could not make."""
    if not settings.prometheus.url:
        return []
    import httpx2

    from devops_cli.http.egress import configured_level
    from devops_cli.http.urls import service_base_url
    from devops_cli.prometheus.client import PrometheusClient

    texts = MESSAGES.infra
    try:
        base = service_base_url(settings.prometheus.url, "prometheus.url")
        with PrometheusClient(base, configured_level(settings.ai)) as client:
            answer = client.query(CRITICAL_ALERTS_QUERY)
    except (httpx2.HTTPError, ValueError) as exc:
        return [texts.apply_alerts_unread.format(detail=mask_secrets(str(exc)))]
    series = (answer.get("data") or {}).get("result") or ()
    return [
        texts.apply_alert_firing.format(name=(item.get("metric") or {}).get("alertname", "?"))
        for item in series
    ]


def _last_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return mask_secrets(lines[-1]) if lines else ""


__all__ = [
    "CRITICAL_ALERTS_QUERY",
    "GET_NODES_ARGS",
    "KUBECTL",
    "Cluster",
    "Read",
    "critical_alerts",
    "drain_args",
    "get_node_args",
    "grace_period",
    "is_evicted",
    "kubectl_argv",
    "node_problems",
    "parse_node",
    "pods_args",
    "uncordon_args",
]
