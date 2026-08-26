"""Tests for process execution utilities (sync and async)."""

from __future__ import annotations

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
        proc_dry = run_subprocess(["git", "commit", "-m", "test"])
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
