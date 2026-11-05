"""GPU architecture thresholds turn a tier template into manifests and gateway routes (#3501)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.commands.ai_gateway import app as ai_gateway_app
from devops_cli.config.constants import CONST_RAG_MAX_CHUNK_TOKENS
from devops_cli.config.defaults import (
    DEFAULT_LLM_GATEWAY_CONFIG_PATH,
    DEFAULT_LLM_GPU_THRESHOLDS_PATH,
    DEFAULT_LLM_PROFILES_PATH,
    DEFAULT_LLM_SERVICES_PATH,
    DEFAULT_LLM_TIER_TEMPLATES_PATH,
)
from devops_cli.exceptions.k8s import KubernetesDeployError
from devops_cli.k8s.gpu_thresholds import (
    GpuThresholds,
    TierManifests,
    load_gpu_thresholds,
    load_tier_templates,
    render_tier_manifests,
)

runner = CliRunner()

SLOW = "http://ollama-48gib-slow.llm.svc.cluster.local:11434"

_TEMPLATE = """\
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: ollama-48gib-slow
  namespace: llm
  labels:
    app.kubernetes.io/name: ollama-48gib-slow
    llm.devops.io/provider: ollama
    llm.devops.io/vram-gib: 48gib
    llm.devops.io/total-vram-gib: "48"
    llm.devops.io/speed-tier: slow
  annotations:
    llm.devops.io/gpu-count: "2"
    llm.devops.io/embedding-model: qwen3-embedding:0.6b
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: ollama-48gib-slow
  template:
    metadata:
      labels:
        app.kubernetes.io/name: ollama-48gib-slow
        llm.devops.io/provider: ollama
        llm.devops.io/vram-gib: 48gib
        llm.devops.io/total-vram-gib: "48"
        llm.devops.io/speed-tier: slow
    spec:
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: nvidia.com/gpu.architecture
                    operator: In
                    values: ["pascal", "maxwell", "kepler"]
                  - key: nvidia.com/gpu.total-vram-gib
                    operator: In
                    values: ["48Gi"]
      containers:
        - name: ollama
          env:
            - name: OLLAMA_CONTEXT_LENGTH
              value: "128000"
            - name: OLLAMA_MAX_LOADED_MODELS
              value: "1"
            - name: OLLAMA_SCHED_SPREAD
              value: "1"
          resources:
            requests:
              cpu: 6000m
              memory: 24Gi
"""

_PROFILES = """\
---
# BEGIN rendered by devops ai gateway render from gpu-thresholds.yaml
# END rendered by devops ai gateway render from gpu-thresholds.yaml
"""

_SERVICES = _PROFILES

_GATEWAY = """\
model_list:
  - model_name: devops-chat
    litellm_params:
      model: ollama_chat/qwen3.8:27b
      api_base: http://ollama-64gib-standard.llm.svc.cluster.local:11434
    model_info:
      max_input_tokens: 160000
  # BEGIN rendered by devops ai gateway render from gpu-thresholds.yaml
  # END rendered by devops ai gateway render from gpu-thresholds.yaml
router_settings:
  routing_strategy: least-busy
"""


def _inputs(gateway: str = _GATEWAY) -> TierManifests:
    return TierManifests(profiles=_PROFILES, services=_SERVICES, gateway=gateway)


def _render(embedding_only: str, per_gpu: str, gateway: str = _GATEWAY) -> TierManifests:
    return render_tier_manifests(
        _inputs(gateway),
        GpuThresholds(embedding_only=embedding_only, per_gpu=per_gpu),
        [yaml.safe_load(_TEMPLATE)],
    )


def _daemonsets(rendered: TierManifests) -> dict[str, dict[str, Any]]:
    return {
        document["metadata"]["name"]: document
        for document in yaml.safe_load_all(rendered.profiles)
        if document
    }


def _env(daemonset: dict[str, Any]) -> dict[str, str]:
    container = daemonset["spec"]["template"]["spec"]["containers"][0]
    return {var["name"]: var["value"] for var in container["env"]}


def _routes(rendered: TierManifests) -> list[tuple[str, str, int]]:
    return [
        (
            m["model_name"],
            m["litellm_params"]["api_base"],
            m["litellm_params"]["order"],
        )
        for m in yaml.safe_load(rendered.gateway)["model_list"]
        if m.get("model_info", {}).get("mode") == "embedding"
    ]


def test_a_tier_at_both_thresholds_runs_one_embedding_instance_per_gpu() -> None:
    """Each GPU gets one instance named for the VRAM it sees, which claims one GPU, keeps one model
    and has its own Service and order 1 route."""
    rendered = _render("pascal", "pascal")
    daemonsets = _daemonsets(rendered)
    gpu1 = daemonsets["ollama-24gib-embed-gpu1"]
    pod = gpu1["spec"]["template"]
    services = {d["metadata"]["name"]: d for d in yaml.safe_load_all(rendered.services) if d}

    assert (
        list(daemonsets),
        _env(gpu1),
        pod["spec"]["containers"][0]["resources"]["limits"]["nvidia.com/gpu"],
        {k: v for k, v in pod["metadata"]["labels"].items() if k != "app.kubernetes.io/name"},
        gpu1["spec"]["selector"]["matchLabels"]["app.kubernetes.io/name"],
        "annotations" in gpu1["metadata"],
        services["ollama-24gib-embed-gpu1"]["spec"]["selector"],
        _routes(rendered),
    ) == (
        ["ollama-24gib-embed-gpu0", "ollama-24gib-embed-gpu1"],
        {
            "OLLAMA_CONTEXT_LENGTH": str(CONST_RAG_MAX_CHUNK_TOKENS),
            "OLLAMA_MAX_LOADED_MODELS": "1",
            "LLAMA_ARG_THREADS": "1",
            "OLLAMA_NOPRUNE": "1",
        },
        1,
        {
            "llm.devops.io/provider": "ollama",
            "llm.devops.io/vram-gib": "24gib",
            "llm.devops.io/total-vram-gib": "24",
            "llm.devops.io/speed-tier": "embed",
            "llm.devops.io/gpu-instance": "1",
        },
        "ollama-24gib-embed-gpu1",
        False,
        {
            "llm.devops.io/provider": "ollama",
            "llm.devops.io/vram-gib": "24gib",
            "llm.devops.io/speed-tier": "embed",
            "llm.devops.io/gpu-instance": "1",
        },
        [
            (
                "qwen3-embedding:0.6b",
                "http://ollama-24gib-embed-gpu0.llm.svc.cluster.local:11434",
                1,
            ),
            (
                "qwen3-embedding:0.6b",
                "http://ollama-24gib-embed-gpu1.llm.svc.cluster.local:11434",
                1,
            ),
        ],
    )


def test_a_later_gpu_instance_needs_a_node_with_that_many_gpus() -> None:
    """The instance of the second GPU schedules only where a second GPU exists, and the first
    instance adds no requirement."""
    daemonsets = _daemonsets(_render("pascal", "pascal"))

    def _keys(name: str) -> dict[str, list[str]]:
        spec = daemonsets[name]["spec"]["template"]["spec"]
        affinity = spec["affinity"]["nodeAffinity"][
            "requiredDuringSchedulingIgnoredDuringExecution"
        ]
        [term] = affinity["nodeSelectorTerms"]
        return {e["key"]: e["values"] for e in term["matchExpressions"]}

    assert (
        "nvidia.com/gpu.count" in _keys("ollama-24gib-embed-gpu0"),
        _keys("ollama-24gib-embed-gpu1")["nvidia.com/gpu.count"],
    ) == (False, ["2", "3", "4", "5", "6", "7", "8"])


def test_a_tier_newer_than_both_thresholds_runs_as_its_template_says() -> None:
    """Below the tier's newest architecture, neither threshold changes the tier, and a chat tier
    gets no embedding route: it loads one model (#3567)."""
    rendered = _render("maxwell", "kepler")
    (tier,) = _daemonsets(rendered).values()
    template = yaml.safe_load(_TEMPLATE)
    del template["metadata"]["annotations"]

    (service,) = filter(None, yaml.safe_load_all(rendered.services))

    assert (tier, service["metadata"]["name"], service["spec"]["selector"], _routes(rendered)) == (
        template,
        "ollama-48gib-slow",
        {
            "llm.devops.io/provider": "ollama",
            "llm.devops.io/vram-gib": "48gib",
            "llm.devops.io/speed-tier": "slow",
        },
        [],
    )


def test_the_two_thresholds_act_alone() -> None:
    """The embedding threshold changes what a tier serves and its CPU threads, the per-GPU one how
    many instances. A chat tier keeps the default thread count, which it needs on the CPU."""
    embedding_only = _render("pascal", "kepler")
    per_gpu = _render("kepler", "pascal")
    (single,) = _daemonsets(embedding_only).values()

    assert (
        list(_daemonsets(embedding_only)),
        _env(single)["OLLAMA_MAX_LOADED_MODELS"],
        _env(single)["OLLAMA_SCHED_SPREAD"],
        _routes(embedding_only),
        _env(_daemonsets(per_gpu)["ollama-24gib-slow-gpu0"])["OLLAMA_MAX_LOADED_MODELS"],
        _env(single)["LLAMA_ARG_THREADS"],
        "LLAMA_ARG_THREADS" in _env(_daemonsets(per_gpu)["ollama-24gib-slow-gpu0"]),
        _routes(per_gpu),
    ) == (
        ["ollama-48gib-embed"],
        "1",
        "1",
        [("qwen3-embedding:0.6b", "http://ollama-48gib-embed.llm.svc.cluster.local:11434", 1)],
        "1",
        "1",
        False,
        [],
    )


def test_a_threshold_newer_than_every_template_is_refused() -> None:
    """A tier with no template, such as one that accepts any architecture, cannot follow the
    threshold, so `volta` fails and does not leave a volta node as it is."""
    with pytest.raises(KubernetesDeployError, match="volta"):
        _render("volta", "pascal")


def test_an_unknown_architecture_is_refused() -> None:
    """A typing error in the file fails at load, and a file with an unknown key too."""
    with pytest.raises(ValueError, match="pascl"):
        GpuThresholds(embedding_only="pascl", per_gpu="pascal")


@pytest.mark.parametrize("service", ["ollama-48gib-slow", "ollama-24gib-embed-gpu0"])
def test_a_chat_route_on_an_embedding_only_tier_is_refused(service: str) -> None:
    """Moving a chat group is a routing decision, so the render names the group and moves none."""
    gateway = _GATEWAY.replace("ollama-64gib-standard", service)

    with pytest.raises(KubernetesDeployError, match="devops-chat"):
        _render("pascal", "pascal", gateway)


def test_a_chat_route_stays_on_a_tier_newer_than_the_embedding_threshold() -> None:
    """Only the embedding threshold refuses a chat route, so per-GPU alone accepts it."""
    gateway = _GATEWAY.replace("ollama-64gib-standard", "ollama-24gib-slow-gpu0")

    assert "devops-chat" in _render("kepler", "pascal", gateway).gateway


def test_a_second_render_changes_nothing() -> None:
    """The output of the render is a valid input with the same output."""
    thresholds = GpuThresholds(embedding_only="pascal", per_gpu="pascal")
    templates = [yaml.safe_load(_TEMPLATE)]
    once = render_tier_manifests(_inputs(), thresholds, templates)

    assert render_tier_manifests(once, thresholds, templates) == once


def test_a_lower_threshold_collapses_the_instances_of_an_earlier_render() -> None:
    """Lowering a threshold removes what the higher value wrote."""
    templates = [yaml.safe_load(_TEMPLATE)]
    high = render_tier_manifests(
        _inputs(), GpuThresholds(embedding_only="pascal", per_gpu="pascal"), templates
    )
    low = GpuThresholds(embedding_only="kepler", per_gpu="kepler")

    assert render_tier_manifests(high, low, templates) == render_tier_manifests(
        _inputs(), low, templates
    )


def test_a_file_without_the_markers_is_refused() -> None:
    """The render has no place to write in a manifest with no markers, and says which."""
    with pytest.raises(KubernetesDeployError, match="BEGIN rendered"):
        render_tier_manifests(
            TierManifests(profiles="", services=_SERVICES, gateway=_GATEWAY),
            GpuThresholds(embedding_only="pascal", per_gpu="pascal"),
            [yaml.safe_load(_TEMPLATE)],
        )


def test_the_tracked_manifests_are_the_output_of_the_render() -> None:
    """The tracked thresholds and templates give exactly the tracked manifests, so a hand edit of
    a rendered region or a changed threshold with no render fails here."""
    tracked = TierManifests(
        profiles=DEFAULT_LLM_PROFILES_PATH.read_text(encoding="utf-8"),
        services=DEFAULT_LLM_SERVICES_PATH.read_text(encoding="utf-8"),
        gateway=DEFAULT_LLM_GATEWAY_CONFIG_PATH.read_text(encoding="utf-8"),
    )

    assert (
        render_tier_manifests(
            tracked,
            load_gpu_thresholds(DEFAULT_LLM_GPU_THRESHOLDS_PATH),
            load_tier_templates(DEFAULT_LLM_TIER_TEMPLATES_PATH),
        )
        == tracked
    )


def test_the_default_thresholds_are_pascal() -> None:
    """The tracked file sets both thresholds to pascal."""
    assert load_gpu_thresholds(DEFAULT_LLM_GPU_THRESHOLDS_PATH) == GpuThresholds(
        embedding_only="pascal", per_gpu="pascal"
    )


def _write_inputs(tmp_path: Path, gateway: str = _GATEWAY) -> dict[str, Path]:
    """Write one render input of each kind, and return the file of each CLI option."""
    templates = tmp_path / "tier-templates"
    templates.mkdir()
    (templates / "ollama-48gib-slow.yaml").write_text(_TEMPLATE, encoding="utf-8")
    paths = {
        "--config": tmp_path / "config.yaml",
        "--profiles": tmp_path / "profiles.yaml",
        "--services": tmp_path / "services.yaml",
        "--thresholds": tmp_path / "gpu-thresholds.yaml",
        "--tier-templates": templates,
    }
    paths["--config"].write_text(gateway, encoding="utf-8")
    paths["--profiles"].write_text(_PROFILES, encoding="utf-8")
    paths["--services"].write_text(_SERVICES, encoding="utf-8")
    paths["--thresholds"].write_text("embedding_only: pascal\nper_gpu: pascal\n", encoding="utf-8")
    return paths


def _args(paths: dict[str, Path]) -> list[str]:
    return ["render", *(part for flag, path in paths.items() for part in (flag, str(path)))]


def test_cli_render_writes_the_three_manifests_only_with_apply(tmp_path: Path) -> None:
    """Without --apply the command shows the diff of each file and writes none. With it the
    command writes them, and a second run reports nothing to change."""
    paths = _write_inputs(tmp_path)

    shown = runner.invoke(ai_gateway_app, _args(paths))
    unchanged = paths["--profiles"].read_text(encoding="utf-8") == _PROFILES
    applied = runner.invoke(ai_gateway_app, [*_args(paths), "--apply"])
    again = runner.invoke(ai_gateway_app, _args(paths))

    assert (
        shown.exit_code,
        "+  name: ollama-24gib-embed-gpu1" in shown.output,
        unchanged,
        applied.exit_code,
        "ollama-24gib-embed-gpu1" in paths["--services"].read_text(encoding="utf-8"),
        "ollama-24gib-embed-gpu1" in paths["--config"].read_text(encoding="utf-8"),
        again.exit_code,
        "already up to date" in again.output,
    ) == (0, True, True, 0, True, True, 0, True)


def test_cli_render_names_the_chat_group_it_refuses_and_writes_nothing(tmp_path: Path) -> None:
    """A refused render exits 1 with the group in the message, and every file stays as it was."""
    gateway = _GATEWAY.replace("ollama-64gib-standard", "ollama-48gib-slow")
    paths = _write_inputs(tmp_path, gateway)

    result = runner.invoke(ai_gateway_app, [*_args(paths), "--apply"])

    assert (
        result.exit_code,
        "devops-chat" in result.output,
        paths["--profiles"].read_text(encoding="utf-8"),
    ) == (1, True, _PROFILES)
