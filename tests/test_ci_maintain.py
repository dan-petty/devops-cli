"""Unit tests for devops ci maintain command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.ci import app, get_check_spec

runner = CliRunner()


def test_ci_maintain_dry_run() -> None:
    result = runner.invoke(app, ["maintain", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY_RUN" in result.stdout


@patch("devops_cli.commands.ci._returncode", return_value=0)
@patch("devops_cli.commands.ci._run", return_value=True)
@patch("devops_cli.commands.ci._verify_python_314_environment", return_value=True)
def test_ci_maintain_live(
    mock_verify: MagicMock, mock_run: MagicMock, mock_returncode: MagicMock
) -> None:
    """The audit runs through the audit check's own command, never a real `uv audit` (#1697)."""
    result = runner.invoke(app, ["maintain", "--fix"])
    assert (
        result.exit_code,
        mock_run.called,
        [call.args[0] for call in mock_returncode.call_args_list],
    ) == (0, True, [get_check_spec("audit").cmd])


@pytest.mark.parametrize(
    ("returncode", "reported"),
    [(1, "found vulnerabilities"), (2, "could not run")],
    ids=["vulnerable", "could-not-run"],
)
def test_maintain_audits_with_uv_audit_and_says_whether_the_audit_ran(
    returncode: int, reported: str
) -> None:
    """uv exits 1 when a check fails and 2 when it cannot run, such as with no network: only the
    first means vulnerabilities (#861)."""
    ran: list[list[str]] = []

    def exit_code(cmd: list[str], **_: object) -> int:
        ran.append(cmd)
        return returncode if cmd == get_check_spec("audit").cmd else 0

    with (
        patch("devops_cli.commands.ci._returncode", side_effect=exit_code),
        patch("devops_cli.commands.ci._verify_python_314_environment", return_value=True),
    ):
        result = runner.invoke(app, ["maintain"])
    assert (
        result.exit_code,
        ["uv", "audit"] in ran,
        any("pip-audit" in part for cmd in ran for part in cmd),
        reported in " ".join(result.output.split()),
    ) == (1, True, False, True)
