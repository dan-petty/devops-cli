"""Tests for devops ci command group."""

from __future__ import annotations

import sys

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


def test_ci_actionlint_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)

        class Res:
            returncode = 0

        return Res()

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["actionlint"])
    assert result.exit_code == 0
    assert any("actionlint" in c for c in called)


def test_ci_lint_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)

        class Res:
            returncode = 0

        return Res()

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["lint", "--fix"])
    assert result.exit_code == 0
    assert any("ruff" in c and "check" in c and "--fix" in c for c in called)


def test_ci_format_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)

        class Res:
            returncode = 0

        return Res()

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["format"])
    assert result.exit_code == 0
    assert any("ruff" in c and "format" in c and "--check" in c for c in called)


def test_ci_typecheck_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)

        class Res:
            returncode = 0

        return Res()

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["typecheck"])
    assert result.exit_code == 0
    assert any("mypy" in c and "--python-version" in c and "3.14" in c for c in called)


def test_ci_test_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)

        class Res:
            returncode = 0

        return Res()

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["test", "-v", "-k", "unit"])
    assert result.exit_code == 0
    assert any("pytest" in c and "-v" in c and "-k" in c for c in called)


def test_ci_docs_command(monkeypatch) -> None:
    called = []

    def mock_run(cmd, *args, **kwargs):
        called.append(cmd)

        class Res:
            returncode = 0

        return Res()

    monkeypatch.setattr("subprocess.run", mock_run)

    result = runner.invoke(app, ["docs"])
    assert result.exit_code == 0
    assert any("devops" in c and "docs" in c and "check" in c for c in called)


def test_ci_python_version_check_failure(monkeypatch) -> None:
    monkeypatch.setattr(sys, "version_info", (3, 12, 0))

    result = runner.invoke(app, ["typecheck"])
    assert result.exit_code == 1
    assert "Strict Python 3.14+ requirement failed" in result.output


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
    assert "actionlint" in result.output
    assert any("uv" in c and "audit" in c for c in called)
    assert any("bandit" in c for c in called)
    assert any("actionlint" in c for c in called)
