"""The workspaces a sandbox may mount, and the refusals before any engine call."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.config.constants import (
    CONST_X11_SOCKET_DIR,
)
from devops_cli.docker.sandbox import WorkloadSandboxConfig, WorkloadSandboxRunner
from devops_cli.exceptions.docker import DockerSandboxError
from devops_cli.exceptions.sandbox import (
    SandboxValidationError,
)
from devops_cli.sandbox.engine import WorkloadSandboxEngine
from devops_cli.sandbox.models import (
    SandboxDeployConfig,
)
from devops_cli.sandbox.registry import SandboxRegistry
from tests.web_fakes import scripted_resolver


def test_sandbox_workspace_validation_forbidden_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Engine rejects forbidden root paths, user home, and sensitive dirs."""
    engine = WorkloadSandboxEngine(registry=SandboxRegistry(tmp_path / "reg.json"))

    # Sensitive paths
    for forbidden in ["/", "/etc", "/usr", "/bin"]:
        cfg = SandboxDeployConfig(workspace_dir=Path(forbidden))
        with pytest.raises(SandboxValidationError, match=r"forbidden|symbolic link"):
            engine.validate_workspace_dir(cfg.workspace_dir)

    # Symlink workspace
    target = tmp_path / "real_dir"
    target.mkdir()
    symlink_dir = tmp_path / "symlink_dir"
    symlink_dir.symlink_to(target)

    cfg_symlink = SandboxDeployConfig(workspace_dir=symlink_dir)
    with pytest.raises(SandboxValidationError, match="symbolic link"):
        engine.validate_workspace_dir(cfg_symlink.workspace_dir)

    # The directory holding the engine socket DOCKER_HOST names
    monkeypatch.setenv("DOCKER_HOST", f"unix://{tmp_path}/var/run/docker.sock")
    cfg_sock = SandboxDeployConfig(workspace_dir=tmp_path / "var" / "run")
    with pytest.raises(SandboxValidationError, match="container engine"):
        engine.validate_workspace_dir(cfg_sock.workspace_dir)
    monkeypatch.delenv("DOCKER_HOST")

    # Sensitive subpath (.git, .ssh, .kube, .aws)
    git_path = tmp_path / ".git"
    git_path.mkdir()
    cfg_git = SandboxDeployConfig(workspace_dir=git_path)
    with pytest.raises(SandboxValidationError, match="credential or repository"):
        engine.validate_workspace_dir(cfg_git.workspace_dir)


def _run_docker_sandbox(workspace: Path, tmp_path: Path) -> None:
    """Run a workload as `devops docker sandbox` and `devops test sandbox` do."""

    config = WorkloadSandboxConfig(workspace_dir=workspace, command=["true"])
    WorkloadSandboxRunner(config, exclude_home_dir=True).run()


def _deploy_sandbox(workspace: Path, tmp_path: Path) -> None:
    """Deploy a sandbox as `devops sandbox deploy` does."""
    registry = SandboxRegistry(tmp_path / "reg.json")
    engine = WorkloadSandboxEngine(registry=registry, exclude_home_dir=True)
    engine.deploy(SandboxDeployConfig(workspace_dir=workspace))


_SANDBOX_RUNNERS: dict[str, tuple[Any, type[Exception]]] = {
    "docker-sandbox": (_run_docker_sandbox, DockerSandboxError),
    "sandbox-deploy": (_deploy_sandbox, SandboxValidationError),
}


def _run_docker_sandbox_dry_run(workspace: Path, tmp_path: Path) -> Any:
    """Run `devops docker sandbox --dry-run` and return its result."""
    from devops_cli.commands.docker import app as docker_app

    return CliRunner().invoke(
        docker_app, ["sandbox", "--dry-run", "--workspace", str(workspace), "true"]
    )


def _run_test_sandbox_dry_run(workspace: Path, tmp_path: Path) -> Any:
    """Run `devops test sandbox --dry-run` and return its result."""
    from devops_cli.commands.test_cmd import app as test_app

    return CliRunner().invoke(
        test_app, ["sandbox", "--dry-run", "--workspace", str(workspace), "true"]
    )


_SANDBOX_DRY_RUNNERS: dict[str, tuple[Any, type[Exception]]] = {
    "docker-sandbox": (_run_docker_sandbox_dry_run, DockerSandboxError),
    "test-sandbox": (_run_test_sandbox_dry_run, DockerSandboxError),
}


def _engine_dir(tmp_path: Path) -> Path:
    return tmp_path / "d" / "engine"


def _symlinked_engine_socket(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    """Link `link/docker.sock` to `real/docker.sock`, as Docker Desktop's WSL integration links
    /var/run/docker.sock into /mnt/wsl, so the socket the client opens lives in `real`."""
    real, link = tmp_path / "real", tmp_path / "link"
    real.mkdir()
    link.mkdir()
    (link / "docker.sock").symlink_to(real / "docker.sock")
    return real, real, {"DOCKER_HOST": f"unix://{link}/docker.sock"}


def _symlinked_ssh_agent_socket(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    """Link `link/agent.1` to `real/agent.1`, so the agent socket the client opens lives in `real`."""
    real, link = tmp_path / "real", tmp_path / "link"
    real.mkdir()
    link.mkdir()
    (link / "agent.1").symlink_to(real / "agent.1")
    return real, real, {"SSH_AUTH_SOCK": f"{link}/agent.1"}


# Each case: the workspace, the directory its refusal names, and the environment it runs under.
_REFUSED_WORKSPACES: dict[str, Any] = {
    "run": lambda tmp, rt: (Path("/run"), Path("/run"), {}),
    "run-user": lambda tmp, rt: (Path("/run/user/1000"), Path("/run"), {}),
    "run-user-gnupg": lambda tmp, rt: (Path("/run/user/1000/gnupg"), Path("/run"), {}),
    "var-run": lambda tmp, rt: (Path("/var/run"), Path("/var/run"), {}),
    "runtime-dir": lambda tmp, rt: (rt, rt, {}),
    "under-runtime-dir": lambda tmp, rt: (rt / "sub", rt, {}),
    "holds-runtime-dir": lambda tmp, rt: (rt.parent, rt, {}),
    "engine-socket-dir": lambda tmp, rt: (
        _engine_dir(tmp),
        _engine_dir(tmp),
        {"DOCKER_HOST": f"unix://{_engine_dir(tmp)}/docker.sock"},
    ),
    "under-engine-socket-dir": lambda tmp, rt: (
        _engine_dir(tmp) / "sub",
        _engine_dir(tmp),
        {"DOCKER_HOST": f"unix://{_engine_dir(tmp)}/docker.sock"},
    ),
    "holds-engine-socket-dir": lambda tmp, rt: (
        _engine_dir(tmp).parent,
        _engine_dir(tmp),
        {"DOCKER_HOST": f"unix://{_engine_dir(tmp)}/docker.sock"},
    ),
    # docker-py reads `unix://tmp/...` as `/tmp/...`, so the check must too.
    "engine-socket-dir-two-slash": lambda tmp, rt: (
        _engine_dir(tmp),
        _engine_dir(tmp),
        {"DOCKER_HOST": f"unix://{str(_engine_dir(tmp)).lstrip('/')}/docker.sock"},
    ),
    "symlinked-engine-socket": lambda tmp, rt: _symlinked_engine_socket(tmp),
    "unsupported-engine-endpoint": lambda tmp, rt: (
        tmp / "ws",
        tmp / "ws",
        {"DOCKER_HOST": "fd://"},
    ),
    # docker-py's parse_host raises a bare ValueError here, not a DockerException.
    "unparseable-engine-endpoint": lambda tmp, rt: (
        tmp / "ws",
        tmp / "ws",
        {"DOCKER_HOST": "tcp://host:abc"},
    ),
    "system-subpath": lambda tmp, rt: (Path("/etc/ssl"), Path("/etc/ssl"), {}),
    "ssh-agent-dir": lambda tmp, rt: (
        tmp / "ssh-abc",
        tmp / "ssh-abc",
        {"SSH_AUTH_SOCK": f"{tmp}/ssh-abc/agent.1"},
    ),
    "holds-ssh-agent-dir": lambda tmp, rt: (
        tmp,
        tmp / "ssh-abc",
        {"SSH_AUTH_SOCK": f"{tmp}/ssh-abc/agent.1"},
    ),
    "symlinked-ssh-agent-socket": lambda tmp, rt: _symlinked_ssh_agent_socket(tmp),
    # VS Code puts its SSH-auth socket directly in /tmp.
    "vscode-ssh-auth-socket": lambda tmp, rt: (
        tmp,
        tmp,
        {"SSH_AUTH_SOCK": f"{tmp}/vscode-ssh-auth-x.sock"},
    ),
    "x11-dir": lambda tmp, rt: (CONST_X11_SOCKET_DIR, CONST_X11_SOCKET_DIR, {}),
    # The test's runtime directory lies under /tmp, so it is cleared for the X11 rule to answer.
    "holds-x11-dir": lambda tmp, rt: (
        CONST_X11_SOCKET_DIR.parent,
        CONST_X11_SOCKET_DIR,
        {"XDG_RUNTIME_DIR": ""},
    ),
}


@pytest.mark.parametrize("runner_name", sorted(_SANDBOX_RUNNERS))
@pytest.mark.parametrize("case", sorted(_REFUSED_WORKSPACES))
def test_a_workspace_overlapping_a_socket_directory_is_refused_before_any_engine_call(
    runner_name: str,
    case: str,
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    docker_engine: Any,
) -> None:
    """Both runners refuse /run, the runtime directory and the engine socket's directory when the
    workspace is, holds or sits under one (#1115), and the SSH agent's directory and
    /tmp/.X11-unix when the workspace is or holds one (#1384). The refusal names the workspace and
    that directory."""
    run, refusal = _SANDBOX_RUNNERS[runner_name]
    runtime_dir = tmp_path_factory.mktemp("rt")
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime_dir))
    workspace, protected, env = _REFUSED_WORKSPACES[case](tmp_path, runtime_dir)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    client = MagicMock()

    with docker_engine(client), pytest.raises(refusal) as refused:
        run(workspace, tmp_path)

    message = str(refused.value)
    assert (str(workspace) in message, str(protected) in message, client.mock_calls) == (
        True,
        True,
        [],
    )


@pytest.mark.parametrize("runner_name", sorted(_SANDBOX_RUNNERS))
@pytest.mark.parametrize("docker_host", [None, "tcp://192.0.2.1:2375"], ids=["unset", "tcp"])
def test_a_workspace_beside_the_socket_directories_is_mounted(
    runner_name: str,
    docker_host: str | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    docker_engine: Any,
) -> None:
    """A tcp endpoint names no socket, so only /run and the runtime directory stay protected."""
    run, _refusal = _SANDBOX_RUNNERS[runner_name]
    if docker_host:
        monkeypatch.setenv("DOCKER_HOST", docker_host)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    client = MagicMock()

    with docker_engine(client):
        run(workspace, tmp_path)

    assert list(client.containers.create.call_args.kwargs["volumes"]) == [str(workspace)]


@pytest.mark.parametrize("runner_name", sorted(_SANDBOX_RUNNERS))
@pytest.mark.parametrize(
    "agent_socket",
    ["{tmp}/vscode-ssh-auth-x.sock", None, "", "agent.1"],
    ids=["vscode-in-parent", "unset", "empty", "relative"],
)
def test_a_workspace_beside_the_ssh_agent_directory_is_mounted(
    runner_name: str,
    agent_socket: str | None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    docker_engine: Any,
) -> None:
    """The SSH agent rule is one-way, so a workspace under the agent's directory is mounted, and an
    unset, empty or relative SSH_AUTH_SOCK adds no rule (#1384). Resolving `agent.1` would make the
    working directory, here the workspace, the agent's directory."""
    run, _refusal = _SANDBOX_RUNNERS[runner_name]
    workspace = tmp_path / "ws"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    if agent_socket is None:
        monkeypatch.delenv("SSH_AUTH_SOCK", raising=False)
    else:
        monkeypatch.setenv("SSH_AUTH_SOCK", agent_socket.format(tmp=tmp_path))
    client = MagicMock()

    with docker_engine(client):
        run(workspace, tmp_path)

    assert list(client.containers.create.call_args.kwargs["volumes"]) == [str(workspace)]


@pytest.mark.parametrize("tool_name", ["docker_sandbox", "sandbox_deploy"])
@pytest.mark.parametrize(
    "case", ["unsupported-engine-endpoint", "unparseable-engine-endpoint", "ssh-agent-dir"]
)
def test_mcp_sandbox_tools_refuse_the_workspace_before_any_command_runs(
    tool_name: str, case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The tool raises the shared check's refusal, so the client gets it and no command runs.

    The workspace is in the work tree. The tool confines the workspace first, so a workspace
    outside the tree never reaches the shared check (#3480)."""
    from devops_cli.ai.mcp import server

    monkeypatch.chdir(tmp_path)
    workspace, _protected, env = _REFUSED_WORKSPACES[case](tmp_path, tmp_path)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    tool = getattr(server, tool_name)

    with (
        patch("devops_cli.ai.mcp.server._run_mcp_cmd") as run_command,
        pytest.raises(SandboxValidationError) as raised,
    ):
        tool(command=["true"], workspace=str(workspace))
    assert raised.value.error_code == "SANDBOX_VALIDATION_ERROR"

    assert run_command.called is False


def test_sandbox_deploy_dry_run_looks_up_no_engine_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The workspace check reads DOCKER_HOST without the engine's egress check, so a dry run
    neither resolves a tcp engine's host nor refuses it as private (#1115)."""
    from devops_cli.commands.sandbox import app as sandbox_app

    monkeypatch.setenv("DOCKER_HOST", "tcp://example.com:2375")
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "false")
    resolver = scripted_resolver(monkeypatch, {"example.com": [["93.184.216.34"]]})

    res = CliRunner().invoke(sandbox_app, ["deploy", "--workspace", str(tmp_path), "--dry-run"])

    assert (res.exit_code, resolver.lookups.get("example.com", 0)) == (0, 0)


@pytest.mark.parametrize("runner_name", sorted(_SANDBOX_DRY_RUNNERS))
@pytest.mark.parametrize("case", sorted(_REFUSED_WORKSPACES))
def test_sandbox_dry_runs_refuse_invalid_workspaces(
    runner_name: str,
    case: str,
    tmp_path: Path,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
    docker_engine: Any,
) -> None:
    """Both devops docker sandbox --dry-run and devops test sandbox --dry-run refuse invalid
    workspaces before making any engine calls (#1383). The command reports the refusal, which
    names the workspace and the protected directory, and exits with its status (#2487)."""
    run, refusal = _SANDBOX_DRY_RUNNERS[runner_name]
    runtime_dir = tmp_path_factory.mktemp("rt")
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(runtime_dir))
    workspace, protected, env = _REFUSED_WORKSPACES[case](tmp_path, runtime_dir)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    client = MagicMock()

    with docker_engine(client):
        result = run(workspace, tmp_path)

    assert (
        result.exit_code,
        type(result.exception),
        str(workspace) in result.output,
        str(protected) in result.output,
        client.mock_calls,
    ) == (refusal("").exit_code, SystemExit, True, True, [])


@pytest.mark.parametrize("subcommand", ["docker-sandbox", "test-sandbox"])
def test_docker_and_test_sandbox_dry_runs_make_no_request(
    subcommand: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    docker_engine: Any,
) -> None:
    """A dry run with tcp DOCKER_HOST and private networks disallowed records no host lookup and no client call (#1383)."""
    from devops_cli.commands.docker import app as docker_app
    from devops_cli.commands.test_cmd import app as test_app

    app = docker_app if subcommand == "docker-sandbox" else test_app
    args = ["sandbox", "--dry-run", "--workspace", str(tmp_path), "true"]
    monkeypatch.setenv("DOCKER_HOST", "tcp://example.com:2375")
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "false")
    resolver = scripted_resolver(monkeypatch, {"example.com": [["93.184.216.34"]]})
    client = MagicMock()

    with docker_engine(client):
        res = CliRunner().invoke(app, args, catch_exceptions=False)

    assert (res.exit_code, resolver.lookups.get("example.com", 0), client.mock_calls) == (0, 0, [])


def test_sandbox_workspace_validation_user_home(tmp_path: Path) -> None:
    """Workspace validation blocks mounting user home directory and subpaths by default."""
    engine_default = WorkloadSandboxEngine(registry=SandboxRegistry(tmp_path / "reg.json"))
    assert engine_default.exclude_home_dir is True

    with pytest.raises(SandboxValidationError, match="home directory"):
        engine_default.validate_workspace_dir(Path.home())

    with pytest.raises(SandboxValidationError, match="home directory"):
        engine_default.validate_workspace_dir(Path.home() / "subproject")

    with pytest.raises(SandboxValidationError, match="home directory"):
        engine_default.validate_workspace_dir(Path("/home/test/workspace"))

    # When exclude_home_dir is explicitly disabled:
    engine_allow = WorkloadSandboxEngine(
        registry=SandboxRegistry(tmp_path / "reg.json"),
        exclude_home_dir=False,
    )
    assert engine_allow.exclude_home_dir is False

    # Home root is still forbidden even when exclude_home_dir is False
    with pytest.raises(SandboxValidationError, match="home directory"):
        engine_allow.validate_workspace_dir(Path.home())

    # Valid non-forbidden workspace succeeds
    valid_dir = tmp_path / "valid_workspace"
    valid_dir.mkdir()
    assert engine_allow.validate_workspace_dir(valid_dir) == valid_dir.resolve()
