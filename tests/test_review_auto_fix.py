"""Tests for automated PR remediation branch generator and auto-fix CLI."""

from __future__ import annotations

from typer.testing import CliRunner

from devops_cli.commands.review import app as review_app

runner = CliRunner()


def test_review_auto_fix_cli() -> None:
    """Verify devops ai review auto-fix command."""
    res = runner.invoke(review_app, ["auto-fix", "cwe-200-leak", "--dry-run"])
    assert res.exit_code == 0
    assert (
        "Created remediation topic branch" in res.output or "fix/finding-cwe-200-leak" in res.output
    )
