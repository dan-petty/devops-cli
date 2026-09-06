"""Typer CLI command module for devops mcp FastMCP integration."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.config.defaults import (
    DEFAULT_MCP_HOST,
    DEFAULT_MCP_PORT,
    DEFAULT_MCP_TRANSPORT,
)
from devops_cli.core.cli import new_typer
from devops_cli.lang import ERRORS, HELP, MESSAGES

_LAZY_OBJECT_MAPPING: dict[str, tuple[str, str]] = {
    "run_mcp_server": ("devops_cli.ai.mcp", "run_mcp_server"),
    "list_mcp_tools": ("devops_cli.ai.mcp", "list_mcp_tools"),
    "print_error": ("devops_cli.output", "print_error"),
    "print_info": ("devops_cli.output", "print_info"),
    "print_table": ("devops_cli.output", "print_table"),
    "render_table": ("devops_cli.output", "render_table"),
    "write_stderr": ("devops_cli.output", "write_stderr"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_OBJECT_MAPPING:
        mod_path, obj_name = _LAZY_OBJECT_MAPPING[name]
        module = importlib.import_module(mod_path)
        return getattr(module, obj_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _get(name: str) -> Any:
    mod_dict = sys.modules[__name__].__dict__
    if name in mod_dict:
        return mod_dict[name]
    if name in _LAZY_OBJECT_MAPPING:
        mod_path, obj_name = _LAZY_OBJECT_MAPPING[name]
        module = importlib.import_module(mod_path)
        return getattr(module, obj_name)
    return getattr(sys.modules[__name__], name)


app = new_typer(name="mcp", help=HELP.mcp.app)


@app.command("serve", help=HELP.mcp.serve)
def serve_cmd(
    transport: Annotated[
        str,
        typer.Option(
            "--transport",
            "-t",
            help=HELP.mcp.transport,
        ),
    ] = DEFAULT_MCP_TRANSPORT,
    host: Annotated[
        str,
        typer.Option(
            "--host",
            "-h",
            help=HELP.mcp.host,
        ),
    ] = DEFAULT_MCP_HOST,
    port: Annotated[
        int,
        typer.Option(
            "--port",
            "-p",
            help=HELP.mcp.port,
        ),
    ] = DEFAULT_MCP_PORT,
    allow_remote: Annotated[
        bool,
        typer.Option(
            "--allow-remote",
            help=HELP.mcp.allow_remote,
        ),
    ] = False,
) -> None:
    """Launch FastMCP server to expose devops-cli tools to MCP clients."""
    if transport not in {"stdio", "sse"}:
        _get("print_error")(ERRORS.mcp.invalid_transport.format(transport=transport))
        raise typer.Exit(1)

    if transport == "sse":
        _get("print_info")(MESSAGES.mcp.starting_sse.format(host=host, port=port))
    else:
        # For stdio, stdout must carry ONLY MCP JSON-RPC. Write status to stderr.
        _get("write_stderr")(MESSAGES.mcp.starting_stdio)

    try:
        _get("run_mcp_server")(transport=transport, host=host, port=port, allow_remote=allow_remote)
    except ValueError as exc:
        _get("print_error")(str(exc))
        raise typer.Exit(1)


@app.command("tools", help=HELP.mcp.tools)
def tools_cmd() -> None:
    """List all registered FastMCP tools and descriptions."""
    tools = _get("list_mcp_tools")()
    table = _get("render_table")(
        title=MESSAGES.mcp.table_title_tools,
        columns=[(MESSAGES.mcp.col_tool_name, "cyan"), (MESSAGES.mcp.col_description, "white")],
        rows=[[t["name"], t["description"]] for t in tools],
    )
    _get("print_table")(table)


@app.command("export-schemas", help=HELP.mcp.export_schemas)
def export_schemas_cmd(
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            "-o",
            help=HELP.mcp.output_dir,
        ),
    ] = Path.home() / ".gemini" / "antigravity-ide" / "mcp" / "devops-cli",
) -> None:
    """Export tool JSON schemas and instructions for MCP clients and Antigravity IDE."""
    import asyncio
    import json

    from devops_cli.ai.mcp.server import mcp

    output_dir.mkdir(parents=True, exist_ok=True)
    tools = asyncio.run(mcp.list_tools())

    count = 0
    for t in tools:
        schema = {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
        }
        dest = output_dir / f"{t.name}.json"
        dest.write_text(json.dumps(schema, separators=(",", ":")), encoding="utf-8")
        count += 1

    instructions_file = output_dir / "instructions.md"
    if hasattr(mcp, "instructions") and mcp.instructions:
        instructions_file.write_text(mcp.instructions, encoding="utf-8")

    _get("print_info")(f"✓ Exported {count} tool schema(s) and instructions to {output_dir}")
