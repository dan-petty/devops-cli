"""Comprehensive unit tests for fast CLI entry interception, help rendering, and dry run dispatch."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import devops_cli.core
import devops_cli.core.dry_run
import devops_cli.dry_run
import devops_cli.models.dry_run
from devops_cli.dry_run.state import (
    format_command,
    is_dry_run,
    is_dry_run_requested,
    render_dry_run_result,
    set_dry_run,
)
from devops_cli.entry import main
from devops_cli.main import main_entry


def test_is_dry_run_requested() -> None:
    assert is_dry_run_requested(["--dry-run", "repos", "status"]) is True
    assert is_dry_run_requested(["repos", "status", "--dry-run"]) is True
    assert is_dry_run_requested(["repos", "status"]) is False
    assert is_dry_run_requested([]) is False


def test_set_and_is_dry_run() -> None:
    set_dry_run(False)
    assert is_dry_run() is False
    set_dry_run(True)
    assert is_dry_run() is True
    set_dry_run(False)
    assert is_dry_run() is False


def test_format_command() -> None:
    cmd = ["git", "status"]
    assert format_command(cmd) == "git status"
    assert format_command(cmd, cwd="/tmp/repo") == "(cd /tmp/repo && git status)"


def test_render_dry_run_result(capsys: pytest.CaptureFixture[str]) -> None:
    render_dry_run_result(
        command="devops repos sync",
        action="sync",
        target="dan-petty/devops-cli",
        details={"branch": "main"},
    )
    captured = capsys.readouterr()
    assert "dry-run" in captured.out or "devops repos sync" in captured.out


def test_dry_run_getattr() -> None:
    cls = getattr(devops_cli.dry_run, "CommandDryRunResult")
    assert cls is not None
    with pytest.raises(AttributeError):
        _ = getattr(devops_cli.dry_run, "nonexistent_attr_xyz")


def test_core_dry_run_exports() -> None:
    assert callable(devops_cli.core.dry_run.format_command)
    assert callable(devops_cli.core.dry_run.is_dry_run)
    assert callable(devops_cli.core.dry_run.set_dry_run)
    assert devops_cli.models.dry_run.CommandDryRunResult is not None


def test_core_getattr_exports() -> None:
    assert callable(getattr(devops_cli.core, "run_subprocess"))
    assert callable(getattr(devops_cli.core, "find_repo_root"))
    assert callable(getattr(devops_cli.core, "validate_path"))
    assert callable(getattr(devops_cli.core, "is_dry_run"))
    with pytest.raises(AttributeError):
        _ = getattr(devops_cli.core, "nonexistent_core_attr")


def test_main_helpers_and_entrypoint() -> None:
    with patch("devops_cli.entry.main") as mock_main:
        main_entry()
        mock_main.assert_called_once()


def test_entry_main_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["devops", "--version"])
    captured = capsys.readouterr()
    assert "0.2.2" in captured.out


def test_entry_main_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["devops", "--help"])
    captured = capsys.readouterr()
    assert "DevOps CLI" in captured.out


def test_entry_main_binary_path_argv(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["/usr/local/bin/devops", "--version"])
    captured = capsys.readouterr()
    assert "0.2.2" in captured.out


def test_entry_main_dry_run_delegation() -> None:
    mock_app = MagicMock()
    with patch("devops_cli.main.app", mock_app):
        set_dry_run(False)
        main(["devops", "--dry-run", "repos", "status"])
        assert is_dry_run() is True
        mock_app.assert_called_once_with(["--dry-run", "repos", "status"], prog_name="devops")
        set_dry_run(False)


def test_entry_main_default_sys_argv() -> None:
    with patch("sys.argv", ["devops", "--version"]):
        with pytest.raises(SystemExit):
            main()


def test_entrypoint_flows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test fast CLI entrypoint flows including shell completion, version, help, and dry-run."""
    from devops_cli.entry import is_completion_requested

    # 1. Shell completion detection and dispatch
    monkeypatch.setenv("_DEVOPS_COMPLETE", "complete_zsh")
    assert is_completion_requested() is True
    with patch("devops_cli.main.app") as mock_complete_app:
        main(["repos"])
        mock_complete_app.assert_called_once()
    monkeypatch.delenv("_DEVOPS_COMPLETE", raising=False)

    monkeypatch.setenv("_TYPER_COMPLETE_ARGS", "devops repos")
    assert is_completion_requested() is True
    monkeypatch.delenv("_TYPER_COMPLETE_ARGS", raising=False)
    assert is_completion_requested() is False

    # 2. Subcommand without devops prefix
    with patch("devops_cli.main.app") as mock_app:
        main(["repos", "list", "--dry-run"])
        mock_app.assert_called_once()
