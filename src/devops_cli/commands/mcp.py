"""Typer CLI command module for devops mcp FastMCP integration."""

from __future__ import annotations

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
from devops_cli.dry_run import is_dry_run
from devops_cli.dry_run.decorator import dry_run_class
from devops_cli.dry_run.requests import PlannedRequest, render_request_plan
from devops_cli.lang import ERRORS, HELP, MESSAGES
from devops_cli.output import print_error, print_info, print_table, render_table, write_stderr

app = new_typer(name="mcp", help=HELP.mcp.app)


def server_args(transport: str, host: str, port: int, allow_remote: bool) -> dict[str, Any]:
    """The arguments of `run_mcp_server`, as the start and its dry run use them."""
    return {"transport": transport, "host": host, "port": port, "allow_remote": allow_remote}


def plan_serve(args: dict[str, Any]) -> list[PlannedRequest]:
    """The bind (`sse` only) and the start of the MCP server. A start makes no outbound
    request: the tools make requests only when a client calls them."""
    requests: list[PlannedRequest] = []
    if args["transport"] == "sse":
        requests.append(PlannedRequest(method="BIND", target=f"tcp {args['host']}:{args['port']}"))
    requests.append(PlannedRequest(method="START", target=f"mcp server ({args['transport']})"))
    return requests


@app.command("serve", help=HELP.mcp.serve)
@dry_run_class("request-plan")
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
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Launch FastMCP server to expose devops-cli tools to MCP clients."""
    if transport not in {"stdio", "sse"}:
        print_error(ERRORS.mcp.invalid_transport.format(transport=transport))
        raise typer.Exit(1)

    args = server_args(transport, host, port, allow_remote)
    if dry_run or is_dry_run():
        from devops_cli.ai.mcp.server import check_sse_bind

        try:
            check_sse_bind(transport, host, allow_remote=allow_remote)
        except ValueError as exc:
            print_error(str(exc))
            raise typer.Exit(1) from exc
        render_request_plan(
            MESSAGES.mcp.serve_dry_run_heading, plan_serve(args), [MESSAGES.mcp.serve_dry_run_note]
        )
        return

    if transport == "sse":
        print_info(MESSAGES.mcp.starting_sse.format(host=host, port=port))
    else:
        # For stdio, stdout must carry ONLY MCP JSON-RPC. Write status to stderr.
        write_stderr(MESSAGES.mcp.starting_stdio)

    try:
        runner_fn = getattr(sys.modules[__name__], "run_mcp_server")
        runner_fn(**args)
    except ValueError as exc:
        print_error(str(exc))
        raise typer.Exit(1) from exc


@app.command("tools", help=HELP.mcp.tools)
@dry_run_class("no-external-request")
def tools_cmd() -> None:
    """List all registered FastMCP tools and descriptions."""
    lister_fn = getattr(sys.modules[__name__], "list_mcp_tools")
    tools = lister_fn()
    table = render_table(
        title=MESSAGES.mcp.table_title_tools,
        columns=[(MESSAGES.mcp.col_tool_name, "cyan"), (MESSAGES.mcp.col_description, "white")],
        rows=[[t["name"], t["description"]] for t in tools],
    )
    print_table(table)


@app.command("export-schemas", help=HELP.mcp.export_schemas)
@dry_run_class("no-external-request")
def export_schemas_cmd(
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir",
            "-o",
            show_default="~/.gemini/antigravity-ide/mcp/devops-cli",
            help=HELP.mcp.output_dir,
        ),
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Export tool JSON schemas and instructions for MCP clients and Antigravity IDE."""
    import asyncio
    import json

    from devops_cli.ai.mcp.server import mcp

    out_dir = output_dir or (Path.home() / ".gemini" / "antigravity-ide" / "mcp" / "devops-cli")
    # The registry, not the client-facing listing: exported schemas document the whole
    # catalogue, and `mcp.list_tools()` runs the domain gate, which would cut the export
    # to the eager domains alone.
    tools = asyncio.run(mcp._list_tools())
    if dry_run or is_dry_run():
        print_info(
            MESSAGES.mcp.export_dry_run.format(count=len(tools), directory=out_dir), prefix=False
        )
        return
    out_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for t in tools:
        annotations = (
            t.annotations.model_dump(by_alias=True, exclude_none=True)
            if t.annotations is not None
            else {}
        )
        schema = {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
            "annotations": annotations,
        }
        dest = out_dir / f"{t.name}.json"
        dest.write_text(json.dumps(schema, separators=(",", ":")), encoding="utf-8")
        count += 1

    instructions_file = out_dir / "instructions.md"
    instructions_text = getattr(mcp, "instructions", "") or ""
    instructions_file.write_text(instructions_text, encoding="utf-8")

    if instructions_text:
        print_info(f"✓ Exported {count} tool schema(s) and instructions to {out_dir}")
    else:
        print_info(f"✓ Exported {count} tool schema(s) to {out_dir}")


def __getattr__(name: str) -> Any:
    if name == "run_mcp_server":
        from devops_cli.ai.mcp.server import run_mcp_server

        return run_mcp_server
    if name == "list_mcp_tools":
        from devops_cli.ai.mcp.server import list_mcp_tools

        return list_mcp_tools
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
