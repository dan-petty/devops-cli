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
