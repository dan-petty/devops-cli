"""Typer CLI command module for devops mcp FastMCP integration."""

from __future__ import annotations

from typing import Annotated

import typer

from devops_cli.ai.mcp import list_mcp_tools, run_mcp_server
from devops_cli.core.cli import new_typer
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.output import (
    print_error,
    print_info,
    print_table,
    render_table,
    write_stderr,
)

app = new_typer(name="mcp", help=HELP.mcp.app)


@app.command("serve", help=HELP.mcp.serve)
def serve_cmd(
    transport: Annotated[
        str,
        typer.Option(
            "--transport",
            "-t",
            help="Transport protocol for FastMCP server (stdio | sse).",
        ),
    ] = "stdio",
    host: Annotated[
        str,
        typer.Option(
            "--host",
            "-h",
            help="Host interface for SSE transport.",
        ),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option(
            "--port",
            "-p",
            help="Port number for SSE transport.",
        ),
    ] = 8000,
    allow_remote: Annotated[
        bool,
        typer.Option(
            "--allow-remote",
            help="Permit binding SSE transport to non-loopback network interfaces.",
        ),
    ] = False,
) -> None:
    """Launch FastMCP server to expose devops-cli tools to MCP clients."""
    if transport not in {"stdio", "sse"}:
        print_error(ERRORS.mcp.invalid_transport.format(transport=transport))
        raise typer.Exit(1)

    if transport == "sse":
        print_info(MESSAGES.mcp.starting_sse.format(host=host, port=port))
    else:
        # For stdio, stdout must carry ONLY MCP JSON-RPC. Write status to stderr.
        write_stderr(MESSAGES.mcp.starting_stdio)

    try:
        run_mcp_server(transport=transport, host=host, port=port, allow_remote=allow_remote)
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(1)


@app.command("tools", help=HELP.mcp.tools)
def tools_cmd() -> None:
    """List all registered FastMCP tools and descriptions."""
    tools = list_mcp_tools()
    table = render_table(
        title=MESSAGES.mcp.table_title_tools,
        columns=[(MESSAGES.mcp.col_tool_name, "cyan"), (MESSAGES.mcp.col_description, "white")],
        rows=[[t["name"], t["description"]] for t in tools],
    )
    print_table(table)
