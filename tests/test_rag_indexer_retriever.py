"""Unit tests for WorkspaceIndexer and SemanticRetriever."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from devops_cli.ai.rag.embeddings import EmbeddingsEngine, EmbeddingsError
from devops_cli.ai.rag.indexer import WorkspaceIndexer
from devops_cli.ai.rag.qdrant import QdrantClient
from devops_cli.ai.rag.retriever import SemanticRetriever
from devops_cli.config.settings import AIConfig


class FakeQdrantClient(QdrantClient):
    def __init__(self) -> None:
        super().__init__("http://localhost:6333", allow_private_network=True)
        self.collections: dict[str, list[dict]] = {}

    def is_alive(self) -> bool:
        return True

    def ensure_collection(self, name: str, vector_size: int, distance: str = "Cosine") -> bool:
        if name not in self.collections:
            self.collections[name] = []
        return True

    def get_collection_info(self, name: str) -> dict:
        if name in self.collections:
            return {
                "points_count": len(self.collections[name]),
                "config": {"params": {"vectors": {"size": 384}}},
            }
        return {}

    def upsert_points(self, name: str, points: list[dict], *, batch_size: int = 64) -> int:
        if name not in self.collections:
            self.collections[name] = []
        self.collections[name].extend(points)
        return len(points)

    def delete_points_by_files(
        self,
        name: str,
        file_paths: Sequence[str],
        *,
        project_name: str | None = None,
        wait: bool = False,
    ) -> bool:
        for f in file_paths:
            self.delete_points_by_file(name, f, project_name=project_name)
        return True

    def delete_points_by_file(
        self, name: str, file_path: str, *, project_name: str | None = None
    ) -> bool:
        if name in self.collections:
            self.collections[name] = [
                p
                for p in self.collections[name]
                if not (
                    p.get("payload", {}).get("file_path") == file_path
                    and (
                        project_name is None
                        or p.get("payload", {}).get("project_name") == project_name
                    )
                )
            ]
        return True

    def search_points(
        self,
        name: str,
        query_vector: list[float],
        *,
        limit: int = 5,
        score_threshold: float | None = None,
        filter_payload: dict | None = None,
    ) -> list[dict]:
        pts = self.collections.get(name, [])
        results = []
        for p in pts:
            score = 0.85
            if score_threshold is None or score >= score_threshold:
                results.append({"id": p["id"], "score": score, "payload": p["payload"]})
        return results[:limit]


class FixedVectorEngine(EmbeddingsEngine):
    """An engine whose model answers every text with the same unit vector."""

    def __init__(self) -> None:
        super().__init__(AIConfig(provider="custom", ollama_urls=[]), valkey_client=None)

    def _dispatch_embed(self, prefixed_miss: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0, 0.0] for _ in prefixed_miss]


def test_indexer_and_retriever_flow(tmp_path: Path) -> None:
    # Setup test workspace files
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    code_file = src_dir / "app.py"
    code_file.write_text("def run_app():\n    print('app running')\n", encoding="utf-8")

    doc_file = tmp_path / "README.md"
    doc_file.write_text("# App Documentation\nHow to run app.\n", encoding="utf-8")

    qdrant = FakeQdrantClient()
    embedder = FixedVectorEngine()

    indexer = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        cache_dir=tmp_path / ".cache",
    )

    stats = indexer.index_workspace(tmp_path)
    assert stats["indexed_files"] == 2
    assert stats["total_chunks"] >= 2
    assert stats["removed_files"] == 0

    # Second index run should skip unchanged files
    stats2 = indexer.index_workspace(tmp_path)
    assert stats2["indexed_files"] == 0
    assert stats2["skipped_files"] == 2
    assert stats2["removed_files"] == 0

    # Query retriever
    retriever = SemanticRetriever(qdrant=qdrant, embedder=embedder)
    results = retriever.search("how to run app", top_k=5)
    assert len(results) >= 1
    assert any("app" in r.chunk.content for r in results)

    context = retriever.retrieve_context("how to run app")
    assert context.has_results is True
    assert "<rag_context>" in context.formatted_text

    # Third run: Delete README.md -> should remove 1 outdated file from Qdrant and cache
    doc_file.unlink()
    stats3 = indexer.index_workspace(tmp_path)
    assert stats3["indexed_files"] == 0
    assert stats3["skipped_files"] == 1
    assert stats3["removed_files"] == 1
    assert len(qdrant.collections.get(indexer.docs_collection, [])) == 0


def test_index_and_index_kb_coexistence(tmp_path: Path) -> None:
    """Ensure indexing workspace and indexing knowledge base do not purge each other."""
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    ws_file = ws_dir / "main.py"
    ws_file.write_text("print('hello workspace')", encoding="utf-8")

    qdrant = FakeQdrantClient()
    embedder = FixedVectorEngine()

    indexer = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        cache_dir=tmp_path / ".cache",
    )

    # 1. Index workspace
    ws_stats = indexer.index_workspace(ws_dir, project="my-workspace")
    assert ws_stats["indexed_files"] == 1
    assert len(qdrant.collections.get(indexer.code_collection, [])) >= 1

    # 2. Index knowledge base with isolated mock KB dir
    mock_kb_dir = tmp_path / "mock_kb"
    mock_kb_dir.mkdir()
    (mock_kb_dir / "guide.md").write_text("# KB Guide\nKnowledge base content.", encoding="utf-8")

    from unittest.mock import patch

    with patch("devops_cli.ai.kb.get_knowledge_base_dir", return_value=mock_kb_dir):
        kb_stats = indexer.index_knowledge_base()
        assert kb_stats["indexed_files"] >= 1
        assert kb_stats["removed_files"] == 0
        # Workspace code points must NOT be deleted
        assert len(qdrant.collections.get(indexer.code_collection, [])) >= 1

        # 3. Re-index workspace (should not delete KB docs)
        ws_stats2 = indexer.index_workspace(ws_dir, project="my-workspace")
        assert ws_stats2["removed_files"] == 0
        assert len(qdrant.collections.get(indexer.docs_collection, [])) >= 1


def test_indexer_file_filters_and_gitignore(tmp_path: Path) -> None:
    """Verify _load_gitignore_spec, _is_indexable_file, and collection stats."""
    from devops_cli.ai.rag.indexer import (
        _get_single_collection_stat,
        _is_indexable_file,
        _load_gitignore_spec,
    )

    # 1. _load_gitignore_spec
    gi_file = tmp_path / ".gitignore"
    gi_file.write_text("*.tmp\nbuild/\n", encoding="utf-8")
    spec = _load_gitignore_spec(tmp_path)
    assert spec is not None

    assert _load_gitignore_spec(tmp_path / "nonexistent") is None

    # 2. _is_indexable_file
    code_f = tmp_path / "main.py"
    code_f.write_text("print('hi')", encoding="utf-8")
    assert _is_indexable_file(code_f, tmp_path, gitignore_spec=spec) is True

    tmp_f = tmp_path / "test.tmp"
    tmp_f.write_text("temp", encoding="utf-8")
    assert _is_indexable_file(tmp_f, tmp_path, gitignore_spec=spec) is False

    docker_f = tmp_path / "Dockerfile"
    docker_f.write_text("FROM alpine", encoding="utf-8")
    assert _is_indexable_file(docker_f, tmp_path) is True

    # 3. _get_single_collection_stat
    qdrant = FakeQdrantClient()
    qdrant.collections["test_coll"] = [{"id": 1, "payload": {}}]
    stat = _get_single_collection_stat(qdrant, "test_coll", cached_file_count=5)
    assert stat is not None
    assert stat.collection_name == "test_coll"
    assert stat.total_vectors == 1


def test_a_query_that_cannot_be_embedded_fails_the_search() -> None:
    """Search and context retrieval raise the EmbeddingsError instead of searching with nothing.

    An empty result would read as "nothing relevant is indexed", and Qdrant is never asked.
    """
    searched: list[list[float]] = []

    class RecordingQdrant(FakeQdrantClient):
        def search_points(
            self, name: str, query_vector: list[float], **kwargs: object
        ) -> list[dict]:
            searched.append(query_vector)
            return []

    engine = EmbeddingsEngine(AIConfig(provider="custom", ollama_urls=[]), valkey_client=None)
    retriever = SemanticRetriever(qdrant=RecordingQdrant(), embedder=engine)

    with pytest.raises(EmbeddingsError) as from_search:
        retriever.search("how to run app")
    with pytest.raises(EmbeddingsError) as from_context:
        retriever.retrieve_context("how to run app")

    assert (from_search.value.details, from_context.value.details, searched) == (
        {"model": engine.model, "provider": "custom"},
        {"model": engine.model, "provider": "custom"},
        [],
    )


def test_indexing_text_the_model_cannot_embed_raises_and_stores_nothing(tmp_path: Path) -> None:
    """Indexing raises the EmbeddingsError and upserts no point, so no stand-in vector is stored.

    The file is not recorded as indexed either, so the next run retries it.
    """
    (tmp_path / "app.py").write_text("def run_app():\n    print('app running')\n", "utf-8")
    qdrant = FakeQdrantClient()
    engine = EmbeddingsEngine(AIConfig(provider="custom", ollama_urls=[]), valkey_client=None)
    indexer = WorkspaceIndexer(qdrant=qdrant, embedder=engine, cache_dir=tmp_path / ".cache")

    with pytest.raises(EmbeddingsError) as raised:
        indexer.index_workspace(tmp_path, include_kb=False)

    assert (
        raised.value.details["model"],
        [point for points in qdrant.collections.values() for point in points],
        indexer._load_cache(),
    ) == (engine.model, [], {})


def test_indexer_skips_lockfiles(tmp_path: Path) -> None:
    """The indexer skips uv.lock, other *.lock files, package-lock.json, pnpm-lock.yaml and go.sum."""
    from devops_cli.ai.rag.indexer import _is_indexable_file

    lockfiles = [
        tmp_path / "uv.lock",
        tmp_path / "Cargo.lock",
        tmp_path / "poetry.lock",
        tmp_path / "package-lock.json",
        tmp_path / "pnpm-lock.yaml",
        tmp_path / "go.sum",
    ]
    for lf in lockfiles:
        lf.write_text("lock content", encoding="utf-8")
        assert _is_indexable_file(lf, tmp_path) is False

    valid_file = tmp_path / "regular.py"
    valid_file.write_text("print('hello')", encoding="utf-8")
    assert _is_indexable_file(valid_file, tmp_path) is True


def test_failed_second_batch_ends_with_exit_1_and_preserves_first_batch(tmp_path: Path) -> None:
    """A failed batch ends index with exit 1 naming first and last file, while earlier batches stay cached for resume."""
    from typing import Any

    from devops_cli.config.constants import CONST_EXIT_FAILURE

    file_a = tmp_path / "file_a.py"
    file_b = tmp_path / "file_b.py"
    file_c = tmp_path / "file_c.py"
    file_a.write_text("def a(): pass\n", encoding="utf-8")
    file_b.write_text("def b(): pass\n", encoding="utf-8")
    file_c.write_text("def c(): pass\n", encoding="utf-8")

    qdrant = FakeQdrantClient()
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()

    batch_calls = 0

    class StubFailingSecondBatchEmbedder:
        model = "test-model"
        batch_size = 1

        def embed_texts(self, texts: list[str], *, is_query: bool = False) -> list[list[float]]:
            nonlocal batch_calls
            batch_calls += 1
            if batch_calls == 2:
                raise RuntimeError("Gateway 504 Gateway Timeout")
            return [[0.1] * 8 for _ in texts]

    embedder = StubFailingSecondBatchEmbedder()
    indexer = WorkspaceIndexer(qdrant=qdrant, embedder=embedder, cache_dir=cache_dir)  # type: ignore[arg-type]

    with pytest.raises(EmbeddingsError) as exc_info:
        indexer.index_workspace(tmp_path, include_kb=False)

    assert (
        exc_info.value.exit_code == CONST_EXIT_FAILURE
        and "Failed to embed batch from" in exc_info.value.message
        and "Gateway 504 Gateway Timeout" in exc_info.value.message
    )

    cached = indexer._load_cache()
    assert len(cached) == 1
    assert "file_a.py" in next(iter(cached.keys()))

    embedder_recovered = StubFailingSecondBatchEmbedder()

    def fake_embed(texts: list[str], **kwargs: Any) -> list[list[float]]:
        return [[0.2] * 8 for _ in texts]

    embedder_recovered.embed_texts = fake_embed  # type: ignore[method-assign]
    indexer_resume = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder_recovered,
        cache_dir=cache_dir,  # type: ignore[arg-type]
    )

    result = indexer_resume.index_workspace(tmp_path, include_kb=False, force=False)
    assert (result["indexed_files"], result["skipped_files"]) == (2, 1)
