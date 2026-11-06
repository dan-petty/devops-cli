"""The trace context a sandbox container and each exec carry (#702)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from devops_cli.config.constants import (
    CONST_TRACEPARENT_ENV_VAR,
    CONST_TRACESTATE_ENV_VAR,
)
from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.models import (
    SandboxDeployConfig,
    SandboxInstance,
    SandboxNetworkConfig,
)
from devops_cli.sandbox.registry import SandboxRegistry
from devops_cli.telemetry import extract_env, get_recent_spans
from tests.support.fakes.docker_engine import DockerEngineFake

_TRACE_ENV_VARS = (CONST_TRACEPARENT_ENV_VAR, CONST_TRACESTATE_ENV_VAR)


def _deploy(
    tmp_path: Path, docker_daemon: DockerEngineFake, **config: Any
) -> tuple[WorkloadSandboxEngine, SandboxDeployConfig, SandboxInstance]:
    """Deploy a sandbox on the Docker fake and return the engine, the config and the instance."""
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    engine = WorkloadSandboxEngine(registry=SandboxRegistry(tmp_path / "reg.json"))
    cfg = SandboxDeployConfig(workspace_dir=workspace, **config)
    return engine, cfg, engine.deploy(cfg)


def _created_environment(docker_daemon: DockerEngineFake) -> dict[str, str]:
    """The environment the one container was created with."""
    (created,) = (call for call in docker_daemon.calls if call.name == "containers.create")
    environment: dict[str, str] = created.kwargs["environment"]
    return environment


def _exec_environments(docker_daemon: DockerEngineFake) -> list[Any]:
    """The environment of each exec, oldest first."""
    return [
        call.kwargs["environment"]
        for call in docker_daemon.calls
        if call.name == "container.exec_run"
    ]


def _span_ids(name: str) -> list[str]:
    """The ids of the finished spans with this name, oldest first."""
    return [span["spanId"] for span in get_recent_spans() if span.get("name") == name]


def test_a_deployed_sandbox_is_parented_to_its_deploy_span(
    tmp_path: Path, docker_daemon: DockerEngineFake, tracer: Any
) -> None:
    """The container's TRACEPARENT names the deploy span; the config's env is left as it was."""
    docker_daemon.add_image("python:3.14-slim")
    _engine, cfg, _instance = _deploy(tmp_path, docker_daemon, env={"APP_MODE": "test"})
    environment = _created_environment(docker_daemon)
    child = extract_env(environment)
    assert (
        child.span_id if child else None,
        {key: environment[key] for key in environment if key not in _TRACE_ENV_VARS},
        cfg.env,
    ) == (_span_ids("sandbox.deploy")[0], {"APP_MODE": "test"}, {"APP_MODE": "test"})


def test_a_proxied_sandbox_keeps_its_proxy_variables_beside_the_trace_context(
    tmp_path: Path, docker_daemon: DockerEngineFake, tracer: Any
) -> None:
    """In a proxy mode the proxy variables are still set when the trace context is added."""
    docker_daemon.add_image("python:3.14-slim")
    proxy = "http://example.com:3128"
    network = SandboxNetworkConfig(
        mode="public_whitelist", public_whitelist=["93.184.216.34"], egress_proxy=proxy
    )
    _deploy(tmp_path, docker_daemon, network_config=network, env={"APP_MODE": "test"})
    environment = _created_environment(docker_daemon)
    child = extract_env(environment)
    assert (
        child.span_id if child else None,
        {key: environment[key] for key in environment if key not in _TRACE_ENV_VARS},
    ) == (
        _span_ids("sandbox.deploy")[0],
        {"HTTP_PROXY": proxy, "HTTPS_PROXY": proxy, "ALL_PROXY": proxy, "APP_MODE": "test"},
    )


def test_a_sandbox_deployed_with_tracing_off_gets_exactly_its_configured_env(
    tmp_path: Path, docker_daemon: DockerEngineFake, config: Callable[..., Path]
) -> None:
    """With tracing disabled the container's environment is the config's env and nothing else."""
    docker_daemon.add_image("python:3.14-slim")
    config(telemetry={"enabled": False})

    _deploy(tmp_path, docker_daemon, env={"APP_MODE": "test"})

    assert _created_environment(docker_daemon) == {"APP_MODE": "test"}


def test_each_exec_is_parented_to_its_own_exec_span(
    tmp_path: Path, docker_daemon: DockerEngineFake, tracer: Any
) -> None:
    """Two execs carry different parents, each its own `sandbox.exec` span, never the deploy span."""
    docker_daemon.add_image("python:3.14-slim")
    engine, _cfg, instance = _deploy(tmp_path, docker_daemon)

    engine.exec(instance.instance_id, ["env"])
    engine.exec(instance.instance_id, ["env"])

    contexts = [extract_env(environment) for environment in _exec_environments(docker_daemon)]
    parents = [context.span_id if context else None for context in contexts]
    assert (parents, len(set(parents)), _span_ids("sandbox.deploy")[0] in parents) == (
        _span_ids("sandbox.exec"),
        2,
        False,
    )


def test_an_exec_with_tracing_off_sends_no_environment(
    tmp_path: Path, docker_daemon: DockerEngineFake, config: Callable[..., Path]
) -> None:
    """With tracing disabled an exec passes no environment, as before."""
    docker_daemon.add_image("python:3.14-slim")
    config(telemetry={"enabled": False})
    engine, _cfg, instance = _deploy(tmp_path, docker_daemon)

    engine.exec(instance.instance_id, ["env"])

    assert _exec_environments(docker_daemon) == [None]
