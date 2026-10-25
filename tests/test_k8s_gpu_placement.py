"""deploy-stack warns about GPU nodes that no Ollama tier accepts (#1367).

The accepted labels come from the required `matchExpressions` of each Ollama DaemonSet in
`k8s/llm/profiles/ollama-profiles.yaml`, so the tests read that file, not a copy of its values.
Each case answers `kubectl get nodes -o json` through the process edge and runs the command.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.commands.k8s import app
from devops_cli.config.constants import (
    CONST_K8S_GPU_ARCHITECTURE_LABEL,
    CONST_K8S_GPU_PRESENT_LABEL,
    CONST_K8S_GPU_RESOURCE,
    CONST_K8S_GPU_TOTAL_VRAM_LABEL,
)
from devops_cli.k8s.gpu_placement import ollama_tiers
from tests.support.paths import REPO_ROOT

runner = CliRunner()
PROFILES = REPO_ROOT / "k8s" / "llm" / "profiles" / "ollama-profiles.yaml"


def _node(name: str, labels: dict[str, str] | None = None, gpus: str | None = None) -> dict:
    capacity = {CONST_K8S_GPU_RESOURCE: gpus} if gpus is not None else {}
    return {
        "metadata": {"name": name, "labels": labels or {}},
        "status": {
            "capacity": capacity,
            "conditions": [{"type": "Ready", "status": "True"}],
        },
    }


def _deploy(nodes: object, *, argo: bool = False, fail: bool = False) -> tuple[int, str]:
    """Run `deploy-stack --stack llm` over a cluster that lists `nodes`; return its exit code
    and output."""

    def cluster(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if cmd[1:4] == ["get", "nodes", "-o"]:
            return subprocess.CompletedProcess(
                cmd, 1 if fail else 0, "" if fail else json.dumps({"items": nodes}), ""
            )
        if cmd[:2] == ["helm", "version"]:
            return subprocess.CompletedProcess(cmd, 0, "v3.17.0\n", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    with (
        patch("devops_cli.commands.k8s._cluster_reachable", return_value=True),
        patch("devops_cli.commands.k8s._run_cmd", side_effect=cluster),
        patch(
            "devops_cli.commands.k8s.stack_lifecycle._is_cluster_argo_managed",
            return_value=argo,
        ),
        patch(
            "devops_cli.commands.k8s.stack_lifecycle._handle_argo_managed_deployment",
        ),
        patch("devops_cli.commands.k8s.port_forward"),
        patch("devops_cli.k8s.credentials.sync_k8s_credentials", return_value={}),
    ):
        result = runner.invoke(
            app, ["deploy-stack", "--stack", "llm", "--no-push-secrets", "--k8s-dir", "k8s"]
        )
    return result.exit_code, result.output


_GOOD = _node(
    "gpu-ok",
    {
        CONST_K8S_GPU_PRESENT_LABEL: "true",
        CONST_K8S_GPU_TOTAL_VRAM_LABEL: "16Gi",
    },
    gpus="1",
)


def test_a_labelled_gpu_node_gets_no_warning() -> None:
    """A node whose total-vram label a tier accepts is placed, so nothing is said."""
    exit_code, output = _deploy([_GOOD])

    assert (exit_code, "nvidia.com/gpu.total-vram-gib" in output) == (0, False)


def test_an_unlabelled_gpu_node_is_named_with_the_command_that_labels_it() -> None:
    """A GPU node without the total-vram label is named, with `kubectl label node` to fix it,
    and the deploy goes on."""
    bare = _node("gpu-bare", {CONST_K8S_GPU_PRESENT_LABEL: "true"}, gpus="1")

    exit_code, output = _deploy([_GOOD, bare])

    assert (
        exit_code,
        "gpu-bare" in output,
        f"kubectl label node gpu-bare {CONST_K8S_GPU_TOTAL_VRAM_LABEL}=<N>Gi" in output,
        "gpu-ok" in output,
    ) == (0, True, True, False)


def test_a_total_outside_every_tier_is_named_with_the_value_it_has() -> None:
    """A total-vram value that no tier accepts is named with that value."""
    odd = _node("gpu-odd", {CONST_K8S_GPU_TOTAL_VRAM_LABEL: "17Gi"}, gpus="1")

    exit_code, output = _deploy([_GOOD, odd])

    assert (exit_code, "gpu-odd" in output, "17Gi" in output) == (0, True, True)


def test_a_node_without_gpus_gets_no_warning() -> None:
    """A node with no GPU capacity and no `gpu.present` label is not a GPU node."""
    plain = _node("cpu-only", {})

    exit_code, output = _deploy([_GOOD, plain])

    assert (exit_code, "cpu-only" in output) == (0, False)


def test_an_architecture_outside_the_split_tiers_is_named() -> None:
    """The 24gib tier also needs an architecture: a node with the total but another architecture
    is named with its architecture."""
    tier = next(t for t in ollama_tiers(PROFILES) if CONST_K8S_GPU_ARCHITECTURE_LABEL in t.terms[0])
    total = sorted(tier.terms[0][CONST_K8S_GPU_TOTAL_VRAM_LABEL])[0]
    wrong = _node(
        "gpu-arch",
        {
            CONST_K8S_GPU_TOTAL_VRAM_LABEL: total,
            CONST_K8S_GPU_ARCHITECTURE_LABEL: "no-such-architecture",
        },
        gpus="1",
    )

    exit_code, output = _deploy([_GOOD, wrong])

    assert (exit_code, "gpu-arch" in output, "no-such-architecture" in output) == (0, True, True)


def test_no_node_that_any_tier_accepts_says_no_ollama_pod_will_schedule() -> None:
    """When every GPU node is refused, the output says no Ollama pod will schedule, and the
    deploy still exits 0."""
    bare = _node("gpu-bare", {CONST_K8S_GPU_PRESENT_LABEL: "true"}, gpus="1")

    exit_code, output = _deploy([bare])

    assert (exit_code, "no Ollama pod will schedule" in output) == (0, True)


def test_a_failed_node_read_says_the_labels_were_not_checked() -> None:
    """When `kubectl get nodes` fails, deploy-stack says it could not check the labels."""
    exit_code, output = _deploy([], fail=True)

    assert (exit_code, "could not check" in output) == (0, True)


def test_the_check_runs_before_the_argo_cd_early_return() -> None:
    """On an Argo CD-managed cluster the warning still prints, since the node read comes before
    the early return."""
    bare = _node("gpu-bare", {CONST_K8S_GPU_PRESENT_LABEL: "true"}, gpus="1")

    exit_code, output = _deploy([bare], argo=True)

    assert (exit_code, "gpu-bare" in output) == (0, True)


def test_other_stacks_do_not_read_the_nodes_for_placement() -> None:
    """Only the llm stack has Ollama tiers: deploy-stack for infra reads no node for this."""
    calls: list[list[str]] = []

    def cluster(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"items": []}), "")

    with (
        patch("devops_cli.commands.k8s._cluster_reachable", return_value=True),
        patch("devops_cli.commands.k8s._run_cmd", side_effect=cluster),
        patch(
            "devops_cli.commands.k8s.stack_lifecycle._is_cluster_argo_managed", return_value=True
        ),
        patch("devops_cli.commands.k8s.stack_lifecycle._handle_argo_managed_deployment"),
    ):
        runner.invoke(
            app, ["deploy-stack", "--stack", "infra", "--no-push-secrets", "--k8s-dir", "k8s"]
        )

    assert [c for c in calls if c[1:4] == ["get", "nodes", "-o"]] == []


def test_a_dry_run_reads_no_node_and_runs_nothing() -> None:
    """`deploy-stack --stack llm --dry-run` makes no `_run_cmd` or subprocess call."""
    with (
        patch("devops_cli.commands.k8s._run_cmd") as mock_cmd,
        patch("subprocess.run") as mock_run,
        patch("subprocess.Popen") as mock_popen,
    ):
        result = runner.invoke(
            app, ["deploy-stack", "--stack", "llm", "--dry-run", "--k8s-dir", "k8s"]
        )

    assert (result.exit_code, mock_cmd.called, mock_run.called, mock_popen.called) == (
        0,
        False,
        False,
        False,
    )


def test_every_ollama_tier_requires_its_labels_with_in_and_only_in() -> None:
    """The check reads each tier's `matchExpressions` as `In` lists, so a tier written with
    another operator would be read wrongly: the profiles hold none, and a new one fails here."""
    operators = {
        expression["operator"]
        for document in yaml.safe_load_all(PROFILES.read_text(encoding="utf-8"))
        if document and document.get("kind") == "DaemonSet"
        for term in document["spec"]["template"]["spec"]["affinity"]["nodeAffinity"][
            "requiredDuringSchedulingIgnoredDuringExecution"
        ]["nodeSelectorTerms"]
        for expression in term["matchExpressions"]
    }

    assert operators == {"In"}


def test_the_tiers_are_read_from_the_profiles() -> None:
    """Nine Ollama tiers, each requiring a total-vram label, three of them an architecture too."""
    tiers = ollama_tiers(PROFILES)

    assert (
        len(tiers),
        all(CONST_K8S_GPU_TOTAL_VRAM_LABEL in t.terms[0] for t in tiers),
        sum(CONST_K8S_GPU_ARCHITECTURE_LABEL in t.terms[0] for t in tiers),
    ) == (9, True, 3)


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
