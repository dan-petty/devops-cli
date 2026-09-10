"""CLI commands for Tree-Sitter multilingual AST parsing and code graph synthesis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from devops_cli.ai.ast.engine import TreeSitterEngine
from devops_cli.ai.ast.graph import CodeGraphBuilder
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run, render_dry_run_result
from devops_cli.lang import HELP
from devops_cli.output import print_error, print_info, print_success, write_stdout

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


@app.command(name="parse")
def ast_parse_cmd(
    file_path: Annotated[Path, typer.Argument(help=HELP.ai.ast_parse)],
    query: Annotated[str, typer.Option("--query", "-q", help=HELP.ai.ast_query)] = "",
    json_output: Annotated[bool, typer.Option("--json", help=HELP.options.json_output)] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Parse source file concrete syntax tree and extract structural symbols."""
    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops ai ast parse",
            action="parse_syntax_tree",
            details={"file": str(file_path), "query": query, "status": "DRY_RUN_PARSED"},
        )
        return

    if not file_path.is_file():
        print_error(f"Target source file not found: {file_path}")
        raise typer.Exit(code=1)

    engine = TreeSitterEngine()
    if query:
        code = file_path.read_text(encoding="utf-8", errors="replace")
        matches = engine.query_code(code, file_path.suffix, query)
        write_stdout(json.dumps(matches, indent=2) + "\n")
        return

    file_map = engine.parse_file(file_path)
    if not file_map:
        print_error(f"Unsupported language or file size exceeded for {file_path}")
        raise typer.Exit(code=1)

    if json_output:
        write_stdout(json.dumps(file_map.to_dict(), indent=2) + "\n")
        return

    write_stdout(_render_symbols_text(file_path, file_map.symbols) + "\n")


@app.command(name="graph")
def ast_graph_cmd(
    target_dir: Annotated[Path | None, typer.Option("--dir", "-d", help=HELP.ai.target_dir)] = None,
    max_files: Annotated[int, typer.Option("--max-files", "-n", help=HELP.ai.max_files)] = 100,
    output_path: Annotated[
        Path | None, typer.Option("--output", "-o", help=HELP.options.output_path)
    ] = None,
    fmt: Annotated[str, typer.Option("--format", "-f", help=HELP.ai.graph_format)] = "json",
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
) -> None:
    """Synthesize whole-repository symbol dependency and reference graph."""
    if dry_run or is_dry_run():
        render_dry_run_result(
            command="devops ai ast graph",
            action="build_code_graph",
            details={
                "target_dir": str(target_dir) if target_dir else ".",
                "max_files": max_files,
                "format": fmt,
                "status": "DRY_RUN_GRAPHED",
            },
        )
        return

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
