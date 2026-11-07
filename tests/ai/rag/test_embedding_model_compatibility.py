"""A collection records its embedding model, and a different model is refused (#1066)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsError
from devops_cli.ai.rag.indexer import WorkspaceIndexer
from devops_cli.ai.rag.models import CodeChunk, SearchResult
from devops_cli.ai.rag.reranker import SearchReranker
from devops_cli.ai.rag.retriever import SemanticRetriever
from devops_cli.config.constants import CONST_EXIT_FAILURE
from tests.support.fakes.qdrant import seed_chunk

pytestmark = pytest.mark.usefixtures("keyring_store")

OLD_MODEL = "bge-m3:latest"
NEW_MODEL = "qwen3-embedding:0.6b"


def _store_indexed_with(qdrant: Any, embedder: Any, model: str) -> None:
    """Hold a point of `model` in the code collection, and give the embedder another model."""
    seed_chunk(qdrant, embedder, "def old(): pass", file_path="existing.py", embedding_model=model)
    embedder.model = NEW_MODEL


def test_a_collection_refuses_an_index_run_with_a_different_model_and_keeps_its_points(
    tmp_path: Path, qdrant: Any, embedder: Any
) -> None:
    (tmp_path / "main.py").write_text("def hello(): pass\n", encoding="utf-8")
    _store_indexed_with(qdrant, embedder, OLD_MODEL)
    qdrant.calls.clear()
    indexer = WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=tmp_path / ".cache")

    with pytest.raises(EmbeddingsError) as exc_info:
        indexer.index_workspace(tmp_path, project="p", include_kb=False)

    err = exc_info.value
    assert (
        err.exit_code,
        err.is_transient,
        OLD_MODEL in str(err),
        NEW_MODEL in str(err),
        "devops ai rag clear --force" in str(err),
    ) == (CONST_EXIT_FAILURE, False, True, True, True)
    assert [
        call[0] for call in qdrant.calls if call[0] in ("delete_collection", "upsert_points")
    ] == []
    assert len(qdrant.collections["devops_code"]) == 1


def test_search_checks_the_model_of_a_collection_once_per_process(
    qdrant: Any, embedder: Any
) -> None:
    _store_indexed_with(qdrant, embedder, OLD_MODEL)
    retriever = SemanticRetriever(
        qdrant=qdrant,
        embedder=embedder,
        code_collection="devops_code",
        docs_collection="devops_docs",
    )

    with pytest.raises(EmbeddingsError) as exc_info:
        retriever.search("test query")
    err = exc_info.value
    assert (err.is_transient, OLD_MODEL in str(err), NEW_MODEL in str(err)) == (False, True, True)

    with pytest.raises(EmbeddingsError) as raised:
        retriever.search("test query again")
    assert raised.value.error_code == "EMBEDDINGS_ERROR"
    assert [call[0] for call in qdrant.calls].count("scroll_points") == 1


def test_two_servers_with_one_label_are_checked_against_their_own_model(
    qdrant: Any, embedder: Any
) -> None:
    """The second server is checked against its own model, not skipped or compared with the first."""
    from tests.support.fakes.qdrant import FakeQdrantClient

    other = FakeQdrantClient()
    other.base_url = "http://example.com:6334"
    seed_chunk(qdrant, embedder, "def a(): pass", embedding_model=embedder.model)
    seed_chunk(other, embedder, "def a(): pass", embedding_model="other-model")

    SemanticRetriever(qdrant=qdrant, embedder=embedder).search("query")
    with pytest.raises(EmbeddingsError, match="embedding model mismatch"):
        SemanticRetriever(qdrant=other, embedder=embedder).search("query")


def test_the_reranker_sorts_equal_fused_rank_in_cosine_order() -> None:
    """Two results with one fused rank but cosines 0.9 and 0.4 come out in cosine order."""

    def result(chunk_id: str, vector_score: float) -> SearchResult:
        chunk = CodeChunk(
            id=chunk_id,
            file_path=f"src/{chunk_id}.py",
            start_line=1,
            end_line=5,
            content="def calculate(): return 42",
            language="python",
            doc_type="code",
        )
        return SearchResult(chunk=chunk, score=0.5, vector_score=vector_score, fused_score=0.5)

    reranked = SearchReranker().rerank(
        "calculate", [result("chunk_low_cosine", 0.4), result("chunk_high_cosine", 0.9)]
    )

    assert ([r.chunk.id for r in reranked], [r.vector_score for r in reranked]) == (
        ["chunk_high_cosine", "chunk_low_cosine"],
        [0.9, 0.4],
    )
    assert (reranked[0].rerank_score or 0.0) > (reranked[1].rerank_score or 0.0)
