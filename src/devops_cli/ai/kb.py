"""Built-in DevOps CLI Knowledge Base access module for agent grounding and RAG indexing.

Provides programmatic access to the 43 bundled knowledge base articles across:
- topics/ (Core architectural guides)
- tools/ (Integrated tool references)
- tasks/ (Operational workflow procedures)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_KB_DIR = Path(__file__).resolve().parent / "knowledge_base"


def get_knowledge_base_dir() -> Path:
    """Return the absolute path to the bundled knowledge base directory."""
    return _KB_DIR


def list_knowledge_base_articles(category: str | None = None) -> list[Path]:
    """Discover all markdown articles in the bundled knowledge base.

    Args:
        category: Optional filter ('topics', 'tools', 'tasks'). If None, returns all articles.

    Returns:
        Sorted list of Path objects for matching markdown files.
    """
    kb_dir = get_knowledge_base_dir()
    if not kb_dir.is_dir():
        logger.debug("Knowledge base directory not found at %s", kb_dir)
        return []

    search_dir = kb_dir / category if category else kb_dir
    if not search_dir.exists():
        return []

    articles: list[Path] = []
    for p in search_dir.rglob("*.md"):
        if p.is_file() and p.name != "README.md":
            articles.append(p)

    return sorted(articles)


def load_kb_article(relative_path: str) -> str | None:
    """Load the contents of a specific knowledge base markdown article.

    Args:
        relative_path: Relative path within knowledge_base
            (e.g. 'topics/agentic_ai_and_code_reviews.md')

    Returns:
        Article text content, or None if the article is not found or path escapes KB root.
    """
    kb_dir = get_knowledge_base_dir()
    target = (kb_dir / relative_path).resolve()
    if not target.is_relative_to(kb_dir) or not target.is_file():
        return None

    try:
        return target.read_text(encoding="utf-8")
    except OSError as exc:
        logger.debug("Failed reading knowledge base article %s: %s", relative_path, exc)
        return None


def get_knowledge_base_stats() -> dict[str, Any]:
    """Return summary statistics of the bundled knowledge base."""
    kb_dir = get_knowledge_base_dir()
    topics = list_knowledge_base_articles("topics")
    tools = list_knowledge_base_articles("tools")
    tasks = list_knowledge_base_articles("tasks")

    return {
        "kb_dir": str(kb_dir),
        "exists": kb_dir.is_dir(),
        "topics_count": len(topics),
        "tools_count": len(tools),
        "tasks_count": len(tasks),
        "total_articles": len(topics) + len(tools) + len(tasks),
    }
