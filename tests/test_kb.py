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
    assert (kb_dir / "devops_cli").is_dir()
    assert (kb_dir / "devops_cli" / "tasks").is_dir()
    assert (kb_dir / "it_domains").is_dir()
    assert (kb_dir / "it_domains" / "topics").is_dir()
    assert (kb_dir / "it_domains" / "tools").is_dir()


def test_list_knowledge_base_articles_all() -> None:
    articles = list_knowledge_base_articles()
    # 40 devops_cli (4 core + 13 tasks + 23 libraries) + 40 it_domains (11 topics + 29 tools)
    assert len(articles) == 80
    assert all(a.suffix == ".md" for a in articles)
    assert all(a.name != "README.md" for a in articles)
    assert any(a.name == "valkey.md" for a in articles)


def test_list_knowledge_base_articles_by_division() -> None:
    devops_cli_articles = list_knowledge_base_articles("devops_cli")
    it_domains_articles = list_knowledge_base_articles("it_domains")

    assert len(devops_cli_articles) == 40  # 4 core + 13 tasks + 23 libraries
    assert len(it_domains_articles) == 40  # 11 topics + 29 tools


def test_list_knowledge_base_articles_by_category() -> None:
    # Test canonical subcategory paths
    topics = list_knowledge_base_articles("it_domains/topics")
    assert len(topics) == 11

    tools = list_knowledge_base_articles("it_domains/tools")
    assert len(tools) == 29

    tasks = list_knowledge_base_articles("devops_cli/tasks")
    assert len(tasks) == 13

    libraries = list_knowledge_base_articles("devops_cli/libraries")
    assert len(libraries) == 23


def test_load_kb_article_success() -> None:
    # Test loading via division path
    content_new = load_kb_article("it_domains/topics/agentic_ai_and_code_reviews.md")
    assert content_new is not None
    assert "Agentic AI" in content_new

    # Test loading devops_cli core article
    arch_content = load_kb_article("devops_cli/architecture.md")
    assert arch_content is not None
    assert "DevOps CLI Architecture" in arch_content

    # Test loading python_packages article
    pkg_content = load_kb_article("devops_cli/python_packages.md")
    assert pkg_content is not None
    assert "Python Packages & Code Libraries Reference Manual" in pkg_content

    # Test loading a dedicated library article
    typer_content = load_kb_article("devops_cli/libraries/typer.md")
    assert typer_content is not None
    assert "Typer & Click" in typer_content

    # Test loading Valkey tool manual
    valkey_content = load_kb_article("it_domains/tools/valkey.md")
    assert valkey_content is not None
    assert "Valkey" in valkey_content


def test_load_kb_article_missing_or_invalid() -> None:
    assert load_kb_article("nonexistent/article.md") is None
    # Path traversal protection
    assert load_kb_article("../../outside.md") is None


def test_get_knowledge_base_stats() -> None:
    stats = get_knowledge_base_stats()
    assert stats.exists is True
    assert stats.devops_cli_count == 40
    assert stats.it_domains_count == 40
    assert stats.topics_count == 11
    assert stats.tools_count == 29
    assert stats.tasks_count == 13
    assert stats.total_articles == 80


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


def test_kb_missing_directory_and_invalid_category(tmp_path: Path, monkeypatch) -> None:
    """Verify list_knowledge_base_articles and stats when directory is missing."""
    import devops_cli.ai.kb as kb_mod

    # Non-existent category
    assert list_knowledge_base_articles("nonexistent_category") == []

    # Missing directory
    monkeypatch.setattr(kb_mod, "_KB_DIR", tmp_path / "nonexistent_kb")
    assert list_knowledge_base_articles() == []
    assert load_kb_article("any.md") is None
    stats = get_knowledge_base_stats()
    assert stats.exists is False
    assert stats.total_articles == 0
