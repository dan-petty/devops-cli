"""Typer CLI command module for devops mcp FastMCP integration."""

from __future__ import annotations

from typing import Annotated

import typer

from devops_cli.core.cli import new_typer
from devops_cli.output import (
    print_error,
    print_info,
    print_table,
    render_table,
    write_stderr,
)

app = new_typer(name="mcp", help="FastMCP server and Model Context Protocol integrations.")


@app.command("serve")
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
        print_error(f"Invalid transport '{transport}'. Choose 'stdio' or 'sse'.")
        raise typer.Exit(1)

    if transport == "sse":
        print_info(f"Starting FastMCP server (SSE) on http://{host}:{port}...")
    else:
        # For stdio, stdout must carry ONLY MCP JSON-RPC. Write status to stderr.
        write_stderr("Starting FastMCP server (stdio) — devops-cli\n")

    try:
        from devops_cli.ai.mcp import run_mcp_server

        run_mcp_server(transport=transport, host=host, port=port, allow_remote=allow_remote)
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(1)


@app.command("tools")
def tools_cmd() -> None:
    """List all registered FastMCP tools and descriptions."""
    from devops_cli.ai.mcp import list_mcp_tools

    tools = list_mcp_tools()
    table = render_table(
        title="Registered FastMCP Tools (devops-cli)",
        columns=[("MCP Tool Name", "cyan"), ("Description", "white")],
        rows=[[t["name"], t["description"]] for t in tools],
    )
    print_table(table)
