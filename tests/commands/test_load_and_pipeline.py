"""Unit tests for devops test load and devops pipeline run commands."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from devops_cli.commands.pipeline import app as pipeline_app
from devops_cli.commands.pipeline import run_pipeline_cmd
from devops_cli.commands.test_cmd import app as app_test_cli
from devops_cli.config.commands import build_dagger_cmd, build_k6_cmd
from tests.support.fakes.process import ProcessFake

runner = CliRunner()


def _plan_lines(output: str) -> list[str]:
    """The numbered lines of a request plan, without their numbers."""
    return [line.split(". ", 1)[1] for line in output.splitlines() if re.match(r"^\s*\d+\. ", line)]


@pytest.mark.parametrize("flag_first", [True, False])
def test_test_load_dry_run_lists_the_k6_command(
    tmp_path: Path, cli: Any, process_fake: ProcessFake, flag_first: bool
) -> None:
    """A dry run starts no process, invents no metric, and lists the one `k6 run` (#2260)."""
    script = tmp_path / "smoke.js"
    summary = tmp_path / "summary.json"
    argv = ["test", "load", str(script), "--vus", "5", "--duration", "5s"]
    argv += ["--summary-export", str(summary)]
    with patch("shutil.which", side_effect=AssertionError("no binary lookup")):
        result = cli(["--dry-run", *argv] if flag_first else [*argv, "--dry-run"])

    assert result.exit_code == 0, result.output
    assert process_fake.calls == []
    assert "simulated_metrics" not in result.output
    expected = build_k6_cmd(
        script.resolve(), vus=5, duration="5s", summary_export=summary.resolve()
    )
    assert _plan_lines(result.output) == [" ".join(expected)]


@patch("shutil.which", return_value="/usr/local/bin/k6")
def test_test_load_runs_the_request_of_its_plan(
    _which: MagicMock, tmp_path: Path, cli: Any, process_fake: ProcessFake
) -> None:
    """The real run starts the command of the plan."""
    argv = ["test", "load", str(tmp_path / "smoke.js"), "--vus", "5", "--duration", "5s"]
    planned = _plan_lines(cli([*argv, "--dry-run"]).output)

    result = cli(argv)

    assert result.exit_code == 0, result.output
    assert [" ".join(call.argv) for call in process_fake.calls] == planned


@patch("shutil.which", return_value="/usr/local/bin/k6")
@patch("devops_cli.commands.test_cmd.run_subprocess")
def test_test_load_live(mock_run: MagicMock, mock_which: MagicMock, tmp_path: Path) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    script = tmp_path / "smoke.js"
    script.write_text("export default function() {}")
    result = runner.invoke(app_test_cli, ["load", str(script), "--vus", "5", "--duration", "5s"])
    assert result.exit_code == 0
    assert mock_run.called


@pytest.mark.parametrize("flag_first", [True, False])
def test_pipeline_dry_run_lists_the_dagger_call(
    tmp_path: Path, cli: Any, process_fake: ProcessFake, flag_first: bool
) -> None:
    """A dry run starts no process and lists the one `dagger call` of the run (#2260)."""
    argv = ["pipeline", str(tmp_path), "--function", "build", "--args", "ref=main"]
    with patch("shutil.which", side_effect=AssertionError("no binary lookup")):
        result = cli(["--dry-run", *argv] if flag_first else [*argv, "--dry-run"])

    assert result.exit_code == 0, result.output
    assert process_fake.calls == []
    assert "SIMULATED_SUCCESS" not in result.output
    assert _plan_lines(result.output) == [
        " ".join(build_dagger_cmd(tmp_path.resolve(), "build", ["ref=main"]))
    ]


@patch("shutil.which", return_value="/usr/local/bin/dagger")
def test_pipeline_runs_the_request_of_its_plan(
    _which: MagicMock, tmp_path: Path, cli: Any, process_fake: ProcessFake
) -> None:
    """The real run starts the command of the plan."""
    argv = ["pipeline", str(tmp_path), "--function", "build"]
    planned = _plan_lines(cli([*argv, "--dry-run"]).output)

    result = cli(argv)

    assert result.exit_code == 0, result.output
    assert [" ".join(call.argv) for call in process_fake.calls] == planned


@patch("shutil.which", return_value="/usr/local/bin/dagger")
@patch("devops_cli.commands.pipeline.run_subprocess")
def test_pipeline_run_live(mock_run: MagicMock, mock_which: MagicMock, tmp_path: Path) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
    result = runner.invoke(pipeline_app, [str(tmp_path), "--function", "build"])
    assert result.exit_code == 0
    assert mock_run.called


@patch("shutil.which", return_value=None)
def test_pipeline_run_missing_dagger(mock_which: MagicMock, tmp_path: Path) -> None:
    result = runner.invoke(pipeline_app, [str(tmp_path)])
    assert result.exit_code == 1
    assert "Dagger CLI binary not found" in result.output


@patch("shutil.which", return_value="/usr/local/bin/dagger")
@patch("devops_cli.commands.pipeline.run_subprocess")
def test_pipeline_run_failure(mock_run: MagicMock, mock_which: MagicMock, tmp_path: Path) -> None:
    mock_run.return_value = MagicMock(returncode=2, stdout="", stderr="")
    result = runner.invoke(pipeline_app, [str(tmp_path)])
    assert result.exit_code == 2
    assert "Pipeline execution failed with exit code 2" in result.output


def test_pipeline_run_validates_path_and_function_name(tmp_path: Path) -> None:
    with pytest.raises((typer.Exit, ValueError)) as raised:
        run_pipeline_cmd(pipeline_path=Path("/non/existent/dagger/pipeline.go"))
    assert str(raised.value) != "" or getattr(raised.value, "exit_code", 1) != 0

    with pytest.raises((typer.Exit, ValueError)) as raised:
        run_pipeline_cmd(pipeline_path=tmp_path, function_name="invalid;rm -rf /")
    assert str(raised.value) != "" or getattr(raised.value, "exit_code", 1) != 0
