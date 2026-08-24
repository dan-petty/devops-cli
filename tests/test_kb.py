"""Tests for the bundled DevOps CLI Knowledge Base loader and RAG integration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from devops_cli.ai.kb import (
    get_knowledge_base_dir,
    get_knowledge_base_stats,
    list_knowledge_base_articles,
    load_kb_article,
)
from devops_cli.ai.rag.indexer import WorkspaceIndexer


def test_get_knowledge_base_dir() -> None:
    kb_dir = get_knowledge_base_dir()
    assert kb_dir.is_dir()
    assert (kb_dir / "README.md").is_file()
    assert (kb_dir / "topics").is_dir()
    assert (kb_dir / "tools").is_dir()
    assert (kb_dir / "tasks").is_dir()


def test_list_knowledge_base_articles_all() -> None:
    articles = list_knowledge_base_articles()
    assert len(articles) >= 42  # 10 topics + 20 tools + 12 tasks
    assert all(a.suffix == ".md" for a in articles)
    assert all(a.name != "README.md" for a in articles)


def test_list_knowledge_base_articles_by_category() -> None:
    topics = list_knowledge_base_articles("topics")
    tools = list_knowledge_base_articles("tools")
    tasks = list_knowledge_base_articles("tasks")

    assert len(topics) == 10
    assert len(tools) == 20
    assert len(tasks) == 12


def test_load_kb_article_success() -> None:
    content = load_kb_article("topics/agentic_ai_and_code_reviews.md")
    assert content is not None
    assert "Agentic AI" in content
    assert "Multi-Persona" in content


def test_load_kb_article_missing_or_invalid() -> None:
    assert load_kb_article("nonexistent/article.md") is None
    # Path traversal protection
    assert load_kb_article("../../outside.md") is None


def test_get_knowledge_base_stats() -> None:
    stats = get_knowledge_base_stats()
    assert stats["exists"] is True
    assert stats["topics_count"] == 10
    assert stats["tools_count"] == 20
    assert stats["tasks_count"] == 12
    assert stats["total_articles"] == 42


def test_workspace_indexer_index_knowledge_base(tmp_path: Path) -> None:
    mock_qdrant = MagicMock()
    mock_qdrant.search_points.return_value = []
    mock_embedder = MagicMock()
    mock_embedder.embed_query.return_value = [0.1] * 768
    mock_embedder.embed_batch.return_value = [[0.1] * 768]

    indexer = WorkspaceIndexer(
        qdrant=mock_qdrant,
        embedder=mock_embedder,
        code_collection="test_code",
        docs_collection="test_docs",
        cache_dir=tmp_path,
    )

    results = indexer.index_knowledge_base(force=True)
    assert results["indexed_files"] >= 40
    assert results["total_chunks"] > 0
    assert "test_docs" in results["collections"]
