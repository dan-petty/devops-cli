"""The `devops` entry point: its argv, shell completion and dry-run state."""

from __future__ import annotations

import sys

import pytest

from devops_cli import __version__
from devops_cli.dry_run import in_dry_run_invocation, is_dry_run
from devops_cli.entry import is_completion_requested, main
from tests.support.fakes.process import ProcessFake


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["devops", "--version"], id="relative-devops-binary"),
        pytest.param(["/usr/local/bin/devops", "--version"], id="absolute-devops-binary"),
        pytest.param(["--version"], id="no-program-word"),
    ],
)
def test_the_version_flag_prints_the_version(
    capsys: pytest.CaptureFixture[str], argv: list[str]
) -> None:
    with pytest.raises(SystemExit) as exited:
        main(argv)

    assert exited.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_the_help_flag_prints_the_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exited:
        main(["devops", "--help"])

    assert exited.value.code == 0
    assert "DevOps CLI" in capsys.readouterr().out


def test_the_entry_point_reads_the_arguments_of_the_process(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["devops", "--version"])

    with pytest.raises(SystemExit) as exited:
        main()

    assert exited.value.code == 0
    assert __version__ in capsys.readouterr().out


@pytest.mark.parametrize(
    ("environment", "requested"),
    [
        pytest.param({"_DEVOPS_COMPLETE": "complete_zsh"}, True, id="devops-variable"),
        pytest.param({"_TYPER_COMPLETE_ARGS": "devops repos"}, True, id="typer-variable"),
        pytest.param({}, False, id="no-variable"),
    ],
)
def test_shell_completion_is_requested_by_a_completion_variable(
    monkeypatch: pytest.MonkeyPatch, environment: dict[str, str], requested: bool
) -> None:
    for name in ("_DEVOPS_COMPLETE", "_TYPER_COMPLETE_ARGS"):
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    assert is_completion_requested() is requested


def test_a_completion_request_prints_the_completion_script(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("_DEVOPS_COMPLETE", "source_zsh")

    with pytest.raises(SystemExit) as exited:
        main(["repos"])

    assert exited.value.code == 0
    assert "#compdef devops" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["devops", "--dry-run", "tf", "apply"], id="with-program-word"),
        pytest.param(["--dry-run", "tf", "apply"], id="without-program-word"),
    ],
)
def test_a_dry_run_argv_plans_the_command_and_leaves_the_dry_run_state_on(
    capsys: pytest.CaptureFixture[str], process_fake: ProcessFake, argv: list[str]
) -> None:
    with pytest.raises(SystemExit) as exited:
        main(argv)

    assert exited.value.code == 0
    assert "Plan for applying OpenTofu infrastructure" in capsys.readouterr().out
    assert process_fake.calls == []
    assert is_dry_run() is True


@pytest.mark.parametrize(
    ("argv", "is_dry_run_invocation", "started"),
    [
        pytest.param(["uv", "sync", "--dry-run"], True, [], id="own-flag-of-the-command"),
        pytest.param(
            ["uv", "run", "--", "pytest", "--dry-run"],
            False,
            [("run", "pytest", "--dry-run")],
            id="flag-after-the-separator",
        ),
    ],
)
def test_the_own_dry_run_flag_of_a_command_marks_the_invocation_after_the_root_clears_the_state(
    process_fake: ProcessFake,
    argv: list[str],
    is_dry_run_invocation: bool,
    started: list[tuple[str, ...]],
) -> None:
    """The root command clears the dry-run state for the `--dry-run` of a command, which the
    command reads itself. The invocation stays a dry run, so the process makes no external request,
    such as a telemetry export. A `--dry-run` after `--` belongs to the passed-through command."""
    with pytest.raises(SystemExit) as exited:
        main(argv)

    assert exited.value.code == 0
    assert (is_dry_run(), in_dry_run_invocation()) == (False, is_dry_run_invocation)
    assert [call.argv[-3:] for call in process_fake.calls] == started


def test_an_exported_dry_run_request_survives_a_commands_own_dry_run_flag(
    monkeypatch: pytest.MonkeyPatch,
    process_fake: ProcessFake,
) -> None:
    """An exported DEVOPS_CLI_DRY_RUN applies to every command in the environment,
    so a command's own --dry-run flag must not cause the root callback to clear it."""
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "1")
    with pytest.raises(SystemExit) as exited:
        main(["uv", "sync", "--dry-run"])

    assert exited.value.code == 0
    assert is_dry_run() is True
    assert in_dry_run_invocation() is True
    assert process_fake.calls == []


def test_an_early_stop_option_with_dry_run_records_the_invocation_mark(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An early-stop option such as --version exits before the root callback runs,
    but the dry-run invocation mark is recorded for exit telemetry."""
    with pytest.raises(SystemExit) as exited:
        main(["devops", "--dry-run", "--version"])

    assert exited.value.code == 0
    assert __version__ in capsys.readouterr().out
    assert in_dry_run_invocation() is True


def test_entry_point_module_does_not_import_set_dry_run() -> None:
    """src/devops_cli/entry.py sets no dry-run state and leaves it to the root callback."""
    from tests.support.paths import REPO_ROOT

    source = (REPO_ROOT / "src" / "devops_cli" / "entry.py").read_text(encoding="utf-8")
    assert "set_dry_run" not in source
