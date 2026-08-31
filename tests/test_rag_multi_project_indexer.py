"""Unit tests for multi-project indexing and project auto-detection."""

from __future__ import annotations

from pathlib import Path

from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.ai.rag.indexer import WorkspaceIndexer, detect_project_name
from devops_cli.ai.rag.qdrant import QdrantClient


def test_detect_project_name(tmp_path: Path) -> None:
    repo_a = tmp_path / "repos" / "frontend-app"
    repo_a.mkdir(parents=True)
    (repo_a / "package.json").write_text("{}", encoding="utf-8")
    src_file = repo_a / "src" / "index.ts"
    src_file.parent.mkdir(parents=True)
    src_file.write_text("console.log('hi')", encoding="utf-8")

    assert detect_project_name(src_file, tmp_path) == "frontend-app"


def test_multi_project_indexing(tmp_path: Path) -> None:
    # Repo 1: Go backend
    go_repo = tmp_path / "go-service"
    go_repo.mkdir()
    (go_repo / "go.mod").write_text("module go-service", encoding="utf-8")
    (go_repo / "main.go").write_text("package main\nfunc Run() {}", encoding="utf-8")

    # Repo 2: Rust service
    rs_repo = tmp_path / "rs-service"
    rs_repo.mkdir()
    (rs_repo / "Cargo.toml").write_text('[package]\nname = "rs-service"', encoding="utf-8")
    (rs_repo / "lib.rs").write_text("pub fn compute() {}", encoding="utf-8")

    # Documentation directory
    docs_dir = tmp_path / "wiki"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Team Wiki\nWelcome to internal docs.", encoding="utf-8")

    upserted: dict[str, list[dict]] = {}

    class DummyQdrant(QdrantClient):
        def is_alive(self) -> bool:
            return True

        def ensure_collection(self, collection_name: str, vector_size: int = 384) -> bool:
            return True

        def upsert_points(self, collection_name: str, points: list[dict]) -> bool:
            upserted.setdefault(collection_name, []).extend(points)
            return True

    class DummyEmbedder(EmbeddingsEngine):
        def embed_batch(self, texts: list[str], prefix: str = "") -> list[list[float]]:
            return [[0.1] * 384 for _ in texts]

        def embed(self, text: str, prefix: str = "") -> list[float]:
            return [0.1] * 384

    indexer = WorkspaceIndexer(
        qdrant=DummyQdrant(base_url="http://mock:6333", allow_private_network=True),
        embedder=DummyEmbedder(),
        code_collection="test_code",
        docs_collection="test_docs",
        cache_dir=tmp_path / ".cache",
    )

    stats = indexer.index_workspace(tmp_path)
    assert stats["indexed_files"] >= 3
    assert stats["code_chunks"] >= 2
    assert stats["doc_chunks"] >= 1

    # Check project tags in payloads
    code_points = upserted.get("test_code", [])
    projects = {p["payload"]["project_name"] for p in code_points}
    assert "go-service" in projects
    assert "rs-service" in projects

    doc_points = upserted.get("test_docs", [])
    assert any(p["payload"]["category"] == "docs" for p in doc_points)
