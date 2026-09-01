"""Unit tests for uv CLI subcommands (devops_cli.commands.uv)."""

from __future__ import annotations

import subprocess
from pathlib import Path
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


def test_uv_commands(tmp_path: Path) -> None:
    """Verify uv sync, lock, and python-install subcommands."""
    with patch("devops_cli.commands.uv.run_subprocess", return_value=_mock_proc(0)):
        res_sync = runner.invoke(uv_app, ["sync", "--frozen"])
        assert res_sync.exit_code == 0

        res_lock = runner.invoke(uv_app, ["lock", "--upgrade"])
        assert res_lock.exit_code == 0

        res_py = runner.invoke(uv_app, ["python-install", "--version", "3.14.0"])
        assert res_py.exit_code == 0

        # uv run with args
        res_run = runner.invoke(uv_app, ["run", "pytest", "-q"])
        assert res_run.exit_code == 0


def test_uv_python_install_and_run_edge_cases(tmp_path: Path) -> None:
    """Verify uv python-install from .python-version, invalid version, and uv run errors."""
    import pytest

    import devops_cli.commands.uv as uv_mod

    # 1. uv run missing args
    res_no_args = runner.invoke(uv_app, ["run"])
    assert res_no_args.exit_code == 1

    # 2. python-install from .python-version file
    (tmp_path / ".python-version").write_text("3.14.7\n", encoding="utf-8")
    with (
        patch("devops_cli.commands.uv._get_project_root", return_value=tmp_path),
        patch("devops_cli.commands.uv.run_subprocess", return_value=_mock_proc(0)),
    ):
        res_pv = runner.invoke(uv_app, ["python-install"])
        assert res_pv.exit_code == 0

    # 3. python-install without version or .python-version
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with patch("devops_cli.commands.uv._get_project_root", return_value=empty_dir):
        res_err = runner.invoke(uv_app, ["python-install"])
        assert res_err.exit_code == 1

    # 4. python-install invalid version format
    res_bad = runner.invoke(uv_app, ["python-install", "--version", "bad$$version"])
    assert res_bad.exit_code == 1

    # 5. Non-zero exit from subprocess
    with patch("devops_cli.commands.uv.run_subprocess", return_value=_mock_proc(2)):
        res_fail = runner.invoke(uv_app, ["sync"])
        assert res_fail.exit_code == 2

    # 6. Lazy getattr and _get
    assert uv_mod.__getattr__("run_subprocess") is not None
    with pytest.raises(AttributeError):
        uv_mod.__getattr__("non_existent_attribute_12345")
    assert uv_mod._get("run_subprocess") is not None
    assert uv_mod._get("app") is not None
