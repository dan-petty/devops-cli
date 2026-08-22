"""Semantic code and documentation retriever for RAG context augmentation with re-ranking."""

from __future__ import annotations

import logging
import time
from typing import Any

from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.ai.rag.models import CodeChunk, RAGContext, SearchResult
from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.ai.rag.reranker import SearchReranker
from devops_cli.config.defaults import (
    DEFAULT_RAG_COLLECTION,
    DEFAULT_RAG_DOCS_COLLECTION,
    DEFAULT_RAG_SCORE_THRESHOLD,
    DEFAULT_RAG_TOP_K,
)
from devops_cli.telemetry import record_metric, trace_span

logger = logging.getLogger(__name__)


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
    ) -> list[SearchResult]:
        """Execute semantic search across vector collections with faceted filters and re-ranking."""
        k = max(1, min(top_k if top_k is not None else self.default_top_k, 100))
        fetch_limit = max(k * 3, 10) if rerank else k
        raw_threshold = (
            score_threshold if score_threshold is not None else self.default_score_threshold
        )
        threshold = max(0.0, min(raw_threshold, 1.0)) if raw_threshold is not None else None
        start = time.perf_counter()

        with trace_span(
            "ai.rag.search",
            {"query_length": len(query), "top_k": k, "project": project or "all"},
        ):
            try:
                query_vec = self.embedder.embed_query(query)
            except Exception as exc:
                logger.warning("Failed to embed search query: %s", exc)
                return []

        if collection:
            target_collections = [collection]
        elif category == "docs":
            target_collections = [self.docs_collection]
        elif category in ("code", "iac", "config"):
            target_collections = [self.code_collection]
        else:
            target_collections = [self.code_collection, self.docs_collection]

        filter_payload: dict[str, Any] = {}
        if file_filter:
            filter_payload["file_path"] = file_filter
        if project:
            filter_payload["project_name"] = project
        if language:
            filter_payload["language"] = language
        if category:
            filter_payload["category"] = category

        active_filter = filter_payload if filter_payload else None

        raw_results: list[dict[str, Any]] = []
        for coll in target_collections:
            try:
                points = self.qdrant.search_points(
                    coll,
                    query_vec,
                    limit=fetch_limit,
                    score_threshold=threshold,
                    filter_payload=active_filter,
                )
                raw_results.extend(points)
            except Exception as exc:
                logger.debug("Failed searching collection %s: %s", coll, exc)

        results: list[SearchResult] = []
        for pt in raw_results:
            payload = pt.get("payload", {})
            chunk = CodeChunk(
                id=str(pt.get("id", "")),
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
            )
            results.append(SearchResult(chunk=chunk, score=float(pt.get("score", 0.0))))

        if rerank and results:
            final_results = self.reranker.rerank(query, results, top_k=k)
        else:
            results.sort(key=lambda x: x.score, reverse=True)
            final_results = results[:k]

        record_metric(
            "devops_cli_rag_query_duration_ms",
            (time.perf_counter() - start) * 1000,
            unit="ms",
        )
        return final_results

    def filter_and_validate_results(
        self,
        results: list[SearchResult],
        *,
        max_chars: int = 15000,
        max_per_file: int = 4,
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
        rerank: bool = True,
        max_chars: int = 15000,
    ) -> RAGContext:
        """Search and format results into a validated, structured prompt context block."""
        results = self.search(
            query,
            top_k=top_k,
            score_threshold=score_threshold,
            collection=collection,
            project=project,
            language=language,
            category=category,
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
        persona_lower = persona.lower()
        expanded_query = query
        category: str | None = None

        if "sec" in persona_lower:
            expanded_query = f"{query} security auth secrets token validation permissions"
            category = "code"
        elif "arch" in persona_lower:
            expanded_query = f"{query} architecture design patterns interfaces abstractions"
        elif "qa" in persona_lower or "test" in persona_lower:
            expanded_query = f"{query} tests fixtures mocks assertions coverage"
            category = "code"
        elif "pm" in persona_lower or "product" in persona_lower:
            expanded_query = f"{query} requirements api specification contract docs"
            category = "docs"
        elif "audit" in persona_lower:
            expanded_query = f"{query} compliance logging error handling telemetry reliability"

        return self.retrieve_context(
            expanded_query,
            top_k=top_k,
            score_threshold=score_threshold,
            project=project,
            language=language,
            category=category,
            rerank=True,
        )
