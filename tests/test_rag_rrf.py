"""Tests for Reciprocal Rank Fusion (RRF) in hybrid semantic retrieval."""

from __future__ import annotations

from devops_cli.ai.rag.models import CodeChunk, SearchResult
from devops_cli.ai.rag.retriever import reciprocal_rank_fusion


def test_reciprocal_rank_fusion() -> None:
    """Verify RRF rank merging between dense and sparse results."""
    c1 = CodeChunk(id="c1", file_path="a.py", start_line=1, end_line=10, content="code1")
    c2 = CodeChunk(id="c2", file_path="b.py", start_line=1, end_line=10, content="code2")
    dense = [SearchResult(chunk=c1, score=0.9), SearchResult(chunk=c2, score=0.8)]
    sparse = [SearchResult(chunk=c2, score=12.0), SearchResult(chunk=c1, score=8.0)]

    fused = reciprocal_rank_fusion(dense, sparse)
    assert len(fused) == 2
    assert fused[0].score > 0
