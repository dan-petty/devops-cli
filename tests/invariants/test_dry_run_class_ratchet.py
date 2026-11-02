"""Ratchet invariant: command dry-run classification and gaps list (#2230).

Every command reachable from `_COMMAND_SPECS` must either declare a dry-run class
('request-plan' or 'no-external-request') or appear in `tests/fixtures/dry_run_gaps.json`.
"""

from __future__ import annotations

import importlib
import json
from typing import Any

import typer
from typer.testing import CliRunner

from devops_cli import main as main_module
from devops_cli.config.constants import CONST_MCP_EXPOSURE_TABLE
from devops_cli.core.cli import new_typer
from devops_cli.dry_run.decorator import (
    CONST_DRY_RUN_CLASSES,
    dry_run_class,
    get_dry_run_class,
)
from devops_cli.main import _COMMAND_SPECS
from tests.support.paths import FIXTURES

CONST_GAPS_FILE = FIXTURES / "dry_run_gaps.json"
runner = CliRunner()


def _extract_commands(cmd: Any, prefix: str) -> dict[str, Any]:
    """Recursively collect leaf commands and runnable group callbacks."""
    results: dict[str, Any] = {}
    subcommands = getattr(cmd, "commands", None)
    if subcommands:
        if getattr(cmd, "invoke_without_command", False) and getattr(cmd, "callback", None):
            results[prefix] = cmd
        for sub_name, subcmd in sorted(subcommands.items()):
            child_prefix = f"{prefix} {sub_name}".strip()
            results.update(_extract_commands(subcmd, child_prefix))
    else:
        results[prefix] = cmd
    return results


def _collect_reachable_commands() -> dict[str, Any]:
    """Traverse all CLI entrypoints in _COMMAND_SPECS and collect commands."""
    all_cmds: dict[str, Any] = {}
    for name, (module_path, _) in sorted(_COMMAND_SPECS.items()):
        mod = importlib.import_module(module_path)
        app = getattr(mod, "app")
        click_cmd = typer.main.get_command(app)
        all_cmds.update(_extract_commands(click_cmd, name))
    return all_cmds


def _command_declares_dry_run(cmd: Any) -> bool:
    """Check if a Click command declares a --dry-run option."""
    params = getattr(cmd, "params", [])
    return any(
        getattr(p, "name", "") == "dry_run" or "--dry-run" in getattr(p, "opts", []) for p in params
    )


def audit_dry_run_ratchet(commands: dict[str, Any], gaps: set[str]) -> list[str]:
    """Audit commands against the gap list according to ratchet invariants."""
    errors: list[str] = []

    # Criterion 3: check for stale gap entries that no longer match any command.
    for gap in sorted(gaps):
        if gap not in commands:
            errors.append(
                f"Entry '{gap}' in tests/fixtures/dry_run_gaps.json does not match any reachable command path."
            )

    for path, cmd in sorted(commands.items()):
        cls = get_dry_run_class(cmd)

        # Criterion 1: command with no class and not in gaps list.
        if cls is None:
            if path not in gaps:
                classes_str = ", ".join(repr(c) for c in CONST_DRY_RUN_CLASSES)
                errors.append(
                    f"Command '{path}' has no dry-run class ({classes_str}) and is not in tests/fixtures/dry_run_gaps.json."
                )
        else:
            # Criterion 2: command has class but is still in gaps list.
            if path in gaps:
                errors.append(
                    f"Command '{path}' has dry-run class '{cls}' but is still listed in tests/fixtures/dry_run_gaps.json. Remove this entry from the list."
                )

            # Criterion 4: request-plan command must declare --dry-run.
            if cls == "request-plan" and not _command_declares_dry_run(cmd):
                errors.append(
                    f"Command '{path}' has class 'request-plan' but does not declare --dry-run."
                )

    return errors


def test_ratchet_fails_when_command_lacks_class_and_not_in_gaps() -> None:
    """Criterion 1: unclassified command not in gaps list fails with class names and fixture path."""
    app = new_typer(no_args_is_help=True)

    @app.command(name="unclassified")
    def unclassified() -> None:
        pass

    @app.command(name="dummy")
    def dummy() -> None:
        pass

    click_cmd = typer.main.get_command(app)
    cmds = _extract_commands(click_cmd, "demo")
    errors = audit_dry_run_ratchet(cmds, {"demo dummy"})

    assert len(errors) == 1
    assert "Command 'demo unclassified' has no dry-run class" in errors[0]
    assert "'request-plan'" in errors[0]
    assert "'no-external-request'" in errors[0]
    assert "tests/fixtures/dry_run_gaps.json" in errors[0]


def test_ratchet_fails_when_classified_command_remains_in_gaps() -> None:
    """Criterion 2: classified command still in gap list tells author to remove entry."""
    app = new_typer(no_args_is_help=True)

    @app.command(name="classified")
    @dry_run_class("no-external-request")
    def classified() -> None:
        pass

    @app.command(name="dummy")
    def dummy() -> None:
        pass

    click_cmd = typer.main.get_command(app)
    cmds = _extract_commands(click_cmd, "demo")
    errors = audit_dry_run_ratchet(cmds, {"demo classified", "demo dummy"})

    assert len(errors) == 1
    assert "Command 'demo classified' has dry-run class 'no-external-request'" in errors[0]
    assert "Remove this entry from the list" in errors[0]


def test_ratchet_fails_when_gap_entry_is_not_a_command() -> None:
    """Criterion 3: stale entry in gaps list fails."""
    app = new_typer(no_args_is_help=True)

    @app.command(name="existing")
    @dry_run_class("no-external-request")
    def existing() -> None:
        pass

    @app.command(name="dummy")
    def dummy() -> None:
        pass

    click_cmd = typer.main.get_command(app)
    cmds = _extract_commands(click_cmd, "demo")
    errors = audit_dry_run_ratchet(cmds, {"demo non_existent", "demo dummy"})

    assert len(errors) == 1
    assert (
        "Entry 'demo non_existent' in tests/fixtures/dry_run_gaps.json does not match any reachable command path."
        in errors[0]
    )


def test_ratchet_fails_when_request_plan_lacks_dry_run() -> None:
    """Criterion 4: request-plan command without --dry-run option fails."""
    app = new_typer(no_args_is_help=True)

    @app.command(name="missing-option")
    @dry_run_class("request-plan")
    def missing_option() -> None:
        pass

    @app.command(name="dummy")
    def dummy() -> None:
        pass

    click_cmd = typer.main.get_command(app)
    cmds = _extract_commands(click_cmd, "demo")
    errors = audit_dry_run_ratchet(cmds, {"demo dummy"})

    assert len(errors) == 1
    assert (
        "Command 'demo missing-option' has class 'request-plan' but does not declare --dry-run."
        in errors[0]
    )


def test_dry_run_class_ratchet_repository_invariant() -> None:
    """Repository invariant: every reachable command conforms to the ratchet and gaps file."""
    assert CONST_GAPS_FILE.is_file(), f"Missing fixture file: {CONST_GAPS_FILE}"
    raw_gaps = json.loads(CONST_GAPS_FILE.read_text(encoding="utf-8"))
    assert isinstance(raw_gaps, list), "Gaps fixture must be a JSON array"
    assert raw_gaps == sorted(raw_gaps), "Gaps fixture must be lexicographically sorted"
    assert len(raw_gaps) == len(set(raw_gaps)), "Gaps fixture must not contain duplicates"

    commands = _collect_reachable_commands()
    gaps_set = set(raw_gaps)

    errors = audit_dry_run_ratchet(commands, gaps_set)
    assert errors == []


def test_mcp_exposure_table_no_external_request_read_only() -> None:
    """Criterion 7: MCP tools wrapping no-external-request commands must have read_only=True."""
    commands = _collect_reachable_commands()

    mismatches: list[str] = []
    for path_tuple, _timeout, read_only, _format_json in CONST_MCP_EXPOSURE_TABLE:
        cmd_path = " ".join(path_tuple)
        cmd = commands.get(cmd_path)
        if cmd is not None and get_dry_run_class(cmd) == "no-external-request":
            if not read_only:
                mismatches.append(
                    f"MCP tool for '{cmd_path}' has read_only=False but command is 'no-external-request'"
                )

    assert mismatches == []


def test_lazy_proxy_dry_run_no_external_request_execution(monkeypatch, capsys) -> None:
    """Criterion 5: devops --dry-run runs a no-external-request command and prints preview for unclassified."""
    from devops_cli.core.cli import _handle_lazy_proxy_dry_run

    delegated_calls: list[tuple[str, str, list[str]]] = []

    def _fake_delegate(module_path: str, command_name: str, args: list[str]) -> None:
        delegated_calls.append((module_path, command_name, args))

    monkeypatch.setattr(main_module, "_delegate", _fake_delegate)
    stub = "tests.support.dry_run_stub:app"

    # 1. Unclassified command prints generic preview and does NOT execute
    _handle_lazy_proxy_dry_run(stub, "stub", ["plain"])
    assert "Would run delegated command: devops stub plain" in capsys.readouterr().out
    assert len(delegated_calls) == 0

    # 2. Command with no-external-request class executes normally without --dry-run
    _handle_lazy_proxy_dry_run(stub, "stub", ["marked"])
    assert "Would run delegated command" not in capsys.readouterr().out
    assert delegated_calls == [("tests.support.dry_run_stub", "stub", ["marked"])]
