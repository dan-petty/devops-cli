"""Tests for devops ci command group."""

from __future__ import annotations

from typer.testing import CliRunner

from devops_cli.commands.ci import app

runner = CliRunner()


def test_ci_audit_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)

        class Res:
            returncode = 0

        return Res()

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["audit"])
    assert result.exit_code == 0
    assert any("uv" in c and "audit" in c for c in called)


def test_ci_all_checks_includes_audit(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)

        class Res:
            returncode = 0

        return Res()

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "audit" in result.output
    assert any("uv" in c and "audit" in c for c in called)
