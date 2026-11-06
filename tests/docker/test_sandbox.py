"""Tests for the isolated Dockerized workload sandbox runner (`docker/sandbox.py`).

The runner runs on `docker_daemon`, the in-memory Docker engine of
`tests/support/fakes/docker_engine.py`. A test scripts what the container prints and exits with,
and reads the container creation and removal from the fake's recorded calls.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.constants import (
    CONST_TRACEPARENT_ENV_VAR,
    CONST_TRACESTATE_ENV_VAR,
)
from devops_cli.config.defaults import DEFAULT_SANDBOX_PIDS_LIMIT
from devops_cli.docker.sandbox import (
    WorkloadSandboxConfig,
    WorkloadSandboxRunner,
)
from devops_cli.exceptions.docker import DockerSandboxError
from devops_cli.sandbox.models import SandboxNetworkConfig
from devops_cli.telemetry import extract_env, get_recent_spans
from tests.support.fakes.dns import DnsFake
from tests.support.fakes.docker_engine import DockerEngineFake


@pytest.fixture(autouse=True)
def _every_name_is_public(dns: DnsFake) -> None:
    """Resolve every external name to one public address, as the whitelist checks need."""
    dns.answer_every_name()


_TRACE_ENV_VARS = (CONST_TRACEPARENT_ENV_VAR, CONST_TRACESTATE_ENV_VAR)


def test_sandbox_config_defaults(tmp_path: Path) -> None:
    """Test WorkloadSandboxConfig default values and volume mapping."""
    cfg = WorkloadSandboxConfig(
        workspace_dir=tmp_path,
        command=["pytest", "-v"],
    )
    assert cfg.image == "python:3.14-slim"
    assert cfg.memory_limit == "2g"
    assert cfg.cpu_limit == 2.0
    assert cfg.network_mode == "none"
    assert cfg.rootless is True
    assert cfg.read_only is True


def _created(engine: DockerEngineFake) -> dict[str, Any]:
    """The arguments of the one container creation that reached the engine."""
    (create,) = [call for call in engine.calls if call.name == "containers.create"]
    return {"image": create.args[0], **create.kwargs}


def test_sandbox_runner_docker_execution_success(
    tmp_path: Path, docker_daemon: DockerEngineFake
) -> None:
    """A sandboxed command runs to its exit, its output is read, and its container is removed."""
    docker_daemon.script_every_run(stdout=b"sandbox-ok\n")
    cfg = WorkloadSandboxConfig(
        workspace_dir=tmp_path,
        command=["python3", "-c", "print('sandbox-ok')"],
        image="alpine:3",
    )

    res = WorkloadSandboxRunner(cfg).run()

    create_kwargs = _created(docker_daemon)
    removals = [call for call in docker_daemon.calls if call.name == "api.remove_container"]
    assert (res.exit_code, res.stdout, docker_daemon.container_state) == (0, "sandbox-ok\n", {})
    assert [(call.args, call.kwargs["force"]) for call in removals] == [((res.container_id,), True)]
    assert (
        create_kwargs.get("cap_drop"),
        create_kwargs.get("security_opt"),
        create_kwargs.get("pids_limit"),
    ) == (["ALL"], ["no-new-privileges:true"], 256)


def test_sandbox_runner_docker_execution_failure(
    tmp_path: Path, docker_daemon: DockerEngineFake
) -> None:
    """A failing command gives its exit code and its stderr, and its container is removed."""
    docker_daemon.script_every_run(stderr=b"Error occurred", exit_code=1)
    cfg = WorkloadSandboxConfig(workspace_dir=tmp_path, command=["exit", "1"], image="alpine:3")

    res = WorkloadSandboxRunner(cfg).run()

    assert (res.exit_code, res.stderr, docker_daemon.container_state) == (1, "Error occurred", {})


def test_sandbox_runner_env_and_hardening_propagation(
    tmp_path: Path, docker_daemon: DockerEngineFake
) -> None:
    """Config env and container hardening reach the Engine API creation payload."""
    docker_daemon.script_every_run(stdout=b"hello")
    cfg = WorkloadSandboxConfig(
        workspace_dir=tmp_path,
        command=["python3", "-c", "print('hello')"],
        image="alpine:3",
        env={"TEST_VAR": "custom_val", "API_KEY": "secret123"},
    )

    res = WorkloadSandboxRunner(cfg).run()

    create_kwargs = _created(docker_daemon)
    environment = create_kwargs["environment"]
    assert res.exit_code == 0
    assert (
        {key: environment[key] for key in environment if key not in _TRACE_ENV_VARS},
        create_kwargs["cap_drop"],
        create_kwargs["security_opt"],
        create_kwargs["pids_limit"],
        create_kwargs["network_mode"],
    ) == (
        {"TEST_VAR": "custom_val", "API_KEY": "secret123"},
        ["ALL"],
        ["no-new-privileges:true"],
        DEFAULT_SANDBOX_PIDS_LIMIT,
        "none",
    )


def test_workload_sandbox_runner_exclude_home_dir(tmp_path: Path) -> None:
    """Verify WorkloadSandboxRunner enforces exclude_home_dir preference."""
    cfg_home = WorkloadSandboxConfig(workspace_dir=Path.home(), command=["echo", "hi"])
    runner_default = WorkloadSandboxRunner(cfg_home)
    assert runner_default.exclude_home_dir is True
    with pytest.raises(DockerSandboxError, match="home directory"):
        runner_default.run()

    cfg_subhome = WorkloadSandboxConfig(
        workspace_dir=Path.home() / "some_nested_dir",
        command=["echo", "hi"],
    )
    runner_sub = WorkloadSandboxRunner(cfg_subhome)
    with pytest.raises(DockerSandboxError, match="home directory"):
        runner_sub.run()

    # When exclude_home_dir is explicitly disabled:
    runner_allow = WorkloadSandboxRunner(cfg_home, exclude_home_dir=False)
    assert runner_allow.exclude_home_dir is False
    # Home root is still forbidden
    with pytest.raises(DockerSandboxError, match="home directory"):
        runner_allow.run()


# ─────────────────────────────────────────────────────────────────────────────
# Trace context in workload containers (#702)
# ─────────────────────────────────────────────────────────────────────────────


def _environment_of_run(cfg: WorkloadSandboxConfig, engine: DockerEngineFake) -> dict[str, str]:
    """Run a workload on the fake engine and return the environment its container was created with."""
    engine.script_every_run()
    WorkloadSandboxRunner(cfg).run()
    environment: dict[str, str] = _created(engine)["environment"]
    return environment


def test_a_workload_is_parented_to_its_run_span(
    tmp_path: Path, docker_daemon: DockerEngineFake, tracer: Any
) -> None:
    """The container's TRACEPARENT names the run span; the config's env is left as it was."""
    cfg = WorkloadSandboxConfig(
        workspace_dir=tmp_path, command=["env"], image="alpine:3", env={"APP_MODE": "test"}
    )
    environment = _environment_of_run(cfg, docker_daemon)
    child = extract_env(environment)
    run_spans = [
        span["spanId"]
        for span in get_recent_spans()
        if span.get("name") == "docker.workload_sandbox.run"
    ]
    assert (
        child.span_id if child else None,
        {key: environment[key] for key in environment if key not in _TRACE_ENV_VARS},
        cfg.env,
    ) == (run_spans[0], {"APP_MODE": "test"}, {"APP_MODE": "test"})


def test_a_proxied_workload_keeps_its_proxy_variables_beside_the_trace_context(
    tmp_path: Path, docker_daemon: DockerEngineFake, tracer: Any
) -> None:
    """In a proxy mode the proxy variables are still set when the trace context is added."""
    proxy = "http://example.com:3128"
    cfg = WorkloadSandboxConfig(
        workspace_dir=tmp_path,
        command=["env"],
        image="alpine:3",
        env={"APP_MODE": "test"},
        network_config=SandboxNetworkConfig(
            mode="public_whitelist", public_whitelist=["93.184.216.34"], egress_proxy=proxy
        ),
    )
    environment = _environment_of_run(cfg, docker_daemon)
    assert (
        extract_env(environment) is not None,
        {key: environment[key] for key in environment if key not in _TRACE_ENV_VARS},
    ) == (
        True,
        {"HTTP_PROXY": proxy, "HTTPS_PROXY": proxy, "ALL_PROXY": proxy, "APP_MODE": "test"},
    )


def test_a_workload_run_with_tracing_off_gets_exactly_its_configured_env(
    tmp_path: Path, docker_daemon: DockerEngineFake, config: Callable[..., Path]
) -> None:
    """With tracing disabled the container's environment is the config's env and nothing else."""
    config(telemetry={"enabled": False})
    cfg = WorkloadSandboxConfig(
        workspace_dir=tmp_path, command=["env"], image="alpine:3", env={"APP_MODE": "test"}
    )

    assert _environment_of_run(cfg, docker_daemon) == {"APP_MODE": "test"}
