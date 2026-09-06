"""Unit tests for RAG CLI commands and dry-run mode."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.ai.rag.models import CodeChunk, SearchResult
from devops_cli.commands.rag import app
from devops_cli.main import app as main_app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_rag_index_dry_run(runner: CliRunner, tmp_path: Path) -> None:
    test_file = tmp_path / "main.py"
    test_file.write_text("def hello(): pass", encoding="utf-8")

    result = runner.invoke(main_app, ["--dry-run", "ai", "rag", "index", str(tmp_path)])
    assert result.exit_code == 0
    assert "Would run delegated command: devops ai rag index" in result.output


def test_rag_query_dry_run(runner: CliRunner) -> None:
    result = runner.invoke(main_app, ["--dry-run", "ai", "rag", "query", "how to deploy pods"])
    assert result.exit_code == 0
    assert "Would run delegated command: devops ai rag query" in result.output


def test_rag_status_command(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.ai.rag.qdrant import QdrantClient

    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")
    monkeypatch.setattr(QdrantClient, "is_alive", lambda self: True)
    monkeypatch.setattr(QdrantClient, "list_collections", lambda self: ["devops_code"])
    monkeypatch.setattr(
        QdrantClient,
        "get_collection_info",
        lambda self, name: {"points_count": 42, "config": {"params": {"vectors": {"size": 384}}}},
    )

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "RAG Vector Store Status" in result.output
    assert "devops_code" in result.output
    assert "42" in result.output


def test_rag_clear_command(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.ai.rag.qdrant import QdrantClient

    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")
    monkeypatch.setattr(QdrantClient, "is_alive", lambda self: True)
    deleted: list[str] = []
    monkeypatch.setattr(
        QdrantClient, "delete_collection", lambda self, name: deleted.append(name) or True
    )

    result = runner.invoke(app, ["clear", "--force"])
    assert result.exit_code == 0
    assert "Cleared collection" in result.output
    assert len(deleted) >= 1


def test_rag_index_and_query_execution(runner: CliRunner, tmp_path: Path) -> None:
    """Test full rag index, index-kb, query, and explain subcommands."""
    sample_file = tmp_path / "app.py"
    sample_file.write_text("def run_app(): pass\n", encoding="utf-8")

    mock_qdrant = MagicMock()
    mock_qdrant.is_alive.return_value = True
    mock_qdrant.collection_exists.return_value = True

    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = [0.1] * 384
    mock_embedder.embed_batch.return_value = [[0.1] * 384]

    mock_chunk = SearchResult(
        chunk=CodeChunk(
            id="c1",
            file_path="app.py",
            start_line=1,
            end_line=1,
            content="def run_app(): pass",
            language="python",
            symbol_names=["run_app"],
        ),
        score=0.95,
    )

    mock_retriever = MagicMock()
    mock_retriever.search.return_value = [mock_chunk]

    with (
        patch(
            "devops_cli.commands.rag._get_rag_components",
            return_value=(mock_qdrant, mock_embedder, "devops_code", "devops_docs"),
        ),
        patch(
            "devops_cli.ai.rag.indexer.WorkspaceIndexer.index_workspace",
            return_value={"files_indexed": 1, "chunks_indexed": 2, "pruned_chunks": 0},
        ),
        patch(
            "devops_cli.ai.rag.indexer.WorkspaceIndexer.index_knowledge_base",
            return_value={"indexed_files": 1, "total_chunks": 2},
        ),
        patch("devops_cli.ai.rag.retriever.SemanticRetriever", return_value=mock_retriever),
    ):
        res_idx = runner.invoke(app, ["index", str(tmp_path), "--project", "test_proj"])
        assert res_idx.exit_code == 0

        res_idx_kb = runner.invoke(app, ["index-kb"])
        assert res_idx_kb.exit_code == 0

        res_query = runner.invoke(app, ["query", "run_app", "--top-k", "3"])
        assert res_query.exit_code == 0

        res_query_cat = runner.invoke(app, ["query", "run_app", "--category", "code"])
        assert res_query_cat.exit_code == 0

        res_explain = runner.invoke(app, ["--explain"])
        assert res_explain.exit_code == 0


def test_rag_error_branches(runner: CliRunner, tmp_path: Path) -> None:
    """Verify non-existent path and qdrant down error handling."""
    # 1. Non-existent path
    res_no_path = runner.invoke(app, ["index", str(tmp_path / "nonexistent_dir")])
    assert res_no_path.exit_code == 1

    # 2. Qdrant down
    mock_down_qdrant = MagicMock()
    mock_down_qdrant.is_alive.return_value = False
    mock_down_qdrant.base_url = "http://localhost:6333"

    mock_embed = MagicMock()
    with patch(
        "devops_cli.commands.rag._get_rag_components",
        return_value=(mock_down_qdrant, mock_embed, "code", "docs"),
    ):
        res_idx_down = runner.invoke(app, ["index", str(tmp_path)])
        assert res_idx_down.exit_code == 1

        res_kb_down = runner.invoke(app, ["index-kb"])
        assert res_kb_down.exit_code == 1


def test_rag_index_cmd_handles_canonical_indexer_keys(runner: CliRunner, tmp_path: Path) -> None:
    """Verify index_cmd cleanly handles canonical indexer result keys without KeyError."""
    mock_qdrant = MagicMock()
    mock_qdrant.is_alive.return_value = True
    mock_qdrant.base_url = "http://localhost:6333"
    mock_embedder = MagicMock()
    mock_embedder.model = "test-model"

    canonical_results = {
        "indexed_files": 5,
        "total_chunks": 12,
        "code_chunks": 8,
        "doc_chunks": 4,
        "removed_files": 2,
        "skipped_files": 10,
        "collections": ["code", "docs"],
    }

    with (
        patch(
            "devops_cli.commands.rag._get_rag_components",
            return_value=(mock_qdrant, mock_embedder, "code", "docs"),
        ),
        patch(
            "devops_cli.ai.rag.indexer.WorkspaceIndexer.index_workspace",
            return_value=canonical_results,
        ),
    ):
        res = runner.invoke(app, ["index", str(tmp_path)])
        assert res.exit_code == 0
        assert "Indexed 5 files (12 chunks)" in res.output
        assert "pruned 2 stale chunks" in res.output
