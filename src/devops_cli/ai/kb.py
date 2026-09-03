"""Built-in DevOps CLI Knowledge Base access module for agent grounding and RAG indexing.

Provides programmatic access to the bundled knowledge base articles across:
- it_domains/topics/ (Core architectural guides)
- it_domains/tools/ (Integrated tool references)
- devops_cli/tasks/ (Operational workflow procedures)
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

_KB_DIR = Path(__file__).resolve().parent / "knowledge_base"


def get_knowledge_base_dir() -> Path:
    """Return the absolute path to the bundled knowledge base directory."""
    return _KB_DIR


def list_knowledge_base_articles(category: str | None = None) -> list[Path]:
    """Discover all markdown articles in the bundled knowledge base.

    Args:
        category: Optional subfolder filter ('devops_cli', 'it_domains',
            'devops_cli/tasks', 'it_domains/topics', 'it_domains/tools').
            If None, returns all articles across all divisions.

    Returns:
        Sorted list of Path objects for matching markdown files.
    """
    kb_dir = get_knowledge_base_dir()
    if not kb_dir.is_dir():
        logger.debug("Knowledge base directory not found at %s", kb_dir)
        return []

    kb_resolved = kb_dir.resolve()
    search_dir = (kb_resolved / category).resolve() if category else kb_resolved
    if not search_dir.is_relative_to(kb_resolved) or not search_dir.exists():
        return []

    articles: list[Path] = []
    for p in search_dir.rglob("*.md"):
        if p.is_file() and p.name != "README.md":
            articles.append(p)

    return sorted(articles)


def load_kb_article(relative_path: str) -> str | None:
    """Load the contents of a specific knowledge base markdown article.

    Args:
        relative_path: Relative path within knowledge_base.

    Returns:
        Article text content, or None if the article is not found or path escapes KB root.
    """
    kb_dir = get_knowledge_base_dir()
    kb_resolved = kb_dir.resolve()
    target = (kb_resolved / relative_path).resolve()

    if not target.is_relative_to(kb_resolved) or not target.is_file():
        return None

    try:
        return target.read_text(encoding="utf-8")
    except OSError as exc:
        logger.debug("Failed reading knowledge base article %s: %s", relative_path, exc)
        return None


class KnowledgeBaseStats(BaseModel):
    """Summary statistics of the bundled DevOps CLI knowledge base."""

    model_config = ConfigDict(frozen=True)

    kb_dir: str
    exists: bool
    devops_cli_count: int
    it_domains_count: int
    topics_count: int
    tools_count: int
    tasks_count: int
    total_articles: int


def get_knowledge_base_stats() -> KnowledgeBaseStats:
    """Return summary statistics of the bundled knowledge base."""
    kb_dir = get_knowledge_base_dir()
    devops_cli_articles = list_knowledge_base_articles("devops_cli")
    it_domains_articles = list_knowledge_base_articles("it_domains")
    topics = list_knowledge_base_articles("it_domains/topics")
    tools = list_knowledge_base_articles("it_domains/tools")
    tasks = list_knowledge_base_articles("devops_cli/tasks")

    return KnowledgeBaseStats(
        kb_dir=str(kb_dir),
        exists=kb_dir.is_dir(),
        devops_cli_count=len(devops_cli_articles),
        it_domains_count=len(it_domains_articles),
        topics_count=len(topics),
        tools_count=len(tools),
        tasks_count=len(tasks),
        total_articles=len(devops_cli_articles) + len(it_domains_articles),
    )
