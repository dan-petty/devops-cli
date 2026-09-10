"""CLI commands to ingest library API contracts, type stubs, and documentation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import typer

from devops_cli.config.defaults import DEFAULT_TABLE_FORMAT
from devops_cli.core.cli import new_typer
from devops_cli.lang import HELP

if TYPE_CHECKING:
    from devops_cli.ai.rag.library_store import LibraryVectorStore
    from devops_cli.models.library import LibraryContract

logger = logging.getLogger(__name__)

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


def _load_local_contracts(contracts_dir: Path) -> list[LibraryContract]:
    """Load all valid LibraryContract instances from a local directory."""
    from devops_cli.models.library import LibraryContract

    contracts: list[LibraryContract] = []
    if not contracts_dir.exists():
        return contracts

    for filepath in sorted(contracts_dir.glob("*.json")):
        try:
            contract = LibraryContract.model_validate_json(filepath.read_text(encoding="utf-8"))
            contracts.append(contract)
        except Exception as exc:
            logger.debug("Skipping invalid contract file %s: %s", filepath.name, exc)
            continue
    return contracts


def _render_index_libraries_table(contracts: list[Any], dry_run: bool) -> None:
    """Render summary table for indexed library contracts."""
    from devops_cli.output import print_table

    mode_tag = " [dry-run]" if dry_run else ""
    rows = [
        [
            c.package_name,
            c.version,
            str(c.total_modules),
            str(c.total_functions),
            str(c.total_classes),
            "Simulated" if dry_run else "Indexed",
        ]
        for c in contracts
    ]
    print_table(
        title=f"Library Contracts Indexing{mode_tag}",
        columns=[
            ("Package", "cyan"),
            ("Version", "green"),
            ("Modules", "yellow"),
            ("Functions", "magenta"),
            ("Classes", "blue"),
            ("Status", "bold white"),
        ],
        rows=rows,
    )


def _render_query_exact_table(sig: Any) -> None:
    """Render table display for an exact symbol signature lookup."""
    from devops_cli.models.library import ClassSignature, FunctionSignature
    from devops_cli.output import print_table

    if isinstance(sig, FunctionSignature):
        rows = [
            ["Name", sig.name],
            ["Qualname", sig.qualname],
            ["Parameters", ", ".join(p.name for p in sig.parameters) or "(none)"],
            ["Return Type", sig.return_annotation],
            ["Docstring", (sig.docstring or "(none)").strip().split("\n")[0]],
        ]
    elif isinstance(sig, ClassSignature):
        rows = [
            ["Name", sig.name],
            ["Qualname", sig.qualname],
            ["Bases", ", ".join(sig.bases) or "(none)"],
            ["Methods", ", ".join(sig.methods.keys()) or "(none)"],
            ["Docstring", (sig.docstring or "(none)").strip().split("\n")[0]],
        ]
    else:
        rows = [["Symbol", getattr(sig, "name", str(sig))]]

    print_table(
        title=f"Symbol Signature: {getattr(sig, 'name', 'Result')}",
        columns=[("Property", "cyan"), ("Value", "bold green")],
        rows=rows,
    )


def _render_search_results_table(results: list[Any]) -> None:
    """Render table display for semantic library search results."""
    from devops_cli.output import print_table

    rows = [
        [
            f"{r.score:.3f}",
            r.symbol_name,
            r.package_name,
            r.kind,
            r.signature_text or (r.docstring or "")[:60],
        ]
        for r in results
    ]
    print_table(
        title="Library Search Results",
        columns=[
            ("Score", "cyan"),
            ("Symbol / Title", "bold green"),
            ("Package", "yellow"),
            ("Kind", "magenta"),
            ("Signature / Summary", "white"),
        ],
        rows=rows,
    )


def _resolve_runtime_valkey_client() -> Any:
    """Attempt to resolve and connect to a live Valkey client."""
    try:
        from devops_cli.commands.valkey import _resolve_client

        client = _resolve_client()
        return client if client.ping() else None
    except Exception as exc:
        logger.debug("Valkey client unavailable for library vector tier: %s", exc)
        return None


def _resolve_runtime_qdrant_and_embedder() -> tuple[Any, Any]:
    """Attempt to resolve and connect to a live Qdrant client and EmbeddingsEngine."""
    try:
        from devops_cli.ai.rag.embeddings import EmbeddingsEngine
        from devops_cli.ai.rag.indexer import resolve_qdrant_client
        from devops_cli.config.settings import get_ai_api_key, load_settings

        settings = load_settings()
        client = resolve_qdrant_client()
        if not client.is_alive():
            return None, None
        embedder = EmbeddingsEngine(
            ai_config=settings.ai,
            api_key=get_ai_api_key(settings),
        )
        return client, embedder
    except Exception as exc:
        logger.debug("Qdrant or embedder unavailable for library vector tier: %s", exc)
        return None, None


def _build_runtime_vector_store(
    contracts_dir: Path,
    *,
    semantic_needed: bool = True,
    dry_run: bool = False,
) -> LibraryVectorStore:
    """Construct LibraryVectorStore wired with Qdrant, embedder, and Valkey clients if available."""
    from devops_cli.ai.rag.library_store import LibraryVectorStore

    if dry_run:
        return LibraryVectorStore(local_contracts_dir=contracts_dir)

    valkey_client = _resolve_runtime_valkey_client()
    qdrant_client, embedder = (
        _resolve_runtime_qdrant_and_embedder() if semantic_needed else (None, None)
    )

    return LibraryVectorStore(
        qdrant_client=qdrant_client,
        valkey_client=valkey_client,
        embedder=embedder,
        local_contracts_dir=contracts_dir,
    )


@app.command(name="index-libraries")
def index_libraries(
    contracts_dir: Annotated[Path, typer.Option("--dir", "-d", help=HELP.ai.contracts_dir)] = Path(
        ".data/libraries"
    ),
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.options.dry_run)] = False,
    output_format: Annotated[
        str, typer.Option("--format", "-f", help=HELP.options.format_type)
    ] = DEFAULT_TABLE_FORMAT,
) -> None:
    """Index exported library API contracts into Qdrant vector collection and Valkey cache."""
    import json

    from devops_cli.output import print_warning, write_stdout

    contracts = _load_local_contracts(contracts_dir)
    if not contracts:
        print_warning(f"No library contract JSON files found in {contracts_dir}.")
        return

    if not dry_run:
        store = _build_runtime_vector_store(contracts_dir, semantic_needed=True, dry_run=False)
        for contract in contracts:
            store.index_contract(contract)

    if output_format == "json":
        payload = [
            {"package": c.package_name, "version": c.version, "dry_run": dry_run} for c in contracts
        ]
        write_stdout(json.dumps(payload, indent=2) + "\n")
        return

    _render_index_libraries_table(contracts, dry_run=dry_run)


@app.command(name="query-library")
def query_library(
    query: Annotated[str, typer.Argument(help=HELP.ai.query_library)],
    package: Annotated[
        str | None, typer.Option("--package", "-p", help=HELP.ai.package_name)
    ] = None,
    exact: Annotated[bool, typer.Option("--exact", "-e", help=HELP.ai.exact_lookup)] = False,
    top_k: Annotated[int, typer.Option("--top-k", "-k", help=HELP.options.limit)] = 5,
    contracts_dir: Annotated[
        Path, typer.Option("--contracts-dir", help=HELP.ai.contracts_dir)
    ] = Path(".data/libraries"),
    output_format: Annotated[
        str, typer.Option("--format", "-f", help=HELP.options.format_type)
    ] = DEFAULT_TABLE_FORMAT,
) -> None:
    """Search library contracts and documentation via semantic search or exact symbol lookup."""
    import json

    from devops_cli.output import print_error, write_stdout

    store = _build_runtime_vector_store(
        contracts_dir,
        semantic_needed=not exact,
        dry_run=False,
    )

    if exact:
        sig = store.lookup_symbol(query, package=package)
        if sig is None:
            print_error(f"Symbol '{query}' not found in library contracts or cache.")
            raise typer.Exit(code=1)
        if output_format == "json":
            write_stdout(sig.model_dump_json(indent=2) + "\n")
            return
        _render_query_exact_table(sig)
        return

    results = store.search(query, package=package, top_k=top_k)
    if output_format == "json":
        write_stdout(json.dumps([r.model_dump() for r in results], indent=2) + "\n")
        return

    _render_search_results_table(results)
