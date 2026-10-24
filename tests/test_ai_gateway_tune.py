"""`devops ai gateway tune`: measure each gateway deployment and recommend routing weights."""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from devops_cli.ai import gateway_bench as bench
from devops_cli.ai.gateway_tune import (
    GatewayTuneError,
    GpuInfo,
    backend_pods,
    bench_script,
    calculate_hardware_concurrency,
    calculate_hardware_weights,
    discover_pool,
    gpu_bandwidth_gbps,
    gpu_inventory,
    measure_in_gateway_pod,
    recommend_weights,
    tune_pool,
)
from devops_cli.ai.run_store import Mechanism, new_run
from devops_cli.ai.spend.models import BackendSpendSummary
from devops_cli.commands.ai_gateway import app as gateway_cli_app
from devops_cli.config.defaults import DEFAULT_GATEWAY_TUNE_IMAGE
from devops_cli.config.settings import AIConfig

runner = CliRunner()

REMOTE_OPENAI = "http://remote.example.com:8000/v1"
OLLAMA_0 = "http://ollama-0.ollama-nodes.llm.svc.cluster.local:11434"


def _deployment(
    name: str, dep_id: str, model: str, api_base: str, max_input: int | None = None, **params: Any
) -> dict[str, Any]:
    return {
        "model_name": name,
        "litellm_params": {"model": model, "api_base": api_base, **params},
        "model_info": {"id": dep_id, "max_input_tokens": max_input},
    }


MODEL_INFO = [
    _deployment(
        "devops-review",
        "a",
        "openai/qwen2.5-coder-32b-instruct",
        REMOTE_OPENAI,
        max_input=12288,
        weight=5,
    ),
    _deployment("devops-review", "b", "ollama_chat/gpt-oss:20b", OLLAMA_0, weight=1),
    _deployment("devops-chat", "c", "ollama_chat/qwen2.5-coder:7b", OLLAMA_0),
]


class TestBench:
    """The standard-library sweep that runs inside the gateway pod."""

    def test_each_backend_is_called_through_its_openai_compatible_chat_api(self) -> None:
        """Verify an OpenAI-compatible base keeps its /v1 base and Ollama gains one, with the provider prefix dropped."""
        assert (
            bench.chat_target("openai/qwen2.5-coder-32b-instruct", REMOTE_OPENAI),
            bench.chat_target("ollama_chat/gpt-oss:20b", OLLAMA_0),
            bench.chat_target("ollama/bge-m3", "http://ollama.example.com:11434/"),
        ) == (
            (f"{REMOTE_OPENAI}/chat/completions", "qwen2.5-coder-32b-instruct"),
            (f"{OLLAMA_0}/v1/chat/completions", "gpt-oss:20b"),
            ("http://ollama.example.com:11434/v1/chat/completions", "bge-m3"),
        )

    def test_level_counts_only_successful_requests_toward_throughput(self) -> None:
        """Verify a level reports requests, errors, tokens and rate, with a unique prompt each."""
        bodies: list[dict[str, Any]] = []

        def post(url: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
            bodies.append(body)
            if len(bodies) == 3:
                raise OSError("connection reset")
            return {"usage": {"completion_tokens": 10}}

        level = bench.run_level(
            "http://backend.example.com/v1/chat/completions",
            "m",
            "prompt",
            20,
            concurrency=2,
            total=4,
            timeout=5.0,
            fixed_length=True,
            post=post,
        )

        prompts = [b["messages"][0]["content"] for b in bodies]
        assert (
            level["concurrency"],
            level["requests"],
            level["errors"],
            level["completion_tokens"],
            level["requests_per_second"] > 0,
            {(b["model"], b["max_tokens"], b["ignore_eos"]) for b in bodies},
            len(set(prompts)),
            all(prompt.endswith("prompt") for prompt in prompts),
            level["last_error"],
        ) == (2, 4, 1, 30, True, {("m", 20, True)}, 4, True, "OSError: connection reset")

    def test_natural_length_level_lets_the_model_stop(self) -> None:
        """Verify the cost pass does not force a reply length."""
        bodies: list[dict[str, Any]] = []

        def post(url: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
            bodies.append(body)
            return {"usage": {"completion_tokens": 3}}

        bench.run_level(
            "http://b.example.com/v1/chat/completions",
            "m",
            "p",
            20,
            concurrency=1,
            total=2,
            timeout=5.0,
            post=post,
        )

        assert ["ignore_eos" in b for b in bodies] == [False, False]

    def test_run_level_returns_replies_when_requested(self) -> None:
        """Verify run_level collects and returns response text when return_replies=True."""

        def post(url: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
            return {
                "usage": {"completion_tokens": 15},
                "choices": [{"message": {"content": '{"result": "ok"}'}}],
            }

        level = bench.run_level(
            "http://backend.example.com/v1/chat/completions",
            "model-test",
            "probe prompt",
            50,
            concurrency=1,
            total=2,
            timeout=5.0,
            return_replies=True,
            post=post,
        )

        assert level["requests"] == 2
        assert level["errors"] == 0
        assert level["replies"] == ['{"result": "ok"}', '{"result": "ok"}']

    def test_measure_executes_probes_when_provided(self) -> None:
        """Verify measure runs probe levels and returns their replies."""
        calls: list[dict[str, Any]] = []

        def post(url: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
            calls.append(body)
            return {
                "usage": {"completion_tokens": 10},
                "choices": [{"message": {"content": "mock reply"}}],
            }

        def get(url: str, timeout: float) -> tuple[int, str]:
            return 200, 'vllm:cache_config_info{num_gpu_blocks="10",block_size="16"}'

        dep = {
            "deployment_id": "dep-1",
            "model": "openai/test-model",
            "api_base": REMOTE_OPENAI,
        }
        probes = [
            {"name": "json_adherence", "prompt": "return json", "rounds": 1, "max_tokens": 20}
        ]

        results = bench.measure(
            deployments=[dep],
            levels=[1],
            rounds=1,
            prompt="sweep prompt",
            max_tokens=20,
            post=post,
            get=get,
            probes=probes,
        )

        assert len(results) == 1
        assert "probes" in results[0]
        assert results[0]["probes"] is not None
        assert "json_adherence" in results[0]["probes"]
        assert results[0]["probes"]["json_adherence"]["replies"] == ["mock reply"]

    def test_engine_info_reads_vllm_kv_capacity_and_recognises_ollama(self) -> None:
        """Verify vLLM's KV-cache token capacity is read from /metrics and Ollama is detected."""
        metrics = (
            "# HELP vllm:cache_config_info Information of the LLMEngine CacheConfig\n"
            'vllm:cache_config_info{block_size="16",num_gpu_blocks="6413"} 1.0\n'
        )
        pages = {
            "http://example.com:8000/metrics": (200, metrics),
            "http://example.com:11434/metrics": (404, ""),
            "http://example.com:11434/api/version": (200, '{"version": "0.32.14"}'),
            "http://example.com:9000/metrics": (404, ""),
            "http://example.com:9000/api/version": (404, ""),
        }

        def get(url: str, timeout: float) -> tuple[int, str]:
            return pages[url]

        assert (
            bench.engine_info("http://example.com:8000/v1", get),
            bench.engine_info("http://example.com:11434", get),
            bench.engine_info("http://example.com:9000/v1", get),
        ) == (
            {"engine": "vllm", "kv_cache_tokens": 6413 * 16},
            {"engine": "ollama", "kv_cache_tokens": None},
            {"engine": "unknown", "kv_cache_tokens": None},
        )

    def test_sweep_image_runs_the_projects_python(self) -> None:
        """Verify the sweep container's Python is the version this project targets (3.14)."""
        pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
        python = pyproject["tool"]["mypy"]["python_version"]

        assert DEFAULT_GATEWAY_TUNE_IMAGE == f"python:{python}-slim"

    def test_gateway_bench_imports_only_standard_library(self) -> None:
        """Verify gateway_bench.py imports only stdlib modules so it runs in python:3.14-slim (#792)."""
        import ast
        import sys

        tree = ast.parse(Path(bench.__file__).read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert sorted(imported - sys.stdlib_module_names) == []

    def test_measure_runs_fixed_length_capacity_levels_then_a_natural_cost_pass(self) -> None:
        """Verify capacity levels send concurrency x rounds fixed-length requests, then cost."""
        sent: list[bool] = []

        def post(url: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
            sent.append(bool(body.get("ignore_eos")))
            return {"usage": {"completion_tokens": 1}}

        results = bench.measure(
            [{"deployment_id": "a", "model": "openai/m", "api_base": REMOTE_OPENAI}],
            levels=[1, 3],
            rounds=2,
            prompt="p",
            max_tokens=5,
            timeout=5.0,
            post=post,
            get=lambda url, timeout: (404, ""),
        )

        result = results[0]
        assert (
            result["deployment_id"],
            result["engine"]["engine"],
            [lvl["requests"] for lvl in result["capacity"]],
            (result["cost"]["concurrency"], result["cost"]["requests"]),
            sent,
        ) == ("a", "unknown", [2, 6], (1, 2), [True] * 8 + [False] * 2)


class TestTune:
    """CLI-side discovery, orchestration and weight recommendation."""

    def test_discover_pool_keeps_only_the_model_group(self) -> None:
        """Verify discovery returns the group's deployments with their current weights."""
        assert discover_pool(MODEL_INFO, "devops-review") == [
            {
                "deployment_id": "a",
                "model": "openai/qwen2.5-coder-32b-instruct",
                "api_base": REMOTE_OPENAI,
                "weight": 5,
                "max_input_tokens": 12288,
            },
            {
                "deployment_id": "b",
                "model": "ollama_chat/gpt-oss:20b",
                "api_base": OLLAMA_0,
                "weight": 1,
                "max_input_tokens": None,
            },
        ]

    def test_weights_are_throughput_relative_to_the_slowest_deployment(self) -> None:
        """Verify weights scale from the slowest measured deployment; unreachable ones get 0."""
        assert recommend_weights({"a": 1.2, "b": 0.8, "c": 0.21, "d": 0.2, "e": 0.0}) == {
            "a": 6,
            "b": 4,
            "c": 1,
            "d": 1,
            "e": 0,
        }

    def test_recommend_weights_with_overrides(self) -> None:
        """Verify user configuration overrides supersede measured throughput weights."""
        rates = {"vllm": 1.2, "ollama": 0.2}
        overrides = {"vllm": 8, "ollama": 2}
        assert (
            recommend_weights(rates),
            recommend_weights(rates, overrides=overrides),
        ) == (
            {"vllm": 6, "ollama": 1},
            {"vllm": 8, "ollama": 2},
        )

    def test_calculate_hardware_weights_and_concurrency(self) -> None:
        """Verify dynamic hardware properties compute appropriate weights and concurrency."""
        deployments = [
            {
                "deployment_id": "vllm-dual-3090",
                "backend": "vllm",
                "engine": "vllm",
                "gpus": [
                    {"name": "RTX 3090", "bandwidth_gbps": 936.0},
                    {"name": "RTX 3090", "bandwidth_gbps": 936.0},
                ],
            },
            {
                "deployment_id": "ollama-v100",
                "backend": "ollama",
                "engine": "ollama",
                "gpus": [
                    {"name": "Tesla V100", "bandwidth_gbps": 900.0},
                ],
            },
        ]
        weights = calculate_hardware_weights(deployments)
        concurrency = calculate_hardware_concurrency(deployments)
        overrides_weights = calculate_hardware_weights(
            deployments, overrides={"vllm-dual-3090": 10}
        )
        overrides_concurrency = calculate_hardware_concurrency(
            deployments, overrides={"ollama-v100": 4}
        )

        assert (
            weights,
            concurrency,
            overrides_weights["vllm-dual-3090"],
            overrides_concurrency["ollama-v100"],
        ) == (
            {"vllm-dual-3090": 6, "ollama-v100": 1},
            {"vllm-dual-3090": 64, "ollama-v100": 1},
            10,
            4,
        )

    def test_gpu_bandwidth_is_looked_up_by_the_most_specific_model_name(self) -> None:
        """Verify nvidia-smi names map to memory bandwidth, preferring the longest match."""
        assert (
            gpu_bandwidth_gbps("NVIDIA GeForce RTX 5070 Ti"),
            gpu_bandwidth_gbps("NVIDIA GeForce RTX 3090"),
            gpu_bandwidth_gbps("Tesla PG500-216"),
            gpu_bandwidth_gbps("Quadro P6000"),
            gpu_bandwidth_gbps("Imaginary GPU 9000"),
        ) == (896.0, 936.0, 900.0, 432.0, None)

    def test_backend_pods_resolve_pod_and_service_addresses(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify a per-pod address names its pod, and a Service address its running pods."""
        calls: list[list[str]] = []

        def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append(cmd)
            out = (
                json.dumps({"spec": {"selector": {"app": "ollama-16gib"}}})
                if "svc" in cmd
                else "ollama-16gib-7c9"
            )
            return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

        monkeypatch.setattr("devops_cli.ai.gateway_tune.subprocess.run", fake_run)

        assert (
            backend_pods(OLLAMA_0, None),
            backend_pods("http://ollama-16gib.llm.svc.cluster.local:11434", "lab"),
            backend_pods("http://ollama.example.com:11434", None),
            [c[3:6] for c in calls],
        ) == (
            ("llm", ["ollama-0"]),
            ("llm", ["ollama-16gib-7c9"]),
            (None, []),
            [["get", "svc", "ollama-16gib"], ["get", "pods", "-n"]],
        )

    def test_gpu_inventory_parses_nvidia_smi(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify each GPU visible to the backend pod is listed with memory and bandwidth."""
        monkeypatch.setattr(
            "devops_cli.ai.gateway_tune.subprocess.run",
            lambda cmd, **kw: subprocess.CompletedProcess(
                cmd, 0, stdout="Quadro P6000, 24576\nNVIDIA GeForce GTX 1050 Ti, 4096\n", stderr=""
            ),
        )

        assert [g.model_dump() for g in gpu_inventory("llm", "ollama-0", None)] == [
            {"name": "Quadro P6000", "memory_mib": 24576, "bandwidth_gbps": 432.0},
            {"name": "NVIDIA GeForce GTX 1050 Ti", "memory_mib": 4096, "bandwidth_gbps": 112.0},
        ]

    def test_bench_script_is_the_bench_module_plus_a_call_with_the_spec(self) -> None:
        """Verify the script sent to the pod runs the bench module on the given spec."""
        spec = {"deployments": [], "levels": [1], "rounds": 1, "prompt": "p", "max_tokens": 1}
        script = bench_script(spec)
        namespace: dict[str, Any] = {}
        printed: list[str] = []
        namespace["print"] = printed.append

        exec(compile(script, "<bench>", "exec"), namespace)  # nosec B102  # runs the bench script under test

        assert json.loads(printed[-1]) == []

    def test_sweep_runs_in_an_ephemeral_container_on_a_running_gateway_pod(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify the sweep attaches to a gateway pod and pipes script to exec."""
        kubectl = _FakeKubectl(exit_code=0, logs='noise\n[{"deployment_id": "a"}]')
        monkeypatch.setattr("devops_cli.ai.gateway_tune.subprocess.run", kubectl)
        monkeypatch.setattr("devops_cli.ai.gateway_tune.time.sleep", lambda _s: None)

        result = measure_in_gateway_pod(
            {"deployments": []},
            namespace="llm",
            deployment="llm-gateway",
            context="lab",
            container="gateway-tune-0a1b2c",
            lifetime_seconds=90.5,
        )

        debug = kubectl.called("debug")
        exec_call = kubectl.called("exec")
        exec_input = kubectl.inputs[kubectl.calls.index(exec_call)]
        assert (
            result,
            debug[:5],
            debug[5:11],
            debug[-2:],
            exec_call[:6],
            exec_call[-3:],
            "def measure(" in (exec_input or ""),
            kubectl.called("pods")[-1],
        ) == (
            [{"deployment_id": "a"}],
            ["kubectl", "--context", "lab", "debug", "pod/llm-gateway-abc"],
            [
                "-n",
                "llm",
                "--profile=restricted",
                "--image=python:3.14-slim",
                "--container=gateway-tune-0a1b2c",
                "--",
            ],
            ["sleep", "91"],
            ["kubectl", "--context", "lab", "exec", "-i", "llm-gateway-abc"],
            ["--", "python", "-"],
            True,
            "jsonpath={.items[0].metadata.name}",
        )

    def test_sweep_delivers_prompt_exceeding_argv_limit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify prompts exceeding Linux 131,072-byte argv limit are delivered via stdin."""
        large_prompt = "x" * 150_000
        spec = {
            "deployments": [{"deployment_id": "a", "model": "m", "api_base": REMOTE_OPENAI}],
            "levels": [1],
            "rounds": 1,
            "prompt": large_prompt,
            "max_tokens": 10,
        }
        kubectl = _FakeKubectl(exit_code=0, logs='[{"deployment_id": "a"}]')
        monkeypatch.setattr("devops_cli.ai.gateway_tune.subprocess.run", kubectl)
        monkeypatch.setattr("devops_cli.ai.gateway_tune.time.sleep", lambda _s: None)

        result = measure_in_gateway_pod(
            spec,
            namespace="llm",
            deployment="llm-gateway",
            container="gateway-tune-0a1b2c",
            lifetime_seconds=600.0,
        )

        exec_call = kubectl.called("exec")
        exec_input = kubectl.inputs[kubectl.calls.index(exec_call)] or ""
        assert (
            result,
            len(exec_input) > 131_072,
            large_prompt in exec_input,
            exec_call[-3:],
        ) == (
            [{"deployment_id": "a"}],
            True,
            True,
            ["--", "python", "-"],
        )

    def test_calculate_weights_with_backend_label_overrides(self) -> None:
        """Verify recommend_weights matches overrides by backend label when deployment IDs are distinct."""
        deployments = [
            {"deployment_id": "dep-1", "backend": "vllm"},
            {"deployment_id": "dep-2", "backend": "ollama"},
        ]
        rates = {"dep-1": 10.0, "dep-2": 2.0}
        weights_default = recommend_weights(rates, deployments=deployments)
        weights_backend = recommend_weights(
            rates, overrides={"vllm": 8, "ollama": 3}, deployments=deployments
        )
        weights_precedence = recommend_weights(
            rates, overrides={"vllm": 8, "dep-1": 12}, deployments=deployments
        )
        assert (
            weights_default,
            weights_backend,
            weights_precedence,
        ) == (
            {"dep-1": 5, "dep-2": 1},
            {"dep-1": 8, "dep-2": 3},
            {"dep-1": 12, "dep-2": 1},
        )

    def test_tune_pool_applies_concurrency_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify tune_pool calculates recommended_concurrency with config overrides."""
        monkeypatch.setattr(
            "devops_cli.ai.gateway_tune.fetch_model_info",
            lambda url, allow, key: MODEL_INFO,
        )
        monkeypatch.setattr(
            "devops_cli.ai.gateway_tune.deployment_gpus",
            lambda api_base, context: [GpuInfo(name="RTX 3090", memory_mib=24576)],
        )

        def fake_measure(spec: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
            dep_id = spec["deployments"][0]["deployment_id"]
            return [
                {
                    "deployment_id": dep_id,
                    "engine": {"engine": "vllm" if dep_id == "a" else "ollama"},
                    "capacity": [_level(1, 100)],
                    "cost": _level(1, 100),
                }
            ]

        monkeypatch.setattr("devops_cli.ai.gateway_tune.measure_in_gateway_pod", fake_measure)

        report = tune_pool(
            gateway_url=REMOTE_OPENAI,
            allow_private=True,
            api_key=None,
            model_group="devops-review",
            levels=[1],
            rounds=1,
            prompt_tokens=100,
            max_tokens=50,
            request_timeout=10.0,
            namespace="llm",
            deployment="llm-gateway",
            overrides={"remote": 10},
            concurrency_overrides={"remote": 32, "b": 4},
        )

        concurrencies = {d.deployment_id: d.recommended_concurrency for d in report.deployments}
        weights = {d.deployment_id: d.recommended_weight for d in report.deployments}
        assert (concurrencies, weights) == ({"a": 32, "b": 4}, {"a": 10, "b": 1})

    def test_unreachable_api_server_is_retried(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify kubectl calls that never reached the API server are retried, others are not."""
        replies = iter(
            [
                (
                    1,
                    "Unable to connect to the server: dial tcp: lookup api.example.com: no such host",
                ),
                (0, "Quadro P6000, 24576"),
                (1, 'Error from server (NotFound): pods "gone" not found'),
            ]
        )
        calls: list[list[str]] = []

        def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append(cmd)
            code, text = next(replies)
            return subprocess.CompletedProcess(
                cmd, code, stdout=text if code == 0 else "", stderr="" if code == 0 else text
            )

        monkeypatch.setattr("devops_cli.ai.gateway_tune.subprocess.run", fake_run)
        monkeypatch.setattr("devops_cli.ai.gateway_tune.time.sleep", lambda _s: None)

        gpus = gpu_inventory("llm", "ollama-0", None)
        with pytest.raises(GatewayTuneError, match="NotFound"):
            gpu_inventory("llm", "gone", None)

        assert ([g.name for g in gpus], len(calls)) == (["Quadro P6000"], 3)

    def test_missing_gateway_deployment_reports_kubectl_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify a missing gateway deployment raises with kubectl's message."""
        monkeypatch.setattr(
            "devops_cli.ai.gateway_tune.subprocess.run",
            lambda cmd, **kw: subprocess.CompletedProcess(
                cmd, 1, stdout="", stderr='deployments.apps "llm-gateway" not found'
            ),
        )

        with pytest.raises(GatewayTuneError, match="llm-gateway"):
            measure_in_gateway_pod(
                {"deployments": []},
                namespace="llm",
                deployment="llm-gateway",
                container="gateway-tune-0a1b2c",
                lifetime_seconds=600.0,
            )

    def test_failed_sweep_reports_the_container_logs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify a non-zero exit raises with the sweep container's output."""
        kubectl = _FakeKubectl(exit_code=1, logs="SyntaxError: invalid syntax")
        monkeypatch.setattr("devops_cli.ai.gateway_tune.subprocess.run", kubectl)
        monkeypatch.setattr("devops_cli.ai.gateway_tune.time.sleep", lambda _s: None)

        with pytest.raises(GatewayTuneError, match="SyntaxError"):
            measure_in_gateway_pod(
                {"deployments": []},
                namespace="llm",
                deployment="llm-gateway",
                container="gateway-tune-0a1b2c",
                lifetime_seconds=600.0,
            )

    def test_a_run_attaches_one_sweep_container_that_outlives_every_deployment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify every deployment of a run is swept in one container that lasts the run.

        A container an earlier run left running has an unknown remaining life, so the run
        attaches its own, and the one sleep covers the exec budget of both deployments.
        """
        kubectl = _FakeKubectl(
            exit_code=0, logs=_SWEEP_REPLY, containers={"gateway-tune-0a1b2c": {"running": {}}}
        )

        _tune_both_deployments(monkeypatch, kubectl, request_timeout=10.2)

        debugs = kubectl.all_called("debug")
        (run_container,) = kubectl.containers.keys() - {"gateway-tune-0a1b2c"}
        assert re.fullmatch(r"gateway-tune-[0-9a-f]{6}", run_container)
        # (10.2 s * 1 round * (1 level + 1 cost pass + 4 capability probes) + 60 s) * 2 deployments = 242.4 s.
        assert (
            [c[-3:] for c in debugs],
            [c[c.index("-c") + 1] for c in kubectl.all_called("exec")],
        ) == (
            [["--", "sleep", "243"]],
            [run_container, run_container],
        )

    def test_a_sweep_container_that_exits_mid_run_stops_the_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify a run whose container exited fails naming it, rather than attaching another."""
        kubectl = _FakeKubectl(exit_code=0, logs=_SWEEP_REPLY, expire_after_execs=1)

        with pytest.raises(GatewayTuneError, match="exited before the run finished") as raised:
            _tune_both_deployments(monkeypatch, kubectl, request_timeout=10.0)

        (run_container,) = kubectl.containers
        assert (
            run_container in str(raised.value),
            len(kubectl.all_called("debug")),
            len(kubectl.all_called("exec")),
        ) == (True, 1, 1)


class _FakeKubectl:
    """Answer the kubectl calls of one sweep: deployment, pods, container state, debug, exec.

    ``containers`` holds the state of each ephemeral container already on the pod, and
    ``expire_after_execs`` ends every container once that many sweeps have run on the pod.
    """

    def __init__(
        self,
        *,
        exit_code: int,
        logs: str,
        containers: dict[str, dict[str, Any]] | None = None,
        expire_after_execs: int | None = None,
    ) -> None:
        self.exit_code = exit_code
        self.logs = logs
        self.containers = dict(containers or {})
        self.expire_after_execs = expire_after_execs
        self.calls: list[list[str]] = []
        self.inputs: list[str | None] = []
        self.execs = 0

    def called(self, verb: str) -> list[str]:
        return next(c for c in self.calls if verb in c)

    def all_called(self, verb: str) -> list[list[str]]:
        return [c for c in self.calls if verb in c]

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(cmd)
        self.inputs.append(kwargs.get("input") or kwargs.get("input_data"))
        if "deployment" in cmd:
            out = json.dumps({"spec": {"selector": {"matchLabels": {"app": "llm-gateway"}}}})
            return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")
        if "pods" in cmd:
            out = "llm-gateway-abc"
            return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")
        if "debug" in cmd:
            name = next(a for a in cmd if a.startswith("--container=")).split("=", 1)[1]
            self.containers[name] = {"running": {}}
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if "exec" in cmd:
            return self._exec(cmd)
        statuses = [{"name": name, "state": state} for name, state in self.containers.items()]
        out = json.dumps({"status": {"ephemeralContainerStatuses": statuses}})
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    def _exec(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        self.execs += 1
        if self.execs == self.expire_after_execs:
            self.containers = {name: {"terminated": {"exitCode": 0}} for name in self.containers}
        if self.exit_code != 0:
            return subprocess.CompletedProcess(cmd, self.exit_code, stdout="", stderr=self.logs)
        return subprocess.CompletedProcess(cmd, 0, stdout=self.logs, stderr="")


def _level(concurrency: int, tokens: int, wall: float = 1.0) -> dict[str, Any]:
    return {
        "concurrency": concurrency,
        "requests": 2 * concurrency,
        "errors": 0,
        "wall_seconds": wall,
        "requests_per_second": 2 * concurrency / wall,
        "p50_latency_seconds": wall,
        "completion_tokens": tokens,
    }


_SWEEP_REPLY = json.dumps(
    [{"engine": {"engine": "vllm"}, "capacity": [_level(1, 100)], "cost": _level(1, 100)}]
)


def _tune_both_deployments(
    monkeypatch: pytest.MonkeyPatch, kubectl: _FakeKubectl, *, request_timeout: float
) -> None:
    """Run `tune_pool` over the two `devops-review` deployments with only kubectl faked."""
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.fetch_model_info", lambda url, allow, key: MODEL_INFO
    )
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.deployment_gpus",
        lambda api_base, context: [GpuInfo(name="RTX 3090", memory_mib=24576)],
    )
    monkeypatch.setattr("devops_cli.ai.gateway_tune.subprocess.run", kubectl)
    monkeypatch.setattr("devops_cli.ai.gateway_tune.time.sleep", lambda _s: None)

    tune_pool(
        gateway_url=REMOTE_OPENAI,
        allow_private=True,
        api_key=None,
        model_group="devops-review",
        levels=[1],
        rounds=1,
        prompt_tokens=100,
        max_tokens=50,
        request_timeout=request_timeout,
        namespace="llm",
        deployment="llm-gateway",
    )


def test_tune_pool_uses_spend_ledger_cost_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify cost tokens per request is taken from the spend ledger when recorded."""
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.fetch_model_info",
        lambda url, allow, key: MODEL_INFO[:1],
    )
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.deployment_gpus",
        lambda api_base, context: [
            GpuInfo(name="RTX 3090", memory_mib=24576, bandwidth_gbps=936.0)
        ],
    )

    fake_ledger = MagicMock()
    fake_report = MagicMock()
    fake_report.backends = [
        BackendSpendSummary(
            served_by=REMOTE_OPENAI,
            models=["devops-review"],
            request_count=50,
            prompt_tokens=10000,
            completion_tokens=7500,
            total_tokens=17500,
            completion_tokens_per_request=150.0,
            mean_duration_seconds=1.2,
        )
    ]
    fake_ledger.get_lifetime_report.return_value = fake_report

    measured_specs: list[dict[str, Any]] = []

    def fake_measure(spec: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
        measured_specs.append(spec)
        dep_id = spec["deployments"][0]["deployment_id"]
        return [
            {
                "deployment_id": dep_id,
                "engine": {"engine": "vllm"},
                "capacity": [_level(1, 100)],
                "cost": None,
            }
        ]

    monkeypatch.setattr("devops_cli.ai.gateway_tune.measure_in_gateway_pod", fake_measure)

    report = tune_pool(
        gateway_url=REMOTE_OPENAI,
        allow_private=True,
        api_key=None,
        model_group="devops-review",
        levels=[1],
        rounds=1,
        prompt_tokens=100,
        max_tokens=50,
        request_timeout=10.0,
        namespace="llm",
        deployment="llm-gateway",
        spend_ledger=fake_ledger,
    )

    dep = report.deployments[0]
    assert dep.cost_tokens_per_request == 150.0
    assert measured_specs[0].get("include_cost") is False


def test_tune_pool_falls_back_to_synthetic_probe_when_spend_ledger_has_no_backend_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify cost falls back to probe when spend ledger has no records for the backend."""
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.fetch_model_info",
        lambda url, allow, key: MODEL_INFO[:1],
    )
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.deployment_gpus",
        lambda api_base, context: [
            GpuInfo(name="RTX 3090", memory_mib=24576, bandwidth_gbps=936.0)
        ],
    )

    fake_ledger = MagicMock()
    fake_report = MagicMock()
    fake_report.backends = []
    fake_ledger.get_lifetime_report.return_value = fake_report

    measured_specs: list[dict[str, Any]] = []

    def fake_measure(spec: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
        measured_specs.append(spec)
        dep_id = spec["deployments"][0]["deployment_id"]
        return [
            {
                "deployment_id": dep_id,
                "engine": {"engine": "vllm"},
                "capacity": [_level(1, 100)],
                "cost": _level(1, 200),
            }
        ]

    monkeypatch.setattr("devops_cli.ai.gateway_tune.measure_in_gateway_pod", fake_measure)

    report = tune_pool(
        gateway_url=REMOTE_OPENAI,
        allow_private=True,
        api_key=None,
        model_group="devops-review",
        levels=[1],
        rounds=1,
        prompt_tokens=100,
        max_tokens=50,
        request_timeout=10.0,
        namespace="llm",
        deployment="llm-gateway",
        spend_ledger=fake_ledger,
    )

    dep = report.deployments[0]
    assert dep.cost_tokens_per_request == 100.0
    assert measured_specs[0].get("include_cost") is True


def test_tune_pool_estimate_scales_capacity_by_gpu_bandwidth_without_sending_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify capacity estimation scales by GPU memory bandwidth from measured deployment without sending load."""
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.fetch_model_info",
        lambda url, allow, key: [MODEL_INFO[1]],
    )
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.deployment_gpus",
        lambda api_base, context: [
            GpuInfo(name="RTX 3090", memory_mib=24576, bandwidth_gbps=936.0),
            GpuInfo(name="RTX 3090", memory_mib=24576, bandwidth_gbps=936.0),
        ],
    )

    prior_run = new_run(
        Mechanism.GATEWAY_TUNE,
        setup={"levels": [1, 2], "rounds": 1, "prompt_tokens": 512, "max_tokens": 100},
        subject={"model_group": "devops-review"},
        results={
            "model_group": "devops-review",
            "prompt_tokens": 512,
            "max_tokens": 100,
            "deployments": [
                {
                    "deployment_id": "b-old",
                    "backend": "ollama-0",
                    "model": "ollama_chat/gpt-oss:20b",
                    "api_base": OLLAMA_0,
                    "engine": "ollama",
                    "gpus": [{"name": "RTX 3090", "memory_mib": 24576, "bandwidth_gbps": 936.0}],
                    "capacity_tokens_per_second": 60.0,
                    "cost_tokens_per_request": 300.0,
                    "best_concurrency": 2,
                }
            ],
        },
    )
    monkeypatch.setattr("devops_cli.ai.gateway_tune.load_runs", lambda mechanism=None: [prior_run])

    fake_ledger = MagicMock()
    fake_report = MagicMock()
    fake_report.backends = [
        BackendSpendSummary(
            served_by=OLLAMA_0,
            models=["devops-review"],
            request_count=100,
            prompt_tokens=20000,
            completion_tokens=24000,
            total_tokens=44000,
            completion_tokens_per_request=240.0,
            mean_duration_seconds=2.0,
        )
    ]
    fake_ledger.get_lifetime_report.return_value = fake_report

    measure_mock = MagicMock()
    monkeypatch.setattr("devops_cli.ai.gateway_tune.measure_in_gateway_pod", measure_mock)

    report = tune_pool(
        gateway_url=REMOTE_OPENAI,
        allow_private=True,
        api_key=None,
        model_group="devops-review",
        levels=[1],
        rounds=1,
        prompt_tokens=100,
        max_tokens=50,
        request_timeout=10.0,
        namespace="llm",
        deployment="llm-gateway",
        spend_ledger=fake_ledger,
        estimate=True,
    )

    assert measure_mock.call_count == 0
    dep = report.deployments[0]
    assert dep.capacity_tokens_per_second == 120.0
    assert dep.cost_tokens_per_request == 240.0
    assert dep.requests_per_second == 0.5
    assert dep.best_concurrency == 2


def test_tune_pool_estimate_fails_when_no_prior_measured_deployment_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify estimate raises GatewayTuneError when no matching prior measurement exists."""
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.fetch_model_info",
        lambda url, allow, key: [MODEL_INFO[0]],
    )
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.deployment_gpus",
        lambda api_base, context: [
            GpuInfo(name="RTX 3090", memory_mib=24576, bandwidth_gbps=936.0)
        ],
    )
    monkeypatch.setattr("devops_cli.ai.gateway_tune.load_runs", lambda mechanism=None: [])

    with pytest.raises(GatewayTuneError, match="No prior measurements found"):
        tune_pool(
            gateway_url=REMOTE_OPENAI,
            allow_private=True,
            api_key=None,
            model_group="devops-review",
            levels=[1],
            rounds=1,
            prompt_tokens=100,
            max_tokens=50,
            request_timeout=10.0,
            namespace="llm",
            deployment="llm-gateway",
            estimate=True,
        )


def test_tune_command_weighs_capacity_against_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify weights follow capacity (tokens/s) divided by cost (tokens per request)."""
    settings = MagicMock()
    settings.ai = AIConfig(gateway_url="http://gateway.example.com:4000/v1")
    monkeypatch.setattr("devops_cli.commands.ai_gateway.load_settings", lambda: settings)
    monkeypatch.setattr("devops_cli.commands.ai_gateway.get_ai_api_key", lambda _s: "sk-gw")
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.fetch_model_info", lambda url, allow, key: MODEL_INFO
    )
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.deployment_gpus",
        lambda api_base, context: [
            GpuInfo(name="RTX 3090", memory_mib=24576, bandwidth_gbps=936.0)
        ],
    )
    # a: 800 tok/s at concurrency 4, 100 tokens per reply -> 8 req/s.
    # b: 100 tok/s at best, 200 tokens per reply -> 0.5 req/s.
    shapes = {
        "a": (
            [_level(1, 200), _level(4, 800)],
            _level(1, 200),
            {"engine": "vllm", "kv_cache_tokens": 20288},
        ),
        "b": (
            [_level(1, 100), _level(4, 90)],
            _level(1, 400),
            {"engine": "ollama", "kv_cache_tokens": None},
        ),
    }

    def fake_measure(spec: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
        dep_id = spec["deployments"][0]["deployment_id"]
        capacity, cost, engine = shapes[dep_id]
        return [{"deployment_id": dep_id, "engine": engine, "capacity": capacity, "cost": cost}]

    monkeypatch.setattr("devops_cli.ai.gateway_tune.measure_in_gateway_pod", fake_measure)

    result = runner.invoke(gateway_cli_app, ["tune", "--concurrency", "1,4", "--format", "json"])

    report = json.loads(result.stdout)
    # The default prompt is DEFAULT_GATEWAY_TUNE_PROMPT_TOKENS (512 tokens), capped below
    # a deployment's max_input_tokens.
    assert (
        report["prompt_tokens"],
        [d["prompt_tokens"] for d in report["deployments"]],
    ) == (512, [512, 512])
    assert (
        result.exit_code,
        report["model_group"],
        [
            (
                d["backend"],
                d["engine"],
                d["best_concurrency"],
                d["capacity_tokens_per_second"],
                d["cost_tokens_per_request"],
                d["requests_per_second"],
                d["recommended_weight"],
                d["gpus"][0]["bandwidth_gbps"],
            )
            for d in report["deployments"]
        ],
    ) == (
        0,
        "devops-review",
        [
            ("remote", "vllm", 4, 800.0, 100.0, 8.0, 16, 936.0),
            ("ollama-0", "ollama", 1, 100.0, 200.0, 0.5, 1, 936.0),
        ],
    )


def test_tune_command_estimate_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify tune command with --estimate runs without sweep container and records run."""
    settings = MagicMock()
    settings.ai = AIConfig(gateway_url=REMOTE_OPENAI)
    monkeypatch.setattr("devops_cli.commands.ai_gateway.load_settings", lambda: settings)
    monkeypatch.setattr("devops_cli.commands.ai_gateway.get_ai_api_key", lambda _s: "sk-gw")
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.fetch_model_info",
        lambda url, allow, key: MODEL_INFO[:1],
    )
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.deployment_gpus",
        lambda api_base, context: [
            GpuInfo(name="RTX 4090", memory_mib=24576, bandwidth_gbps=1008.0)
        ],
    )

    prior_run = new_run(
        Mechanism.GATEWAY_TUNE,
        setup={"levels": [1], "rounds": 1, "prompt_tokens": 512, "max_tokens": 100},
        subject={"model_group": "devops-review"},
        results={
            "model_group": "devops-review",
            "prompt_tokens": 512,
            "max_tokens": 100,
            "deployments": [
                {
                    "deployment_id": "a-baseline",
                    "backend": "remote",
                    "model": "openai/qwen2.5-coder-32b-instruct",
                    "api_base": REMOTE_OPENAI,
                    "engine": "vllm",
                    "gpus": [{"name": "RTX 3090", "memory_mib": 24576, "bandwidth_gbps": 936.0}],
                    "capacity_tokens_per_second": 468.0,
                    "cost_tokens_per_request": 100.0,
                    "best_concurrency": 4,
                }
            ],
        },
    )
    monkeypatch.setattr("devops_cli.ai.gateway_tune.load_runs", lambda mechanism=None: [prior_run])

    recorded_runs: list[Any] = []
    monkeypatch.setattr(
        "devops_cli.commands.ai_gateway.record_run",
        lambda *args, **kwargs: (
            recorded_runs.append((args, kwargs)) or MagicMock(run_id="run-123", path=Path("p"))
        ),
    )
    monkeypatch.setattr("devops_cli.commands.ai_gateway.announce_run", lambda *args, **kwargs: None)

    measure_mock = MagicMock()
    monkeypatch.setattr("devops_cli.ai.gateway_tune.measure_in_gateway_pod", measure_mock)

    result = runner.invoke(gateway_cli_app, ["tune", "--estimate", "--format", "json"])
    assert result.exit_code == 0
    assert measure_mock.call_count == 0
    assert len(recorded_runs) == 1
    report = json.loads(result.stdout)
    assert report["deployments"][0]["capacity_tokens_per_second"] == round(
        468.0 * (1008.0 / 936.0), 2
    )
    assert report["deployments"][0]["capabilities"]["probed"] is False
    assert report["deployments"][0]["capabilities"]["summary_label"] == "unmeasured"

    result_table = runner.invoke(gateway_cli_app, ["tune", "--estimate"])
    assert result_table.exit_code == 0
    assert "Capabilities" in result_table.stdout
    assert "unmeasured" in result_table.stdout


def test_tune_pool_runs_capability_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify tune_pool sends capability probes and attaches scored DeploymentCapabilities."""
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.fetch_model_info",
        lambda url, allow, key: MODEL_INFO[:1],
    )
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.deployment_gpus",
        lambda api_base, context: [
            GpuInfo(name="RTX 3090", memory_mib=24576, bandwidth_gbps=936.0)
        ],
    )

    probe_payload = {
        "json_adherence": {
            "replies": [
                '{"file": "a.py", "line": 1, "severity": "HIGH", "rule_id": "R1", "description": "d"}'
            ]
        },
        "tool_choice": {"replies": ["inspect_ast"]},
        "deep_recall": {"replies": ["CANARY-RECALL-9824"]},
        "explicit_prohibition": {
            "replies": ["SUMMARY: Code review validates system quality without defect leaks."]
        },
    }

    measured_specs: list[dict[str, Any]] = []

    def fake_measure(spec: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
        measured_specs.append(spec)
        dep_id = spec["deployments"][0]["deployment_id"]
        return [
            {
                "deployment_id": dep_id,
                "engine": {"engine": "vllm"},
                "capacity": [_level(1, 100)],
                "cost": _level(1, 100),
                "probes": probe_payload,
            }
        ]

    monkeypatch.setattr("devops_cli.ai.gateway_tune.measure_in_gateway_pod", fake_measure)

    report = tune_pool(
        gateway_url=REMOTE_OPENAI,
        allow_private=True,
        api_key=None,
        model_group="devops-review",
        levels=[1],
        rounds=1,
        prompt_tokens=100,
        max_tokens=50,
        request_timeout=10.0,
        namespace="llm",
        deployment="llm-gateway",
    )

    assert len(measured_specs) == 1
    assert "probes" in measured_specs[0]
    assert len(measured_specs[0]["probes"]) == 4

    dep = report.deployments[0]
    assert dep.capabilities.probed is True
    assert dep.capabilities.all_passed is True
    assert dep.capabilities.passed_probes_count == 4
    assert "4/4 passed" in dep.capabilities.summary_label


def test_tune_command_renders_capabilities_and_records_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify tune command table shows Capabilities column and record_run persists probe results."""
    settings = MagicMock()
    settings.ai = AIConfig(gateway_url=REMOTE_OPENAI)
    monkeypatch.setattr("devops_cli.commands.ai_gateway.load_settings", lambda: settings)
    monkeypatch.setattr("devops_cli.commands.ai_gateway.get_ai_api_key", lambda _s: "sk-gw")
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.fetch_model_info",
        lambda url, allow, key: MODEL_INFO[:1],
    )
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.deployment_gpus",
        lambda api_base, context: [
            GpuInfo(name="RTX 4090", memory_mib=24576, bandwidth_gbps=1008.0)
        ],
    )

    probe_payload = {
        "json_adherence": {
            "replies": [
                '{"file": "x.py", "line": 5, "severity": "LOW", "rule_id": "L1", "description": "desc"}'
            ]
        },
        "tool_choice": {"replies": ["inspect_ast"]},
        "deep_recall": {"replies": ["CANARY-RECALL-9824"]},
        "explicit_prohibition": {
            "replies": ["SUMMARY: Static analysis inspects code structure and idioms."]
        },
    }

    def fake_measure(spec: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
        dep_id = spec["deployments"][0]["deployment_id"]
        return [
            {
                "deployment_id": dep_id,
                "engine": {"engine": "vllm"},
                "capacity": [_level(1, 100)],
                "cost": _level(1, 100),
                "probes": probe_payload,
            }
        ]

    monkeypatch.setattr("devops_cli.ai.gateway_tune.measure_in_gateway_pod", fake_measure)

    recorded_runs: list[Any] = []
    monkeypatch.setattr(
        "devops_cli.commands.ai_gateway.record_run",
        lambda *args, **kwargs: (
            recorded_runs.append((args, kwargs)) or MagicMock(run_id="run-456", path=Path("p"))
        ),
    )
    monkeypatch.setattr("devops_cli.commands.ai_gateway.announce_run", lambda *args, **kwargs: None)

    result = runner.invoke(gateway_cli_app, ["tune", "--rounds", "1"])
    assert result.exit_code == 0
    assert "Capabilities" in result.stdout
    assert "4/4" in result.stdout

    assert len(recorded_runs) == 1
    args, kwargs = recorded_runs[0]
    results_dict = kwargs.get("results") or (args[3] if len(args) > 3 else {})
    dep_rec = results_dict["deployments"][0]
    assert dep_rec["capabilities"]["probed"] is True
    assert dep_rec["capabilities"]["probes"]["json_adherence"]["passed"] == 1


def test_tune_command_renders_capabilities_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify tune command JSON format outputs full capabilities structure."""
    settings = MagicMock()
    settings.ai = AIConfig(gateway_url=REMOTE_OPENAI)
    monkeypatch.setattr("devops_cli.commands.ai_gateway.load_settings", lambda: settings)
    monkeypatch.setattr("devops_cli.commands.ai_gateway.get_ai_api_key", lambda _s: "sk-gw")
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.fetch_model_info",
        lambda url, allow, key: MODEL_INFO[:1],
    )
    monkeypatch.setattr(
        "devops_cli.ai.gateway_tune.deployment_gpus",
        lambda api_base, context: [
            GpuInfo(name="RTX 4090", memory_mib=24576, bandwidth_gbps=1008.0)
        ],
    )

    probe_payload = {
        "json_adherence": {
            "replies": [
                '{"file": "x.py", "line": 5, "severity": "LOW", "rule_id": "L1", "description": "desc"}'
            ]
        },
        "tool_choice": {"replies": ["inspect_ast"]},
        "deep_recall": {"replies": ["CANARY-RECALL-9824"]},
        "explicit_prohibition": {
            "replies": ["SUMMARY: Static analysis inspects code structure and idioms."]
        },
    }

    def fake_measure(spec: dict[str, Any], **kwargs: Any) -> list[dict[str, Any]]:
        dep_id = spec["deployments"][0]["deployment_id"]
        return [
            {
                "deployment_id": dep_id,
                "engine": {"engine": "vllm"},
                "capacity": [_level(1, 100)],
                "cost": _level(1, 100),
                "probes": probe_payload,
            }
        ]

    monkeypatch.setattr("devops_cli.ai.gateway_tune.measure_in_gateway_pod", fake_measure)
    monkeypatch.setattr(
        "devops_cli.commands.ai_gateway.record_run",
        lambda *args, **kwargs: MagicMock(run_id="run-456", path=Path("p")),
    )
    monkeypatch.setattr("devops_cli.commands.ai_gateway.announce_run", lambda *args, **kwargs: None)

    result = runner.invoke(gateway_cli_app, ["tune", "--rounds", "1", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    caps = data["deployments"][0]["capabilities"]
    assert caps["probed"] is True
    assert caps["all_passed"] is True
    assert caps["passed_probes_count"] == 4
