"""Unit tests for uv CLI subcommands (devops_cli.commands.uv)."""

from __future__ import annotations

import subprocess
from unittest.mock import patch

from typer.testing import CliRunner

from devops_cli.commands.uv import app as uv_app

runner = CliRunner()


def _mock_proc(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["uv"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_uv_commands() -> None:
    """Verify uv sync, lock, and python-install subcommands."""
    with patch("devops_cli.commands.uv.run_subprocess", return_value=_mock_proc(0)):
        res_sync = runner.invoke(uv_app, ["sync", "--frozen"])
        assert res_sync.exit_code == 0

        res_lock = runner.invoke(uv_app, ["lock", "--upgrade"])
        assert res_lock.exit_code == 0

        res_py = runner.invoke(uv_app, ["python-install", "--version", "3.14"])
        assert res_py.exit_code == 0
