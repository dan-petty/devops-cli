"""Unit tests for search re-ranking and multi-signal hybrid scoring."""

from __future__ import annotations

from devops_cli.ai.rag.models import CodeChunk, SearchResult
from devops_cli.ai.rag.reranker import SearchReranker


def test_reranker_symbol_bonus_and_intent() -> None:
    chunk1 = CodeChunk(
        id="c1",
        file_path="src/server.go",
        start_line=1,
        end_line=20,
        content="func DeployServer() {}",
        language="go",
        category="code",
        symbol_names=["DeployServer"],
        metadata={"security_tags": ["network"]},
    )
    chunk2 = CodeChunk(
        id="c2",
        file_path="docs/deploy.md",
        start_line=1,
        end_line=30,
        content="# Deployment Guide\nHow to deploy the application",
        language="markdown",
        category="docs",
        symbol_names=["Deployment Guide"],
        metadata={},
    )

    r1 = SearchResult(chunk=chunk1, score=0.70)
    r2 = SearchResult(chunk=chunk2, score=0.75)

    reranker = SearchReranker()

    # Query with exact symbol "DeployServer" should boost chunk1
    results_code = reranker.rerank("DeployServer implementation", [r1, r2])
    assert len(results_code) == 2
    assert results_code[0].chunk.id == "c1"
    assert results_code[0].rerank_score is not None
    assert results_code[0].rank_factors["symbol"] == 1.0

    # Query asking "how to deploy guide" should boost documentation chunk2
    results_doc = reranker.rerank("how to deploy overview guide", [r1, r2])
    assert len(results_doc) == 2
    assert results_doc[0].chunk.id == "c2"
    assert results_doc[0].rank_factors["intent"] == 1.0


def test_reranker_empty_results() -> None:
    reranker = SearchReranker()
    assert reranker.rerank("some query", []) == []
