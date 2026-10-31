"""CLI commands for Tree-Sitter multilingual AST parsing and code graph synthesis."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer

from devops_cli.ai.ast.engine import TreeSitterEngine
from devops_cli.ai.ast.graph import CodeGraphBuilder
from devops_cli.config.constants import (
    CONST_OUTPUT_FORMAT_JSON,
    CONST_OUTPUT_FORMAT_TABLE,
)
from devops_cli.config.defaults import DEFAULT_TABLE_FORMAT
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import dry_run_class
from devops_cli.lang import HELP
from devops_cli.output import print_error, print_info, print_success, write_stdout
from devops_cli.output.serialization import emit_serialized, resolve_format

app = new_typer(
    help=HELP.ai.ast,
    no_args_is_help=True,
)


def _render_symbols_text(file_path: Path, symbols: list[Any]) -> str:
    lines = [f"AST Symbols for {file_path} ({len(symbols)} symbols found):"]
    for s in symbols:
        scope = f" [{s.parent_scope}]" if s.parent_scope else ""
        lines.append(
            f"  - {s.kind.value:<10} {s.name}{scope} (lines {s.span.line_start}-{s.span.line_end})"
        )
    return "\n".join(lines)


def _exit_unparsable(file_path: Path) -> NoReturn:
    print_error(f"Unsupported language or file size exceeded for {file_path}")
    raise typer.Exit(code=1)


def _query_file(
    engine: TreeSitterEngine, file_path: Path, query: str
) -> list[dict[str, Any]] | None:
    """The file's captures of the query; a query tree-sitter cannot compile exits with its error."""
    from tree_sitter import QueryError

    try:
        return engine.query_file(file_path, query)
    except QueryError as exc:
        print_error(f"Invalid tree-sitter query: {str(exc)[:256]}")
        raise typer.Exit(code=1) from exc


@dry_run_class("no-external-request")
@app.command(name="parse")
def ast_parse_cmd(
    file_path: Annotated[Path, typer.Argument(help=HELP.ai.ast_parse)],
    query: Annotated[str, typer.Option("--query", "-q", help=HELP.ai.ast_query)] = "",
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help=HELP.options.format_type),
    ] = DEFAULT_TABLE_FORMAT,
    json_output: Annotated[bool, typer.Option("--json", help=HELP.options.json_output)] = False,
) -> None:
    """Parse source file concrete syntax tree and extract structural symbols."""
    if not file_path.is_file():
        print_error(f"Target source file not found: {file_path}")
        raise typer.Exit(code=1)

    engine = TreeSitterEngine()
    if query:
        matches = _query_file(engine, file_path, query)
        if matches is None:
            _exit_unparsable(file_path)
        resolved = resolve_format(
            output_format,
            json_output=json_output,
            default_format=CONST_OUTPUT_FORMAT_JSON,
        )
        emit_serialized(matches, resolved)
        return

    file_map = engine.parse_file(file_path)
    if not file_map:
        _exit_unparsable(file_path)

    resolved = resolve_format(output_format, json_output=json_output)
    if resolved != CONST_OUTPUT_FORMAT_TABLE:
        emit_serialized(file_map.to_dict(), resolved)
        return

    write_stdout(_render_symbols_text(file_path, file_map.symbols) + "\n")


@dry_run_class("no-external-request")
@app.command(name="graph")
def ast_graph_cmd(
    target_dir: Annotated[Path | None, typer.Option("--dir", "-d", help=HELP.ai.target_dir)] = None,
    max_files: Annotated[int, typer.Option("--max-files", "-n", help=HELP.ai.max_files)] = 100,
    output_path: Annotated[
        Path | None, typer.Option("--output", "-o", help=HELP.options.output_path)
    ] = None,
    fmt: Annotated[str, typer.Option("--format", "-f", help=HELP.ai.graph_format)] = "json",
) -> None:
    """Synthesize whole-repository symbol dependency and reference graph."""
    builder = CodeGraphBuilder(root_dir=target_dir, max_files=max_files)
    graph = builder.build()

    content = graph.to_dot() if fmt.lower() == "dot" else graph.to_json(indent=2)
    if output_path:
        output_path.write_text(content + "\n", encoding="utf-8")
        print_success(f"Synthesized code graph saved to {output_path}")
    else:
        print_info(
            f"[bold]Synthesized Code Graph[/bold] ({len(graph.files)} files, {len(graph.nodes)} symbols, {len(graph.edges)} edges):\n",
            prefix=False,
        )
        write_stdout(content + "\n")
