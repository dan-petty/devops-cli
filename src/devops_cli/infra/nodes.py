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
- **Down during the apply**: the workloads of the pods that the drain evicts and that mount a
  claim whose PersistentVolume only the node can mount (`kubectl get pvc` and `kubectl get pv`,
  node affinity on `kubernetes.io/hostname`). They cannot start on another node, so they are down
  until the node is uncordoned. The apply names them; it does not stop for them.
- **Uncordon**: `kubectl uncordon <node>`.

The health gate reads every node of the cluster except the nodes of the hosts out of service:
each is Ready and has no memory, disk or PID pressure. When `prometheus.url` is set, no alert with
`severity="critical"` fires, except an alert whose node is a node out of service: its label `node`,
else its label `instance`. The gate leaves out such an alert, as it leaves out the node itself, and
gives one line for it (#5455). After a host, the apply waits for the nodes before the uncordon and
for the alerts after it, because Prometheus can run on the node of the host. A read that fails is a
problem, not an error: the waits read again until their time ends, so they go on through the short
gap in which the API server of a control-plane node restarts.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
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
# The labels of an alert that name its node, in order: node-exporter names its node in `instance`.
_ALERT_NODE_LABELS: Final[tuple[str, ...]] = ("node", "instance")
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


def drain_args(node: str, timeout_seconds: int, *, server_dry_run: bool) -> tuple[str, ...]:
    """The drain of `node` with no `--force`; with `server_dry_run`, the server dry run of the drain."""
    args = ("drain", node, *_DRAIN_OPTIONS, f"--timeout={timeout_seconds}s")
    return (*args, _SERVER_DRY_RUN) if server_dry_run else args


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


CLAIMS_ARGS: Final[tuple[str, ...]] = ("get", "pvc", "--all-namespaces", "-o", "json")
VOLUMES_ARGS: Final[tuple[str, ...]] = ("get", "pv", "-o", "json")
_HOSTNAME_LABEL: Final[str] = "kubernetes.io/hostname"
_IN: Final[str] = "In"
_POD_TEMPLATE_HASH: Final[str] = "pod-template-hash"
_REPLICA_SET: Final[str] = "ReplicaSet"
_DEPLOYMENT: Final[str] = "Deployment"


def is_pinned(volume: Mapping[str, Any], node: str) -> bool:
    """Whether only `node` can mount the PersistentVolume `volume`: each term of its required
    node affinity names `node` alone by its host name label, as a local volume does."""
    affinity = ((volume.get("spec") or {}).get("nodeAffinity") or {}).get("required") or {}
    terms = affinity.get("nodeSelectorTerms") or ()
    return bool(terms) and all(
        any(
            expression.get("key") == _HOSTNAME_LABEL
            and expression.get("operator") == _IN
            and list(expression.get("values") or ()) == [node]
            for expression in term.get("matchExpressions") or ()
        )
        for term in terms
    )


def workload(pod: Mapping[str, Any]) -> str:
    """The workload of a pod as `<namespace>/<name> (<kind>)`: the Deployment of a pod of a
    ReplicaSet, else the owner of the pod, else the pod."""
    metadata = pod.get("metadata") or {}
    namespace = metadata.get("namespace") or ""
    owners = metadata.get("ownerReferences") or ()
    if not owners:
        return f"{namespace}/{metadata.get('name')} (Pod)"
    kind, name = str(owners[0].get("kind")), str(owners[0].get("name"))
    template = (metadata.get("labels") or {}).get(_POD_TEMPLATE_HASH)
    if kind == _REPLICA_SET and template and name.endswith(f"-{template}"):
        kind, name = _DEPLOYMENT, name.removesuffix(f"-{template}")
    return f"{namespace}/{name} ({kind})"


def pinned_workloads(
    pods: Iterable[Mapping[str, Any]],
    claims: Iterable[Mapping[str, Any]],
    volumes: Iterable[Mapping[str, Any]],
    node: str,
) -> tuple[str, ...]:
    """The workloads of the `pods` that a drain evicts and that mount a claim whose volume only
    `node` can mount, sorted."""
    pinned = {
        (volume.get("metadata") or {}).get("name") for volume in volumes if is_pinned(volume, node)
    }
    bound = {
        (
            (claim.get("metadata") or {}).get("namespace"),
            (claim.get("metadata") or {}).get("name"),
        ): (claim.get("spec") or {}).get("volumeName")
        for claim in claims
    }
    found = set()
    for pod in pods:
        if not is_evicted(pod):
            continue
        namespace = (pod.get("metadata") or {}).get("namespace")
        for mount in (pod.get("spec") or {}).get("volumes") or ():
            claim = (mount.get("persistentVolumeClaim") or {}).get("claimName")
            if claim and bound.get((namespace, claim)) in pinned:
                found.add(workload(pod))
    return tuple(sorted(found))


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
class Alerts:
    """What the query of the critical alerts gave: the problems that stop the gate, and one line
    for each alert of a node out of service that the gate left out."""

    problems: list[str]
    left_out: list[str]


def alert_node(labels: Mapping[str, Any]) -> str | None:
    """The node that an alert names: its label `node`, else its label `instance`; none when it has
    neither."""
    return next((str(labels[key]) for key in _ALERT_NODE_LABELS if labels.get(key)), None)


@dataclass(frozen=True)
class Cluster:
    """The cluster of an infra repo: its kube context, the nodes of its hosts out of service,
    which the health gate does not read, and the settings of the bounds and of Prometheus. The
    alert reads give each line of an alert that they left out to `on_left_out`."""

    context: str
    settings: Settings
    offline_nodes: frozenset[str] = frozenset()
    on_left_out: Callable[[str], None] | None = None

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
        """The problems of the cluster: each node that is not Ready or has pressure, and each
        critical alert that fires, except those of the nodes out of service."""
        problems = self.node_health()
        return problems if problems else self.alert_health()

    def alert_health(self) -> list[str]:
        """Each critical alert that fires, except an alert of a node out of service, or the problem
        of a query that gets no answer. Each alert left out goes to `on_left_out`."""
        alerts = critical_alerts(self.settings, self.offline_nodes)
        if self.on_left_out is not None:
            for line in alerts.left_out:
                self.on_left_out(line)
        return alerts.problems

    def node_health(self) -> list[str]:
        """Each node that is not Ready or has pressure, except the nodes out of service."""
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
        return problems

    def drain_check(self, node: str) -> str | None:
        """The problem that would stop the drain of `node`, from a server dry run that changes
        nothing; none when the drain would finish."""
        timeout = DEFAULT_INFRA_DRAIN_CHECK_TIMEOUT_SECONDS
        args = drain_args(node, timeout, server_dry_run=True)
        return self._kubectl(args, timeout + DEFAULT_INFRA_DRAIN_MARGIN_SECONDS).problem

    def pods(self, node: str) -> list[dict[str, Any]]:
        """The pods of `node`; none when the read fails, and the drain says why."""
        read = self._kubectl(pods_args(node), DEFAULT_INFRA_KUBECTL_TIMEOUT_SECONDS)
        return list((read.document or {}).get("items") or ())

    def down_during_apply(self, node: str, pods: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
        """The workloads of the pods of `node` that the drain evicts and that mount a volume that
        only `node` can mount: they cannot start on another node, so they are down until the node
        is uncordoned. A read that fails gives one line that says so."""
        claims = self._kubectl(CLAIMS_ARGS, DEFAULT_INFRA_KUBECTL_TIMEOUT_SECONDS)
        volumes = self._kubectl(VOLUMES_ARGS, DEFAULT_INFRA_KUBECTL_TIMEOUT_SECONDS)
        problem = claims.problem or volumes.problem
        if problem is not None:
            return (MESSAGES.infra.apply_pinned_unread.format(problem=problem),)
        return pinned_workloads(
            pods,
            (claims.document or {}).get("items") or (),
            (volumes.document or {}).get("items") or (),
            node,
        )

    def drain_bound(self, pods: Iterable[Mapping[str, Any]]) -> int:
        """The bound of a drain in seconds: `infra.drain_timeout_seconds`, or the longest grace
        period of a pod in `pods` that the drain evicts and the margin, when that is longer. The
        drain waits for each pod to stop in its own grace period, so a shorter bound stops a drain
        that goes as it should."""
        setting = self.settings.infra.drain_timeout_seconds
        longest = max((grace_period(item) for item in pods if is_evicted(item)), default=0)
        return max(setting, longest + DEFAULT_INFRA_DRAIN_MARGIN_SECONDS if longest else 0)

    def drain(self, node: str, bound: int) -> str | None:
        """Cordon and drain `node` within `bound` seconds; the problem when the drain does not
        finish."""
        args = drain_args(node, bound, server_dry_run=False)
        return self._kubectl(args, bound + DEFAULT_INFRA_DRAIN_MARGIN_SECONDS).problem

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

    def wait_nodes_healthy(self) -> list[str]:
        """Wait until every node in service is Ready with no pressure on two reads one poll
        interval apart; the problems of the last read when the time ends."""
        return self._wait(self.node_health)

    def wait_alerts_clear(self) -> list[str]:
        """Wait until no critical alert fires on two reads one poll interval apart, when
        `prometheus.url` is set; the problems of the last read when the time ends. An alert of a
        node out of service does not count. A Prometheus that does not answer yet, such as one
        whose volume only the node of the host mounts, is read again."""
        if not self.settings.prometheus.url:
            return []
        return self._wait(self.alert_health)

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


def critical_alerts(settings: Settings, offline_nodes: frozenset[str] = frozenset()) -> Alerts:
    """Each critical alert that fires, when `prometheus.url` is set. An alert whose node is in
    `offline_nodes` is left out with one line that says why; every other alert is a problem. A
    query that gets no answer is a problem: the gate does not pass on a read that it could not
    make."""
    if not settings.prometheus.url:
        return Alerts([], [])
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
        return Alerts([texts.apply_alerts_unread.format(detail=mask_secrets(str(exc)))], [])
    alerts = Alerts([], [])
    for item in (answer.get("data") or {}).get("result") or ():
        labels = item.get("metric") or {}
        name = labels.get("alertname", "?")
        node = alert_node(labels)
        if node is not None and node in offline_nodes:
            alerts.left_out.append(texts.apply_alert_left_out.format(name=name, node=node))
        else:
            alerts.problems.append(texts.apply_alert_firing.format(name=name))
    return alerts


def _last_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return mask_secrets(lines[-1]) if lines else ""


__all__ = [
    "CLAIMS_ARGS",
    "CRITICAL_ALERTS_QUERY",
    "GET_NODES_ARGS",
    "KUBECTL",
    "VOLUMES_ARGS",
    "Alerts",
    "Cluster",
    "Read",
    "alert_node",
    "critical_alerts",
    "drain_args",
    "get_node_args",
    "grace_period",
    "is_evicted",
    "is_pinned",
    "kubectl_argv",
    "node_problems",
    "parse_node",
    "pinned_workloads",
    "pods_args",
    "uncordon_args",
    "workload",
]
