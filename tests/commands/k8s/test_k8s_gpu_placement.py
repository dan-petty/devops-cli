"""deploy-stack warns about GPU nodes that no Ollama tier accepts (#1367).

The accepted labels come from the required `matchExpressions` of each Ollama DaemonSet in
`k8s/llm/profiles/ollama-profiles.yaml`, so the tests read that file, not a copy of its values.
Each case answers `kubectl get nodes -o json` through the process edge and runs the command.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.config.constants import (
    CONST_K8S_GPU_ARCHITECTURE_LABEL,
    CONST_K8S_GPU_PRESENT_LABEL,
    CONST_K8S_GPU_RESOURCE,
    CONST_K8S_GPU_TOTAL_VRAM_LABEL,
    CONST_K8S_OLLAMA_PROVIDER_LABEL,
)
from devops_cli.k8s.gpu_placement import ollama_tiers, placement_warnings
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.fakes.process import ProcessAnswer, ProcessFake


def _node(name: str, labels: dict[str, str] | None = None, gpus: str | None = None) -> dict:
    capacity = {CONST_K8S_GPU_RESOURCE: gpus} if gpus is not None else {}
    return {
        "metadata": {"name": name, "labels": labels or {}},
        "status": {
            "capacity": capacity,
            "conditions": [{"type": "Ready", "status": "True"}],
        },
    }


def _deploy(
    nodes: object,
    *,
    process_fake: ProcessFake,
    cluster: FakeCluster,
    cli: Any,
    argo: bool = False,
    fail: bool = False,
) -> tuple[int, str]:
    """Run `deploy-stack --stack llm` over a cluster that lists `nodes`; return its exit code
    and output."""
    process_fake.answer(
        lambda call: call.argv[1:4] == ("get", "nodes", "-o"),
        ProcessAnswer(
            returncode=1 if fail else 0, stdout="" if fail else json.dumps({"items": nodes})
        ),
    )
    process_fake.answer(
        lambda call: call.argv[:2] == ("helm", "version"),
        ProcessAnswer(returncode=0, stdout="v3.17.0\n"),
    )
    if argo:
        cluster.custom_objects.objects[("argoproj.io", "v1alpha1", "applications")] = [
            {"metadata": {"name": "cluster", "namespace": "argocd"}}
        ]
    result = cli(["k8s", "deploy-stack", "--stack", "llm", "--no-push-secrets", "--k8s-dir", "k8s"])
    return result.exit_code, result.output


_GOOD = _node(
    "gpu-ok",
    {
        CONST_K8S_GPU_PRESENT_LABEL: "true",
        CONST_K8S_GPU_TOTAL_VRAM_LABEL: "16Gi",
    },
    gpus="1",
)


def test_a_labelled_gpu_node_gets_no_warning(
    process_fake: ProcessFake, cluster: FakeCluster, cli: Any
) -> None:
    """A node whose total-vram label a tier accepts is placed, so nothing is said."""
    exit_code, output = _deploy([_GOOD], process_fake=process_fake, cluster=cluster, cli=cli)

    assert (exit_code, "nvidia.com/gpu.total-vram-gib" in output) == (0, False)


def test_an_unlabelled_gpu_node_is_named_with_the_command_that_labels_it(
    process_fake: ProcessFake, cluster: FakeCluster, cli: Any
) -> None:
    """A GPU node without the total-vram label is named, with `kubectl label node` to fix it,
    and the deploy goes on."""
    bare = _node("gpu-bare", {CONST_K8S_GPU_PRESENT_LABEL: "true"}, gpus="1")

    exit_code, output = _deploy([_GOOD, bare], process_fake=process_fake, cluster=cluster, cli=cli)

    assert (
        exit_code,
        "gpu-bare" in output,
        f"kubectl label node gpu-bare {CONST_K8S_GPU_TOTAL_VRAM_LABEL}=<N>Gi" in output,
        "gpu-ok" in output,
    ) == (0, True, True, False)


def test_a_total_outside_every_tier_is_named_with_the_value_it_has(
    process_fake: ProcessFake, cluster: FakeCluster, cli: Any
) -> None:
    """A total-vram value that no tier accepts is named with that value."""
    odd = _node("gpu-odd", {CONST_K8S_GPU_TOTAL_VRAM_LABEL: "17Gi"}, gpus="1")

    exit_code, output = _deploy([_GOOD, odd], process_fake=process_fake, cluster=cluster, cli=cli)

    assert (exit_code, "gpu-odd" in output, "17Gi" in output) == (0, True, True)


def test_a_node_without_gpus_gets_no_warning(
    process_fake: ProcessFake, cluster: FakeCluster, cli: Any
) -> None:
    """A node with no GPU capacity and no `gpu.present` label is not a GPU node."""
    plain = _node("cpu-only", {})

    exit_code, output = _deploy([_GOOD, plain], process_fake=process_fake, cluster=cluster, cli=cli)

    assert (exit_code, "cpu-only" in output) == (0, False)


def _profiles(path: Path) -> Path:
    """A profiles file with one Ollama tier that needs a total of 24Gi and the architecture
    `ada`, in the shape of `k8s/llm/profiles/ollama-profiles.yaml`."""
    provider_key, provider = CONST_K8S_OLLAMA_PROVIDER_LABEL
    terms = [
        {
            "matchExpressions": [
                {"key": CONST_K8S_GPU_TOTAL_VRAM_LABEL, "operator": "In", "values": ["24Gi"]},
                {"key": CONST_K8S_GPU_ARCHITECTURE_LABEL, "operator": "In", "values": ["ada"]},
            ]
        }
    ]
    daemon_set = {
        "apiVersion": "apps/v1",
        "kind": "DaemonSet",
        "metadata": {"name": "ollama-24gib", "labels": {provider_key: provider}},
        "spec": {
            "template": {
                "spec": {
                    "affinity": {
                        "nodeAffinity": {
                            "requiredDuringSchedulingIgnoredDuringExecution": {
                                "nodeSelectorTerms": terms
                            }
                        }
                    }
                }
            }
        },
    }
    path.write_text(yaml.safe_dump(daemon_set), encoding="utf-8")
    return path


def test_an_architecture_outside_the_split_tiers_is_named(tmp_path: Path) -> None:
    """A tier that also needs an architecture: a node with the total but another architecture
    is named with its architecture."""
    tiers = ollama_tiers(_profiles(tmp_path / "ollama-profiles.yaml"))
    wrong = _node(
        "gpu-arch",
        {
            CONST_K8S_GPU_TOTAL_VRAM_LABEL: "24Gi",
            CONST_K8S_GPU_ARCHITECTURE_LABEL: "no-such-architecture",
        },
        gpus="1",
    )

    warnings = placement_warnings([wrong], tiers)

    assert (
        any("gpu-arch" in w and "no-such-architecture" in w and "ada" in w for w in warnings),
        len(warnings),
    ) == (True, 2)


def test_no_node_that_any_tier_accepts_says_no_ollama_pod_will_schedule(
    process_fake: ProcessFake, cluster: FakeCluster, cli: Any
) -> None:
    """When every GPU node is refused, the output says no Ollama pod will schedule, and the
    deploy still exits 0."""
    bare = _node("gpu-bare", {CONST_K8S_GPU_PRESENT_LABEL: "true"}, gpus="1")

    exit_code, output = _deploy([bare], process_fake=process_fake, cluster=cluster, cli=cli)

    assert (exit_code, "no Ollama pod will schedule" in output) == (0, True)


def test_a_failed_node_read_says_the_labels_were_not_checked(
    process_fake: ProcessFake, cluster: FakeCluster, cli: Any
) -> None:
    """When `kubectl get nodes` fails, deploy-stack says it could not check the labels."""
    exit_code, output = _deploy([], fail=True, process_fake=process_fake, cluster=cluster, cli=cli)

    assert (exit_code, "could not check" in output) == (0, True)


def test_the_check_runs_before_the_argo_cd_early_return(
    process_fake: ProcessFake, cluster: FakeCluster, cli: Any
) -> None:
    """On an Argo CD-managed cluster the warning still prints, since the node read comes before
    the early return."""
    bare = _node("gpu-bare", {CONST_K8S_GPU_PRESENT_LABEL: "true"}, gpus="1")

    exit_code, output = _deploy(
        [bare], argo=True, process_fake=process_fake, cluster=cluster, cli=cli
    )

    assert (exit_code, "gpu-bare" in output) == (0, True)


def test_other_stacks_do_not_read_the_nodes_for_placement(
    process_fake: ProcessFake, cluster: FakeCluster, cli: Any
) -> None:
    """Only the llm stack has Ollama tiers: deploy-stack for infra reads no node for this."""
    process_fake.answer(
        lambda call: call.argv[:2] == ("helm", "version"),
        ProcessAnswer(returncode=0, stdout="v3.17.0\n"),
    )
    cluster.custom_objects.objects[("argoproj.io", "v1alpha1", "applications")] = [
        {"metadata": {"name": "cluster", "namespace": "argocd"}}
    ]

    cli(["k8s", "deploy-stack", "--stack", "infra", "--no-push-secrets", "--k8s-dir", "k8s"])

    node_reads = [c for c in process_fake.calls if c.argv[1:4] == ("get", "nodes", "-o")]
    assert node_reads == []


def test_a_dry_run_reads_no_node_and_runs_nothing(process_fake: ProcessFake, cli: Any) -> None:
    """`deploy-stack --stack llm --dry-run` starts no process."""
    result = cli(["k8s", "deploy-stack", "--stack", "llm", "--dry-run", "--k8s-dir", "k8s"])

    assert (result.exit_code, process_fake.calls) == (0, [])


def test_a_tier_with_another_operator_is_refused(tmp_path: Path) -> None:
    """A profile whose expression is not `In` raises, rather than being read as a list."""
    from devops_cli.exceptions.k8s import KubernetesDeployError

    profile = tmp_path / "profiles.yaml"
    profile.write_text(
        "kind: DaemonSet\n"
        "metadata:\n  name: ollama-8gib\n  labels:\n    llm.devops.io/provider: ollama\n"
        "spec:\n  template:\n    spec:\n      affinity:\n        nodeAffinity:\n"
        "          requiredDuringSchedulingIgnoredDuringExecution:\n"
        "            nodeSelectorTerms:\n              - matchExpressions:\n"
        "                  - key: nvidia.com/gpu.total-vram-gib\n"
        "                    operator: NotIn\n                    values: ['8Gi']\n",
        encoding="utf-8",
    )

    with pytest.raises(KubernetesDeployError, match="operator"):
        ollama_tiers(profile)
