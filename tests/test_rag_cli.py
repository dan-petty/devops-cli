"""Unit tests for RAG CLI commands and dry-run mode."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

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

    monkeypatch.setattr(QdrantClient, "is_alive", lambda self: True)
    deleted: list[str] = []
    monkeypatch.setattr(
        QdrantClient, "delete_collection", lambda self, name: deleted.append(name) or True
    )

    result = runner.invoke(app, ["clear", "--force"])
    assert result.exit_code == 0
    assert "Cleared collection" in result.output
    assert len(deleted) >= 1
