"""Tests for OpenTofu / Terraform PR plan diff notifier CLI."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from devops_cli.commands.tf import app as tf_app

runner = CliRunner()


def test_tf_notify_plan_cli() -> None:
    """Verify devops tf notify-plan command."""
    res = runner.invoke(tf_app, ["notify-plan", "--dry-run"])
    assert res.exit_code == 0
    assert "post_tf_pr_comment" in res.output

    res_json = runner.invoke(tf_app, ["notify-plan", "--json", "--pr", "42"])
    assert res_json.exit_code == 0
    data = json.loads(res_json.output)
    assert data["pr"] == 42
    assert "### 🚀 OpenTofu / Terraform Plan Summary" in data["comment"]
