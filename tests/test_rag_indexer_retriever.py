"""Unit tests for WorkspaceIndexer and SemanticRetriever."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.rag.embeddings import EmbeddingsEngine
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

    def delete_points_by_file(self, name: str, file_path: str) -> bool:
        if name in self.collections:
            self.collections[name] = [
                p
                for p in self.collections[name]
                if p.get("payload", {}).get("file_path") != file_path
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


def test_indexer_and_retriever_flow(tmp_path: Path) -> None:
    # Setup test workspace files
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    code_file = src_dir / "app.py"
    code_file.write_text("def run_app():\n    print('app running')\n", encoding="utf-8")

    doc_file = tmp_path / "README.md"
    doc_file.write_text("# App Documentation\nHow to run app.\n", encoding="utf-8")

    qdrant = FakeQdrantClient()
    ai_cfg = AIConfig(provider="custom", ollama_urls=[])
    embedder = EmbeddingsEngine(ai_cfg)

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
