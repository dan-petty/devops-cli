"""RAG (Retrieval-Augmented Generation) management commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import typer
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table

from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.ai.rag.indexer import WorkspaceIndexer
from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.ai.rag.retriever import SemanticRetriever
from devops_cli.config.defaults import (
    DEFAULT_RAG_COLLECTION,
    DEFAULT_RAG_DOCS_COLLECTION,
    DEFAULT_RAG_SCORE_THRESHOLD,
    DEFAULT_RAG_TOP_K,
)
from devops_cli.config.settings import get_ai_api_key, load_settings
from devops_cli.core.cli import new_typer
from devops_cli.dry_run import is_dry_run
from devops_cli.lang import MESSAGES
from devops_cli.output import (
    get_console,
    print_error,
    print_info,
    print_panel,
    print_success,
    print_table,
    print_warning,
    render_dry_run_result,
)

app = new_typer(
    help="Manage RAG vector embeddings, indexing, and semantic code search (Qdrant).",
    no_args_is_help=True,
)


@app.callback(invoke_without_command=True)
def rag_main(
    ctx: typer.Context,
    explain: Annotated[
        bool,
        typer.Option(
            "--explain",
            "-e",
            help="Explain RAG vector embeddings, Qdrant indexing, and terminology",
        ),
    ] = False,
) -> None:
    """Manage RAG vector embeddings, indexing, and semantic code search (Qdrant)."""
    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("rag")
        raise typer.Exit(0)


# =============================================================================
# RAG Vector Components Resolution Helper
# =============================================================================


def _get_rag_components() -> tuple[QdrantClient, EmbeddingsEngine, str, str]:
    """Resolve configured Qdrant client, Embeddings engine, and collection names."""
    settings = load_settings()
    qdrant_url = settings.qdrant.url or "http://localhost:6333"
    prefix = settings.qdrant.collection_prefix or "devops"
    code_coll = f"{prefix}_code" if prefix else DEFAULT_RAG_COLLECTION
    docs_coll = f"{prefix}_docs" if prefix else DEFAULT_RAG_DOCS_COLLECTION

    qdrant = QdrantClient(
        base_url=qdrant_url,
        allow_private_network=settings.ai.allow_private_network,
    )
    embedder = EmbeddingsEngine(
        ai_config=settings.ai,
        api_key=get_ai_api_key(settings),
    )
    return qdrant, embedder, code_coll, docs_coll


# =============================================================================
# Command: devops rag index
# =============================================================================


@app.command("index")
def index_cmd(
    path: Annotated[
        Path,
        typer.Argument(
            help="Directory or file to index into vector store",
        ),
    ] = Path("."),
    project: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Project / repository name override"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Re-index all files ignoring content hash cache"),
    ] = False,
    include_kb: Annotated[
        bool,
        typer.Option(
            "--include-kb/--no-include-kb",
            help="Include bundled DevOps CLI Knowledge Base in docs collection",
        ),
    ] = True,
    collection: Annotated[
        str | None,
        typer.Option("--collection", "-c", help="Target collection override"),
    ] = None,
    explain: Annotated[
        bool,
        typer.Option(
            "--explain",
            "-e",
            help="Explain RAG vector embeddings, Qdrant indexing, and terminology",
        ),
    ] = False,
) -> None:
    """Scan and index workspace code and documentation into Qdrant vector database."""
    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("rag")
        return
    target_path = path.resolve()
    if not target_path.exists():
        print_error(f"Path not found: {target_path}", prefix=False)
        raise typer.Exit(1)

    if is_dry_run():
        render_dry_run_result(
            command="devops ai rag index",
            target=str(target_path),
            action="vector_indexing",
            details={
                "path": str(target_path),
                "project": project,
                "force": force,
                "include_kb": include_kb,
                "collection": collection,
            },
        )
        return

    qdrant, embedder, code_coll, docs_coll = _get_rag_components()
    if collection:
        code_coll = collection
        docs_coll = collection

    if not qdrant.is_alive():
        print_error(
            f"Cannot connect to Qdrant at [bold]{qdrant.base_url}[/bold]\n"
            "Tip: Deploy or start Qdrant via 'devops k8s deploy-stack llm'",
            prefix=False,
        )
        raise typer.Exit(1)

    indexer = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        code_collection=code_coll,
        docs_collection=docs_coll,
    )

    get_console().print(
        Rule(
            f" [cyan]RAG Workspace Indexer[/cyan]  "
            f"[dim]Qdrant: {qdrant.base_url} | Model: {embedder.model}[/dim] ",
            style="cyan",
        )
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=get_console(),
    ) as progress:
        task_id = progress.add_task("Indexing files...", total=100)

        def _on_progress(desc: str, current: int, total: int) -> None:
            pct = (current / max(1, total)) * 100
            progress.update(task_id, description=f"{desc} ({current}/{total})", completed=pct)

        results = indexer.index_workspace(
            target_path,
            project=project,
            force=force,
            include_kb=include_kb,
            progress_callback=_on_progress,
        )

    removed_msg = (
        f", removed [yellow]{results['removed_files']}[/yellow] outdated file(s)"
        if results.get("removed_files")
        else ""
    )
    print_success(
        f"Indexing complete! Indexed [cyan]{results['indexed_files']}[/cyan] file(s), "
        f"upserted [cyan]{results['total_chunks']}[/cyan] chunk(s)"
        f"{removed_msg} (skipped {results['skipped_files']} unchanged files)."
    )


# =============================================================================
# Command: devops rag index-kb
# =============================================================================


@app.command("index-kb")
def index_kb_cmd(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Re-index all KB files ignoring cache"),
    ] = False,
    collection: Annotated[
        str | None,
        typer.Option("--collection", "-c", help="Target collection override"),
    ] = None,
    explain: Annotated[
        bool,
        typer.Option(
            "--explain",
            "-e",
            help="Explain RAG vector embeddings, Qdrant indexing, and terminology",
        ),
    ] = False,
) -> None:
    """Index the bundled DevOps CLI Knowledge Base into Qdrant for RAG agent retrieval."""
    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("rag")
        return

    if is_dry_run():
        render_dry_run_result(
            command="devops ai rag index-kb",
            target="src/devops_cli/ai/knowledge_base",
            action="vector_indexing_kb",
            details={
                "force": force,
                "collection": collection,
            },
        )
        return

    qdrant, embedder, code_coll, docs_coll = _get_rag_components()
    if collection:
        docs_coll = collection

    if not qdrant.is_alive():
        print_error(
            f"Cannot connect to Qdrant at [bold]{qdrant.base_url}[/bold]\n"
            "Tip: Deploy or start Qdrant via 'devops k8s deploy-stack llm'",
            prefix=False,
        )
        raise typer.Exit(1)

    indexer = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        code_collection=code_coll,
        docs_collection=docs_coll,
    )

    get_console().print(
        Rule(
            f" [cyan]RAG Knowledge Base Indexer[/cyan]  "
            f"[dim]Qdrant: {qdrant.base_url} | Model: {embedder.model}[/dim] ",
            style="cyan",
        )
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=get_console(),
    ) as progress:
        task_id = progress.add_task("Indexing knowledge base...", total=100)

        def _on_progress(desc: str, current: int, total: int) -> None:
            pct = (current / max(1, total)) * 100
            progress.update(task_id, description=f"{desc} ({current}/{total})", completed=pct)

        results = indexer.index_knowledge_base(
            force=force,
            progress_callback=_on_progress,
        )

    print_success(
        f"Knowledge Base indexing complete! "
        f"Indexed [cyan]{results['indexed_files']}[/cyan] KB file(s), "
        f"upserted [cyan]{results['total_chunks']}[/cyan] chunk(s) "
        f"into [magenta]{docs_coll}[/magenta]."
    )


# =============================================================================
# Command: devops ai rag query / search
# =============================================================================


@app.command("query")
@app.command("search")
def search(
    query: Annotated[str, typer.Argument(help="Natural language query or code search term")],
    project: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Filter results by project name"),
    ] = None,
    language: Annotated[
        str | None,
        typer.Option("--language", "-l", help="Filter results by programming language"),
    ] = None,
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Filter by category (code, docs, topics, tasks)"),
    ] = None,
    top_k: Annotated[
        int,
        typer.Option("--top-k", "-k", help="Number of results to return"),
    ] = DEFAULT_RAG_TOP_K,
    min_score: Annotated[
        float,
        typer.Option("--min-score", "-s", help="Minimum similarity score (0.0 - 1.0)"),
    ] = DEFAULT_RAG_SCORE_THRESHOLD,
    collection: Annotated[
        str | None,
        typer.Option("--collection", help="Target Qdrant collection (default: auto)"),
    ] = None,
    file_filter: Annotated[
        str | None,
        typer.Option("--file", "-f", help="Filter by filepath glob pattern"),
    ] = None,
    explain: Annotated[
        bool,
        typer.Option("--explain", help="Explain how RAG vector search works"),
    ] = False,
) -> None:
    """Perform semantic search across indexed workspace code and documentation."""
    if explain:
        from devops_cli.ai.explain import render_explanation

        render_explanation("rag")
        return
    if is_dry_run():
        render_dry_run_result(
            command="devops ai rag query",
            target=query,
            action="semantic_search",
            details={
                "query": query,
                "project": project,
                "language": language,
                "category": category,
                "top_k": top_k,
                "min_score": min_score,
                "collection": collection,
                "file_filter": file_filter,
            },
        )
        return

    qdrant, embedder, code_coll, docs_coll = _get_rag_components()

    if not qdrant.is_alive():
        print_error(f"Cannot connect to Qdrant vector store at {qdrant.base_url}", prefix=False)
        raise typer.Exit(1)

    retriever = SemanticRetriever(
        qdrant=qdrant,
        embedder=embedder,
        code_collection=code_coll,
        docs_collection=docs_coll,
        default_top_k=top_k,
        default_score_threshold=min_score,
    )

    results = retriever.search(
        query,
        top_k=top_k,
        score_threshold=min_score,
        collection=collection,
        project=project,
        language=language,
        category=category,
        file_filter=file_filter,
    )

    if not results:
        print_warning(f"No matching code/documentation found for query: {query!r}", prefix=False)
        return

    get_console().print(
        Rule(
            f" [cyan]RAG Semantic Search[/cyan]: '{query}' "
            f"({len(results)} matches, min_score={min_score}) ",
            style="cyan",
        )
    )

    for idx, r in enumerate(results, 1):
        chunk = r.chunk
        proj_tag = f"[{chunk.project_name}] " if chunk.project_name != "default" else ""
        title = (
            f"[bold cyan]#{idx}[/bold cyan] {proj_tag}[green]{chunk.file_path}[/green]:"
            f"[yellow]{chunk.start_line}-{chunk.end_line}[/yellow] "
            f"([blue]{chunk.language}[/blue], Score: [magenta]{r.score:.3f}[/magenta])"
        )
        if chunk.section_path:
            title += f" [dim]path: {' > '.join(chunk.section_path)}[/dim]"
        elif chunk.symbol_names:
            title += f" [dim]symbols: {', '.join(chunk.symbol_names)}[/dim]"

        syntax = Syntax(
            chunk.content,
            chunk.language,
            line_numbers=True,
            start_line=chunk.start_line,
            theme="monokai",
        )
        print_panel(Panel(syntax, title=title, border_style="blue"))


# =============================================================================
# Command: devops rag status
# =============================================================================


def _render_collections_table(qdrant: Any, collections: list[str]) -> None:
    """Build and print summary table of active Qdrant vector collections."""
    coll_table = Table(title="Active Vector Collections")
    coll_table.add_column("Collection", style="cyan")
    coll_table.add_column("Vectors Count", justify="right")
    coll_table.add_column("Vector Size", justify="right")
    coll_table.add_column("Status")

    for coll_name in collections:
        info = qdrant.get_collection_info(coll_name)
        pts = (
            info.get("points_count")
            or info.get("vectors_count")
            or info.get("indexed_vectors_count")
            or 0
        )
        params = info.get("config", {}).get("params", {})
        vec_params = params.get("vectors", {})
        v_size = vec_params.get("size", 0) if isinstance(vec_params, dict) else 0
        c_status = info.get("status", "ok")
        coll_table.add_row(coll_name, str(pts), str(v_size), c_status)

    print_table(coll_table)


@app.command("status")
def status_cmd() -> None:
    """Display status of vector database collections and embedding configurations."""
    qdrant, embedder, code_coll, docs_coll = _get_rag_components()
    settings = load_settings()

    is_alive = qdrant.is_alive()
    status_str = "[green]✓ online[/green]" if is_alive else "[red]✗ offline[/red]"

    table = Table(title="RAG Vector Store Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")

    table.add_row("Qdrant Endpoint", qdrant.base_url)
    table.add_row("Qdrant Status", status_str)
    table.add_row("Embedding Provider", settings.ai.provider)
    table.add_row("Embedding Model", embedder.model)
    table.add_row("Code Collection", code_coll)
    table.add_row("Docs Collection", docs_coll)
    table.add_row("RAG Enabled", str(settings.ai.rag.enabled))

    print_table(table)

    if is_alive:
        try:
            collections = qdrant.list_collections()
            if collections:
                _render_collections_table(qdrant, collections)
        except Exception as exc:
            print_warning(f"Could not fetch collection details: {exc}", prefix=False)


# =============================================================================
# Command: devops rag clear / reset
# =============================================================================


@app.command("clear")
@app.command(
    "reset", help="Alias for clear — clear vector index collections and reset local cache."
)
def clear_cmd(
    collection: Annotated[
        str | None,
        typer.Option("--collection", "-c", help="Specific collection to delete (default: all)"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Bypass confirmation prompt"),
    ] = False,
) -> None:
    """Clear vector index collections from Qdrant."""
    qdrant, _, code_coll, docs_coll = _get_rag_components()

    if not qdrant.is_alive():
        print_error(f"Cannot connect to Qdrant vector store at {qdrant.base_url}", prefix=False)
        raise typer.Exit(1)

    targets = [collection] if collection else [code_coll, docs_coll]

    if not force:
        confirm = typer.confirm(
            f"Are you sure you want to clear collections: {', '.join(targets)}?"
        )
        if not confirm:
            print_info(MESSAGES.rag.operation_cancelled, prefix=False)
            return

    for coll in targets:
        qdrant.delete_collection(coll)
        print_success(f"Cleared collection: {coll}")

    # Remove local cache
    cache_file = Path(".data/rag/index_cache.json")
    if cache_file.exists():
        cache_file.unlink()
        print_success(MESSAGES.rag.reset_cache_success)
