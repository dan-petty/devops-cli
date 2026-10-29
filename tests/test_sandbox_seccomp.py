"""A sandbox carries a seccomp profile that the container engine applies (#1822)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from devops_cli.docker.engine import get_engine
from devops_cli.docker.sandbox import WorkloadSandboxConfig, WorkloadSandboxRunner
from devops_cli.exceptions.sandbox import SandboxValidationError
from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.models import DEFAULT_SANDBOX_POLICY, SandboxDeployConfig, SandboxPolicy
from devops_cli.sandbox.registry import SandboxRegistry
from devops_cli.sandbox.seccomp import load_seccomp_profile
from tests.support.fakes.docker_engine import DockerEngineFake

# An allow-list profile: every system call that it does not name fails with EPERM.
_PROFILE = {
    "defaultAction": "SCMP_ACT_ERRNO",
    "architectures": ["SCMP_ARCH_X86_64"],
    "syscalls": [{"names": ["read", "write", "exit_group"], "action": "SCMP_ACT_ALLOW"}],
}
_COMPACT = json.dumps(_PROFILE, separators=(",", ":"))


def _write_profile(directory: Path, profile: Any = _PROFILE, name: str = "profile.json") -> Path:
    path = directory / name
    text = profile if isinstance(profile, str) else json.dumps(profile, indent=2)
    path.write_text(text, encoding="utf-8")
    return path


def _policy_with(path: Path) -> SandboxPolicy:
    return DEFAULT_SANDBOX_POLICY.model_copy(update={"seccomp_profile": load_seccomp_profile(path)})


def _created_security_opts(fake: DockerEngineFake) -> list[list[str]]:
    return [
        list(call.kwargs.get("security_opt") or [])
        for call in fake.calls
        if call.name == "containers.create"
    ]


def test_the_default_policy_carries_no_profile_and_declares_no_seccomp_option() -> None:
    """A policy that names no profile leaves the engine's default profile in place."""
    policy = SandboxPolicy()

    assert (policy.seccomp_profile, policy.to_docker_security_kwargs()["security_opt"]) == (
        None,
        ["no-new-privileges:true"],
    )


def test_a_profile_loads_as_its_absolute_path_and_compact_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A relative path resolves against the working directory, and the JSON loses its spaces."""
    _write_profile(tmp_path)
    monkeypatch.chdir(tmp_path)

    profile = load_seccomp_profile(Path("profile.json"))

    assert (profile.path, profile.document) == (tmp_path / "profile.json", _COMPACT)


_REFUSED_PROFILES: dict[str, tuple[Any, str]] = {
    "not JSON": ("{defaultAction: SCMP_ACT_ERRNO", "is not JSON"),
    "not an object": (["SCMP_ACT_ERRNO"], "is not a JSON object"),
    "no default action": ({"syscalls": []}, "names no defaultAction"),
    "a default action that is not text": ({"defaultAction": 1}, "names no defaultAction"),
    "allows every call by default": (
        {"defaultAction": "SCMP_ACT_ALLOW"},
        "allows every system call by default",
    ),
    "logs and allows every call by default": (
        {"defaultAction": "SCMP_ACT_LOG"},
        "allows every system call by default",
    ),
}


@pytest.mark.parametrize("case", sorted(_REFUSED_PROFILES))
def test_a_profile_that_does_not_confine_by_default_is_refused(case: str, tmp_path: Path) -> None:
    """A profile must parse, be a JSON object, and refuse the calls it does not name."""
    content, fragment = _REFUSED_PROFILES[case]
    path = _write_profile(tmp_path, content)

    with pytest.raises(SandboxValidationError) as caught:
        load_seccomp_profile(path)

    assert (fragment in caught.value.message, str(path) in caught.value.message) == (True, True)


def test_a_missing_profile_file_is_refused(tmp_path: Path) -> None:
    """A path that names no file stops the load and names the path."""
    missing = tmp_path / "absent.json"

    with pytest.raises(SandboxValidationError) as caught:
        load_seccomp_profile(missing)

    assert (str(missing) in caught.value.message, "Cannot read" in caught.value.message) == (
        True,
        True,
    )


def test_a_policy_renders_its_profile_inline_or_as_its_path(tmp_path: Path) -> None:
    """Docker takes the profile's JSON in `security_opt`; an older Podman takes its path."""
    path = _write_profile(tmp_path)
    policy = _policy_with(path)

    assert (
        policy.to_docker_security_kwargs()["security_opt"],
        policy.to_docker_security_kwargs(inline_seccomp=False)["security_opt"],
    ) == (
        ["no-new-privileges:true", f"seccomp={_COMPACT}"],
        ["no-new-privileges:true", f"seccomp={path}"],
    )


_ENGINE_VERSIONS: dict[str, tuple[str | None, bool]] = {
    "docker": (None, True),
    "podman 5.6.2": ("5.6.2", False),
    "podman 6.1.4": ("6.1.4", False),
    "podman 6.2.0-rc1": ("6.2.0-rc1", True),
    "podman 6.2.0": ("6.2.0", True),
    "podman 6.3.1": ("6.3.1", True),
    "podman with an unreadable version": ("unknown", False),
}


@pytest.mark.parametrize("case", sorted(_ENGINE_VERSIONS))
def test_the_engine_takes_an_inline_profile_on_docker_and_on_podman_from_6_2(
    case: str, docker_daemon: DockerEngineFake
) -> None:
    """Podman's compat API reads an inline profile only from 6.2.0 (containers/podman#29726)."""
    podman_version, inline = _ENGINE_VERSIONS[case]
    if podman_version is not None:
        docker_daemon.set_podman(podman_version)

    assert get_engine().accepts_inline_seccomp_profile() is inline


def _deploy_config(workspace: Path, policy: SandboxPolicy) -> SandboxDeployConfig:
    return SandboxDeployConfig(image="alpine:3", name="sec", workspace_dir=workspace, policy=policy)


@pytest.mark.parametrize(
    ("podman_version", "inline"), [(None, True), ("6.1.4", False), ("6.2.0", True)]
)
def test_both_runners_create_the_container_with_the_profile_the_engine_reads(
    podman_version: str | None,
    inline: bool,
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
    docker_daemon: DockerEngineFake,
) -> None:
    """`sandbox deploy` and the workload runner send the form that the engine takes.

    The workspace is outside `tmp_path`, which holds the fake engine's socket.
    """
    if podman_version is not None:
        docker_daemon.set_podman(podman_version)
    workspace = tmp_path_factory.mktemp("ws")
    path = _write_profile(tmp_path)
    policy = _policy_with(path)
    expected = f"seccomp={_COMPACT}" if inline else f"seccomp={path}"

    engine = WorkloadSandboxEngine(registry=SandboxRegistry(tmp_path / "reg.json"))
    engine.deploy(_deploy_config(workspace, policy))
    runner = WorkloadSandboxRunner(
        WorkloadSandboxConfig(
            workspace_dir=workspace, command=["true"], image="alpine:3", policy=policy
        )
    )
    workload_kwargs = runner._build_create_kwargs(workspace)

    assert (_created_security_opts(docker_daemon), workload_kwargs["security_opt"]) == (
        [["no-new-privileges:true", expected]],
        ["no-new-privileges:true", expected],
    )


def test_the_engine_is_asked_for_its_version_only_when_the_policy_has_a_profile(
    tmp_path: Path, tmp_path_factory: pytest.TempPathFactory, docker_daemon: DockerEngineFake
) -> None:
    """A sandbox with no profile sends no `GET /version` for the seccomp form."""
    workspace = tmp_path_factory.mktemp("ws")
    engine = WorkloadSandboxEngine(registry=SandboxRegistry(tmp_path / "reg.json"))

    engine.deploy(_deploy_config(workspace, SandboxPolicy()))
    without_profile = [call.name for call in docker_daemon.calls]
    engine.deploy(_deploy_config(workspace, _policy_with(_write_profile(tmp_path))))

    assert ("version" in without_profile, "version" in [c.name for c in docker_daemon.calls]) == (
        False,
        True,
    )


_COMMANDS: dict[str, list[str]] = {
    "sandbox deploy": ["sandbox", "deploy", "--dry-run"],
    "docker sandbox": ["docker", "sandbox", "--dry-run"],
    "test sandbox": ["test", "sandbox", "--dry-run"],
}


def _argv(command: str, workspace: Path, profile: Path) -> list[str]:
    argv = [*_COMMANDS[command], "--workspace", str(workspace), "--seccomp-profile", str(profile)]
    return argv if command == "sandbox deploy" else [*argv, "true"]


@pytest.mark.parametrize("command", sorted(_COMMANDS))
def test_each_sandbox_command_names_the_profile_in_its_dry_run(
    command: str, tmp_path: Path, cli: Any
) -> None:
    """The dry run sends nothing and names the profile that the container would get."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    path = _write_profile(tmp_path)

    result = cli(_argv(command, workspace, path))

    assert (result.exit_code, f'"seccomp_profile": "{path}"' in result.output) == (0, True)


@pytest.mark.parametrize("command", sorted(_COMMANDS))
def test_each_sandbox_command_refuses_a_profile_that_allows_every_call(
    command: str, tmp_path: Path, cli: Any
) -> None:
    """A bad profile stops the command with one error line and no traceback."""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    path = _write_profile(tmp_path, {"defaultAction": "SCMP_ACT_ALLOW"})

    result = cli(_argv(command, workspace, path))

    assert (
        result.exit_code,
        "allows every system call by default" in result.output,
        "Traceback" in result.output,
    ) == (SandboxValidationError.exit_code, True, False)
