"""Tests for the bundled DevOps CLI Knowledge Base loader and RAG integration."""

from __future__ import annotations

import ast
import importlib
import importlib.util
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import tree_sitter
import tree_sitter_markdown

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


def _child(node: Any, kind: str) -> Any | None:
    """The first child of a tree-sitter node that has the given type."""
    return next((child for child in node.children if child.type == kind), None)


def _python_fences(article: Path) -> list[tuple[int, str]]:
    """Each Python fence in a Markdown article, as the line its code starts on and the code."""
    parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_markdown.language()))
    fences: list[tuple[int, str]] = []
    stack = [parser.parse(article.read_bytes()).root_node]
    while stack:
        node = stack.pop()
        stack.extend(node.children)
        info = _child(node, "info_string") if node.type == "fenced_code_block" else None
        language = _child(info, "language") if info is not None else None
        content = _child(node, "code_fence_content")
        if language is None or language.text != b"python" or content is None:
            continue
        # A fence in a list item keeps the item's indent on every line but its first.
        indent = " " * content.start_point.column
        fences.append(
            (content.start_point.row + 1, textwrap.dedent(indent + content.text.decode()))
        )
    return fences


def _resolves(dotted: str) -> bool:
    """Whether `a.b.c` is an attribute of the module `a.b`, or a module itself."""
    module_name, _, attribute = dotted.rpartition(".")
    try:
        if module_name and hasattr(importlib.import_module(module_name), attribute):
            return True
        return importlib.util.find_spec(dotted) is not None
    except ImportError:
        return False


def _devops_cli_imports(node: ast.AST) -> list[str]:
    """The dotted devops_cli names an import statement brings in."""
    if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "devops_cli":
        return [f"{node.module}.{alias.name}" for alias in node.names]
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names if alias.name.split(".")[0] == "devops_cli"]
    return []


def _unresolved_imports(code: str) -> list[tuple[int, str]]:
    """Each devops_cli name the code imports that does not exist, with its line in the code."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [(exc.lineno or 1, f"does not parse: {exc.msg}")]
    return [
        (node.lineno, name)
        for node in ast.walk(tree)
        for name in _devops_cli_imports(node)
        if not _resolves(name)
    ]


def test_kb_python_examples_import_real_symbols() -> None:
    """Every name a knowledge-base Python example imports from devops_cli exists. `devops ai chat`
    and the harness retrieve these examples, and `from devops_cli.commands.k8s import pods`
    taught agents an import that fails (#956)."""
    kb_dir = get_knowledge_base_dir()
    missing = [
        f"{article.relative_to(kb_dir)}:{start + line - 1}: {name}"
        for article in sorted(kb_dir.rglob("*.md"))
        if "devops_cli" in article.read_text(encoding="utf-8")
        for start, code in _python_fences(article)
        for line, name in _unresolved_imports(code)
    ]

    assert missing == []
