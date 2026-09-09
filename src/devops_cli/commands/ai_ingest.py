"""CLI commands to ingest library API contracts, type stubs, and documentation."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from devops_cli.config.defaults import DEFAULT_TABLE_FORMAT
from devops_cli.core.cli import new_typer
from devops_cli.lang import HELP

app = new_typer(
    help=HELP.ai.ingest,
    no_args_is_help=True,
)


@app.command(name="library")
def ingest_library(
    package_name: Annotated[str, typer.Argument(help=HELP.ai.ingest_library)],
    max_depth: Annotated[int, typer.Option("--max-depth", "-d", help=HELP.ai.max_depth)] = 1,
    output_dir: Annotated[
        Path | None, typer.Option("--output-dir", "-o", help=HELP.options.output_dir)
    ] = None,
    output_format: Annotated[
        str, typer.Option("--format", "-f", help=HELP.options.format_type)
    ] = DEFAULT_TABLE_FORMAT,
) -> None:
    """Introspect an installed Python package and extract its public API contract."""
    from devops_cli.ai.library.introspector import PackageIntrospector
    from devops_cli.output import print_error, print_table, write_stdout

    introspector = PackageIntrospector()
    try:
        contract = introspector.introspect_package(package_name, max_depth=max_depth)
        target_dir = output_dir or Path(".data/libraries")
        saved_file = introspector.save_to_dir(contract, target_dir)
    except Exception as exc:
        print_error(f"Failed to ingest library '{package_name}': {exc}")
        raise typer.Exit(code=1) from exc

    if output_format == "json":
        write_stdout(contract.model_dump_json(indent=2) + "\n")
        return

    rows = [
        ["Package Name", contract.package_name],
        ["Version", contract.version],
        ["Timestamp", contract.timestamp],
        ["Total Modules", str(contract.total_modules)],
        ["Total Functions / Methods", str(contract.total_functions)],
        ["Total Classes", str(contract.total_classes)],
        ["Saved File", str(saved_file)],
    ]
    print_table(
        title=f"Library Contract: {contract.package_name}",
        columns=[("Field", "cyan"), ("Value", "bold green")],
        rows=rows,
    )


@app.command(name="docs")
def ingest_docs(
    source: Annotated[str, typer.Argument(help=HELP.ai.ingest_docs)],
    output_dir: Annotated[
        Path | None, typer.Option("--output-dir", "-o", help=HELP.options.output_dir)
    ] = None,
    max_pages: Annotated[int, typer.Option("--max-pages", "-p", help=HELP.options.limit)] = 10,
    output_format: Annotated[
        str, typer.Option("--format", "-f", help=HELP.options.format_type)
    ] = DEFAULT_TABLE_FORMAT,
) -> None:
    """Ingest local or remote documentation into chunked markdown knowledge files."""
    from devops_cli.ai.library.docs_ingester import DocsIngester
    from devops_cli.output import print_error, print_table, write_stdout

    ingester = DocsIngester()
    try:
        if source.startswith(("http://", "https://")):
            result = ingester.ingest_remote_docs(source, output_dir=output_dir, max_pages=max_pages)
        else:
            result = ingester.ingest_local_docs(Path(source), output_dir=output_dir)
    except Exception as exc:
        print_error(f"Failed to ingest documentation from '{source}': {exc}")
        raise typer.Exit(code=1) from exc

    if output_format == "json":
        write_stdout(result.model_dump_json(indent=2) + "\n")
        return

    rows = [
        ["Source", result.source],
        ["Is Remote", str(result.is_remote)],
        ["Total Pages", str(result.total_pages)],
        ["Total Chunks", str(result.total_chunks)],
        ["Output Directory", result.output_dir],
    ]
    print_table(
        title=f"Documentation Ingest: {source}",
        columns=[("Property", "cyan"), ("Value", "bold green")],
        rows=rows,
    )
