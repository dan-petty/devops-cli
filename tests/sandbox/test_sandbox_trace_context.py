"""The trace context a sandbox container and each exec carry (#702)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from devops_cli.config.constants import (
    CONST_TRACEPARENT_ENV_VAR,
    CONST_TRACESTATE_ENV_VAR,
)
from devops_cli.config.settings import TelemetryConfig
from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.models import (
    SandboxDeployConfig,
    SandboxInstance,
    SandboxNetworkConfig,
)
from devops_cli.sandbox.registry import SandboxRegistry
from devops_cli.telemetry import (
    extract_env,
    get_recent_spans,
    reset_tracer,
)

# ─────────────────────────────────────────────────────────────────────────────
# Trace context in sandbox containers and execs (#702)
# ─────────────────────────────────────────────────────────────────────────────

_TRACE_ENV_VARS = (CONST_TRACEPARENT_ENV_VAR, CONST_TRACESTATE_ENV_VAR)


def _deploy_with_mock_engine(
    tmp_path: Path, docker_engine: Any, **config: Any
) -> tuple[WorkloadSandboxEngine, SandboxDeployConfig, SandboxInstance, MagicMock]:
    """Deploy a sandbox through a mocked Engine API client and return what it was handed."""
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    engine = WorkloadSandboxEngine(registry=SandboxRegistry(tmp_path / "reg.json"))
    container = MagicMock()
    container.id = "cont-trace-1"
    container.exec_run.return_value = (0, b"")
    client = MagicMock()
    client.containers.create.return_value = container
    client.containers.get.return_value = container
    cfg = SandboxDeployConfig(workspace_dir=workspace, **config)
    with docker_engine(client):
        instance = engine.deploy(cfg)
    return engine, cfg, instance, client


def _span_ids(name: str) -> list[str]:
    """The ids of the finished spans with this name, oldest first."""
    return [span["spanId"] for span in get_recent_spans() if span.get("name") == name]


def test_a_deployed_sandbox_is_parented_to_its_deploy_span(
    tmp_path: Path, docker_engine: Any, tracer: Any
) -> None:
    """The container's TRACEPARENT names the deploy span; the config's env is left as it was."""
    _engine, cfg, _instance, client = _deploy_with_mock_engine(
        tmp_path, docker_engine, env={"APP_MODE": "test"}
    )
    environment = client.containers.create.call_args.kwargs["environment"]
    child = extract_env(environment)
    assert (
        child.span_id if child else None,
        {key: environment[key] for key in environment if key not in _TRACE_ENV_VARS},
        cfg.env,
    ) == (_span_ids("sandbox.deploy")[0], {"APP_MODE": "test"}, {"APP_MODE": "test"})


def test_a_proxied_sandbox_keeps_its_proxy_variables_beside_the_trace_context(
    tmp_path: Path, docker_engine: Any, tracer: Any
) -> None:
    """In a proxy mode the proxy variables are still set when the trace context is added."""
    proxy = "http://example.com:3128"
    network = SandboxNetworkConfig(
        mode="public_whitelist", public_whitelist=["93.184.216.34"], egress_proxy=proxy
    )
    _engine, _cfg, _instance, client = _deploy_with_mock_engine(
        tmp_path, docker_engine, network_config=network, env={"APP_MODE": "test"}
    )
    environment = client.containers.create.call_args.kwargs["environment"]
    child = extract_env(environment)
    assert (
        child.span_id if child else None,
        {key: environment[key] for key in environment if key not in _TRACE_ENV_VARS},
    ) == (
        _span_ids("sandbox.deploy")[0],
        {"HTTP_PROXY": proxy, "HTTPS_PROXY": proxy, "ALL_PROXY": proxy, "APP_MODE": "test"},
    )


def test_a_sandbox_deployed_with_tracing_off_gets_exactly_its_configured_env(
    tmp_path: Path, docker_engine: Any
) -> None:
    """With tracing disabled the container's environment is the config's env and nothing else."""
    with patch(
        "devops_cli.telemetry.tracer._resolve_telemetry_settings",
        return_value=TelemetryConfig(enabled=False),
    ):
        reset_tracer()
        _engine, _cfg, _instance, client = _deploy_with_mock_engine(
            tmp_path, docker_engine, env={"APP_MODE": "test"}
        )
        reset_tracer()
    assert client.containers.create.call_args.kwargs["environment"] == {"APP_MODE": "test"}


def test_each_exec_is_parented_to_its_own_exec_span(
    tmp_path: Path, docker_engine: Any, tracer: Any
) -> None:
    """Two execs carry different parents, each its own `sandbox.exec` span, never the deploy span."""
    engine, _cfg, instance, client = _deploy_with_mock_engine(tmp_path, docker_engine)
    with docker_engine(client):
        engine.exec(instance.instance_id, ["env"])
        engine.exec(instance.instance_id, ["env"])
    contexts = [
        extract_env(exec_call.kwargs["environment"])
        for exec_call in client.containers.get.return_value.exec_run.call_args_list
    ]
    parents = [context.span_id if context else None for context in contexts]
    assert (parents, len(set(parents)), _span_ids("sandbox.deploy")[0] in parents) == (
        _span_ids("sandbox.exec"),
        2,
        False,
    )


def test_an_exec_with_tracing_off_sends_no_environment(tmp_path: Path, docker_engine: Any) -> None:
    """With tracing disabled an exec passes no environment, as before."""
    with patch(
        "devops_cli.telemetry.tracer._resolve_telemetry_settings",
        return_value=TelemetryConfig(enabled=False),
    ):
        reset_tracer()
        engine, _cfg, instance, client = _deploy_with_mock_engine(tmp_path, docker_engine)
        with docker_engine(client):
            engine.exec(instance.instance_id, ["env"])
        reset_tracer()
    exec_run = client.containers.get.return_value.exec_run
    assert exec_run.call_args.kwargs["environment"] is None
