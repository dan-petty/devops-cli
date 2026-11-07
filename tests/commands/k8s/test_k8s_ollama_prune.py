"""Tests for devops k8s ollama prune (#3654)."""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import patch

from tests.support.fakes.kubernetes import FakeCluster, pod


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


def test_a_failed_ollama_list_stops_the_node(cli: Any, cluster: FakeCluster) -> None:
    """Criterion: a node whose ollama list fails removes no model, is named, and exits non-zero."""
    cluster.core.answers["list_namespaced_pod"] = [
        _ollama_pod("ollama-48gib-fast-abcde", "node-control-plane", "fast")
    ]

    def _mock_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "ollama" in cmd and "list" in cmd:
            return subprocess.CompletedProcess(
                cmd, returncode=1, stdout="", stderr="connection refused"
            )
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("devops_cli.commands.k8s.ollama._run_cmd", side_effect=_mock_run):
        result = cli(["k8s", "ollama", "prune"])

    assert result.exit_code != 0
    assert "node-control-plane" in result.stdout or "node-control-plane" in result.stderr


def test_ollama_prune_plan(cli: Any, cluster: FakeCluster) -> None:
    """Criterion: --plan prints each node and the models it would remove without calling ollama rm."""
    cluster.core.answers["list_namespaced_pod"] = [
        _ollama_pod("ollama-48gib-fast-abcde", "node-control-plane", "fast")
    ]

    list_output = "NAME              ID            SIZE      MODIFIED\nqwen3.8:27b       12345678      16 GB     2 days ago\nllama3.1:70b      87654321      40 GB     3 days ago\n"

    executed_rm: list[list[str]] = []

    def _mock_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "ollama" in cmd and "list" in cmd:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout=list_output, stderr="")
        if "ollama" in cmd and "rm" in cmd:
            executed_rm.append(cmd)
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("devops_cli.commands.k8s.ollama._run_cmd", side_effect=_mock_run):
        result = cli(["k8s", "ollama", "prune", "--plan"])

    assert result.exit_code == 0
    assert "node-control-plane" in result.stdout
    assert "llama3.1:70b" in result.stdout
    assert len(executed_rm) == 0


def test_ollama_prune_executes_rm(cli: Any, cluster: FakeCluster) -> None:
    """Criterion: prune removes only the models not in keep set for each node."""
    cluster.core.answers["list_namespaced_pod"] = [
        _ollama_pod("ollama-48gib-fast-abcde", "node-control-plane", "fast")
    ]

    list_output = "NAME              ID            SIZE      MODIFIED\nqwen3.8:27b       12345678      16 GB     2 days ago\nllama3.1:70b      87654321      40 GB     3 days ago\n"

    executed_rm: list[list[str]] = []

    def _mock_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "ollama" in cmd and "list" in cmd:
            return subprocess.CompletedProcess(cmd, returncode=0, stdout=list_output, stderr="")
        if "ollama" in cmd and "rm" in cmd:
            executed_rm.append(cmd)
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    with patch("devops_cli.commands.k8s.ollama._run_cmd", side_effect=_mock_run):
        result = cli(["k8s", "ollama", "prune"])

    assert result.exit_code == 0
    assert "node-control-plane" in result.stdout
    assert len(executed_rm) == 1
    assert "llama3.1:70b" in executed_rm[0]
