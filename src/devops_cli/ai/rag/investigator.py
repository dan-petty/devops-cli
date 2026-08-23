"""Safe, non-blocking RAG investigation step for grounding AI tasks and generation workflows."""

from __future__ import annotations

import logging
import time

from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.ai.rag.models import RAGContext
from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.ai.rag.retriever import SemanticRetriever
from devops_cli.config import settings as settings_mod
from devops_cli.config.defaults import (
    DEFAULT_RAG_COLLECTION,
    DEFAULT_RAG_DOCS_COLLECTION,
    DEFAULT_RAG_SCORE_THRESHOLD,
    DEFAULT_RAG_TOP_K,
)
from devops_cli.config.settings import Settings
from devops_cli.telemetry import record_metric, trace_span

logger = logging.getLogger(__name__)


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
    max_chars: int = 12000,
) -> RAGContext | None:
    """Execute a safe, non-blocking RAG investigation step to retrieve relevant context.

    Returns:
        RAGContext if the vector store is available and matching chunks are retrieved;
        None if RAG is disabled, unreachable, or yields zero relevant results.
    """
    clean_query = query.strip()
    if not clean_query:
        return None

    st = settings or settings_mod.load_settings()
    if not st.ai.rag.enabled:
        return None

    max_query_len = 2048
    is_truncated = len(clean_query) > max_query_len
    search_query = clean_query[:max_query_len] if is_truncated else clean_query

    t0 = time.perf_counter()
    with trace_span(
        "ai.rag.investigation",
        {
            "query_length": len(clean_query),
            "search_query_length": len(search_query),
            "query_truncated": is_truncated,
            "persona": persona or "none",
            "project": project or "all",
        },
    ):
        try:
            qdrant_url = st.qdrant.url or "http://localhost:6333"
            qdrant = QdrantClient(
                base_url=qdrant_url,
                allow_private_network=st.ai.allow_private_network,
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

            if persona:
                ctx = retriever.retrieve_context_for_persona(
                    search_query,
                    persona=persona,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    project=project,
                    language=language,
                )
            else:
                ctx = retriever.retrieve_context(
                    search_query,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    project=project,
                    language=language,
                    category=category,
                    file_filter=file_filter,
                    max_chars=max_chars,
                )

            duration_ms = (time.perf_counter() - t0) * 1000.0
            record_metric("ai.rag.investigation.duration_ms", duration_ms)

            if ctx.has_results:
                record_metric("ai.rag.investigation.hits", len(ctx.results))
                logger.debug(
                    "RAG investigation retrieved %d chunks in %.1fms for query: %.50s",
                    len(ctx.results),
                    duration_ms,
                    clean_query,
                )
                return ctx

            record_metric("ai.rag.investigation.empty", 1)
            return None
        except Exception as exc:
            logger.debug("RAG investigation skipped due to error: %s", exc)
            return None


def format_rag_investigation_for_prompt(
    ctx: RAGContext | None,
    heading: str = "Grounding Architecture & Code Context",
) -> str:
    """Format RAG investigation results into an XML-demarcated prompt block."""
    if not ctx or not ctx.has_results:
        return ""

    return f"\n\n### {heading}\n{ctx.formatted_text}\n"
