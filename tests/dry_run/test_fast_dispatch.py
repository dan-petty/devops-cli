"""Comprehensive unit tests for fast CLI entry interception, help rendering, and dry run dispatch."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import devops_cli.dry_run
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


def test_a_dry_run_after_the_separator_belongs_to_the_passed_through_command() -> None:
    """`devops k8s run-job -- roadmap sync --dry-run` runs the Job; the Job previews."""
    assert (
        is_dry_run_requested(["k8s", "run-job", "--", "roadmap", "sync", "--dry-run"]),
        is_dry_run_requested(["k8s", "run-job", "--dry-run", "--", "--version"]),
    ) == (False, True)


def test_a_help_flag_after_the_separator_runs_the_command_and_keeps_its_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`devops k8s run-job -- review --help` runs the Job, so the Job's exit code is kept."""
    import sys
    import types

    import typer

    import devops_cli.main as main_module

    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENABLED", "false")
    module = types.ModuleType("fake_passthrough_commands")
    module.app = typer.Typer()  # type: ignore[attr-defined]
    received: list[list[str]] = []

    @module.app.command()  # type: ignore[attr-defined]
    def run(args: list[str]) -> None:
        received.append(args)
        raise typer.Exit(3)

    monkeypatch.setitem(sys.modules, "fake_passthrough_commands", module)
    with pytest.raises(typer.Exit) as exited:
        main_module._delegate("fake_passthrough_commands", "fake", ["--", "review", "--help"])
    assert (exited.value.exit_code, received) == (3, [["review", "--help"]])


def test_set_and_is_dry_run() -> None:
    set_dry_run(False)
    assert is_dry_run() is False
    set_dry_run(True)
    assert is_dry_run() is True
    set_dry_run(False)
    assert is_dry_run() is False


def test_format_command(tmp_path: Path) -> None:
    cmd = ["git", "status"]
    repo = tmp_path / "repo"
    assert format_command(cmd) == "git status"
    assert format_command(cmd, cwd=str(repo)) == f"(cd {repo} && git status)"


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
    from devops_cli.dry_run.models import CommandDryRunResult

    cls = getattr(devops_cli.dry_run, "CommandDryRunResult")
    assert cls is CommandDryRunResult
    with pytest.raises(AttributeError, match="nonexistent_attr_xyz"):
        _ = getattr(devops_cli.dry_run, "nonexistent_attr_xyz")


def test_core_dry_run_exports() -> None:
    from devops_cli.dry_run.models import CommandDryRunResult
    from devops_cli.dry_run.state import (
        format_command,
        is_dry_run,
        set_dry_run,
    )

    assert devops_cli.dry_run.format_command is format_command
    assert devops_cli.dry_run.is_dry_run is is_dry_run
    assert devops_cli.dry_run.set_dry_run is set_dry_run
    assert devops_cli.dry_run.CommandDryRunResult is CommandDryRunResult


def test_main_helpers_and_entrypoint() -> None:
    with patch("devops_cli.entry.main") as mock_main:
        main_entry()
        mock_main.assert_called_once()


@pytest.mark.parametrize(
    ("prog_arg",),
    [
        pytest.param("devops", id="relative-devops-binary"),
        pytest.param("/usr/local/bin/devops", id="absolute-devops-binary"),
    ],
)
def test_entry_main_version(capsys: pytest.CaptureFixture[str], prog_arg: str) -> None:
    from devops_cli import __version__

    with pytest.raises(SystemExit) as exc_info:
        main([prog_arg, "--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out


def test_entry_main_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["devops", "--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "DevOps CLI" in captured.out


def test_entry_main_dry_run_delegation() -> None:
    mock_app = MagicMock()
    with patch("devops_cli.main.app", mock_app):
        set_dry_run(False)
        main(["devops", "--dry-run", "repos", "status"])
        assert is_dry_run() is True
        mock_app.assert_called_once_with(["--dry-run", "repos", "status"], prog_name="devops")
        set_dry_run(False)


def test_a_commands_own_dry_run_marks_the_invocation_after_the_root_callback_clears_it() -> None:
    """The root callback clears the state for a command's own `--dry-run`; the invocation
    stays a dry run, so the process makes no external request such as a telemetry export."""
    from devops_cli.dry_run.state import in_dry_run_invocation

    def root_callback_clears(*_: object, **__: object) -> None:
        set_dry_run(False)

    seen = []
    with patch("devops_cli.main.app", MagicMock(side_effect=root_callback_clears)):
        for argv in (
            ["k8s", "push-secrets", "--dry-run"],
            ["k8s", "run-job", "--", "roadmap", "sync", "--dry-run"],
        ):
            main(argv)
            seen.append((is_dry_run(), in_dry_run_invocation()))
    assert seen == [(False, True), (False, False)]


def test_entry_main_default_sys_argv(capsys: pytest.CaptureFixture[str]) -> None:
    from devops_cli import __version__

    with patch("sys.argv", ["devops", "--version"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
    assert exc_info.value.code == 0
    assert __version__ in capsys.readouterr().out


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
