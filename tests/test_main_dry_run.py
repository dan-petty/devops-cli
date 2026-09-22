"""Tests for global CLI dry-run behavior."""

from __future__ import annotations

from typer.testing import CliRunner

import devops_cli.main as main_module

runner = CliRunner()


def test_global_dry_run_skips_delegated_proxy(monkeypatch) -> None:
    called = False

    def _fake_delegate(module_path: str, command_name: str, args: list[str]) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(main_module, "_delegate", _fake_delegate)

    result = runner.invoke(main_module.app, ["--dry-run", "repos", "--unknown-option"])

    assert (
        result.exit_code,
        not called,
        "Would run delegated command" in result.output,
        "devops repos --unknown-option" in result.output,
    ) == (0, True, True, True)


def test_trailing_dry_run_delegates_to_subcommand(monkeypatch) -> None:
    delegated_args: list[str] = []

    def _fake_delegate(module_path: str, command_name: str, args: list[str]) -> None:
        delegated_args.extend(args)

    monkeypatch.setattr(main_module, "_delegate", _fake_delegate)

    result = runner.invoke(main_module.app, ["repos", "sync", "--dry-run"])

    assert (result.exit_code, delegated_args) == (0, ["sync", "--dry-run"])


def test_an_exported_dry_run_variable_is_honoured(monkeypatch) -> None:
    """`is_dry_run()` reads `DEVOPS_CLI_DRY_RUN`, but the root callback cleared it.

    Without the flag the callback called `set_dry_run(False)`, which pops the variable, so
    a wrapper or CI job that exported it got a live run and no indication that its request
    had been dropped. That is how a `sync-notes --all` intended as a preview republished
    every release description in this repository.
    """
    called = False

    def _fake_delegate(module_path: str, command_name: str, args: list[str]) -> None:
        nonlocal called
        called = True

    from devops_cli.dry_run import set_dry_run

    monkeypatch.setattr(main_module, "_delegate", _fake_delegate)
    set_dry_run(False)  # this process has not asked; the variable below is the caller's
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "1")

    result = runner.invoke(main_module.app, ["repos", "sync"])

    assert (result.exit_code, called) == (0, False)


def test_a_dry_run_flag_does_not_latch_for_later_commands(monkeypatch) -> None:
    """The flag applies to the invocation carrying it, not to the rest of the process.

    Honouring an inherited variable naively made one `--dry-run` turn every later command
    in the same process into a preview, which in a long-lived process means it never runs
    anything again.
    """
    calls: list[str] = []

    def _fake_delegate(module_path: str, command_name: str, args: list[str]) -> None:
        calls.append(command_name)

    monkeypatch.setattr(main_module, "_delegate", _fake_delegate)
    monkeypatch.delenv("DEVOPS_CLI_DRY_RUN", raising=False)

    runner.invoke(main_module.app, ["--dry-run", "repos", "sync"])
    runner.invoke(main_module.app, ["repos", "sync"])

    assert calls == ["repos"]


def test_no_flag_and_no_variable_still_executes(monkeypatch) -> None:
    """Honouring the variable must not leave dry-run latched on for ordinary runs."""
    called = False

    def _fake_delegate(module_path: str, command_name: str, args: list[str]) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(main_module, "_delegate", _fake_delegate)
    monkeypatch.delenv("DEVOPS_CLI_DRY_RUN", raising=False)

    result = runner.invoke(main_module.app, ["repos", "sync"])

    assert (result.exit_code, called) == (0, True)
