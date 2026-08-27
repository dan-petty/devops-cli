"""Unit tests for devops test load and devops pipeline run commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.pipeline import app as pipeline_app
from devops_cli.commands.test_cmd import app as test_app

runner = CliRunner()


def test_test_load_dry_run() -> None:
    result = runner.invoke(test_app, ["--dry-run"])
    assert result.exit_code == 0
    assert "DRY_RUN" in result.stdout


@patch("shutil.which", return_value="/usr/local/bin/k6")
@patch("devops_cli.commands.test_cmd.run_subprocess")
def test_test_load_live(mock_run: MagicMock, mock_which: MagicMock, tmp_path: Path) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    script = tmp_path / "smoke.js"
    script.write_text("export default function() {}")
    result = runner.invoke(test_app, [str(script), "--vus", "5", "--duration", "5s"])
    assert result.exit_code == 0
    assert mock_run.called


def test_pipeline_run_dry_run() -> None:
    result = runner.invoke(pipeline_app, ["--dry-run"])
    assert result.exit_code == 0
    assert "DRY_RUN" in result.stdout


@patch("shutil.which", return_value="/usr/local/bin/dagger")
@patch("devops_cli.commands.pipeline.run_subprocess")
def test_pipeline_run_live(mock_run: MagicMock, mock_which: MagicMock, tmp_path: Path) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    result = runner.invoke(pipeline_app, [str(tmp_path), "--function", "build"])
    assert result.exit_code == 0
    assert mock_run.called
