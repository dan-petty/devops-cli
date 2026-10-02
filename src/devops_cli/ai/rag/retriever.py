"""Semantic code and documentation retriever for RAG context augmentation with re-ranking."""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from devops_cli.ai.lexical import bm25_scores
from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.ai.rag.models import CodeChunk, RAGContext, SearchResult
from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.ai.rag.reranker import SearchReranker
from devops_cli.config.defaults import (
    DEFAULT_RAG_COLLECTION,
    DEFAULT_RAG_DOCS_COLLECTION,
    DEFAULT_RAG_MAX_CHARS,
    DEFAULT_RAG_MAX_CHUNKS_PER_FILE,
    DEFAULT_RAG_SCORE_THRESHOLD,
    DEFAULT_RAG_TOP_K,
)
from devops_cli.telemetry import ContextPropagatingThread, trace_span
from devops_cli.telemetry.instruments import RAG_QUERY_DURATION, emit

logger = logging.getLogger(__name__)


@contextmanager
def _timed_stage(stage: str) -> Iterator[None]:
    """Observe a query stage's time on the RAG histogram, labelled by stage and outcome.

    A stage that raises is observed too, as outcome `error`: an embedding that times out is
    exactly the tail the latency panels exist to show. An interrupt records nothing.
    """
    start = time.perf_counter()
    try:
        yield
    except Exception:
        _observe_stage(stage, start, "error")
        raise
    _observe_stage(stage, start, "ok")


def _observe_stage(stage: str, start: float, outcome: str) -> None:
    elapsed_ms = (time.perf_counter() - start) * 1000
    emit(RAG_QUERY_DURATION, elapsed_ms, {"stage": stage, "outcome": outcome})


def _embed_search_query(embedder: Any, query: str) -> list[float]:
    """Embed the search query, traced; an EmbeddingsError propagates to the caller.

    A query that cannot be embedded has no vector to search with, so the search fails rather
    than returning nothing, which a caller would read as "no relevant context".
    """
    model_name = getattr(embedder, "model", "default")
    with trace_span("ai.rag.embed_query", {"query_length": len(query), "model": model_name}):
        return embedder.embed_query(query)  # type: ignore[no-any-return]


def _build_rag_filter_payload(
    file_filter: str | None,
    project: str | None,
    language: str | None,
    category: str | None,
) -> dict[str, Any] | None:
    """Build filter payload dict for Qdrant search."""
    filter_payload: dict[str, Any] = {}
    if file_filter:
        filter_payload["file_path"] = file_filter
    if project:
        filter_payload["project_name"] = project
    if language:
        filter_payload["language"] = language
    if category:
        filter_payload["category"] = category
    return filter_payload if filter_payload else None


def _search_collection(
    collection: str,
    *,
    qdrant: Any,
    query_vec: list[float],
    fetch_limit: int,
    threshold: float | None,
    active_filter: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Query one collection's points; a collection whose search fails adds none."""
    try:
        points: list[dict[str, Any]] = qdrant.search_points(
            collection,
            query_vec,
            limit=fetch_limit,
            score_threshold=threshold,
            filter_payload=active_filter,
        )
        return points
    except Exception as exc:
        logger.debug("Failed searching collection %s: %s", collection, exc)
        return []


def _search_collections(
    qdrant: Any,
    target_collections: list[str],
    query_vec: list[float],
    fetch_limit: int,
    threshold: float | None,
    active_filter: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Query Qdrant points across target collections at once, pooled in the collections' order.

    Each collection is a round trip of its own, so searching them one after the other added
    their latencies (#975). Pooling in the collections' order, not the order the replies come
    back in, keeps fusion and ranking, and so the result, the same as a sequential search.

    The first collection is searched on the caller's thread and the rest on daemon threads,
    joined before this returns. A pool's threads would be joined however the caller left, so
    Ctrl-C would wait out the other searches, up to three 60 s attempts each against a
    stalled Qdrant, and the interpreter would wait for them again on exit. Daemon threads are
    not, so an interrupt leaves at once and abandons the searches still running.
    """
    search = functools.partial(
        _search_collection,
        qdrant=qdrant,
        query_vec=query_vec,
        fetch_limit=fetch_limit,
        threshold=threshold,
        active_filter=active_filter,
    )
    replies: list[list[dict[str, Any]]] = [[] for _ in target_collections]

    def search_into(index: int) -> None:
        replies[index] = search(target_collections[index])

    others = [
        ContextPropagatingThread(
            target=search_into, args=(index,), name=f"devops-rag-search-{index}", daemon=True
        )
        for index in range(1, len(replies))
    ]
    for thread in others:
        thread.start()
    if replies:
        search_into(0)
    for thread in others:
        thread.join()
    return [point for points in replies for point in points]


def _project_search_results(raw_results: list[dict[str, Any]]) -> list[SearchResult]:
    """Project raw Qdrant points into typed search results.

    Storage projection is kept separate from ranking so each stage can be tested and
    changed without disturbing the other.
    """
    results: list[SearchResult] = []
    for point in raw_results:
        payload = point.get("payload", {})
        results.append(
            SearchResult(
                chunk=CodeChunk(
                    id=str(point.get("id", "")),
                    file_path=str(payload.get("file_path", "")),
                    start_line=int(payload.get("start_line", 1)),
                    end_line=int(payload.get("end_line", 1)),
                    content=str(payload.get("content", "")),
                    language=str(payload.get("language", "text")),
                    doc_type=str(payload.get("doc_type", "code")),
                    category=str(payload.get("category", "code")),
                    project_name=str(payload.get("project_name", "default")),
                    section_path=list(payload.get("section_path", [])),
                    symbol_names=list(payload.get("symbol_names", [])),
                    metadata=dict(payload.get("metadata", {})),
                    content_hash=str(payload.get("content_hash", "")),
                ),
                score=float(point.get("score", 0.0)),
            )
        )
    return results


def lexical_rerank(query: str, results: list[SearchResult]) -> list[SearchResult]:
    """Rank candidate chunks by BM25 relevance to the literal query text.

    Dense similarity smooths over the exact tokens that make a query specific — an error
    code, a flag, a symbol name — so a literal match can rank below a merely thematic one.
    Scoring the same candidates lexically recovers those, and fusing the two orderings
    keeps the semantic matches that BM25 would miss.
    """
    if not results:
        return []
    ranked = bm25_scores(query, [res.chunk.content for res in results])
    return [results[match.index] for match in ranked]


def hybrid_search_results(
    query: str, dense_results: list[SearchResult], k: int = 60
) -> list[SearchResult]:
    """Fuse dense and lexical rankings of the same candidate pool."""
    lexical = lexical_rerank(query, dense_results)
    if not lexical:
        return dense_results
    return reciprocal_rank_fusion(dense_results, lexical, k=k)


def reciprocal_rank_fusion(
    dense_results: list[SearchResult],
    sparse_results: list[SearchResult],
    k: int = 60,
) -> list[SearchResult]:
    """Combine dense vector and sparse keyword results using Reciprocal Rank Fusion (RRF)."""
    scores: dict[str, float] = {}
    chunk_map: dict[str, SearchResult] = {}

    for rank, res in enumerate(dense_results):
        cid = res.chunk.id or f"{res.chunk.file_path}:{res.chunk.start_line}"
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank + 1))
        chunk_map[cid] = res

    for rank, res in enumerate(sparse_results):
        cid = res.chunk.id or f"{res.chunk.file_path}:{res.chunk.start_line}"
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank + 1))
        if cid not in chunk_map:
            chunk_map[cid] = res

    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    fused: list[SearchResult] = []
    for cid in sorted_ids:
        item = chunk_map[cid]
        item.score = scores[cid]
        fused.append(item)
    return fused


def _expand_persona_rag_query(query: str, persona: str) -> tuple[str, str | None]:
    """Expand query with persona-specific semantic terms and filter category."""
    persona_lower = persona.lower()
    if "sec" in persona_lower:
        return f"{query} security auth secrets token validation permissions", "code"
    if "arch" in persona_lower:
        return f"{query} architecture design patterns interfaces abstractions", None
    if "qa" in persona_lower or "test" in persona_lower:
        return f"{query} tests fixtures mocks assertions coverage", "code"
    if "pm" in persona_lower or "product" in persona_lower:
        return f"{query} requirements api specification contract docs", "docs"
    if "audit" in persona_lower:
        return f"{query} compliance logging error handling telemetry reliability", None
    return query, None


class SemanticRetriever:
    """Retrieves relevant code and documentation chunks to augment LLM prompts."""

    def __init__(
        self,
        qdrant: QdrantClient,
        embedder: EmbeddingsEngine,
        *,
        code_collection: str = DEFAULT_RAG_COLLECTION,
        docs_collection: str = DEFAULT_RAG_DOCS_COLLECTION,
        default_top_k: int = DEFAULT_RAG_TOP_K,
        default_score_threshold: float = DEFAULT_RAG_SCORE_THRESHOLD,
        reranker: SearchReranker | None = None,
    ) -> None:
        self.qdrant = qdrant
        self.embedder = embedder
        self.code_collection = code_collection
        self.docs_collection = docs_collection
        self.default_top_k = default_top_k
        self.default_score_threshold = default_score_threshold
        self.reranker = reranker or SearchReranker()

    def _resolve_collections(self, collection: str | None, category: str | None) -> list[str]:
        """Select which collections a query should target."""
        if collection:
            return [collection]
        if category == "docs":
            return [self.docs_collection]
        if category in ("code", "iac", "config"):
            return [self.code_collection]
        return [self.code_collection, self.docs_collection]

    def _rank_results(
        self,
        query: str,
        results: list[SearchResult],
        k: int,
        *,
        rerank: bool,
        hybrid: bool,
    ) -> list[SearchResult]:
        """Produce the final ordering from the candidate pool."""
        if rerank and results:
            return list(self.reranker.rerank(query, results, top_k=k))
        if hybrid:
            # Fusion already ordered the candidates; re-sorting by raw score would
            # discard the lexical contribution entirely.
            return results[:k]
        return sorted(results, key=lambda r: r.score, reverse=True)[:k]

    def _search_limits(
        self, top_k: int | None, score_threshold: float | None, *, rerank: bool
    ) -> tuple[int, int, float | None]:
        """The result count, the points fetched per collection, and the score threshold.

        Reranking fetches three times the result count, and at least 10, to choose from.
        """
        k = max(1, min(top_k if top_k is not None else self.default_top_k, 100))
        fetch_limit = max(k * 3, 10) if rerank else k
        raw_threshold = (
            score_threshold if score_threshold is not None else self.default_score_threshold
        )
        threshold = max(0.0, min(raw_threshold, 1.0)) if raw_threshold is not None else None
        return k, fetch_limit, threshold

    def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        score_threshold: float | None = None,
        collection: str | None = None,
        project: str | None = None,
        language: str | None = None,
        category: str | None = None,
        file_filter: str | None = None,
        rerank: bool = True,
        hybrid: bool = True,
    ) -> list[SearchResult]:
        """Search vector collections with faceted filters, hybrid fusion, and re-ranking.

        `hybrid` additionally scores the dense candidate pool lexically and fuses the two
        rankings, so exact symbol and identifier matches are not lost to embedding
        smoothing. Set it to False for purely semantic retrieval.

        The RAG histogram times each stage, embedding the query, searching the collections and
        ranking the pool, beside the whole query as `total`, so a slow query's time can be
        attributed (#975).

        Raises EmbeddingsError when the query cannot be embedded.
        """
        k, fetch_limit, threshold = self._search_limits(top_k, score_threshold, rerank=rerank)

        with (
            _timed_stage("total"),
            trace_span(
                "ai.rag.search",
                {
                    "query_length": len(query),
                    "top_k": k,
                    "project": project or "all",
                    "rag.rerank": rerank,
                },
            ) as search_span,
        ):
            with _timed_stage("embedding"):
                query_vec = _embed_search_query(self.embedder, query)
            target_collections = self._resolve_collections(collection, category)
            search_span.set_attribute("rag.collections", target_collections)

            active_filter = _build_rag_filter_payload(file_filter, project, language, category)
            with _timed_stage("search"):
                raw_results = _search_collections(
                    self.qdrant,
                    target_collections,
                    query_vec,
                    fetch_limit,
                    threshold,
                    active_filter,
                )

            with _timed_stage("ranking"):
                results = _project_search_results(raw_results)
                if hybrid and results:
                    results = hybrid_search_results(query, results)
                    search_span.set_attribute("rag.hybrid", True)
                final_results = self._rank_results(query, results, k, rerank=rerank, hybrid=hybrid)

            search_span.set_attribute("rag.results_count", len(final_results))
            if final_results:
                search_span.set_attribute("rag.top_score", final_results[0].score)
            return final_results

    def filter_and_validate_results(
        self,
        results: list[SearchResult],
        *,
        max_chars: int = DEFAULT_RAG_MAX_CHARS,
        max_per_file: int = DEFAULT_RAG_MAX_CHUNKS_PER_FILE,
    ) -> list[SearchResult]:
        """Deduplicate overlapping chunks, enforce file limits, and bound context size."""
        if not results:
            return []

        filtered: list[SearchResult] = []
        file_counts: dict[str, int] = {}
        covered_ranges: dict[str, list[tuple[int, int]]] = {}
        current_chars = 0

        for res in results:
            chunk = res.chunk
            if not chunk.file_path or not chunk.content:
                continue

            # Limit chunks per individual file
            fpath = chunk.file_path
            count = file_counts.get(fpath, 0)
            if count >= max_per_file:
                continue

            # Check line span overlap with existing chunks from the same file
            ranges = covered_ranges.setdefault(fpath, [])
            c_start, c_end = chunk.start_line, chunk.end_line
            overlap = False
            for r_start, r_end in ranges:
                # If overlap exceeds 50% of the smaller chunk, skip redundant duplicate
                overlap_len = max(0, min(c_end, r_end) - max(c_start, r_start) + 1)
                chunk_len = max(1, c_end - c_start + 1)
                if overlap_len / chunk_len > 0.5:
                    overlap = True
                    break

            if overlap:
                continue

            chunk_chars = len(chunk.content)
            if current_chars + chunk_chars > max_chars and filtered:
                # Exceeded total character budget
                break

            ranges.append((c_start, c_end))
            file_counts[fpath] = count + 1
            current_chars += chunk_chars
            filtered.append(res)

        return filtered

    def retrieve_context(
        self,
        query: str,
        *,
        top_k: int | None = None,
        score_threshold: float | None = None,
        collection: str | None = None,
        project: str | None = None,
        language: str | None = None,
        category: str | None = None,
        file_filter: str | None = None,
        rerank: bool = True,
        max_chars: int = DEFAULT_RAG_MAX_CHARS,
    ) -> RAGContext:
        """Search and format results into a validated, structured prompt context block.

        Raises EmbeddingsError when the query cannot be embedded.
        """
        results = self.search(
            query,
            top_k=top_k,
            score_threshold=score_threshold,
            collection=collection,
            project=project,
            language=language,
            category=category,
            file_filter=file_filter,
            rerank=rerank,
        )

        valid_results = self.filter_and_validate_results(results, max_chars=max_chars)

        formatted_parts: list[str] = []
        if valid_results:
            formatted_parts.append("<rag_context>")
            for idx, res in enumerate(valid_results, 1):
                chunk = res.chunk
                display_score = (
                    f"{res.rerank_score:.3f}"
                    if res.rerank_score is not None
                    else f"{res.score:.3f}"
                )
                symbols_info = (
                    f" symbols={','.join(chunk.symbol_names)}" if chunk.symbol_names else ""
                )
                section_info = (
                    f' section="{" > ".join(chunk.section_path)}"' if chunk.section_path else ""
                )
                sec_tags = chunk.metadata.get("security_tags", [])
                sec_info = f' security="{",".join(sec_tags)}"' if sec_tags else ""
                formatted_parts.append(
                    f'<chunk index="{idx}" project="{chunk.project_name}" '
                    f'file="{chunk.file_path}" language="{chunk.language}" '
                    f'lines="{chunk.start_line}-{chunk.end_line}" '
                    f'score="{display_score}"{symbols_info}{section_info}{sec_info}>\n'
                    f"{chunk.content}\n"
                    f"</chunk>"
                )
            formatted_parts.append("</rag_context>")

        formatted_text = "\n\n".join(formatted_parts)
        return RAGContext(
            query=query,
            results=valid_results,
            formatted_text=formatted_text,
        )

    def retrieve_context_for_persona(
        self,
        query: str,
        persona: str,
        *,
        top_k: int | None = None,
        score_threshold: float | None = None,
        project: str | None = None,
        language: str | None = None,
    ) -> RAGContext:
        """Retrieve semantic RAG context tailored to a specific review or chat persona."""
        expanded_query, category = _expand_persona_rag_query(query, persona)
        return self.retrieve_context(
            expanded_query,
            top_k=top_k,
            score_threshold=score_threshold,
            project=project,
            language=language,
            category=category,
            rerank=True,
        )
