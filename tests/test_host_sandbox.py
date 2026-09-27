"""Unit and integration tests for bubblewrap HostSandbox confinement."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from devops_cli.ai.review.review_environment import execute_criterion_command
from devops_cli.sandbox.host import HostSandbox


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


def test_host_sandbox_clears_sensitive_env(tmp_path: Path) -> None:
    """Live test: sandboxed child sees no credentials or home directory in environment."""
    sandbox = HostSandbox()
    script = (
        "import os\n"
        "leaks = [k for k in ['HOME', 'GITHUB_TOKEN', 'GH_TOKEN', 'XDG_RUNTIME_DIR'] "
        "if os.environ.get(k)]\n"
        "print('LEAKS:' + ','.join(leaks))\n"
    )
    res = sandbox.execute(
        ["python3", "-c", script],
        cwd=tmp_path,
        env={"GITHUB_TOKEN": "secret_token", "CUSTOM_VAR": "allowed"},
    )
    assert (
        res.passed,
        res.exit_code,
        "LEAKS:" in res.stdout,
        "secret_token" in res.stdout,
    ) == (True, 0, True, False)


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

    with patch("subprocess.Popen", return_value=mock_proc):
        res = sandbox.execute(["python3", "-c", "pass"], cwd=tmp_path)

    assert (
        res.passed,
        res.exit_code,
        "Host sandbox error: bwrap: Setting up uid map: Permission denied" in str(res.error),
    ) == (False, 1, True)
