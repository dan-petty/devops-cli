"""Tests for process execution utilities (sync and async)."""

from __future__ import annotations

from pathlib import Path

import pytest

from devops_cli.core.process import run_subprocess, run_subprocess_async


def test_run_subprocess_success() -> None:
    proc = run_subprocess(["echo", "hello"])
    assert proc.returncode == 0
    assert proc.stdout.strip() == "hello"


def test_run_subprocess_not_found() -> None:
    proc = run_subprocess(["non_existent_binary_12345"])
    assert proc.returncode == 127
    assert "not found" in proc.stderr.lower()


@pytest.mark.anyio
async def test_run_subprocess_async_success() -> None:
    proc = await run_subprocess_async(["echo", "hello async"])
    assert proc.returncode == 0
    assert proc.stdout.strip() == "hello async"


@pytest.mark.anyio
async def test_run_subprocess_async_not_found() -> None:
    proc = await run_subprocess_async(["non_existent_binary_12345"])
    assert proc.returncode == 127
    assert "not found" in proc.stderr.lower()


@pytest.mark.anyio
async def test_run_subprocess_async_non_zero() -> None:
    proc = await run_subprocess_async(["false"])
    assert proc.returncode != 0


def test_run_subprocess_check_and_timeout(monkeypatch) -> None:
    """Verify run_subprocess error handling with check=True and timeouts."""
    import subprocess

    from devops_cli.dry_run import set_dry_run

    # 1. Non-zero exit with check=True
    with pytest.raises(subprocess.CalledProcessError):
        run_subprocess(["false"], check=True)

    # 2. Not found with check=True
    with pytest.raises(FileNotFoundError):
        run_subprocess(["non_existent_binary_99999"], check=True)

    # 3. Dry run execution
    set_dry_run(True)
    try:
        proc_dry = run_subprocess(["echo", "dry_run_test"])
        assert proc_dry is not None
    finally:
        set_dry_run(False)


@pytest.mark.anyio
async def test_run_subprocess_async_check_and_timeout() -> None:
    """Verify run_subprocess_async error handling with check=True and timeouts."""
    import subprocess

    # 1. Non-zero exit with check=True
    with pytest.raises(subprocess.CalledProcessError):
        await run_subprocess_async(["false"], check=True)

    # 2. Not found with check=True
    with pytest.raises(FileNotFoundError):
        await run_subprocess_async(["non_existent_binary_99999"], check=True)

    # 3. Timeout expiration
    with pytest.raises(subprocess.TimeoutExpired):
        await run_subprocess_async(["sleep", "10"], timeout=0.01)


def test_run_subprocess_cwd_security() -> None:
    """Verify run_subprocess rejects traversal sequences and forbidden system directories in cwd."""
    from pathlib import Path

    from devops_cli.exceptions.security import SecurityError

    with pytest.raises(SecurityError):
        run_subprocess(["echo", "hi"], cwd=Path("../../../escaped"))

    with pytest.raises(SecurityError):
        run_subprocess(["echo", "hi"], cwd=Path("/etc"))


def test_run_subprocess_runs_in_the_runtime_root() -> None:
    """Only a sandbox workspace refuses /run (#1115); a subprocess may still run there."""
    proc = run_subprocess(["pwd"], cwd=Path("/run"))
    assert (proc.returncode, proc.stdout.strip()) == (0, "/run")


@pytest.mark.anyio
async def test_run_subprocess_async_cwd_security() -> None:
    """Verify run_subprocess_async rejects traversal sequences and forbidden system directories in cwd."""
    from pathlib import Path

    from devops_cli.exceptions.security import SecurityError

    with pytest.raises(SecurityError):
        await run_subprocess_async(["echo", "hi"], cwd=Path("../../../escaped"))

    with pytest.raises(SecurityError):
        await run_subprocess_async(["echo", "hi"], cwd=Path("/etc"))


@pytest.mark.anyio
async def test_run_subprocess_async_telemetry_sanitizes_secrets() -> None:
    """Verify run_subprocess_async redacts secrets in telemetry command attributes."""
    from typing import Any
    from unittest.mock import MagicMock, patch

    captured_attrs: dict[str, Any] = {}

    def fake_trace_span(name: str, attributes: dict[str, Any] | None = None):
        if attributes:
            captured_attrs.update(attributes)
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = MagicMock()
        mock_ctx.__exit__.return_value = None
        return mock_ctx

    token = "ghp_1234567890abcdef1234567890abcdef1234"
    cmd = [
        "python3",
        "-c",
        "pass",
        "--token",
        token,
        "--body",
        "super_secret_body",
        "title=super_secret_title",
    ]
    with patch("devops_cli.core.process.trace_span", side_effect=fake_trace_span):
        await run_subprocess_async(cmd)

    cmd_summary = captured_attrs.get("subprocess.cmd", "")
    proc_cmd = captured_attrs.get("process.command_line", "")
    assert (
        token in cmd_summary,
        "super_secret_body" in cmd_summary,
        "super_secret_title" in cmd_summary,
        cmd_summary == proc_cmd,
    ) == (False, False, False, True)


@pytest.mark.anyio
async def test_run_subprocess_async_timeout_kills_process_group(tmp_path: Path) -> None:
    """Verify run_subprocess_async timeout kills entire process group including grandchildren."""
    import os
    import subprocess
    import sys

    pid_file = tmp_path / "grandchild.pid"
    script = (
        "import sys, time, subprocess\n"
        f"child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        f"with open({str(pid_file)!r}, 'w') as f:\n"
        "    f.write(str(child.pid))\n"
        "time.sleep(30)\n"
    )
    cmd = [sys.executable, "-c", script]

    with pytest.raises(subprocess.TimeoutExpired):
        await run_subprocess_async(cmd, timeout=0.6)

    assert pid_file.exists()
    grandchild_pid = int(pid_file.read_text().strip())

    is_alive = True
    try:
        os.kill(grandchild_pid, 0)
    except ProcessLookupError:
        is_alive = False

    assert is_alive is False


def test_process_group_guard_helpers() -> None:
    """Verify process group validation guards against PID 1, 0, negative PIDs, and self."""
    import os

    from devops_cli.core.process import _is_invalid_pgid

    self_pgrp = os.getpgrp() if hasattr(os, "getpgrp") else -1
    assert (
        _is_invalid_pgid(1),
        _is_invalid_pgid(0),
        _is_invalid_pgid(-1),
        _is_invalid_pgid(None),  # type: ignore[arg-type]
        _is_invalid_pgid(self_pgrp) if self_pgrp > 1 else True,
        _is_invalid_pgid(999999),
    ) == (True, True, True, True, True, False)
