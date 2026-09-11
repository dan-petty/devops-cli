"""Documentation generation and validation module for devops-cli."""

from __future__ import annotations

from devops_cli.docs.compactor import (
    DocCompactionRequest,
    DocCompactionResult,
    DocCompactor,
)
from devops_cli.docs.generator import (
    CommandDoc,
    CommandGroupDoc,
    DocGenerator,
    MCPToolDoc,
    ParamDoc,
)

__all__ = [
    "DocGenerator",
    "DocCompactor",
    "DocCompactionRequest",
    "DocCompactionResult",
    "CommandDoc",
    "CommandGroupDoc",
    "ParamDoc",
    "MCPToolDoc",
]
