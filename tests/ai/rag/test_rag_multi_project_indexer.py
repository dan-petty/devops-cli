"""Unit tests for multi-project indexing, project auto-detection, and multitenancy isolation."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from devops_cli.ai.rag.chunker import SemanticChunker
from devops_cli.ai.rag.embeddings import EmbeddingsEngine
from devops_cli.ai.rag.indexer import WorkspaceIndexer, detect_project_name
from devops_cli.ai.rag.qdrant import QdrantClient, QdrantClientError
from devops_cli.config import constants
from devops_cli.config.constants import (
    CONST_INDEX_CACHE_FILENAME,
    CONST_RAG_KB_PROJECT,
)
from devops_cli.config.settings import AIConfig
from tests.support.fakes.clock import ClockFake

CONST_INDEX_COUNTS_FILENAME = getattr(constants, "CONST_INDEX_COUNTS_FILENAME", "index_counts.json")
CONST_RAG_PAYLOAD_INDEXES = getattr(
    constants,
    "CONST_RAG_PAYLOAD_INDEXES",
    (
        {"field_name": "project_name", "field_schema": "keyword", "is_tenant": True},
        {"field_name": "file_path", "field_schema": "keyword"},
    ),
)

pytestmark = [
    pytest.mark.usefixtures("keyring_store"),
    pytest.mark.unreachable("example.com"),
]


class FakeQdrantClient(QdrantClient):
    """Hermetic in-memory fake for Qdrant client operations."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(base_url="http://example.com:6333", allow_private_network=True)
        self.collections: dict[str, dict[str | int, dict[str, Any]]] = {}
        self.payload_schemas: dict[str, dict[str, Any]] = {}
        self.upsert_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []
        self.count_calls: list[dict[str, Any]] = []
        self.index_calls: list[dict[str, Any]] = []
        self.raise_on_delete: bool = False
        self.raise_on_count: bool = False

    def is_alive(self) -> bool:
        return True

    def get_collection_info(self, name: str) -> dict[str, Any]:
        if name not in self.collections:
            return {}
        points = self.collections[name]
        return {
            "status": "green",
            "points_count": len(points),
            "vectors_count": len(points),
            "vector_size": 384,
            "payload_schema": dict(self.payload_schemas.get(name, {})),
        }

    def ensure_collection(
        self,
        name: str,
        vector_size: int = 384,
        distance: str = "Cosine",
        quantize: bool = False,
    ) -> bool:
        if name not in self.collections:
            self.collections[name] = {}
            self.payload_schemas[name] = {}
        for spec in CONST_RAG_PAYLOAD_INDEXES:
            fn = spec["field_name"]
            if fn not in self.payload_schemas[name]:
                self.create_payload_index(
                    name, fn, field_schema=spec.get("field_schema", "keyword")
                )
        return True

    def create_payload_index(
        self,
        collection_name: str,
        field_name: str,
        field_schema: Any = None,
        wait: bool = True,
        **kwargs: Any,
    ) -> Any:
        self.index_calls.append(
            {
                "collection": collection_name,
                "field_name": field_name,
                "field_schema": field_schema,
                "wait": wait,
            }
        )
        if collection_name in self.payload_schemas:
            self.payload_schemas[collection_name][field_name] = field_schema
        return True

    def upsert_points(
        self,
        name: str,
        points: list[dict[str, Any]],
        *,
        batch_size: int = 100,
    ) -> int:
        self.ensure_collection(name)
        for p in points:
            pid = p["id"]
            self.collections[name][pid] = dict(p)
        self.upsert_calls.append({"collection": name, "count": len(points)})
        return len(points)

    def delete_points_by_files(
        self,
        name: str,
        file_paths: Sequence[str],
        *,
        project_name: str | None = None,
        wait: bool = True,
    ) -> bool:
        self.delete_calls.append(
            {
                "collection": name,
                "file_paths": list(file_paths),
                "project_name": project_name,
                "wait": wait,
            }
        )
        if self.raise_on_delete:
            raise QdrantClientError("Simulated delete failure")
        if name not in self.collections:
            return True
        to_del: list[str | int] = []
        for pid, p in self.collections[name].items():
            payload = p.get("payload", {})
            if payload.get("file_path") in file_paths:
                if project_name is None or payload.get("project_name") == project_name:
                    to_del.append(pid)
        for pid in to_del:
            del self.collections[name][pid]
        return True

    def delete_points_by_project(
        self,
        name: str,
        project_name: str,
        *,
        wait: bool = True,
    ) -> bool:
        self.delete_calls.append(
            {
                "collection": name,
                "project_name": project_name,
                "wait": wait,
            }
        )
        if self.raise_on_delete:
            raise QdrantClientError("Simulated delete failure")
        if name not in self.collections:
            return True
        to_del = [
            pid
            for pid, p in self.collections[name].items()
            if p.get("payload", {}).get("project_name") == project_name
        ]
        for pid in to_del:
            del self.collections[name][pid]
        return True

    def count_points(self, name: str, filter_payload: dict[str, Any] | None = None) -> int:
        self.count_calls.append({"collection": name, "filter": filter_payload})
        if self.raise_on_count:
            raise QdrantClientError("Simulated count failure")
        if name not in self.collections:
            return 0
        if not filter_payload:
            return len(self.collections[name])
        count = 0
        for p in self.collections[name].values():
            payload = p.get("payload", {})
            match = True
            for k, v in filter_payload.items():
                if payload.get(k) != v:
                    match = False
                    break
            if match:
                count += 1
        return count

    def scroll_points(
        self,
        name: str,
        limit: int = 1,
        with_payload: bool = True,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        if name not in self.collections:
            return []
        return list(self.collections[name].values())[:limit]

    def delete_collection(self, name: str) -> bool:
        self.collections.pop(name, None)
        self.payload_schemas.pop(name, None)
        return True


class FakeEmbedder(EmbeddingsEngine):
    """Hermetic deterministic embedder for indexing tests."""

    def __init__(self, dimension: int = 384) -> None:
        super().__init__(AIConfig(provider="custom", ollama_urls=[]), valkey_client=None)
        self._dim = dimension

    @property
    def dimension(self) -> int:
        return self._dim

    def _dispatch_embed(self, prefixed_miss: list[str]) -> list[list[float]]:
        return [[0.1] * self._dim for _ in prefixed_miss]


def test_detect_project_name(tmp_path: Path) -> None:
    repo_a = tmp_path / "repos" / "frontend-app"
    repo_a.mkdir(parents=True)
    (repo_a / "package.json").write_text("{}", encoding="utf-8")
    src_file = repo_a / "src" / "index.ts"
    src_file.parent.mkdir(parents=True)
    src_file.write_text("console.log('hi')", encoding="utf-8")

    assert detect_project_name(src_file, tmp_path) == "frontend-app"


def test_multi_project_indexing(tmp_path: Path) -> None:
    go_repo = tmp_path / "go-service"
    go_repo.mkdir()
    (go_repo / "go.mod").write_text("module go-service", encoding="utf-8")
    (go_repo / "main.go").write_text("package main\nfunc Run() {}", encoding="utf-8")

    rs_repo = tmp_path / "rs-service"
    rs_repo.mkdir()
    (rs_repo / "Cargo.toml").write_text('[package]\nname = "rs-service"', encoding="utf-8")
    (rs_repo / "lib.rs").write_text("pub fn compute() {}", encoding="utf-8")

    docs_dir = tmp_path / "wiki"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Team Wiki\nWelcome to internal docs.", encoding="utf-8")

    qdrant = FakeQdrantClient()
    embedder = FakeEmbedder()
    indexer = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        code_collection="test_code",
        docs_collection="test_docs",
        cache_dir=tmp_path / ".cache",
    )

    stats = indexer.index_workspace(tmp_path)
    assert stats["indexed_files"] >= 3
    assert stats["code_chunks"] >= 2
    assert stats["doc_chunks"] >= 1

    code_points = list(qdrant.collections.get("test_code", {}).values())
    projects = {p["payload"]["project_name"] for p in code_points}
    assert "go-service" in projects
    assert "rs-service" in projects


def test_chunk_ids_scoped_by_project(tmp_path: Path) -> None:
    f1 = tmp_path / "README.md"
    f1.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")
    chunker = SemanticChunker()
    c1 = chunker.chunk_file(f1, relative_to=tmp_path, project_name="project-a")
    c2 = chunker.chunk_file(f1, relative_to=tmp_path, project_name="project-b")
    assert len(c1) > 0
    assert len(c2) > 0
    assert c1[0].id != c2[0].id


def test_readme_collision_resolved_between_tree_and_knowledge_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text(
        "# Project\n" + "\n".join(f"line {i}" for i in range(1, 50)), encoding="utf-8"
    )

    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "README.md").write_text(
        "# KB\n" + "\n".join(f"line {i}" for i in range(1, 50)), encoding="utf-8"
    )
    monkeypatch.setattr("devops_cli.ai.kb.get_knowledge_base_dir", lambda: kb_dir)

    qdrant = FakeQdrantClient()
    embedder = FakeEmbedder()
    indexer = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        code_collection="test_code",
        docs_collection="test_docs",
        cache_dir=tmp_path / ".cache",
    )
    indexer.index_workspace(repo_dir, include_kb=True)
    docs = qdrant.collections.get("test_docs", {})
    projs = {p["payload"]["project_name"] for p in docs.values()}
    assert "repo" in projs
    assert CONST_RAG_KB_PROJECT in projs

    repo_points = [p for p in docs.values() if p["payload"]["project_name"] == "repo"]
    kb_points = [p for p in docs.values() if p["payload"]["project_name"] == CONST_RAG_KB_PROJECT]
    assert len(repo_points) > 0
    assert len(kb_points) > 0


def test_two_projects_with_same_readme_keep_own_points_and_deleting_one_leaves_other(
    tmp_path: Path,
) -> None:
    repo_a = tmp_path / "repo-a"
    repo_a.mkdir()
    (repo_a / "README.md").write_text(
        "# Common Title\nContent common to both repos.", encoding="utf-8"
    )

    repo_b = tmp_path / "repo-b"
    repo_b.mkdir()
    (repo_b / "README.md").write_text(
        "# Common Title\nContent common to both repos.", encoding="utf-8"
    )

    qdrant = FakeQdrantClient()
    embedder = FakeEmbedder()
    cache_dir = tmp_path / ".cache"
    indexer = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        code_collection="test_code",
        docs_collection="test_docs",
        cache_dir=cache_dir,
    )
    indexer.index_workspace(repo_a, project="proj-a")
    indexer.index_workspace(repo_b, project="proj-b")

    docs = qdrant.collections.get("test_docs", {})
    pts_a = [p for p in docs.values() if p["payload"]["project_name"] == "proj-a"]
    pts_b = [p for p in docs.values() if p["payload"]["project_name"] == "proj-b"]
    assert len(pts_a) > 0
    assert len(pts_b) > 0

    (repo_a / "README.md").unlink()
    indexer.index_workspace(repo_a, project="proj-a")

    docs_after = qdrant.collections.get("test_docs", {})
    pts_a_after = [p for p in docs_after.values() if p["payload"]["project_name"] == "proj-a"]
    pts_b_after = [p for p in docs_after.values() if p["payload"]["project_name"] == "proj-b"]
    assert len(pts_a_after) == 0
    assert len(pts_b_after) > 0


def test_delete_that_raises_leaves_cache_entry_and_next_run_deletes_points(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    doc_file = repo / "doc.md"
    doc_file.write_text("# Doc\nSome text.", encoding="utf-8")

    qdrant = FakeQdrantClient()
    embedder = FakeEmbedder()
    cache_dir = tmp_path / ".cache"
    indexer = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        code_collection="test_code",
        docs_collection="test_docs",
        cache_dir=cache_dir,
    )
    indexer.index_workspace(repo, project="proj-x")
    assert "proj-x:doc.md" in indexer._load_cache()

    doc_file.unlink()
    qdrant.raise_on_delete = True
    with pytest.raises(QdrantClientError):
        indexer.index_workspace(repo, project="proj-x")

    assert "proj-x:doc.md" in indexer._load_cache()

    qdrant.raise_on_delete = False
    indexer.index_workspace(repo, project="proj-x")
    assert "proj-x:doc.md" not in indexer._load_cache()
    docs = qdrant.collections.get("test_docs", {})
    assert len([p for p in docs.values() if p["payload"]["project_name"] == "proj-x"]) == 0


def test_deleting_every_file_of_project_purges_all_points(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    f1 = repo / "file1.py"
    f1.write_text("def a(): pass\n", encoding="utf-8")
    f2 = repo / "file2.py"
    f2.write_text("def b(): pass\n", encoding="utf-8")

    qdrant = FakeQdrantClient()
    embedder = FakeEmbedder()
    cache_dir = tmp_path / ".cache"
    indexer = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        code_collection="test_code",
        docs_collection="test_docs",
        cache_dir=cache_dir,
    )
    indexer.index_workspace(repo, project="proj-del-all")
    assert len(qdrant.collections.get("test_code", {})) > 0

    f1.unlink()
    f2.unlink()
    indexer.index_workspace(repo, project="proj-del-all")

    code_points = [
        p
        for p in qdrant.collections.get("test_code", {}).values()
        if p["payload"]["project_name"] == "proj-del-all"
    ]
    assert len(code_points) == 0
    cache = indexer._load_cache()
    assert not any(k.startswith("proj-del-all:") for k in cache)


def test_force_on_project_a_keeps_project_b_cache_entries(tmp_path: Path) -> None:
    repo_a = tmp_path / "repo-a"
    repo_a.mkdir()
    (repo_a / "a.py").write_text("def a(): pass\n", encoding="utf-8")

    repo_b = tmp_path / "repo-b"
    repo_b.mkdir()
    (repo_b / "b.py").write_text("def b(): pass\n", encoding="utf-8")

    qdrant = FakeQdrantClient()
    embedder = FakeEmbedder()
    cache_dir = tmp_path / ".cache"
    indexer = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        code_collection="test_code",
        docs_collection="test_docs",
        cache_dir=cache_dir,
    )
    indexer.index_workspace(repo_a, project="proj-a")
    indexer.index_workspace(repo_b, project="proj-b")

    cache = indexer._load_cache()
    assert "proj-a:a.py" in cache
    assert "proj-b:b.py" in cache

    indexer.index_workspace(repo_a, project="proj-a", force=True)

    cache_after = indexer._load_cache()
    assert "proj-a:a.py" in cache_after
    assert "proj-b:b.py" in cache_after


def test_file_deleted_between_two_runs_with_force_leaves_no_point(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    f1 = repo / "keep.py"
    f1.write_text("def keep(): pass\n", encoding="utf-8")
    f2 = repo / "del_me.py"
    f2.write_text("def del_me(): pass\n", encoding="utf-8")

    qdrant = FakeQdrantClient()
    embedder = FakeEmbedder()
    cache_dir = tmp_path / ".cache"
    indexer = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        code_collection="test_code",
        docs_collection="test_docs",
        cache_dir=cache_dir,
    )
    indexer.index_workspace(repo, project="proj-force-del")

    f2.unlink()
    indexer.index_workspace(repo, project="proj-force-del", force=True)

    points = [
        p
        for p in qdrant.collections.get("test_code", {}).values()
        if p["payload"]["project_name"] == "proj-force-del"
    ]
    file_paths = {p["payload"]["file_path"] for p in points}
    assert "del_me.py" not in file_paths
    assert "keep.py" in file_paths


def test_counts_recorded_emptying_one_collection_makes_next_run_embed_every_file(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n", encoding="utf-8")
    (repo / "README.md").write_text("# README\nHello docs.\n", encoding="utf-8")

    qdrant = FakeQdrantClient()
    embedder = FakeEmbedder()
    cache_dir = tmp_path / ".cache"
    indexer = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        code_collection="test_code",
        docs_collection="test_docs",
        cache_dir=cache_dir,
    )
    indexer.index_workspace(repo, project="proj-counts")
    counts = getattr(indexer, "_load_counts", lambda: {})()
    assert "proj-counts" in counts
    assert counts["proj-counts"]["test_code"] > 0
    assert counts["proj-counts"]["test_docs"] > 0

    qdrant.collections["test_code"] = {}

    caplog.clear()
    with caplog.at_level("INFO"):
        stats = indexer.index_workspace(repo, project="proj-counts")

    assert stats["indexed_files"] >= 1
    assert any(
        "proj-counts" in record.message and "test_code" in record.message
        for record in caplog.records
    )
    assert len(qdrant.collections["test_code"]) > 0


def test_no_record_cache_lists_files_over_two_empty_collections_embeds_every_file(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    import hashlib

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n", encoding="utf-8")

    qdrant = FakeQdrantClient()
    embedder = FakeEmbedder()
    cache_dir = tmp_path / ".cache"
    indexer = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        code_collection="test_code",
        docs_collection="test_docs",
        cache_dir=cache_dir,
    )
    cache_file = cache_dir / CONST_INDEX_CACHE_FILENAME
    cache_dir.mkdir(parents=True, exist_ok=True)
    content_hash = hashlib.sha256((repo / "main.py").read_bytes()).hexdigest()
    cache_file.write_text(json.dumps({"proj-unrecorded:main.py": content_hash}), encoding="utf-8")
    counts_file = getattr(indexer, "counts_file", cache_dir / CONST_INDEX_COUNTS_FILENAME)
    assert not counts_file.exists()

    caplog.clear()
    with caplog.at_level("INFO"):
        stats = indexer.index_workspace(repo, project="proj-unrecorded")

    assert stats["indexed_files"] >= 1
    assert any("proj-unrecorded" in record.message for record in caplog.records)
    assert len(qdrant.collections["test_code"]) > 0


def test_cache_write_raises_halfway_leaves_previous_file_readable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / CONST_INDEX_CACHE_FILENAME
    cache_file.write_text(json.dumps({"proj:existing.py": "hash123"}), encoding="utf-8")

    qdrant = FakeQdrantClient()
    embedder = FakeEmbedder()
    indexer = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        code_collection="test_code",
        docs_collection="test_docs",
        cache_dir=cache_dir,
    )

    def faulty_replace(src: Any, dst: Any) -> None:
        raise OSError("Disk write failed midway")

    monkeypatch.setattr(os, "replace", faulty_replace)

    with pytest.raises(OSError, match="Disk write failed midway"):
        indexer._save_cache({"proj:existing.py": "new_hash", "proj:new.py": "hash456"})

    assert json.loads(cache_file.read_text(encoding="utf-8")) == {"proj:existing.py": "hash123"}


def test_new_collection_gets_both_payload_indexes(tmp_path: Path) -> None:
    qdrant = FakeQdrantClient()
    qdrant.ensure_collection("test_code", vector_size=384)
    indexes = qdrant.payload_schemas.get("test_code", {})
    assert "project_name" in indexes
    assert "file_path" in indexes


def test_existing_collection_missing_payload_indexes_gets_both_on_next_index_run(
    tmp_path: Path,
) -> None:
    qdrant = FakeQdrantClient()
    qdrant.collections["test_code"] = {}
    qdrant.collections["test_docs"] = {}
    qdrant.payload_schemas["test_code"] = {}
    qdrant.payload_schemas["test_docs"] = {}

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n", encoding="utf-8")

    embedder = FakeEmbedder()
    indexer = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        code_collection="test_code",
        docs_collection="test_docs",
        cache_dir=tmp_path / ".cache",
    )
    indexer.index_workspace(repo, project="proj-existing-idx")
    assert "project_name" in qdrant.payload_schemas["test_code"]
    assert "file_path" in qdrant.payload_schemas["test_code"]
    assert "project_name" in qdrant.payload_schemas["test_docs"]
    assert "file_path" in qdrant.payload_schemas["test_docs"]


def test_no_delete_path_sends_unwaited_delete(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    f = repo / "f.py"
    f.write_text("def f(): pass\n", encoding="utf-8")

    qdrant = FakeQdrantClient()
    embedder = FakeEmbedder()
    indexer = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        code_collection="test_code",
        docs_collection="test_docs",
        cache_dir=tmp_path / ".cache",
    )
    indexer.index_workspace(repo, project="proj-waited")
    f.unlink()
    indexer.index_workspace(repo, project="proj-waited")
    indexer.index_workspace(repo, project="proj-waited", force=True)

    assert len(qdrant.delete_calls) > 0
    for call in qdrant.delete_calls:
        assert call.get("wait") is True, f"Found un-waited delete: {call}"


def test_count_that_raises_fails_run_and_reindexes_nothing(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("def main(): pass\n", encoding="utf-8")

    qdrant = FakeQdrantClient()
    embedder = FakeEmbedder()
    indexer = WorkspaceIndexer(
        qdrant=qdrant,
        embedder=embedder,
        code_collection="test_code",
        docs_collection="test_docs",
        cache_dir=tmp_path / ".cache",
    )
    indexer.index_workspace(repo, project="proj-count-fail")

    qdrant.raise_on_count = True
    upserts_before = len(qdrant.upsert_calls)
    with pytest.raises(QdrantClientError):
        indexer.index_workspace(repo, project="proj-count-fail")

    assert len(qdrant.upsert_calls) == upserts_before


def test_qdrant_retry_backoff_recorded_on_clock(clock: ClockFake) -> None:
    attempts = 0

    def fail_three_times(_: Any) -> str:
        nonlocal attempts
        attempts += 1
        if attempts <= 3:
            raise ConnectionResetError("connection reset")
        return "success"

    client = QdrantClient(base_url="http://example.com:6333", client=MagicMock())
    result = client._execute_with_retry(
        fail_three_times,
        operation="test_search",
        target="test_target",
        max_attempts=4,
        sleep=clock.sleep,
    )
    assert result == "success"
    assert clock.waits == [0.5, 1.0, 1.5]
