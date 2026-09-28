"""Unit and integration tests for bubblewrap HostSandbox confinement."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.review.review_environment import execute_criterion_command
from devops_cli.sandbox.host import HostSandbox
from devops_cli.sandbox.models import SandboxPolicy


def test_host_sandbox_reads_repo(tmp_path: Path) -> None:
    """Live test: sandboxed child can read files from the mounted repository."""
    data_file = tmp_path / "hello.txt"
    data_file.write_text("sandbox-content", encoding="utf-8")

    result = execute_criterion_command("cat hello.txt", cwd=tmp_path)
    assert (
        result.executable,
        result.passed,
        result.exit_code,
        "sandbox-content" in result.stdout,
    ) == (True, True, 0, True)


def test_host_sandbox_cannot_list_home(tmp_path: Path) -> None:
    """Live test: sandboxed child cannot access /home."""
    sandbox = HostSandbox()
    res = sandbox.execute(["ls", "/home"], cwd=tmp_path)
    assert (
        res.passed,
        res.exit_code != 0,
        "No such file" in res.stderr or "cannot access" in res.stderr,
    ) == (False, True, True)


def test_host_sandbox_cannot_write_repo(tmp_path: Path) -> None:
    """Live test: sandboxed child cannot mutate files in the mounted repository."""
    sandbox = HostSandbox()
    target = tmp_path / "forbidden.txt"
    res = sandbox.execute(["touch", str(target)], cwd=tmp_path)
    assert (
        res.passed,
        res.exit_code != 0,
        "Read-only file system" in res.stderr,
        target.exists(),
    ) == (False, True, True, False)


def test_host_sandbox_cannot_connect_network(tmp_path: Path) -> None:
    """Live test: sandboxed child cannot establish non-loopback network connections."""
    sandbox = HostSandbox()
    script = (
        "import socket\ns = socket.socket()\ns.settimeout(0.5)\ns.connect(('198.51.100.1', 80))\n"
    )
    res = sandbox.execute(["python3", "-c", script], cwd=tmp_path)
    assert (
        res.passed,
        res.exit_code != 0,
        "Network is unreachable" in res.stderr or "timed out" in res.stderr,
    ) == (False, True, True)


def test_host_sandbox_clears_sensitive_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Live test: sandboxed child inherits no host credentials and uses isolated HOME."""
    monkeypatch.setenv("GITHUB_TOKEN", "super_secret_host_token")
    monkeypatch.setenv("SSH_AUTH_SOCK", "/tmp/host_auth.sock")
    sandbox = HostSandbox()
    script = (
        "import os\n"
        "leaks = [k for k in ['GITHUB_TOKEN', 'SSH_AUTH_SOCK'] if os.environ.get(k)]\n"
        "print('LEAKS:' + ','.join(leaks))\n"
        "print('HOME:' + os.environ.get('HOME', ''))\n"
    )
    res = sandbox.execute(["python3", "-c", script], cwd=tmp_path)
    assert (
        res.passed,
        res.exit_code,
        "LEAKS:" in res.stdout,
        "super_secret_host_token" in res.stdout,
        "/tmp/host_auth.sock" in res.stdout,
        "HOME:/tmp" in res.stdout,
    ) == (True, 0, True, False, False, True)


def test_host_sandbox_fails_closed_when_bwrap_missing(tmp_path: Path) -> None:
    """Constraint test: execution fails closed when bubblewrap is unavailable."""
    missing_sandbox = HostSandbox(bwrap_binary="/nonexistent/bwrap")
    assert missing_sandbox.is_available() is False

    result = execute_criterion_command(
        "python -c 'print(1)'",
        cwd=tmp_path,
        sandbox=missing_sandbox,
    )
    assert (
        result.executable,
        result.passed,
        result.exit_code,
        "not available" in str(result.error),
    ) == (True, False, -1, True)


def test_host_sandbox_build_args_structure(tmp_path: Path) -> None:
    """Verify bubblewrap command argument compilation structure and isolation flags."""
    sandbox = HostSandbox()
    args = sandbox.build_bwrap_args(["python3", "-V"], cwd=tmp_path)
    assert (
        "--unshare-all" in args,
        "--new-session" in args,
        "--die-with-parent" in args,
        "--clearenv" in args,
        "--dev" in args,
        "--proc" in args,
        "--tmpfs" in args,
        "--chdir" in args,
        str(tmp_path.resolve()) in args,
    ) == (True, True, True, True, True, True, True, True, True)


def test_host_sandbox_handles_namespace_refusal(tmp_path: Path) -> None:
    """Verify that bubblewrap namespace refusal is caught and reported as sandbox error."""
    sandbox = HostSandbox()
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (
        "",
        "bwrap: Setting up uid map: Permission denied\n",
    )
    mock_proc.returncode = 1
    mock_proc.pid = 999999

    with patch("subprocess.Popen", return_value=mock_proc):
        res = sandbox.execute(["python3", "-c", "pass"], cwd=tmp_path)

    assert (
        res.passed,
        res.exit_code,
        "Host sandbox error: bwrap: Setting up uid map: Permission denied" in str(res.error),
    ) == (False, 1, True)


def test_host_sandbox_consumes_custom_policy(tmp_path: Path) -> None:
    """Verify that HostSandbox mounts and configures according to its SandboxPolicy."""
    custom_policy = SandboxPolicy(
        read_only=False,
        tmpfs={"/tmp": "size=32m", "/var/tmp": "size=16m"},
        system_dirs=("/usr", "/bin"),
        forbidden_env_keys=frozenset({"CUSTOM_SECRET"}),
    )
    sandbox = HostSandbox(policy=custom_policy)
    args = sandbox.build_bwrap_args(
        command_args=["python3", "-c", "pass"],
        cwd=tmp_path,
        env={"CUSTOM_SECRET": "leak", "SAFE_VAR": "value"},
    )
    assert (
        sandbox.policy == custom_policy,
        "--bind" in args,
        "--tmpfs" in args,
        "--size" in args,
        "33554432" in args,
        "/var/tmp" in args,
        "CUSTOM_SECRET" not in str(args),
        "SAFE_VAR" in str(args),
    ) == (True, True, True, True, True, True, True, True)


def test_host_sandbox_kills_process_exceeding_output_cap(tmp_path: Path) -> None:
    """Verify that process generating unbounded output is terminated and output is capped (#663)."""
    sandbox = HostSandbox()
    res = sandbox.execute(
        ["python3", "-c", "import sys; sys.stdout.write('A' * 50000); sys.stdout.flush()"],
        cwd=tmp_path,
        max_output_bytes=1024,
    )
    assert (
        res.passed,
        len(res.stdout) <= 1024,
        "Output exceeded maximum limit" in str(res.error),
    ) == (False, True, True)


def test_host_sandbox_nested_clone_cannot_read_parent_workspace(tmp_path: Path) -> None:
    """Verify nearest repo root is mounted so nested clone cannot traverse parent (#663)."""
    parent = tmp_path / "workspace"
    parent.mkdir()
    (parent / ".git").mkdir()
    (parent / "secret.env").write_text("HOST_SECRET=1", encoding="utf-8")

    clone = parent / "repos" / "nested"
    clone.mkdir(parents=True)
    (clone / ".git").mkdir()
    (clone / "hello.txt").write_text("hello", encoding="utf-8")

    sandbox = HostSandbox()
    res = sandbox.execute(["cat", str(parent / "secret.env")], cwd=clone)
    assert (
        res.passed,
        res.exit_code != 0,
        "No such file" in res.stderr or "cannot access" in res.stderr,
    ) == (False, True, True)


def test_host_sandbox_linked_worktree_runs_git(tmp_path: Path) -> None:
    """Verify linked worktree binds common git directory so git commands succeed (#663)."""
    import subprocess

    main_repo = tmp_path / "main_repo"
    main_repo.mkdir()
    worktree = tmp_path / "linked_worktree"

    subprocess.run(["git", "init"], cwd=main_repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=main_repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=main_repo, check=True)
    (main_repo / "README.md").write_text("# Main", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=main_repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=main_repo, check=True)
    subprocess.run(
        ["git", "worktree", "add", str(worktree), "-b", "feat"], cwd=main_repo, check=True
    )

    sandbox = HostSandbox()
    res = sandbox.execute(["git", "log", "-n", "1", "--oneline"], cwd=worktree)
    assert (
        res.passed,
        res.exit_code,
        "initial commit" in res.stdout,
    ) == (True, 0, True)


def test_terminate_process_group_guards_devcontainer() -> None:
    """Verify that _terminate_process_group safely rejects PID 1, PID 0, self, and mocks."""
    from devops_cli.sandbox.host import _terminate_process_group

    with patch("os.killpg") as mock_killpg:
        # Should guard against non-int, PID <= 1, self, and PGID <= 1
        _terminate_process_group(MagicMock())
        _terminate_process_group(0)
        _terminate_process_group(1)
        _terminate_process_group(-5)
        _terminate_process_group(os.getpid())
        assert mock_killpg.called is False
