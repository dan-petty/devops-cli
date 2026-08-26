"""Unit tests for devops ci maintain command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.ci import app

runner = CliRunner()


def test_ci_maintain_dry_run() -> None:
    result = runner.invoke(app, ["maintain", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY_RUN" in result.stdout


@patch("devops_cli.commands.ci._run", return_value=True)
@patch("devops_cli.commands.ci._verify_python_314_environment", return_value=True)
def test_ci_maintain_live(mock_verify: MagicMock, mock_run: MagicMock) -> None:
    result = runner.invoke(app, ["maintain", "--fix"])
    assert result.exit_code == 0
    assert mock_run.called
