"""Safe, non-blocking RAG investigation step for grounding AI tasks and generation workflows."""

from __future__ import annotations

import functools
import logging
import threading
import time
from typing import Any

from devops_cli.ai.rag.embeddings import EmbeddingsEngine, EmbeddingsError
from devops_cli.ai.rag.models import RAGContext
from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.ai.rag.retriever import SemanticRetriever
from devops_cli.config import settings as settings_mod
from devops_cli.config.defaults import (
    DEFAULT_RAG_COLLECTION,
    DEFAULT_RAG_DOCS_COLLECTION,
    DEFAULT_RAG_INVESTIGATION_MAX_CHARS,
    DEFAULT_RAG_INVESTIGATION_MAX_QUERY_CHARS,
    DEFAULT_RAG_SCORE_THRESHOLD,
    DEFAULT_RAG_TOP_K,
)
from devops_cli.config.settings import Settings
from devops_cli.lang import MESSAGES
from devops_cli.telemetry import record_metric, trace_span

logger = logging.getLogger(__name__)

_INVESTIGATION_CACHE: dict[str, tuple[float, RAGContext | None]] = {}
_RETRIEVER_CACHE: tuple[float, SemanticRetriever] | None = None
_CACHE_TTL_SECONDS = 60.0

# Set by the first lookup the embedding model cannot embed. Each later lookup would send the
# same failing request, and on a node that keeps one model loaded it can evict the model the
# run is using, so RAG stays off for the rest of the process.
_RAG_STOPPED = threading.Event()
_STOP_LOCK = threading.Lock()
# Set by the first lookup the embedding model answers. Until then lookups embed one at a time
# under _PROBE_LOCK, so review workers that start together send one request to a model that
# is not served, not one each before the first failure stops RAG.
_RAG_SERVED = threading.Event()
_PROBE_LOCK = threading.Lock()


def clear_investigation_cache() -> None:
    """Clear in-memory RAG investigation and retriever caches, and lift a run-wide RAG stop."""
    global _RETRIEVER_CACHE, _INVESTIGATION_CACHE
    _RETRIEVER_CACHE = None
    _INVESTIGATION_CACHE.clear()
    _RAG_STOPPED.clear()
    _RAG_SERVED.clear()


def _stop_rag_for_run(model: str, exc: EmbeddingsError) -> None:
    """Turn RAG off for the rest of the process, warning once with the cause and the fix."""
    with _STOP_LOCK:
        if _RAG_STOPPED.is_set():
            return
        _RAG_STOPPED.set()
    record_metric("ai.rag.investigation.stopped", 1)
    logger.warning(MESSAGES.rag.stopped_for_run.format(model=model, error=exc.message))


def _get_or_create_retriever(
    st: Settings, top_k: int | None, score_threshold: float | None
) -> SemanticRetriever | None:
    """Get or create cached SemanticRetriever instance."""
    global _RETRIEVER_CACHE
    now = time.monotonic()
    if _RETRIEVER_CACHE is not None:
        last_t, retriever = _RETRIEVER_CACHE
        if now - last_t < _CACHE_TTL_SECONDS and retriever.qdrant.is_alive():
            return retriever

    from devops_cli.core.validation import validate_url

    raw_url = st.qdrant.url or "http://localhost:6333"
    qdrant_url = validate_url(
        raw_url,
        "Qdrant vector database",
        allow_private=True,
    )
    qdrant = QdrantClient(
        base_url=qdrant_url,
        api_key=settings_mod.get_qdrant_api_key(st),
        allow_private_network=st.ai.allow_private_network,
        timeout=st.qdrant.timeout,
    )
    if not qdrant.is_alive():
        logger.debug(
            "Qdrant vector store unreachable at %s, skipping RAG investigation", qdrant_url
        )
        return None

    embedder = EmbeddingsEngine(ai_config=st.ai, api_key=settings_mod.get_ai_api_key(st))
    prefix = st.qdrant.collection_prefix or "devops"
    code_coll = f"{prefix}_code" if prefix else DEFAULT_RAG_COLLECTION
    docs_coll = f"{prefix}_docs" if prefix else DEFAULT_RAG_DOCS_COLLECTION

    retriever = SemanticRetriever(
        qdrant=qdrant,
        embedder=embedder,
        code_collection=code_coll,
        docs_collection=docs_coll,
        default_top_k=top_k or DEFAULT_RAG_TOP_K,
        default_score_threshold=score_threshold or DEFAULT_RAG_SCORE_THRESHOLD,
    )
    _RETRIEVER_CACHE = (now, retriever)
    return retriever


def _retrieve(
    st: Settings,
    search_query: str,
    *,
    persona: str | None,
    top_k: int | None,
    score_threshold: float | None,
    project: str | None,
    language: str | None,
    category: str | None,
    file_filter: str | None,
    max_chars: int,
) -> RAGContext | None:
    """Retrieve context for the query; None when the store is unreachable or RAG is off.

    Until the embedding model has answered a lookup, lookups take turns, so a model that is
    not served gets one request between them.
    """
    retriever = _get_or_create_retriever(st, top_k, score_threshold)
    if retriever is None:
        return None
    search = functools.partial(
        _search,
        retriever,
        search_query,
        persona=persona,
        top_k=top_k,
        score_threshold=score_threshold,
        project=project,
        language=language,
        category=category,
        file_filter=file_filter,
        max_chars=max_chars,
    )
    if _RAG_SERVED.is_set():
        return search()
    with _PROBE_LOCK:
        if not _RAG_SERVED.is_set():
            ctx = search()
            if ctx is not None:
                _RAG_SERVED.set()
            return ctx
    return search()


def _search(
    retriever: SemanticRetriever,
    search_query: str,
    *,
    persona: str | None,
    top_k: int | None,
    score_threshold: float | None,
    project: str | None,
    language: str | None,
    category: str | None,
    file_filter: str | None,
    max_chars: int,
) -> RAGContext | None:
    """Search for the query's context; None when RAG is off or this lookup turns it off."""
    if _RAG_STOPPED.is_set():
        return None
    try:
        if persona:
            return retriever.retrieve_context_for_persona(
                search_query,
                persona=persona,
                top_k=top_k,
                score_threshold=score_threshold,
                project=project,
                language=language,
            )
        return retriever.retrieve_context(
            search_query,
            top_k=top_k,
            score_threshold=score_threshold,
            project=project,
            language=language,
            category=category,
            file_filter=file_filter,
            max_chars=max_chars,
        )
    except EmbeddingsError as exc:
        _stop_rag_for_run(retriever.embedder.model, exc)
        return None


def _investigation_attributes(
    clean_query: str, persona: str | None, project: str | None
) -> dict[str, Any]:
    """Span attributes describing one investigation's query."""
    return {
        "query_length": len(clean_query),
        "search_query_length": min(len(clean_query), DEFAULT_RAG_INVESTIGATION_MAX_QUERY_CHARS),
        "query_truncated": len(clean_query) > DEFAULT_RAG_INVESTIGATION_MAX_QUERY_CHARS,
        "persona": persona or "none",
        "project": project or "all",
    }


def _recorded_results(
    ctx: RAGContext, r_span: Any, clean_query: str, start_time: float
) -> RAGContext | None:
    """Record a retrieval's duration and hits; the context when it found any, else None."""
    duration_ms = (time.perf_counter() - start_time) * 1000.0
    record_metric("ai.rag.investigation.duration_ms", duration_ms)
    if not ctx.has_results:
        record_metric("ai.rag.investigation.empty", 1)
        return None
    r_span.set_attribute("rag.results_count", len(ctx.results))
    r_span.set_attribute("rag.total_chars", ctx.total_chars)
    record_metric("ai.rag.investigation.hits", len(ctx.results))
    logger.debug(
        "RAG investigation retrieved %d chunks in %.1fms for query: %.50s",
        len(ctx.results),
        duration_ms,
        clean_query,
    )
    return ctx


def investigate_rag_context(
    query: str,
    *,
    persona: str | None = None,
    settings: Settings | None = None,
    top_k: int | None = None,
    score_threshold: float | None = None,
    project: str | None = None,
    language: str | None = None,
    category: str | None = None,
    file_filter: str | None = None,
    max_chars: int = DEFAULT_RAG_INVESTIGATION_MAX_CHARS,
) -> RAGContext | None:
    """Execute a safe, non-blocking RAG investigation step to retrieve relevant context.

    The first lookup whose query the embedding model cannot embed turns RAG off for the rest
    of the process and logs one warning naming the model, the error and the fix. Later calls
    return None without building a retriever or sending a request, until
    `clear_investigation_cache` lifts the stop. Until the model has answered a lookup, lookups
    that run at once, such as the review workers' per-file lookups, embed one at a time, so a
    model that is not served gets one request between them.

    Returns:
        RAGContext if the vector store is available and matching chunks are retrieved;
        None if RAG is disabled or stopped, unreachable, or yields zero relevant results.
    """
    clean_query = query.strip()
    if not clean_query or _RAG_STOPPED.is_set():
        return None

    st = settings or settings_mod.load_settings()
    if not st.ai.rag.enabled:
        return None

    cache_key = (
        f"{clean_query}|{persona}|{top_k}|{score_threshold}|{project}|"
        f"{language}|{category}|{file_filter}|{max_chars}"
    )
    now = time.monotonic()
    cached = _INVESTIGATION_CACHE.get(cache_key)
    if cached is not None and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    start_time = time.perf_counter()
    with trace_span(
        "ai.rag.investigation", _investigation_attributes(clean_query, persona, project)
    ) as r_span:
        try:
            ctx = _retrieve(
                st,
                clean_query[:DEFAULT_RAG_INVESTIGATION_MAX_QUERY_CHARS],
                persona=persona,
                top_k=top_k,
                score_threshold=score_threshold,
                project=project,
                language=language,
                category=category,
                file_filter=file_filter,
                max_chars=max_chars,
            )
        except Exception as exc:
            logger.debug("RAG investigation skipped due to error: %s", exc)
            ctx = None
        found = None if ctx is None else _recorded_results(ctx, r_span, clean_query, start_time)
    _INVESTIGATION_CACHE[cache_key] = (now, found)
    return found


def format_rag_investigation_for_prompt(
    ctx: RAGContext | None,
    heading: str = "Grounding Architecture & Code Context",
) -> str:
    """Format RAG investigation results into an XML-demarcated prompt block."""
    if not ctx or not ctx.has_results:
        return ""

    return f"\n\n### {heading}\n{ctx.formatted_text}\n"
