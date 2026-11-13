"""The node reads, the health gate and the waits of `devops infra apply` (#5125).

A fake `kubectl` answers from a set of nodes (`FakeCluster`), and the `clock` fixture makes each
wait return at once and records it.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx2
import pytest

from devops_cli.config.settings import load_settings
from devops_cli.infra.nodes import (
    Cluster,
    critical_alerts,
    grace_period,
    is_evicted,
    is_pinned,
    node_problems,
    parse_node,
)
from devops_cli.models.infra import NodeState
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.http import WebFake
from tests.support.fakes.process import ProcessFake
from tests.support.infra import KUBE_CONTEXT, FakeCluster, FakeNode

_GIB = 1024**3


def test_a_node_reads_with_its_memory_and_gpus() -> None:
    node = FakeNode("node-1", cordoned=True, gpus=2, capacity_gib=64, allocatable_gib=58)

    assert parse_node(node.item()) == NodeState(
        name="node-1",
        ready="True",
        cordoned=True,
        kernel="6.12.0",
        kubelet="v1.37.2+k3s1",
        memory_capacity_bytes=64 * _GIB,
        memory_allocatable_bytes=58 * _GIB,
        gpu_allocatable=2,
    )


def test_a_node_that_is_not_ready_or_has_pressure_is_a_problem() -> None:
    node = FakeNode("node-2", ready="Unknown", pressure=("DiskPressure", "PIDPressure"))

    assert node_problems(node.item()) == [
        "node-2 is not Ready (Unknown)",
        "node-2 has DiskPressure",
        "node-2 has PIDPressure",
    ]


@pytest.fixture
def cluster(process_fake: ProcessFake, config: Callable[..., Path]) -> FakeCluster:
    config(infra={"node_ready_timeout_seconds": 60})
    nodes = FakeCluster.of(FakeNode("node-1"), FakeNode("node-2"))
    nodes.install(process_fake)
    return nodes


def test_the_health_gate_does_not_read_a_node_out_of_service(cluster: FakeCluster) -> None:
    cluster.nodes["node-2"].ready = "False"

    health = Cluster(KUBE_CONTEXT, load_settings(), frozenset({"node-2"})).health()

    assert health == []


def test_the_wait_for_ready_goes_on_through_a_gap_of_the_api_server(
    cluster: FakeCluster, clock: ClockFake
) -> None:
    cluster.down = 2

    problems = Cluster(KUBE_CONTEXT, load_settings()).wait_ready("node-1", 1)

    assert problems == []
    assert clock.waits == [10.0] * 4


def test_the_wait_for_ready_ends_with_the_last_problem_at_its_bound(
    cluster: FakeCluster, clock: ClockFake
) -> None:
    cluster.nodes["node-1"].gpus = 0

    problems = Cluster(KUBE_CONTEXT, load_settings()).wait_ready("node-1", 1)

    assert problems == ["node-1 has 0 GPUs, not the 1 that it had before the run"]
    assert sum(clock.waits) == 60.0


_ALERTS = {
    "status": "success",
    "data": {
        "resultType": "vector",
        "result": [{"metric": {"alertname": "KubeNodeNotReady", "severity": "critical"}}],
    },
}


def test_a_critical_alert_that_fires_is_a_problem(
    web: WebFake, config: Callable[..., Path]
) -> None:
    config(prometheus={"url": "http://prometheus.example.com:9090"})
    web.serve(lambda request: httpx2.Response(200, json=_ALERTS))

    alerts = critical_alerts(load_settings())

    assert alerts.problems == ["the critical alert KubeNodeNotReady fires"]
    [request] = web.sent
    assert request.url.params["query"] == 'ALERTS{alertstate="firing",severity="critical"}'


def test_a_prometheus_that_does_not_answer_is_a_problem(
    web: WebFake, config: Callable[..., Path], clock: ClockFake
) -> None:
    """A Prometheus that stays down through each attempt is a problem with the mapped line, so
    the gate does not pass on a read that it could not make (#5532)."""
    config(prometheus={"url": "http://prometheus.example.com:9090"})
    web.serve(lambda request: httpx2.Response(503, text="unavailable"))

    [problem] = critical_alerts(load_settings()).problems

    assert problem.startswith(
        "Prometheus did not answer the query of the critical alerts: Prometheus failed after"
        " 4 attempts in "
    )
    assert (": HTTP 503 Service Unavailable" in problem, len(web.sent)) == (True, 4)


def test_a_prometheus_that_answers_after_a_503_is_read_in_one_query(
    web: WebFake, config: Callable[..., Path], clock: ClockFake
) -> None:
    """A restart of some seconds does not stop the gate: the query reads again by itself."""
    config(prometheus={"url": "http://prometheus.example.com:9090"})
    answers = iter([httpx2.Response(503, text="unavailable")])
    web.serve(lambda request: next(answers, httpx2.Response(200, json=_ALERTS)))

    alerts = critical_alerts(load_settings())

    assert (alerts.problems, len(web.sent)) == (["the critical alert KubeNodeNotReady fires"], 2)


def _firing(*labels: dict[str, str]) -> dict[str, object]:
    """The answer of the alert query: one critical alert that fires for each set of `labels`."""
    result = [{"metric": {"severity": "critical", **each}} for each in labels]
    return {"status": "success", "data": {"resultType": "vector", "result": result}}


_LEFT_OUT = (
    "The health gate left out the critical alert NodeNotReady: its node node-5 is out of service"
)


@pytest.mark.parametrize(
    ("labels", "problems", "left_out"),
    [
        pytest.param(
            {"alertname": "NodeNotReady", "node": "node-5"}, [], [_LEFT_OUT], id="offline-node"
        ),
        pytest.param(
            {"alertname": "NodeNotReady", "instance": "node-5"},
            [],
            [_LEFT_OUT],
            id="offline-instance",
        ),
        pytest.param(
            {"alertname": "NodeNotReady", "node": "node-2"},
            ["the critical alert NodeNotReady fires"],
            [],
            id="node-in-service",
        ),
        pytest.param(
            {"alertname": "NodeNotReady", "node": "node-2", "instance": "node-5"},
            ["the critical alert NodeNotReady fires"],
            [],
            id="node-label-first",
        ),
        pytest.param(
            {"alertname": "ClusterMetricsMissing"},
            ["the critical alert ClusterMetricsMissing fires"],
            [],
            id="no-node-label",
        ),
    ],
)
def test_the_alert_gate_leaves_out_only_an_alert_of_a_node_out_of_service(
    web: WebFake,
    config: Callable[..., Path],
    labels: dict[str, str],
    problems: list[str],
    left_out: list[str],
) -> None:
    """A parked node in the offline group keeps its NodeNotReady alert; the gate does not stop for
    it, as it does not read the node itself (#5455)."""
    config(prometheus={"url": "http://prometheus.example.com:9090"})
    web.serve(lambda request: httpx2.Response(200, json=_firing(labels)))

    alerts = critical_alerts(load_settings(), frozenset({"node-5"}))

    assert (alerts.problems, alerts.left_out) == (problems, left_out)


def test_the_health_gate_and_the_alert_wait_name_each_alert_that_they_leave_out(
    cluster: FakeCluster, web: WebFake, config: Callable[..., Path], clock: ClockFake
) -> None:
    """The alert of the node out of service does not stop the gate and does not hold the wait
    after a host until its bound; each read gives one line for the alert that it left out."""
    config(prometheus={"url": "http://prometheus.example.com:9090"})
    answer = _firing({"alertname": "NodeNotReady", "node": "node-5"})
    web.serve(lambda request: httpx2.Response(200, json=answer))
    lines: list[str] = []
    nodes = Cluster(KUBE_CONTEXT, load_settings(), frozenset({"node-5"}), lines.append)

    assert (nodes.health(), nodes.wait_alerts_clear()) == ([], [])
    assert lines == [_LEFT_OUT] * 3
    assert clock.waits == [10.0] * 2


def test_the_health_gate_stops_for_an_alert_of_a_node_in_service_next_to_one_it_leaves_out(
    cluster: FakeCluster, web: WebFake, config: Callable[..., Path]
) -> None:
    config(prometheus={"url": "http://prometheus.example.com:9090"})
    answer = _firing(
        {"alertname": "NodeNotReady", "node": "node-5"},
        {"alertname": "NodeNotReady", "node": "node-2"},
    )
    web.serve(lambda request: httpx2.Response(200, json=answer))
    lines: list[str] = []

    health = Cluster(KUBE_CONTEXT, load_settings(), frozenset({"node-5"}), lines.append).health()

    assert (health, lines) == (["the critical alert NodeNotReady fires"], [_LEFT_OUT])


@pytest.mark.parametrize(
    ("item", "evicted", "grace"),
    [
        pytest.param(
            {"metadata": {"ownerReferences": [{"kind": "ReplicaSet"}]}, "spec": {}},
            True,
            30,
            id="replica-set-default-grace",
        ),
        pytest.param(
            {"metadata": {"ownerReferences": [{"kind": "DaemonSet"}]}, "spec": {}},
            False,
            30,
            id="daemon-set",
        ),
        pytest.param(
            {"metadata": {"annotations": {"kubernetes.io/config.mirror": "x"}}, "spec": {}},
            False,
            30,
            id="mirror-pod",
        ),
        pytest.param(
            {"metadata": {}, "spec": {"terminationGracePeriodSeconds": 1800}},
            True,
            1800,
            id="long-grace",
        ),
        pytest.param(
            {"metadata": {}, "spec": {}, "status": {"phase": "Succeeded"}},
            False,
            30,
            id="ended",
        ),
    ],
)
def test_the_drain_bound_reads_the_pods_that_the_drain_evicts(
    item: dict[str, object], evicted: bool, grace: int
) -> None:
    assert (is_evicted(item), grace_period(item)) == (evicted, grace)


def test_the_drain_bound_is_the_setting_when_no_pod_needs_more(cluster: FakeCluster) -> None:
    nodes = Cluster(KUBE_CONTEXT, load_settings())
    cluster.graces["node-1"] = 90
    cluster.graces["node-2"] = 660

    assert (nodes.drain_bound(nodes.pods("node-1")), nodes.drain_bound(nodes.pods("node-2"))) == (
        180,
        720,
    )


def test_a_volume_that_names_another_node_too_is_not_pinned() -> None:
    term = {
        "matchExpressions": [
            {"key": "kubernetes.io/hostname", "operator": "In", "values": ["node-1", "node-2"]}
        ]
    }
    volume = {"spec": {"nodeAffinity": {"required": {"nodeSelectorTerms": [term]}}}}

    assert (is_pinned(volume, "node-1"), is_pinned({"spec": {}}, "node-1")) == (False, False)


_NO_ALERT = {"status": "success", "data": {"resultType": "vector", "result": []}}


def test_the_alert_wait_reads_again_while_prometheus_does_not_answer(
    web: WebFake, config: Callable[..., Path], clock: ClockFake
) -> None:
    """Prometheus can mount a volume that only the node of the host mounts, so it answers only
    some time after the uncordon."""
    config(
        prometheus={"url": "http://prometheus.example.com:9090"},
        infra={"node_ready_timeout_seconds": 120},
    )
    # Two queries get no answer, each after its 4 attempts; the gate's own wait loop reads again.
    answers = iter([httpx2.Response(503, text="unavailable")] * 8)

    def answer(request: httpx2.Request) -> httpx2.Response:
        return next(answers, httpx2.Response(200, json=_NO_ALERT))

    web.serve(answer)

    problems = Cluster(KUBE_CONTEXT, load_settings()).wait_alerts_clear()

    gate_waits = [wait for wait in clock.waits if wait == 10.0]
    assert problems == []
    assert (len(web.sent), gate_waits, len(clock.waits)) == (10, [10.0] * 4, 10)


def test_the_node_gate_does_not_read_the_alerts(
    cluster: FakeCluster, web: WebFake, config: Callable[..., Path]
) -> None:
    config(prometheus={"url": "http://prometheus.example.com:9090"})

    assert Cluster(KUBE_CONTEXT, load_settings()).node_health() == []
    assert web.sent == []
