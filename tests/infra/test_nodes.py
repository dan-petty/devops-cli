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
from devops_cli.infra.nodes import Cluster, critical_alerts, node_problems, parse_node
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

    problems = critical_alerts(load_settings())

    assert problems == ["the critical alert KubeNodeNotReady fires"]
    [request] = web.sent
    assert request.url.params["query"] == 'ALERTS{alertstate="firing",severity="critical"}'


def test_a_prometheus_that_does_not_answer_is_a_problem(
    web: WebFake, config: Callable[..., Path]
) -> None:
    config(prometheus={"url": "http://prometheus.example.com:9090"})
    web.serve(lambda request: httpx2.Response(503, text="unavailable"))

    [problem] = critical_alerts(load_settings())

    assert problem.startswith("Prometheus did not answer the query of the critical alerts")
