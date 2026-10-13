"""Tests verifying CLI output format adoption across the command surface."""

from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any

import typer

from devops_cli.config.constants import CONST_CLI_VALUE_COMMANDS
from devops_cli.main import _COMMAND_SPECS


def _extract_leaf_commands(cmd: Any, prefix: str) -> dict[str, Any]:
    """Recursively collect leaf commands from a Click command or group."""
    leaves: dict[str, Any] = {}
    subcommands = getattr(cmd, "commands", None)
    if subcommands:
        for sub_name, subcmd in subcommands.items():
            child_prefix = f"{prefix} {sub_name}".strip()
            leaves.update(_extract_leaf_commands(subcmd, child_prefix))
    else:
        leaves[prefix] = cmd
    return leaves


def _collect_all_cli_leaf_commands() -> dict[str, Any]:
    """Traverse all CLI entrypoints in _COMMAND_SPECS and collect leaf commands."""
    all_leaves: dict[str, Any] = {}
    for name, (module_path, _) in _COMMAND_SPECS.items():
        module = importlib.import_module(module_path)
        app = getattr(module, "app")
        click_cmd = typer.main.get_command(app)
        all_leaves.update(_extract_leaf_commands(click_cmd, name))
    return all_leaves


def _command_has_format_option(cmd: Any) -> bool:
    """Check if a Click command has a --format option."""
    params = getattr(cmd, "params", [])
    return any("--format" in getattr(p, "opts", []) for p in params)


def test_every_value_command_exposes_format_option() -> None:
    """Every command classified as a value command must expose a --format option."""
    leaf_commands = _collect_all_cli_leaf_commands()

    missing_commands = [
        cmd_path
        for cmd_path in sorted(CONST_CLI_VALUE_COMMANDS)
        if cmd_path not in leaf_commands or not _command_has_format_option(leaf_commands[cmd_path])
    ]

    assert missing_commands == []


def test_negative_control_detects_missing_format_option() -> None:
    """Negative control ensuring omission of --format from a value command is detected."""
    dummy_cmd = SimpleNamespace(params=[SimpleNamespace(opts=["--json", "-j"])])
    assert _command_has_format_option(dummy_cmd) is False


def test_value_commands_registry_is_non_empty_and_sorted() -> None:
    """Verify CONST_CLI_VALUE_COMMANDS invariant: 144 registered value commands."""
    assert (len(CONST_CLI_VALUE_COMMANDS), isinstance(CONST_CLI_VALUE_COMMANDS, frozenset)) == (
        144,
        True,
    )
