"""Typer CLI command module for devops mcp FastMCP integration."""

from __future__ import annotations

import sys
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from devops_cli.core.cli import new_typer
from devops_cli.mcp import list_mcp_tools, run_mcp_server

app = new_typer(name="mcp", help="FastMCP server and Model Context Protocol integrations.")
_console = Console()


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
        rprint(f"[red]Error: Invalid transport '{transport}'. Choose 'stdio' or 'sse'.[/red]")
        raise typer.Exit(1)

    if transport == "sse":
        rprint(
            f"[bold green]Starting FastMCP server (SSE)[/bold green] on [cyan]http://{host}:{port}[/cyan]..."
        )
    else:
        # For stdio, stdout must carry ONLY MCP JSON-RPC. Write status to stderr.
        print(
            "Starting FastMCP server (stdio) — devops-cli",
            file=sys.stderr,
        )

    try:
        run_mcp_server(transport=transport, host=host, port=port, allow_remote=allow_remote)
    except ValueError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1)


@app.command("tools")
def tools_cmd() -> None:
    """List all registered FastMCP tools and descriptions."""
    tools = list_mcp_tools()
    table = Table(title="Registered FastMCP Tools (devops-cli)", title_style="bold blue")
    table.add_column("MCP Tool Name", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")

    for t in tools:
        table.add_row(t["name"], t["description"])

    _console.print(table)
