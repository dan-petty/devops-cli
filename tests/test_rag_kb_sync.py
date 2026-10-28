"""Unit tests for knowledge base re-indexing, Qdrant drift detection, and status metadata.

Verifies:
1. KB points carry installed KB digest, embedding_model, and indexed_at.
2. KB is lazily rebuilt on first RAG use if empty or digest differs.
3. 30-minute cooldown and single warning on rebuild failure.
4. RAG drift compares Qdrant per-project points and KB digest (detects wiped collection).
5. RAG status displays points, embedding model, dimension, KB digest, and index time.
6. devops_cli_rag_points gauge is emitted on use (#974).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.kb import knowledge_base_digest
from devops_cli.ai.rag.drift import RAGDriftDetector
from devops_cli.ai.rag.indexer import WorkspaceIndexer
from devops_cli.ai.rag.kb_sync import (
    ensure_knowledge_base_ready,
    is_kb_rebuild_needed,
    reset_kb_sync_state,
)
from devops_cli.commands.rag import app
from devops_cli.config.constants import CONST_RAG_KB_PROJECT
from devops_cli.telemetry.instruments import RAG_POINTS

pytestmark = pytest.mark.usefixtures("keyring_store")


class InMemoryQdrantClient:
    """In-memory Qdrant fake supporting count, scroll, get_collection_info, and upsert."""

    def __init__(self) -> None:
        self.api_key: str | None = None
        self.base_url: str = "http://example.com:6333"
        self.collections: dict[str, list[dict[str, Any]]] = {
            "devops_code": [],
            "devops_docs": [],
        }

    def is_alive(self) -> bool:
        return True

    def ensure_collection(self, name: str, vector_size: int, distance: str = "Cosine") -> bool:
        if name not in self.collections:
            self.collections[name] = []
        return True

    def get_collection_info(self, name: str) -> dict[str, Any]:
        pts = self.collections.get(name, [])
        return {
            "points_count": len(pts),
            "config": {"params": {"vectors": {"size": 384}}},
            "status": "green",
        }

    def count_points(self, name: str, filter_payload: dict[str, Any] | None = None) -> int:
        pts = self.collections.get(name, [])
        if not filter_payload:
            return len(pts)
        return sum(
            1
            for p in pts
            if all(p.get("payload", {}).get(k) == v for k, v in filter_payload.items())
        )

    def scroll_points(
        self,
        name: str,
        filter_payload: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        pts = self.collections.get(name, [])
        if filter_payload:
            pts = [
                p
                for p in pts
                if all(p.get("payload", {}).get(k) == v for k, v in filter_payload.items())
            ]
        return pts[:limit]

    def upsert_points(
        self, name: str, points: list[dict[str, Any]], *, batch_size: int = 64
    ) -> int:
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
        wait: bool = True,
    ) -> bool:
        if name in self.collections:
            path_set = set(file_paths)
            self.collections[name] = [
                p
                for p in self.collections[name]
                if not (
                    p.get("payload", {}).get("file_path") in path_set
                    and (
                        project_name is None
                        or p.get("payload", {}).get("project_name") == project_name
                    )
                )
            ]
        return True

    def delete_points_by_project(
        self,
        name: str,
        project_name: str,
        *,
        wait: bool = True,
    ) -> bool:
        if name in self.collections:
            self.collections[name] = [
                p
                for p in self.collections[name]
                if p.get("payload", {}).get("project_name") != project_name
            ]
        return True


class DummyEmbedder:
    """Mock embedder providing deterministic unit vectors."""

    model: str = "test-embed-model"

    def embed(self, text: str) -> list[float]:
        return [0.1] * 384

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.1] * 384


@pytest.fixture(autouse=True)
def clean_kb_sync_state() -> None:
    reset_kb_sync_state()


def test_knowledge_base_digest_is_deterministic(tmp_path: Path) -> None:
    """Digest over KB directory must be deterministic and change when file content changes."""
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    (kb_dir / "file_b.md").write_text("content B\n", encoding="utf-8")
    (kb_dir / "file_a.md").write_text("content A\n", encoding="utf-8")

    digest1 = knowledge_base_digest(kb_dir)
    digest2 = knowledge_base_digest(kb_dir)
    assert digest1 == digest2
    assert len(digest1) == 64

    (kb_dir / "file_a.md").write_text("content A modified\n", encoding="utf-8")
    digest3 = knowledge_base_digest(kb_dir)
    assert digest1 != digest3


def test_chunk_point_records_metadata(tmp_path: Path) -> None:
    """KB chunk points must record embedding_model, kb_digest, and indexed_at."""
    qdrant = InMemoryQdrantClient()
    embedder = DummyEmbedder()
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, qdrant), embedder=cast(Any, embedder), cache_dir=tmp_path / "cache"
    )

    kb_file = tmp_path / "kb_sample.md"
    kb_file.write_text("# Sample KB Article\nDevops instructions.\n", encoding="utf-8")

    stats = indexer.index_workspace(
        tmp_path,
        project=CONST_RAG_KB_PROJECT,
        force=True,
    )
    assert stats["total_chunks"] > 0

    points = qdrant.collections["devops_docs"]
    assert len(points) > 0
    payload = points[0]["payload"]
    assert (
        payload.get("project_name"),
        payload.get("embedding_model"),
        bool(payload.get("kb_digest")),
        bool(payload.get("indexed_at")),
    ) == (CONST_RAG_KB_PROJECT, "test-embed-model", True, True)


def test_is_kb_rebuild_needed_empty_and_mismatch() -> None:
    """Verify is_kb_rebuild_needed returns True when empty or when digest differs."""
    qdrant = InMemoryQdrantClient()
    installed_digest = "abc1234567890def"

    # Empty collection -> needs rebuild
    assert is_kb_rebuild_needed(qdrant, "devops_docs", installed_digest) is True

    # Matching digest -> no rebuild needed
    qdrant.upsert_points(
        "devops_docs",
        [
            {
                "id": "1",
                "vector": [0.1] * 384,
                "payload": {
                    "project_name": CONST_RAG_KB_PROJECT,
                    "kb_digest": installed_digest,
                },
            }
        ],
    )
    assert is_kb_rebuild_needed(qdrant, "devops_docs", installed_digest) is False

    # Differing digest -> needs rebuild
    assert is_kb_rebuild_needed(qdrant, "devops_docs", "different_digest_999") is True


def test_ensure_knowledge_base_ready_rebuilds_and_emits_telemetry(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify ensure_knowledge_base_ready prints progress and emits devops_cli_rag_points."""
    qdrant = InMemoryQdrantClient()
    embedder = DummyEmbedder()
    emitted: list[tuple[str, float, dict[str, Any] | None]] = []

    def mock_emit(instrument: Any, value: float, attrs: dict[str, Any] | None = None) -> None:
        emitted.append((instrument.name, value, attrs))

    with (
        patch("devops_cli.ai.rag.kb_sync.emit", side_effect=mock_emit),
        patch("devops_cli.ai.rag.indexer.WorkspaceIndexer.index_knowledge_base") as mock_idx,
    ):
        mock_idx.return_value = {"indexed_files": 5, "total_chunks": 10}
        success = ensure_knowledge_base_ready(
            qdrant, embedder, "devops_docs", code_collection="devops_code"
        )
        assert success is True
        mock_idx.assert_called_once()

    captured = capsys.readouterr()
    assert "Rebuilding knowledge base index..." in captured.out
    assert any(
        item[0] == RAG_POINTS.name and item[2] == {"collection": "devops_docs"} for item in emitted
    )
    assert any(
        item[0] == RAG_POINTS.name and item[2] == {"collection": "devops_code"} for item in emitted
    )


def test_ensure_knowledge_base_ready_cooldown_and_single_warning(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failure triggers a 30m cooldown and emits at most one warning."""
    qdrant = InMemoryQdrantClient()
    embedder = DummyEmbedder()

    with patch(
        "devops_cli.ai.rag.indexer.WorkspaceIndexer.index_knowledge_base",
        side_effect=RuntimeError("Qdrant explosion"),
    ):
        first = ensure_knowledge_base_ready(qdrant, embedder, "devops_docs")
        second = ensure_knowledge_base_ready(qdrant, embedder, "devops_docs")
        assert (first, second) == (False, False)

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    # Exactly one warning emitted despite two calls
    assert combined.count("Failed rebuilding knowledge base index: Qdrant explosion") == 1


def test_rag_drift_detects_wiped_qdrant_collection_with_intact_cache(tmp_path: Path) -> None:
    """Verify that rag drift flags files as stale when Qdrant points are wiped under an intact cache."""
    cache_dir = tmp_path / ".cache"
    cache_dir.mkdir()
    code_file = tmp_path / "app.py"
    code_file.write_text("print('test')\n", encoding="utf-8")

    qdrant = InMemoryQdrantClient()
    embedder = DummyEmbedder()
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, qdrant), embedder=cast(Any, embedder), cache_dir=cache_dir
    )

    # 1. Initial indexing
    indexer.index_workspace(tmp_path)
    assert len(qdrant.collections["devops_code"]) > 0

    # Clean drift
    detector = RAGDriftDetector(root_dir=tmp_path, indexer=indexer, cache_dir=cache_dir)
    clean_report = detector.detect_drift()
    assert (clean_report.drift_score, clean_report.stale_files) == (0.0, [])

    # 2. Simulate wiped Qdrant collection while cache file remains on disk
    qdrant.collections["devops_code"].clear()
    qdrant.collections["devops_docs"].clear()

    wiped_report = detector.detect_drift()
    assert (wiped_report.drift_score > 0.0, "app.py" in wiped_report.stale_files) == (True, True)


def test_rag_drift_detects_kb_digest_drift(tmp_path: Path) -> None:
    """Verify that rag drift flags kb_drift when recorded digest differs from installed digest."""
    qdrant = InMemoryQdrantClient()
    qdrant.upsert_points(
        "devops_docs",
        [
            {
                "id": "1",
                "vector": [0.1] * 384,
                "payload": {
                    "project_name": CONST_RAG_KB_PROJECT,
                    "kb_digest": "outdated_digest_123",
                },
            }
        ],
    )
    indexer = WorkspaceIndexer(
        qdrant=cast(Any, qdrant), embedder=cast(Any, DummyEmbedder()), cache_dir=tmp_path / "cache"
    )
    detector = RAGDriftDetector(root_dir=tmp_path, indexer=indexer, cache_dir=tmp_path / "cache")

    with patch("devops_cli.ai.rag.drift.knowledge_base_digest", return_value="latest_digest_999"):
        report = detector.detect_drift()
        assert (
            report.kb_drift,
            report.installed_kb_digest,
            report.recorded_kb_digest,
        ) == (True, "latest_digest_999", "outdated_digest_123")


def test_rag_status_table_displays_collection_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify rag status displays points, embedding model, dimension, KB digest, and last index time."""
    runner = CliRunner()
    from devops_cli.ai.rag.qdrant import QdrantClient

    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")
    monkeypatch.setattr(QdrantClient, "is_alive", lambda self: True)
    monkeypatch.setattr(QdrantClient, "list_collections", lambda self: ["devops_docs"])
    monkeypatch.setattr(
        QdrantClient,
        "get_collection_info",
        lambda self, name: {"points_count": 100, "config": {"params": {"vectors": {"size": 384}}}},
    )
    monkeypatch.setattr(
        QdrantClient,
        "scroll_points",
        lambda self, name, filter_payload=None, limit=10: [
            {
                "id": "1",
                "payload": {
                    "embedding_model": "bge-small-en-v1.5",
                    "indexed_at": "2026-10-11T12:00:00Z",
                    "kb_digest": "abcdef0123456789fedcba9876543210",
                    "project_name": CONST_RAG_KB_PROJECT,
                },
            }
        ],
    )

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    output = result.output
    assert "devops_docs" in output
    assert "100" in output
    assert "bge-small-en-v1.5" in output
    assert "384" in output
    assert "abcdef0123456789" in output
    assert "2026-10-11 12:00:00" in output
