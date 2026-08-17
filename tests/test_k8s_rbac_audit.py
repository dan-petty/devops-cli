"""Tests for Kubernetes RBAC audit policy scanner."""

from __future__ import annotations

from typer.testing import CliRunner

from devops_cli.commands.k8s import app

runner = CliRunner()


def test_k8s_rbac_audit_dry_run() -> None:
    result = runner.invoke(app, ["rbac-audit"], env={"DEVOPS_CLI_DRY_RUN": "true"})
    assert result.exit_code == 0
    assert "rbac_audit_scan" in result.output
