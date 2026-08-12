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


def test_ci_coverage_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)

        class Res:
            returncode = 0

        return Res()

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["coverage", "--html"])
    assert result.exit_code == 0
    assert any("--cov=src" in c and "--cov-report=html" in c for c in called)


def test_ci_security_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)

        class Res:
            returncode = 0

        return Res()

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["security", "-s", "high"])
    assert result.exit_code == 0
    assert any("bandit" in c and "-lll" in c for c in called)


def test_ci_all_checks_includes_audit_coverage_and_security(monkeypatch) -> None:
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
    assert "coverage" in result.output
    assert "security" in result.output
    assert any("uv" in c and "audit" in c for c in called)
    assert any("bandit" in c for c in called)
