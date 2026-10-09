"""Tests for global CLI dry-run behavior."""

from __future__ import annotations

import inspect

import pytest
from click import Command, Group
from typer.testing import CliRunner

import devops_cli.main as main_module
from devops_cli.core.command_resolver import module_click_command
from devops_cli.dry_run import set_dry_run

runner = CliRunner()


def test_global_dry_run_unknown_option_exits_2(monkeypatch) -> None:
    called = False

    def _fake_delegate(module_path: str, command_name: str, args: list[str]) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(main_module, "_delegate", _fake_delegate)

    result = runner.invoke(main_module.app, ["--dry-run", "repos", "--unknown-option"])

    assert (result.exit_code, called, "No such option" in result.output) == (2, False, True)


def test_global_dry_run_non_declaring_command_prints_generic_preview(monkeypatch) -> None:
    called = False

    def _fake_delegate(module_path: str, command_name: str, args: list[str]) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(main_module, "_delegate", _fake_delegate)

    result = runner.invoke(main_module.app, ["--dry-run", "install-tools"])

    assert (
        result.exit_code,
        not called,
        "Would run delegated command: devops install-tools" in result.output,
    ) == (0, True, True)


def test_trailing_dry_run_delegates_to_subcommand(monkeypatch) -> None:
    delegated_args: list[str] = []

    def _fake_delegate(module_path: str, command_name: str, args: list[str]) -> None:
        delegated_args.extend(args)

    monkeypatch.setattr(main_module, "_delegate", _fake_delegate)

    result = runner.invoke(main_module.app, ["repos", "sync", "--dry-run"])

    assert (result.exit_code, delegated_args) == (0, ["sync", "--dry-run"])


def test_an_exported_dry_run_variable_is_honoured(monkeypatch) -> None:
    """An exported DEVOPS_CLI_DRY_RUN forwards --dry-run to declaring delegated commands."""
    delegated_args: list[str] = []

    def _fake_delegate(module_path: str, command_name: str, args: list[str]) -> None:
        delegated_args.extend(args)

    monkeypatch.setattr(main_module, "_delegate", _fake_delegate)
    set_dry_run(False)
    monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "1")

    result = runner.invoke(main_module.app, ["repos", "sync"])

    assert (result.exit_code, delegated_args) == (0, ["sync", "--dry-run"])


def test_a_dry_run_flag_does_not_latch_for_later_commands(monkeypatch) -> None:
    """The flag applies to the invocation carrying it, not to the rest of the process."""
    calls: list[tuple[str, list[str]]] = []

    def _fake_delegate(module_path: str, command_name: str, args: list[str]) -> None:
        calls.append((command_name, list(args)))

    monkeypatch.setattr(main_module, "_delegate", _fake_delegate)
    monkeypatch.delenv("DEVOPS_CLI_DRY_RUN", raising=False)

    runner.invoke(main_module.app, ["--dry-run", "repos", "sync"])
    runner.invoke(main_module.app, ["repos", "sync"])

    assert calls == [
        ("repos", ["sync", "--dry-run"]),
        ("repos", ["sync"]),
    ]


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


@pytest.mark.parametrize(
    ("cli_args", "expected_args"),
    [
        (
            ["--dry-run", "k8s", "configure-urls", "--stack", "infra"],
            ["configure-urls", "--dry-run", "--stack", "infra"],
        ),
        (
            ["--dry-run", "tf", "apply"],
            ["apply", "--dry-run"],
        ),
        (
            ["--dry-run", "tf", "destroy"],
            ["destroy", "--dry-run"],
        ),
        (
            ["--dry-run", "sandbox", "deploy", "--", "echo", "test"],
            ["deploy", "--dry-run", "--", "echo", "test"],
        ),
    ],
)
def test_global_dry_run_forwards_flag_correctly(
    monkeypatch, cli_args: list[str], expected_args: list[str]
) -> None:
    """Verify reachable dry-run forwarding places the flag before positionals and '--'."""
    forwarded: list[str] = []

    def _fake_delegate(module_path: str, command_name: str, args: list[str]) -> None:
        forwarded.extend(args)

    monkeypatch.setattr(main_module, "_delegate", _fake_delegate)
    result = runner.invoke(main_module.app, cli_args)

    assert (result.exit_code, forwarded) == (0, expected_args)


def test_global_dry_run_help_fast_path() -> None:
    """--help should bypass dry-run forwarding and display help immediately."""
    result = runner.invoke(main_module.app, ["--dry-run", "repos", "--help"])
    assert (result.exit_code, "Usage: devops repos" in result.output) == (0, True)


def _collect_command_dry_run_info(
    cmd: Command | Group, path: list[str]
) -> list[tuple[str, str, bool, bool]]:
    results: list[tuple[str, str, bool, bool]] = []
    if isinstance(cmd, Group):
        for sub_name, sub in cmd.commands.items():
            results.extend(_collect_command_dry_run_info(sub, [*path, sub_name]))
        return results

    cb = cmd.callback
    if cb is None:
        return results

    try:
        src = inspect.getsource(cb)
    except OSError, TypeError:
        src = ""

    has_ref = any(k in src for k in ["is_dry_run", "render_dry_run_result", "dry_run_command"])
    has_param = any(
        p.name == "dry_run" or "--dry-run" in getattr(p, "opts", []) for p in cmd.params
    )
    uses_param = any(
        k in src for k in ["dry_run", "is_dry_run", "render_dry_run_result"]
    ) or getattr(cb, "_dry_run_command", False)
    results.append(
        (" ".join(path), cb.__name__, has_ref and not has_param, has_param and not uses_param)
    )
    return results


def test_invariants_all_dry_run_commands_consistent() -> None:
    """Every command referencing dry-run declares --dry-run, and every declaring command reads it."""
    missing: list[str] = []
    unused: list[str] = []

    for name, (module_path, _) in main_module._COMMAND_SPECS.items():
        click_cmd = module_click_command(module_path)
        for cmd_name, cb_name, is_missing, is_unused in _collect_command_dry_run_info(
            click_cmd, [name]
        ):
            if is_missing:
                missing.append(f"{cmd_name} ({cb_name})")
            if is_unused:
                unused.append(f"{cmd_name} ({cb_name})")

    assert (missing, unused) == ([], [])
