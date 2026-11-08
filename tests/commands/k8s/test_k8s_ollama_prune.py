"""Tests for devops k8s ollama prune (#3654)."""

from __future__ import annotations

from typing import Any

from tests.support.fakes.kubernetes import FakeCluster, pod
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

_LIST_OUTPUT = (
    "NAME              ID            SIZE      MODIFIED\n"
    "qwen3.8:27b       12345678      16 GB     2 days ago\n"
    "llama3.1:70b      87654321      40 GB     3 days ago\n"
)


def _ollama_call(verb: str) -> Any:
    """A matcher for the `ollama <verb>` that the prune command runs in a pod."""

    def matches(call: ProcessCall) -> bool:
        return call.argv[:1] == ("kubectl",) and "ollama" in call.argv and verb in call.argv

    return matches


def _ollama_calls(process_fake: ProcessFake, verb: str) -> list[tuple[str, ...]]:
    """The argv of each `kubectl exec ... ollama <verb>` that the command started."""
    return [call.argv for call in process_fake.calls if _ollama_call(verb)(call)]


def _ollama_pod(
    name: str, node: str, tier: str, vram: str = "48gib", gpu_instance: str | None = None
) -> Any:
    labels = {
        "llm.devops.io/provider": "ollama",
        "llm.devops.io/vram-gib": vram,
        "llm.devops.io/speed-tier": tier,
    }
    if gpu_instance is not None:
        labels["llm.devops.io/gpu-instance"] = gpu_instance
    p = pod(name=name, namespace="llm", node_name=node)
    p.metadata.labels = labels
    return p


def test_dry_run_makes_no_cluster_call(cli: Any, cluster: FakeCluster) -> None:
    """Criterion: --dry-run prints kubectl exec and ollama rm for each target and calls no cluster API."""
    result = cli(["k8s", "ollama", "prune", "--dry-run"])

    assert result.exit_code == 0
    assert len(cluster.core.calls) == 0
    assert "kubectl exec" in result.stdout
    assert "ollama rm" in result.stdout
    assert "ollama-48gib-fast" in result.stdout
    assert "ollama-64gib-standard" in result.stdout
    assert "ollama-24gib-embed-gpu0" in result.stdout
    assert "ollama-24gib-embed-gpu1" in result.stdout


def test_a_failed_ollama_list_stops_the_node(
    cli: Any, cluster: FakeCluster, process_fake: ProcessFake
) -> None:
    """Criterion: a node whose ollama list fails removes no model, is named, and exits non-zero."""
    cluster.core.answers["list_namespaced_pod"] = [
        _ollama_pod("ollama-48gib-fast-abcde", "node-control-plane", "fast")
    ]
    process_fake.answer(
        _ollama_call("list"), ProcessAnswer(returncode=1, stderr="connection refused")
    )

    result = cli(["k8s", "ollama", "prune"])

    assert result.exit_code != 0
    assert "node-control-plane" in result.stdout or "node-control-plane" in result.stderr
    assert _ollama_calls(process_fake, "rm") == []


def test_ollama_prune_plan(cli: Any, cluster: FakeCluster, process_fake: ProcessFake) -> None:
    """Criterion: --plan prints each node and the models it would remove without calling ollama rm."""
    cluster.core.answers["list_namespaced_pod"] = [
        _ollama_pod("ollama-48gib-fast-abcde", "node-control-plane", "fast")
    ]

    process_fake.answer(_ollama_call("list"), ProcessAnswer(stdout=_LIST_OUTPUT))

    result = cli(["k8s", "ollama", "prune", "--plan"])

    assert result.exit_code == 0
    assert "node-control-plane" in result.stdout
    assert "llama3.1:70b" in result.stdout
    assert _ollama_calls(process_fake, "rm") == []


def test_ollama_prune_executes_rm(
    cli: Any, cluster: FakeCluster, process_fake: ProcessFake
) -> None:
    """Criterion: prune removes only the models not in keep set for each node."""
    cluster.core.answers["list_namespaced_pod"] = [
        _ollama_pod("ollama-48gib-fast-abcde", "node-control-plane", "fast")
    ]

    process_fake.answer(_ollama_call("list"), ProcessAnswer(stdout=_LIST_OUTPUT))

    result = cli(["k8s", "ollama", "prune"])

    assert result.exit_code == 0
    assert "node-control-plane" in result.stdout
    assert len(_ollama_calls(process_fake, "rm")) == 1
    assert "llama3.1:70b" in _ollama_calls(process_fake, "rm")[0]
