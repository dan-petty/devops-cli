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
from devops_cli.help.renderer import (
    get_help_text,
    is_help_requested,
    is_version_requested,
    show_help,
    show_version,
)
from devops_cli.main import _show_fast_help, _show_fast_version, main_entry


def test_is_version_requested() -> None:
    assert is_version_requested(["--version"]) is True
    assert is_version_requested(["-v"]) is True
    assert is_version_requested(["repos", "-v"]) is False
    assert is_version_requested(["repos", "list"]) is False
    assert is_version_requested([]) is False


def test_is_help_requested() -> None:
    assert is_help_requested(["--help"]) is True
    assert is_help_requested(["-h"]) is True
    assert is_help_requested(["--dry-run"]) is True
    assert is_help_requested(["repos", "--help"]) is True
    assert is_help_requested(["repos", "-h"]) is True
    assert is_help_requested(["repos", "list"]) is False
    assert is_help_requested([]) is True


def test_show_version(capsys: pytest.CaptureFixture[str]) -> None:
    show_version()
    captured = capsys.readouterr()
    assert "0.2.2" in captured.out


def test_show_help_root(capsys: pytest.CaptureFixture[str]) -> None:
    assert show_help([]) is True
    captured = capsys.readouterr()
    assert "DevOps CLI" in captured.out
    assert "repos" in captured.out


def test_show_help_subcommands(capsys: pytest.CaptureFixture[str]) -> None:
    subcommands = [
        "ai",
        "repos",
        "scan",
        "tf",
        "workspace",
    ]
    for subcmd in subcommands:
        res = show_help([subcmd, "--help"])
        assert res is True
        captured = capsys.readouterr()
        assert len(captured.out) > 0


def test_show_help_unknown_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    assert show_help(["nonexistent_subcommand", "--help"]) is False
    captured = capsys.readouterr()
    assert captured.out == ""


def test_get_help_text_branches() -> None:
    assert get_help_text(["--dry-run"]) is not None
    assert get_help_text(["--help"]) is not None
    assert get_help_text([]) is not None
    assert get_help_text(["unknown", "foo"]) is None


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


def test_main_helpers_and_entrypoint(capsys: pytest.CaptureFixture[str]) -> None:
    _show_fast_version()
    captured_v = capsys.readouterr()
    assert "0.2.2" in captured_v.out

    _show_fast_help()
    captured_h = capsys.readouterr()
    assert "DevOps CLI" in captured_h.out

    with patch("devops_cli.entry.main") as mock_main:
        main_entry()
        mock_main.assert_called_once()


def test_entry_main_version(capsys: pytest.CaptureFixture[str]) -> None:
    main(["devops", "--version"])
    captured = capsys.readouterr()
    assert "0.2.2" in captured.out


def test_entry_main_help(capsys: pytest.CaptureFixture[str]) -> None:
    main(["devops", "--help"])
    captured = capsys.readouterr()
    assert "DevOps CLI" in captured.out


def test_entry_main_binary_path_argv(capsys: pytest.CaptureFixture[str]) -> None:
    main(["/usr/local/bin/devops", "--version"])
    captured = capsys.readouterr()
    assert "0.2.2" in captured.out


def test_entry_main_dry_run_delegation() -> None:
    mock_app = MagicMock()
    with patch("devops_cli.main.app", mock_app):
        set_dry_run(False)
        main(["devops", "--dry-run", "repos", "status"])
        assert is_dry_run() is True
        mock_app.assert_called_once_with(["--dry-run", "repos", "status"])
        set_dry_run(False)


def test_entry_main_default_sys_argv() -> None:
    with patch("sys.argv", ["devops", "--version"]):
        main()
