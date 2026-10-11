"""Tests for RAG collection embedding model recording, mismatch protection, and cosine ranking (#1066)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsError
from devops_cli.ai.rag.indexer import WorkspaceIndexer
from devops_cli.ai.rag.models import CodeChunk, SearchResult
from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.ai.rag.reranker import SearchReranker
from devops_cli.ai.rag.retriever import SemanticRetriever, reset_search_verified_models
from devops_cli.config.constants import CONST_EXIT_FAILURE


def test_collection_refuses_index_run_with_different_model_keeping_points(tmp_path: Path) -> None:
    """A collection holding bge-m3:latest points refuses an index run with qwen3-embedding:0.6b, keeping points."""
    (tmp_path / "main.py").write_text("def hello(): pass\n", encoding="utf-8")

    initial_point = {
        "id": "existing-1",
        "vector": [0.1] * 1024,
        "payload": {
            "file_path": "existing.py",
            "embedding_model": "bge-m3:latest",
            "project_name": "p",
        },
    }

    mock_qdrant = MagicMock()
    mock_qdrant.api_key = "test-key"
    mock_qdrant.get_collection_info.return_value = {
        "points_count": 1,
        "vector_size": 1024,
        "config": {"params": {"vectors": {"size": 1024}}},
    }
    mock_qdrant.scroll_points.return_value = [initial_point]

    mock_embedder = MagicMock()
    mock_embedder.model = "qwen3-embedding:0.6b"
    mock_embedder.dimension = 1024

    indexer = WorkspaceIndexer(
        qdrant=mock_qdrant,
        embedder=mock_embedder,
        cache_dir=tmp_path / ".cache",
    )

    with pytest.raises(EmbeddingsError) as exc_info:
        indexer.index_workspace(tmp_path, project="p", include_kb=False)

    err = exc_info.value
    err_msg = str(err)
    assert (
        err.exit_code,
        err.is_transient,
        "bge-m3:latest" in err_msg,
        "qwen3-embedding:0.6b" in err_msg,
        "devops ai rag clear --force" in err_msg,
    ) == (CONST_EXIT_FAILURE, False, True, True, True)

    mock_qdrant.delete_collection.assert_not_called()
    mock_qdrant.upsert_points.assert_not_called()


def test_search_dimension_mismatch_raises_permanent_error_without_delete_or_create() -> None:
    """768-dim query against 1024-dim collection raises permanent error, recording no delete or create call."""
    client = QdrantClient("http://localhost:6333", allow_private_network=True)
    mock_native = MagicMock()
    mock_native.query_points.side_effect = Exception(
        "Vector dimension error: expected dim: 1024, got 768"
    )
    client._client = mock_native

    with pytest.raises(EmbeddingsError) as exc_info:
        client.search_points("devops_code", query_vector=[0.1] * 768)

    err = exc_info.value
    assert (
        err.is_transient,
        "1024" in str(err),
        "768" in str(err),
        "devops ai rag clear --force" in str(err),
        mock_native.delete_collection.call_count,
        mock_native.create_collection.call_count,
    ) == (False, True, True, True, 0, 0)


def test_search_checks_model_once_per_process() -> None:
    """Search checks the model a collection records once per process and raises permanent EmbeddingsError."""
    reset_search_verified_models()

    point = {
        "id": "1",
        "payload": {
            "file_path": "main.py",
            "embedding_model": "bge-m3:latest",
        },
    }
    mock_qdrant = MagicMock()
    mock_qdrant.get_collection_info.return_value = {
        "points_count": 1,
        "vector_size": 1024,
    }
    mock_qdrant.scroll_points.return_value = [point]

    mock_embedder = MagicMock()
    mock_embedder.model = "qwen3-embedding:0.6b"
    mock_embedder.embed_query.return_value = [0.1] * 1024

    retriever = SemanticRetriever(
        qdrant=mock_qdrant,
        embedder=mock_embedder,
        code_collection="devops_code",
        docs_collection="devops_docs",
    )

    with pytest.raises(EmbeddingsError) as exc_info:
        retriever.search("test query")

    err = exc_info.value
    assert (
        err.is_transient,
        "bge-m3:latest" in str(err),
        "qwen3-embedding:0.6b" in str(err),
    ) == (False, True, True)

    with pytest.raises(EmbeddingsError):
        retriever.search("test query again")

    assert mock_qdrant.scroll_points.call_count == 1


def test_reranker_sorts_equal_fused_rank_in_cosine_order() -> None:
    """Two results with same fused rank but cosines 0.9 and 0.4 come out of reranker in cosine order."""
    chunk_low = CodeChunk(
        id="chunk_low_cosine",
        file_path="src/low.py",
        start_line=1,
        end_line=5,
        content="def calculate(): return 42",
        language="python",
        doc_type="code",
    )
    chunk_high = CodeChunk(
        id="chunk_high_cosine",
        file_path="src/high.py",
        start_line=1,
        end_line=5,
        content="def calculate(): return 42",
        language="python",
        doc_type="code",
    )

    res_low = SearchResult(
        chunk=chunk_low,
        score=0.5,
        vector_score=0.4,
        fused_score=0.5,
    )
    res_high = SearchResult(
        chunk=chunk_high,
        score=0.5,
        vector_score=0.9,
        fused_score=0.5,
    )

    reranker = SearchReranker()
    reranked = reranker.rerank("calculate", [res_low, res_high])

    assert (
        [r.chunk.id for r in reranked],
        [r.vector_score for r in reranked],
    ) == (
        ["chunk_high_cosine", "chunk_low_cosine"],
        [0.9, 0.4],
    )
    assert (reranked[0].rerank_score or 0.0) > (reranked[1].rerank_score or 0.0)
