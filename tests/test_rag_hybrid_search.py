"""Unit tests for sparse lexical ranking, hybrid retrieval fusion, and vector quantization."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.ai.lexical import LexicalMatch, bm25_scores, tokenize
from devops_cli.ai.rag.models import CodeChunk, SearchResult
from devops_cli.ai.rag.retriever import (
    hybrid_search_results,
    lexical_rerank,
    reciprocal_rank_fusion,
)


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


# ─────────────────────────────────────────────────────────────────────────────
# 1. Tokenisation & BM25 scoring
# ─────────────────────────────────────────────────────────────────────────────


def test_tokenize_lowercases_and_splits_on_word_boundaries() -> None:
    """Tokens are lowercase words, with punctuation dropped."""
    assert tokenize("Set_Cached(key, TTL=30)") == ["set_cached", "key", "ttl", "30"]


def test_bm25_ranks_the_document_containing_the_query_term_first() -> None:
    """A literal term match outranks documents that never mention it."""
    documents = [
        "the connection pool manages sockets",
        "authentication uses a bearer token for each request",
        "generic helper utilities and shared formatting",
    ]
    ranked = bm25_scores("bearer token", documents)

    assert ranked[0].index == 1
    assert ranked[0].score > 0.0


def test_bm25_omits_documents_with_no_matching_terms() -> None:
    """A zero score means no query term appeared, not a tie at the bottom."""
    ranked = bm25_scores("kubernetes", ["postgres replication", "redis eviction"])
    assert ranked == []


def test_bm25_returns_nothing_for_empty_input() -> None:
    """Empty queries, corpora, and punctuation-only queries all yield no ranking."""
    assert bm25_scores("", ["content"]) == []
    assert bm25_scores("query", []) == []
    assert bm25_scores("!!! ???", ["content"]) == []


def test_bm25_skips_empty_documents() -> None:
    """A document with no tokens cannot match and is excluded."""
    ranked = bm25_scores("token", ["", "a bearer token"])
    assert [match.index for match in ranked] == [1]


def test_bm25_rewards_term_frequency() -> None:
    """A document mentioning the term more often scores higher."""
    ranked = bm25_scores("cache", ["cache cache cache layer", "cache layer"])
    assert ranked[0].index == 0


def test_bm25_discounts_terms_common_to_every_document() -> None:
    """A term appearing everywhere carries little discriminating weight.

    Inverse document frequency is what stops a ubiquitous word from dominating the
    ranking, so the rarer term must decide the order.
    """
    documents = [
        "cache layer for vectors",
        "cache layer for embeddings",
        "cache layer for quantization",
    ]
    ranked = bm25_scores("cache quantization", documents)
    assert ranked[0].index == 2


def test_bm25_honours_the_result_limit() -> None:
    """The ranking is truncated to the requested number of matches."""
    ranked = bm25_scores("token", ["token a", "token b", "token c"], limit=2)
    assert len(ranked) == 2


def test_bm25_ranking_is_deterministic_for_tied_scores() -> None:
    """Equal scores fall back to input order, so results never shuffle between runs."""
    documents = ["token alpha", "token beta"]
    first = [m.index for m in bm25_scores("token", documents)]
    second = [m.index for m in bm25_scores("token", documents)]
    assert first == second


def test_lexical_match_is_immutable() -> None:
    """A scored match cannot be mutated after ranking."""
    match = LexicalMatch(index=0, score=1.0)
    with pytest.raises(FrozenInstanceError):
        match.score = 2.0  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Shared scorer reuse
# ─────────────────────────────────────────────────────────────────────────────


def test_conversation_search_uses_the_shared_scorer() -> None:
    """Conversation ranking delegates to the shared BM25 implementation.

    Both consumers share one implementation so a correction to the ranking cannot apply
    to only half the codebase.
    """
    from devops_cli.ai.harness.conversation import bm25_rank

    documents = [
        {"run_id": "r1", "role": "user", "content": "deploy the kubernetes cluster"},
        {"run_id": "r2", "role": "assistant", "content": "unrelated commentary"},
    ]
    matches = bm25_rank("kubernetes", documents)

    assert [m.run_id for m in matches] == ["r1"]
    assert matches[0].score > 0.0


def test_conversation_search_respects_max_matches() -> None:
    """The conversation wrapper still truncates to the requested match count."""
    from devops_cli.ai.harness.conversation import bm25_rank

    documents = [{"run_id": f"r{i}", "role": "user", "content": "token"} for i in range(5)]
    assert len(bm25_rank("token", documents, max_matches=2)) == 2


# ─────────────────────────────────────────────────────────────────────────────
# 3. Hybrid fusion
# ─────────────────────────────────────────────────────────────────────────────


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


# ─────────────────────────────────────────────────────────────────────────────
# 4. Retriever integration
# ─────────────────────────────────────────────────────────────────────────────


def _retriever_with(points: list[dict[str, Any]]) -> Any:
    """Build a retriever whose Qdrant and embedder are stubbed."""
    from devops_cli.ai.rag.retriever import SemanticRetriever

    qdrant = MagicMock()
    qdrant.search_points.return_value = points
    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1, 0.2, 0.3]

    retriever = SemanticRetriever(qdrant=qdrant, embedder=embedder)
    retriever.reranker = MagicMock()
    retriever.reranker.rerank.side_effect = lambda query, results, top_k: results[:top_k]
    return retriever


def _point(point_id: str, content: str, score: float) -> dict[str, Any]:
    """Build a raw Qdrant point payload."""
    return {
        "id": point_id,
        "score": score,
        "payload": {"file_path": f"src/{point_id}.py", "content": content, "language": "python"},
    }


def test_search_applies_hybrid_fusion_by_default() -> None:
    """Search fuses lexical ranking into the dense results unless told otherwise."""
    retriever = _retriever_with(
        [
            _point("semantic", "general discussion of caching strategy", 0.95),
            _point("exact", "def _set_cached(key, value): ...", 0.30),
        ]
    )
    with patch("devops_cli.ai.rag.retriever._embed_search_query", return_value=[0.1]):
        results = retriever.search("_set_cached", rerank=False)

    assert results[0].chunk.id == "exact"


def test_search_can_disable_hybrid_fusion() -> None:
    """Purely semantic retrieval remains available."""
    retriever = _retriever_with(
        [
            _point("semantic", "general discussion of caching strategy", 0.95),
            _point("exact", "def _set_cached(key, value): ...", 0.30),
        ]
    )
    with patch("devops_cli.ai.rag.retriever._embed_search_query", return_value=[0.1]):
        results = retriever.search("_set_cached", rerank=False, hybrid=False)

    assert results[0].chunk.id == "semantic"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Vector quantization
# ─────────────────────────────────────────────────────────────────────────────


def test_quantization_config_requests_int8_storage() -> None:
    """Quantization stores vectors as int8, held in RAM for fast scoring."""
    from devops_cli.ai.rag.qdrant import _build_quantization_config

    config = _build_quantization_config(True)
    assert config is not None
    assert config.scalar.type.value == "int8"
    assert config.scalar.always_ram is True


def test_quantization_can_be_disabled() -> None:
    """Opting out stores full-precision vectors."""
    from devops_cli.ai.rag.qdrant import _build_quantization_config

    assert _build_quantization_config(False) is None


def test_ensure_collection_creates_quantized_collections() -> None:
    """New collections are created with quantization applied by default."""
    from devops_cli.ai.rag.qdrant import QdrantClient

    client = QdrantClient.__new__(QdrantClient)
    client._verified_collections = {}
    client._dim_mismatch_warned = set()
    client.get_collection_info = MagicMock(return_value=None)  # type: ignore[method-assign]
    captured: dict[str, Any] = {}

    def _capture(operation: Any, description: str) -> Any:
        native = MagicMock()
        native.create_collection.side_effect = lambda **kwargs: captured.update(kwargs)
        return operation(native)

    client._execute_with_retry = MagicMock(side_effect=_capture)  # type: ignore[method-assign]

    assert client.ensure_collection("docs", vector_size=768) is True
    assert captured["quantization_config"] is not None
