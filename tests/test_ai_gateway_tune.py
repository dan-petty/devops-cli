"""`devops ai gateway tune`: measure each gateway deployment and recommend routing weights."""

from __future__ import annotations

import json
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
    discover_pool,
    gpu_bandwidth_gbps,
    gpu_inventory,
    measure_in_gateway_pod,
    recommend_weights,
)
from devops_cli.commands.ai_gateway import app as gateway_cli_app
from devops_cli.config.defaults import DEFAULT_GATEWAY_TUNE_IMAGE
from devops_cli.config.settings import AIConfig

runner = CliRunner()

VLLM = "http://vllm.llm.svc.cluster.local:8000/v1"
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
        "devops-review", "a", "openai/qwen2.5-coder-32b-instruct", VLLM, max_input=12288, weight=5
    ),
    _deployment("devops-review", "b", "ollama_chat/gpt-oss:20b", OLLAMA_0, weight=1),
    _deployment("devops-chat", "c", "ollama_chat/qwen2.5-coder:7b", OLLAMA_0),
]


class TestBench:
    """The standard-library sweep that runs inside the gateway pod."""

    def test_each_backend_is_called_through_its_openai_compatible_chat_api(self) -> None:
        """Verify vLLM keeps its /v1 base and Ollama gains one, with the provider prefix dropped."""
        assert (
            bench.chat_target("openai/qwen2.5-coder-32b-instruct", VLLM),
            bench.chat_target("ollama_chat/gpt-oss:20b", OLLAMA_0),
            bench.chat_target("ollama/bge-m3", "http://ollama.example.com:11434/"),
        ) == (
            (f"{VLLM}/chat/completions", "qwen2.5-coder-32b-instruct"),
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

    def test_engine_info_reads_vllm_kv_capacity_and_recognises_ollama(self) -> None:
        """Verify vLLM's KV-cache token capacity is read from /metrics and Ollama is detected."""
        metrics = (
            "# HELP vllm:cache_config_info Information of the LLMEngine CacheConfig\n"
            'vllm:cache_config_info{block_size="16",num_gpu_blocks="6413"} 1.0\n'
        )
        pages = {
            "http://vllm.example.com:8000/metrics": (200, metrics),
            "http://ollama.example.com:11434/metrics": (404, ""),
            "http://ollama.example.com:11434/api/version": (200, '{"version": "0.32.14"}'),
            "http://other.example.com:9000/metrics": (404, ""),
            "http://other.example.com:9000/api/version": (404, ""),
        }

        def get(url: str, timeout: float) -> tuple[int, str]:
            return pages[url]

        assert (
            bench.engine_info("http://vllm.example.com:8000/v1", get),
            bench.engine_info("http://ollama.example.com:11434", get),
            bench.engine_info("http://other.example.com:9000/v1", get),
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

    def test_measure_runs_fixed_length_capacity_levels_then_a_natural_cost_pass(self) -> None:
        """Verify capacity levels send concurrency x rounds fixed-length requests, then cost."""
        sent: list[bool] = []

        def post(url: str, body: dict[str, Any], timeout: float) -> dict[str, Any]:
            sent.append(bool(body.get("ignore_eos")))
            return {"usage": {"completion_tokens": 1}}

        results = bench.measure(
            [{"deployment_id": "a", "model": "openai/m", "api_base": VLLM}],
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
                "api_base": VLLM,
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
                json.dumps({"spec": {"selector": {"app": "vllm"}}}) if "svc" in cmd else "vllm-7c9"
            )
            return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

        monkeypatch.setattr("devops_cli.ai.gateway_tune.subprocess.run", fake_run)

        assert (
            backend_pods(OLLAMA_0, None),
            backend_pods(VLLM, "lab"),
            backend_pods("http://ollama.example.com:11434", None),
            [c[3:6] for c in calls],
        ) == (
            ("llm", ["ollama-0"]),
            ("llm", ["vllm-7c9"]),
            (None, []),
            [["get", "svc", "vllm"], ["get", "pods", "-n"]],
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

        exec(compile(script, "<bench>", "exec"), namespace)  # noqa: S102 - the script under test

        assert json.loads(printed[-1]) == []

    def test_sweep_runs_in_an_ephemeral_container_on_a_running_gateway_pod(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify the sweep attaches to a gateway pod, waits for exit and parses its logs."""
        kubectl = _FakeKubectl(exit_code=0, logs='noise\n[{"deployment_id": "a"}]')
        monkeypatch.setattr("devops_cli.ai.gateway_tune.subprocess.run", kubectl)
        monkeypatch.setattr("devops_cli.ai.gateway_tune.time.sleep", lambda _s: None)

        result = measure_in_gateway_pod(
            {"deployments": []}, namespace="llm", deployment="llm-gateway", context="lab"
        )

        debug = kubectl.called("debug")
        assert (
            result,
            debug[:5],
            debug[5:11],
            debug[-4:-1],
            "def measure(" in debug[-1],
            kubectl.called("pods")[-1],
        ) == (
            [{"deployment_id": "a"}],
            ["kubectl", "--context", "lab", "debug", "pod/llm-gateway-abc"],
            [
                "-n",
                "llm",
                "--profile=restricted",
                "--image=python:3.14-slim",
                f"--container={kubectl.container}",
                "--",
            ],
            ["--", "python", "-c"],
            True,
            "jsonpath={.items[0].metadata.name}",
        )

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
            measure_in_gateway_pod({"deployments": []}, namespace="llm", deployment="llm-gateway")

    def test_failed_sweep_reports_the_container_logs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify a non-zero exit raises with the sweep container's output."""
        kubectl = _FakeKubectl(exit_code=1, logs="SyntaxError: invalid syntax")
        monkeypatch.setattr("devops_cli.ai.gateway_tune.subprocess.run", kubectl)
        monkeypatch.setattr("devops_cli.ai.gateway_tune.time.sleep", lambda _s: None)

        with pytest.raises(GatewayTuneError, match="SyntaxError"):
            measure_in_gateway_pod({"deployments": []}, namespace="llm", deployment="llm-gateway")


class _FakeKubectl:
    """Answer the kubectl calls of one sweep: deployment, pods, debug, pod status, logs."""

    def __init__(self, *, exit_code: int, logs: str) -> None:
        self.exit_code = exit_code
        self.logs = logs
        self.calls: list[list[str]] = []
        self.container = ""
        self.polls = 0

    def called(self, verb: str) -> list[str]:
        return next(c for c in self.calls if verb in c)

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(cmd)
        if "deployment" in cmd:
            out = json.dumps({"spec": {"selector": {"matchLabels": {"app": "llm-gateway"}}}})
        elif "pods" in cmd:
            out = "llm-gateway-abc"
        elif "debug" in cmd:
            self.container = next(a for a in cmd if a.startswith("--container=")).split("=", 1)[1]
            out = ""
        elif "logs" in cmd:
            out = self.logs
        else:
            self.polls += 1
            state = (
                {"running": {}} if self.polls == 1 else {"terminated": {"exitCode": self.exit_code}}
            )
            out = json.dumps(
                {
                    "status": {
                        "ephemeralContainerStatuses": [{"name": self.container, "state": state}]
                    }
                }
            )
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")


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

    report = json.loads(result.output)
    # The default prompt is one review page for the analysis task's window (32768 tokens:
    # 68812 characters, 19660 tokens), capped below a deployment's max_input_tokens.
    assert (
        report["prompt_tokens"],
        [d["prompt_tokens"] for d in report["deployments"]],
    ) == (19660, [11059, 19660])
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
            ("vllm", "vllm", 4, 800.0, 100.0, 8.0, 16, 936.0),
            ("ollama-0", "ollama", 1, 100.0, 200.0, 0.5, 1, 936.0),
        ],
    )
