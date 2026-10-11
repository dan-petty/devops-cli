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
    ClarifyingQuestion,
    CodeLookupInstruction,
    ForageEdge,
    ForageNode,
    ForageTrail,
    KnowledgeGap,
    KnowledgeGapType,
    MarginaliaRecord,
    MarginaliaType,
    SocraticInquiryResult,
)
from devops_cli.ai.research.socratic import (
    SocraticFormulator,
    render_socratic_markdown,
)

__all__ = [
    "BacktrackEvent",
    "ClarifyingQuestion",
    "CodeLookupInstruction",
    "ForageCrawler",
    "ForageEdge",
    "ForageNode",
    "ForageTrail",
    "KnowledgeGap",
    "KnowledgeGapType",
    "MarginaliaRecord",
    "MarginaliaType",
    "SocraticFormulator",
    "SocraticInquiryResult",
    "annotate_file",
    "extract_git_co_changes",
    "extract_markdown_links",
    "extract_python_imports",
    "get_marginalia_path",
    "read_marginalia",
    "render_socratic_markdown",
    "write_marginalia",
]
