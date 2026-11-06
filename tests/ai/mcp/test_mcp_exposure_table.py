"""The exposure table names every CLI command that a tool exposes, and each tool matches its command."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from devops_cli.ai.mcp.server import (
    mcp,
)
from devops_cli.config.constants import CONST_MCP_EXPOSURE_TABLE


@pytest.mark.parametrize(
    ("path", "timeout", "read_only", "format_json"),
    CONST_MCP_EXPOSURE_TABLE,
)
def test_mcp_tool_schema_and_argv_parsing(
    path: tuple[str, ...],
    timeout: float,
    read_only: bool,
    format_json: bool,
) -> None:
    """Walk exposure table, assert schema properties match Click parameters and argv parses."""
    from devops_cli.ai.mcp.generator import (
        _IGNORED_PARAM_NAMES,
        _JSON_PARAM_NAMES,
        _PATH_PARAM_RESTRICTIONS,
        _build_command_argv,
        _introspect_command_parameters,
        resolve_click_command,
    )

    tool_name = "_".join(path).replace("-", "_")
    tool = asyncio.run(mcp.get_tool(tool_name))
    assert tool is not None, f"Tool '{tool_name}' not found on server"

    click_cmd = resolve_click_command(path)
    restrictions = _PATH_PARAM_RESTRICTIONS.get(path)
    expected_params = [
        p.name
        for p in click_cmd.params
        if p.name not in _IGNORED_PARAM_NAMES
        and not (format_json and p.name in _JSON_PARAM_NAMES)
        and (not restrictions or p.name in restrictions["allowed"])
    ]
    schema_props = list(tool.parameters.get("properties", {}).keys())
    assert schema_props == expected_params

    parameters, _ = _introspect_command_parameters(click_cmd, format_json, path)
    sample_kwargs: dict[str, Any] = {}
    for p in parameters:
        sample_kwargs[p.name] = p.default if p.default is not p.empty else "sample"

    argv = _build_command_argv(path, click_cmd, format_json, sample_kwargs)
    args = argv[len(path) :]
    ctx = click_cmd.make_context(path[-1], list(args), resilient_parsing=True)
    assert ctx is not None


def test_every_exposed_mcp_command_is_a_command_of_the_tree() -> None:
    """A command of the tree that `CONST_MCP_EXPOSURE_TABLE` does not name is excluded, so a new
    command needs no entry (#3204); an exposure entry that names no command of the tree fails."""
    from devops_cli.config.constants import (
        CONST_MCP_EXPOSURE_TABLE,
    )
    from devops_cli.core.command_resolver import module_click_command
    from devops_cli.main import _COMMAND_SPECS

    exposed_paths = {entry[0] for entry in CONST_MCP_EXPOSURE_TABLE}

    all_cli_commands: set[tuple[str, ...]] = set()
    for top_name, spec in _COMMAND_SPECS.items():
        if top_name in ("format", "lint"):
            all_cli_commands.add((top_name,))
            continue
        top_cmd = module_click_command(spec[0])
        if top_cmd is None:
            continue

        def walk(cmd: Any, path: tuple[str, ...]) -> None:
            if getattr(cmd, "hidden", False):
                return
            if hasattr(cmd, "commands") and cmd.commands:
                if path == ("ci",):
                    all_cli_commands.add(path)
                for sub_name, sub_cmd in cmd.commands.items():
                    walk(sub_cmd, path + (sub_name,))
            else:
                all_cli_commands.add(path)

        walk(top_cmd, (top_name,))

    assert exposed_paths - all_cli_commands == set()
