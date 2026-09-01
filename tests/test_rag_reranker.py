"""Tests for hybrid search re-ranker and CrossEncoderReranker."""

from __future__ import annotations

from devops_cli.ai.rag.models import CodeChunk, SearchResult
from devops_cli.ai.rag.reranker import CrossEncoderReranker


def test_cross_encoder_reranker() -> None:
    """Verify CrossEncoderReranker evaluates query coverage and positional weights."""
    c1 = CodeChunk(
        id="auth-chunk-1",
        file_path="src/auth.py",
        start_line=1,
        end_line=20,
        content="def authenticate_user(token: str) -> bool:\n    return verify_jwt(token)",
        category="code",
        symbol_names=["authenticate_user"],
    )
    c2 = CodeChunk(
        id="utils-chunk-2",
        file_path="src/utils.py",
        start_line=1,
        end_line=10,
        content="def helper():\n    pass",
        category="code",
        symbol_names=["helper"],
    )

    r1 = SearchResult(chunk=c1, score=0.6)
    r2 = SearchResult(chunk=c2, score=0.5)

    reranker = CrossEncoderReranker(top_k=2)
    reranked = reranker.rerank_candidates("authenticate user with jwt token", [r2, r1])

    assert len(reranked) == 2
    # c1 should be prioritized due to token match and density
    assert reranked[0].chunk.file_path == "src/auth.py"
    assert reranked[0].rerank_score is not None
    assert reranked[0].rerank_score > 0.5


def test_cross_encoder_reranker_empty() -> None:
    """Verify CrossEncoderReranker handles empty candidates cleanly."""
    reranker = CrossEncoderReranker(top_k=5)
    assert reranker.rerank_candidates("query", []) == []
