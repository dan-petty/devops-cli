"""Information foraging and relational epistemic research engine."""

from __future__ import annotations

from devops_cli.ai.research.crawler import ForageCrawler
from devops_cli.ai.research.edges import (
    extract_git_co_changes,
    extract_markdown_links,
    extract_python_imports,
)
from devops_cli.ai.research.marginalia import (
    annotate_file,
    get_marginalia_path,
    read_marginalia,
    write_marginalia,
)
from devops_cli.ai.research.models import (
    BacktrackEvent,
    ForageEdge,
    ForageNode,
    ForageTrail,
    MarginaliaRecord,
    MarginaliaType,
)

__all__ = [
    "BacktrackEvent",
    "ForageCrawler",
    "ForageEdge",
    "ForageNode",
    "ForageTrail",
    "MarginaliaRecord",
    "MarginaliaType",
    "annotate_file",
    "extract_git_co_changes",
    "extract_markdown_links",
    "extract_python_imports",
    "get_marginalia_path",
    "read_marginalia",
    "write_marginalia",
]
