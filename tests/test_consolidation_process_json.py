"""Unit tests for run_json_subprocess (TDD Specification)."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from devops_cli.core.process import run_json_subprocess
from devops_cli.exceptions.base import DevOpsCLIError


def test_run_json_subprocess_parses_json_stdout() -> None:
    """Parses JSON stdout into dict/list cleanly on success."""
    fake_completed = subprocess.CompletedProcess(
        args=["kubectl", "get", "pods", "-o", "json"],
        returncode=0,
        stdout='{"kind": "PodList", "items": [{"name": "pod-1"}]}',
        stderr="",
    )
    with patch("devops_cli.core.process.run_subprocess", return_value=fake_completed):
        res = run_json_subprocess(["kubectl", "get", "pods", "-o", "json"])
        assert res == {"kind": "PodList", "items": [{"name": "pod-1"}]}


def test_run_json_subprocess_raises_on_nonzero_returncode() -> None:
    """Raises DevOpsCLIError when subprocess exits non-zero and check is True (default)."""
    fake_completed = subprocess.CompletedProcess(
        args=["kubectl", "get", "pods"],
        returncode=1,
        stdout="",
        stderr="Error from server: namespace not found",
    )
    with patch("devops_cli.core.process.run_subprocess", return_value=fake_completed):
        with pytest.raises(DevOpsCLIError) as exc_info:
            run_json_subprocess(["kubectl", "get", "pods"])
        assert "namespace not found" in str(exc_info.value) or "Subprocess failed" in str(
            exc_info.value
        )


def test_run_json_subprocess_handles_malformed_json_with_default() -> None:
    """Returns default value when stdout is not valid JSON and default is specified."""
    fake_completed = subprocess.CompletedProcess(
        args=["helm", "list"],
        returncode=0,
        stdout="not json text",
        stderr="",
    )
    with patch("devops_cli.core.process.run_subprocess", return_value=fake_completed):
        res = run_json_subprocess(["helm", "list"], default=[])
        assert res == []


def test_run_json_subprocess_raises_on_malformed_json_without_default() -> None:
    """Raises DevOpsCLIError when stdout is not valid JSON and no default is specified."""
    fake_completed = subprocess.CompletedProcess(
        args=["helm", "list"],
        returncode=0,
        stdout="not json text",
        stderr="",
    )
    with patch("devops_cli.core.process.run_subprocess", return_value=fake_completed):
        with pytest.raises(DevOpsCLIError):
            run_json_subprocess(["helm", "list"])
