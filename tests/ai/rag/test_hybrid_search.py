"""Hybrid retrieval: lexical ranking fused into dense results, and the search that applies it."""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.ai.rag.models import CodeChunk, SearchResult
from devops_cli.ai.rag.retriever import (
    SemanticRetriever,
    hybrid_search_results,
    lexical_rerank,
    reciprocal_rank_fusion,
)
from tests.support.fakes.qdrant import seed_scored_chunk

pytestmark = pytest.mark.usefixtures("keyring_store")


def _result(chunk_id: str, content: str, score: float = 0.5) -> SearchResult:
    """Build a search result carrying the given chunk content."""
    return SearchResult(
        chunk=CodeChunk(
            id=chunk_id,
            file_path=f"src/{chunk_id}.py",
            start_line=1,
            end_line=10,
            content=content,
            language="python",
        ),
        score=score,
    )


def test_lexical_rerank_orders_candidates_by_literal_match() -> None:
    """Candidates are reordered by BM25 relevance to the query text."""
    candidates = [
        _result("a", "generic orchestration helpers"),
        _result("b", "def _set_cached(key, value, ttl): ..."),
    ]
    assert [r.chunk.id for r in lexical_rerank("_set_cached", candidates)] == ["b"]


def test_lexical_rerank_of_empty_candidates_is_empty() -> None:
    """No candidates means no lexical ranking."""
    assert lexical_rerank("query", []) == []


def test_hybrid_promotes_an_exact_symbol_match() -> None:
    """A literal symbol match is promoted above a merely thematic neighbour.

    This is the failure hybrid search exists to fix: embeddings smooth over the exact
    identifier, so the dense ranking buries the chunk that actually defines it.
    """
    dense = [
        _result("semantic", "caching concepts and eviction strategy discussion", score=0.9),
        _result("exact", "def _set_cached(key, value, ttl): store(key, value)", score=0.4),
    ]
    fused = hybrid_search_results("_set_cached", dense)
    assert fused[0].chunk.id == "exact"


def test_hybrid_preserves_dense_results_when_nothing_matches_lexically() -> None:
    """With no literal match, the dense ordering stands unchanged."""
    dense = [_result("a", "alpha content"), _result("b", "beta content")]
    fused = hybrid_search_results("kubernetes", dense)
    assert [r.chunk.id for r in fused] == ["a", "b"]


def test_hybrid_of_empty_results_is_empty() -> None:
    """Fusing nothing yields nothing rather than raising."""
    assert hybrid_search_results("query", []) == []


def test_fusion_keeps_documents_found_by_only_one_ranker() -> None:
    """A chunk found by either ranker survives fusion.

    Fusion must be additive: dropping a result because only one ranker surfaced it would
    defeat the purpose of combining them.
    """
    dense_only = _result("dense", "dense only content")
    sparse_only = _result("sparse", "sparse only content")
    fused = reciprocal_rank_fusion([dense_only], [sparse_only])

    assert {r.chunk.id for r in fused} == {"dense", "sparse"}


def test_fusion_ranks_documents_found_by_both_rankers_highest() -> None:
    """Agreement between rankers is the strongest signal."""
    both = _result("both", "content")
    dense_only = _result("dense", "content")
    sparse_only = _result("sparse", "content")

    fused = reciprocal_rank_fusion([dense_only, both], [sparse_only, both])
    assert fused[0].chunk.id == "both"


def _retriever_with(qdrant: Any, embedder: Any) -> SemanticRetriever:
    """A retriever over a store that holds a thematic chunk and a chunk that defines the symbol."""
    vector = embedder.embed_query("_set_cached")
    seed_scored_chunk(
        qdrant,
        vector,
        0.95,
        "general discussion of caching strategy",
        point_id="semantic",
        file_path="src/semantic.py",
    )
    seed_scored_chunk(
        qdrant,
        vector,
        0.30,
        "def _set_cached(key, value): ...",
        point_id="exact",
        file_path="src/exact.py",
    )
    return SemanticRetriever(
        qdrant=qdrant, embedder=embedder, default_top_k=5, default_score_threshold=0.0
    )


def test_search_applies_hybrid_fusion_by_default(qdrant: Any, embedder: Any) -> None:
    """Search fuses lexical ranking into the dense results unless told otherwise."""
    results = _retriever_with(qdrant, embedder).search("_set_cached", rerank=False)

    assert results[0].chunk.id == "exact"


def test_search_can_disable_hybrid_fusion(qdrant: Any, embedder: Any) -> None:
    """Purely semantic retrieval remains available."""
    results = _retriever_with(qdrant, embedder).search("_set_cached", rerank=False, hybrid=False)

    assert results[0].chunk.id == "semantic"
