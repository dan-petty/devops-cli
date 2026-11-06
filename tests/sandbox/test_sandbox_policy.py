"""The sandbox security policy and the controls each runner declares and sends."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from devops_cli.config.constants import (
    CONST_SANDBOX_DOCKER_INTERNAL_NET,
)
from devops_cli.config.defaults import DEFAULT_SANDBOX_IMAGE
from devops_cli.docker.sandbox import (
    WorkloadSandboxConfig,
    WorkloadSandboxRunner,
    resolve_sandbox_user,
)
from devops_cli.exceptions.docker import DockerSandboxError
from devops_cli.exceptions.sandbox import (
    SandboxValidationError,
)
from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.models import (
    SandboxDeployConfig,
    SandboxPolicy,
)
from devops_cli.sandbox.registry import SandboxRegistry
from tests.support.fakes.docker_engine import DockerEngineFake


def test_sandbox_policy_frozen_immutability_and_kwargs() -> None:
    """Verify SandboxPolicy defaults, immutability, extra forbid, and security kwargs generation."""
    policy = SandboxPolicy()
    assert (
        policy.cap_drop,
        policy.security_opt,
        policy.pids_limit,
        policy.read_only,
        policy.tmpfs,
    ) == (
        ("ALL",),
        ("no-new-privileges:true",),
        256,
        True,
        {"/tmp": "size=64m,noexec"},  # nosec B108  # the in-container mount, under test
    )

    with pytest.raises(ValidationError) as raised:
        # Frozen models cannot be mutated
        policy.pids_limit = 512  # type: ignore[misc]
    assert len(raised.value.errors()) > 0

    with pytest.raises(ValidationError) as raised:
        # Undefined parameters are forbidden
        SandboxPolicy(extra_param=123)  # type: ignore[call-arg]
    assert len(raised.value.errors()) > 0

    sec_kwargs = policy.to_docker_security_kwargs()
    assert (
        sec_kwargs,
        policy.to_docker_security_kwargs(read_only=False)["read_only"],
    ) == (
        {
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges:true"],
            "pids_limit": 256,
            "read_only": True,
            "tmpfs": {"/tmp": "size=64m,noexec"},  # nosec B108  # in-container, under test
        },
        False,
    )


def test_sandbox_policy_identical_security_kwargs_across_builders(
    tmp_path: Path, docker_daemon: DockerEngineFake
) -> None:
    """Verify that WorkloadSandboxEngine and WorkloadSandboxRunner produce identical security kwargs."""
    docker_daemon.add_image(DEFAULT_SANDBOX_IMAGE)
    policy = SandboxPolicy(read_only=True)
    deploy_cfg = SandboxDeployConfig(
        workspace_dir=_workspace(tmp_path), read_only=True, policy=policy
    )
    workload_cfg = WorkloadSandboxConfig(
        workspace_dir=_workspace(tmp_path / "workload"),
        command=["sleep", "1"],
        read_only=True,
        policy=policy,
    )

    WorkloadSandboxEngine(registry=SandboxRegistry(tmp_path / "reg.json")).deploy(deploy_cfg)
    WorkloadSandboxRunner(workload_cfg).run()

    engine_kwargs, docker_kwargs = _create_kwargs(docker_daemon)
    security_keys = ("cap_drop", "security_opt", "pids_limit", "read_only", "tmpfs")
    expected_security = policy.to_docker_security_kwargs(read_only=True)
    assert (
        {k: engine_kwargs[k] for k in security_keys},
        {k: docker_kwargs[k] for k in security_keys},
    ) == (expected_security, expected_security)


# Each case is a policy, a network mode, and the Docker network that mode runs on.
_DECLARED_CONTROL_CASES = {
    "default": (SandboxPolicy(), "isolated", "none"),
    "default bridge": (SandboxPolicy(), "bridge", "bridge"),
    "small pid cap in the sandbox namespace": (
        SandboxPolicy(pids_limit=16),
        "sandbox_namespace",
        CONST_SANDBOX_DOCKER_INTERNAL_NET,
    ),
}


def _workspace(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _create_kwargs(docker_daemon: DockerEngineFake) -> tuple[dict[str, Any], dict[str, Any]]:
    """The arguments of the two create calls: the engine's deploy, then the runner's run."""
    deploy, workload = (
        dict(call.kwargs) for call in docker_daemon.calls if call.name == "containers.create"
    )
    return deploy, workload


def _declared_pair(
    workspace: Path, policy: SandboxPolicy, network_mode: str, workload_read_only: bool = True
) -> tuple[SandboxDeployConfig, WorkloadSandboxConfig]:
    """The deploy and workload configs for one policy and network mode.

    A deployment must keep its root read-only, so only the workload can be made writable.
    """
    return (
        SandboxDeployConfig(workspace_dir=workspace, policy=policy, network_mode=network_mode),
        WorkloadSandboxConfig(
            workspace_dir=workspace,
            command=["true"],
            policy=policy,
            network_mode=network_mode,
            read_only=workload_read_only,
        ),
    )


def test_the_declared_controls_of_the_default_policy_are_the_hardening_the_engine_is_told(
    tmp_path: Path,
) -> None:
    """The default policy declares dropped capabilities, no-new-privileges, a pid cap, a read-only
    root, a noexec /tmp, no network and a read-only workspace mount, and the two runners declare
    the same."""
    deploy_cfg, workload_cfg = _declared_pair(tmp_path, SandboxPolicy(), "isolated")
    expected = {
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "pids_limit": 256,
        "read_only": True,
        "tmpfs": {"/tmp": "size=64m,noexec"},  # nosec B108  # the in-container mount, under test
        "network_mode": "none",
        "workspace_mount_mode": "ro",
    }

    assert (
        WorkloadSandboxEngine.declared_controls(deploy_cfg),
        WorkloadSandboxRunner(workload_cfg).declared_controls(),
    ) == (expected, expected)


def test_a_writable_workload_declares_a_writable_root_and_workspace(tmp_path: Path) -> None:
    """The workload runner's read-only flag reaches the declared root filesystem and the declared
    mode of the workspace mount."""
    cfg = WorkloadSandboxConfig(workspace_dir=tmp_path, command=["true"], read_only=False)

    declared = WorkloadSandboxRunner(cfg).declared_controls()

    assert declared["read_only"] is False
    assert declared["workspace_mount_mode"] == "rw"


@pytest.mark.parametrize(
    ("policy", "network_mode", "docker_network"),
    [pytest.param(*case, id=name) for name, case in _DECLARED_CONTROL_CASES.items()],
)
def test_each_runner_declares_the_same_controls_for_the_same_policy(
    tmp_path: Path, policy: SandboxPolicy, network_mode: str, docker_network: str
) -> None:
    """The deploy engine and the workload runner declare identical controls, on the network
    the mode runs on."""
    deploy_cfg, workload_cfg = _declared_pair(tmp_path, policy, network_mode)

    deploy_controls = WorkloadSandboxEngine.declared_controls(deploy_cfg)

    assert (
        WorkloadSandboxRunner(workload_cfg).declared_controls(),
        deploy_controls["network_mode"],
    ) == (deploy_controls, docker_network)


def _controls_sent(create_kwargs: dict[str, Any], declared: dict[str, Any]) -> dict[str, Any]:
    """The declared controls as a create call carried them, the mount mode read off the
    workspace volume."""
    (workspace_mount,) = create_kwargs["volumes"].values()
    sent = {**create_kwargs, "workspace_mount_mode": workspace_mount["mode"]}
    return {key: sent[key] for key in declared}


@pytest.mark.parametrize("workload_read_only", [True, False], ids=["read-only", "writable"])
@pytest.mark.parametrize(
    ("policy", "network_mode", "docker_network"),
    [pytest.param(*case, id=name) for name, case in _DECLARED_CONTROL_CASES.items()],
)
def test_each_runner_creates_its_container_with_the_controls_it_declares(
    tmp_path: Path,
    docker_daemon: DockerEngineFake,
    policy: SandboxPolicy,
    network_mode: str,
    docker_network: str,
    workload_read_only: bool,
) -> None:
    """The create call each runner sends the engine carries every declared control unchanged,
    the workspace mount mode among them, and no control the engine would reject."""
    docker_daemon.add_image(DEFAULT_SANDBOX_IMAGE)
    deploy_cfg, workload_cfg = _declared_pair(
        _workspace(tmp_path), policy, network_mode, workload_read_only
    )

    WorkloadSandboxEngine(registry=SandboxRegistry(tmp_path / "reg.json")).deploy(deploy_cfg)
    WorkloadSandboxRunner(workload_cfg).run()

    deploy_sent, workload_sent = _create_kwargs(docker_daemon)
    deploy_declared = WorkloadSandboxEngine.declared_controls(deploy_cfg)
    workload_declared = WorkloadSandboxRunner(workload_cfg).declared_controls()
    assert _controls_sent(deploy_sent, deploy_declared) == deploy_declared
    assert _controls_sent(workload_sent, workload_declared) == workload_declared
    assert deploy_declared["network_mode"] == docker_network
    assert deploy_declared["workspace_mount_mode"] == "ro"
    assert workload_declared["workspace_mount_mode"] == ("ro" if workload_read_only else "rw")
    assert "workspace_mount_mode" not in deploy_sent
    assert "workspace_mount_mode" not in workload_sent


def test_declared_controls_ask_the_engine_nothing(
    tmp_path: Path, docker_daemon: DockerEngineFake
) -> None:
    """Declaring the controls looks up no rootless user, provisions no network and injects no
    trace, so the audit and the dry runs make no engine request."""
    deploy_cfg, workload_cfg = _declared_pair(tmp_path, SandboxPolicy(), "sandbox_namespace")

    controls = (
        WorkloadSandboxEngine.declared_controls(deploy_cfg),
        WorkloadSandboxRunner(workload_cfg).declared_controls(),
    )

    assert docker_daemon.calls == []
    assert all("environment" not in declared and "user" not in declared for declared in controls)


@pytest.mark.usefixtures("public_dns")
@pytest.mark.parametrize(
    ("mode", "whitelist"),
    [
        ("public_whitelist", {"public_whitelist": ["example.com"]}),
        ("local_whitelist", {"local_whitelist": ["http://localhost:8080"]}),
    ],
)
def test_a_whitelist_without_an_egress_proxy_declares_its_network_and_refuses_to_run(
    tmp_path: Path, docker_daemon: DockerEngineFake, mode: str, whitelist: dict[str, list[str]]
) -> None:
    """Declaring is not running: the declared network of a whitelist mode is reported, while
    creating the container still needs the proxy that enforces the whitelist."""
    workspace = _workspace(tmp_path)
    deploy_cfg = SandboxDeployConfig(workspace_dir=workspace, network_mode=mode, **whitelist)
    workload_cfg = WorkloadSandboxConfig(
        workspace_dir=workspace, command=["true"], network_mode=mode, **whitelist
    )

    declared = (
        WorkloadSandboxEngine.declared_controls(deploy_cfg)["network_mode"],
        WorkloadSandboxRunner(workload_cfg).declared_controls()["network_mode"],
    )
    with pytest.raises(SandboxValidationError, match="egress proxy"):
        WorkloadSandboxEngine(registry=SandboxRegistry(tmp_path / "reg.json")).deploy(deploy_cfg)
    with pytest.raises(DockerSandboxError, match="egress proxy"):
        WorkloadSandboxRunner(workload_cfg).run()

    assert declared == (CONST_SANDBOX_DOCKER_INTERNAL_NET, CONST_SANDBOX_DOCKER_INTERNAL_NET)
    assert "containers.create" not in docker_daemon.call_names()


def _printed_declared_controls(response: Any) -> dict[str, Any]:
    """The declared_controls a dry run printed, parsed from its JSON response."""
    for line in response.output.splitlines():
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                data = json.loads(line)
                if "declared_controls" in data:
                    return data["declared_controls"]
                if "details" in data and "declared_controls" in data["details"]:
                    return data["details"]["declared_controls"]
            except Exception:
                continue
    if "Command response:\n" in response.output:
        printed: dict[str, Any] = json.loads(response.output.split("Command response:\n")[1])
        controls: dict[str, Any] = printed["details"]["declared_controls"]
        return controls
    raise ValueError(f"Could not parse declared_controls from output: {response.output}")


def test_both_dry_runs_print_the_controls_without_asking_the_engine(
    tmp_path: Path, docker_daemon: DockerEngineFake, cli: Any
) -> None:
    """`devops sandbox deploy --dry-run` and `devops docker sandbox --dry-run` print the same
    declared controls for the same flags and make no engine request."""
    deploy = cli("sandbox", "deploy", "--workspace", tmp_path, "--read-only", "--dry-run")
    workload = cli("docker", "sandbox", "--workspace", tmp_path, "--read-only", "--dry-run", "true")

    deploy_controls = _printed_declared_controls(deploy)
    assert (deploy.exit_code, workload.exit_code) == (0, 0)
    assert deploy_controls == _printed_declared_controls(workload)
    assert (deploy_controls["pids_limit"], deploy_controls["network_mode"]) == (256, "none")
    assert docker_daemon.calls == []


@pytest.mark.parametrize(
    ("security_options", "rootless_user"),
    [(["name=rootless"], "0:0"), ([], f"{os.getuid()}:{os.getgid()}")],
    ids=["rootless-engine", "rootful-engine"],
)
def test_the_sandbox_user_follows_the_engine_mode(
    docker_daemon: DockerEngineFake, security_options: list[str], rootless_user: str
) -> None:
    """The user is 0:0 on a rootless engine and uid:gid on a rootful one, and none for --root."""
    docker_daemon.info_data["SecurityOptions"] = security_options

    assert (resolve_sandbox_user(rootless=True), resolve_sandbox_user(rootless=False)) == (
        rootless_user,
        None,
    )


def test_sandbox_create_kwargs_omits_user_when_running_as_root(
    tmp_path: Path, docker_daemon: DockerEngineFake
) -> None:
    """When rootless=False (--root), create kwargs omits the 'user' key."""
    docker_daemon.add_image(DEFAULT_SANDBOX_IMAGE)
    policy = SandboxPolicy(read_only=True)
    deploy_cfg = SandboxDeployConfig(
        workspace_dir=_workspace(tmp_path), read_only=True, policy=policy, rootless=False
    )
    workload_cfg = WorkloadSandboxConfig(
        workspace_dir=_workspace(tmp_path / "workload"),
        command=["sleep", "1"],
        read_only=True,
        policy=policy,
        rootless=False,
    )

    WorkloadSandboxEngine(registry=SandboxRegistry(tmp_path / "reg.json")).deploy(deploy_cfg)
    WorkloadSandboxRunner(workload_cfg).run()

    engine_kwargs, docker_kwargs = _create_kwargs(docker_daemon)
    assert ("user" in engine_kwargs, "user" in docker_kwargs) == (False, False)
