"""Find a requirement that two active changes both rewrite (ADR 0010).

Two active changes that `MODIFY` one requirement both archive, the spec keeps the later text, and
neither `openspec validate` nor `openspec doctor` says so. OpenSpec's bulk-archive conflict
detection is an agent skill, not a command, so a rehearsal cannot call it and this check is ours.
Delete this module when OpenSpec ships a deterministic check for it (the ADR's Revisit
Conditions).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from devops_cli.config.constants import CONST_OPENSPEC_REWRITING_OPERATIONS
from devops_cli.openspec.tool import OpenSpecTool


@dataclass(frozen=True)
class Overlap:
    """A requirement that more than one active change rewrites, and how each does."""

    capability: str
    requirement: str
    # Each (change, operation) pair, sorted.
    rewrites: tuple[tuple[str, str], ...]


def _rewritten_requirement(delta: dict[str, Any]) -> str:
    """The name of the requirement a delta rewrites: the old name of a rename, else its own."""
    renamed = delta["operation"] == "RENAMED"
    return str(delta["rename"]["from"] if renamed else delta["requirement"]["name"])


def _rewrites(tool: OpenSpecTool, root: Path, change: str) -> set[tuple[str, str, str]]:
    """The (capability, requirement, operation) triples `change` rewrites."""
    shown = tool.read_json(["show", change, "--json", "--deltas-only"], root)
    return {
        (delta["spec"], _rewritten_requirement(delta), delta["operation"])
        for delta in shown["deltas"]
        if delta["operation"] in CONST_OPENSPEC_REWRITING_OPERATIONS
    }


def overlapping_requirements(
    tool: OpenSpecTool, root: Path, changes: Iterable[str]
) -> list[Overlap]:
    """Each requirement that more than one of the active `changes` under `root` rewrites."""
    rewriters: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for change in changes:
        for capability, requirement, operation in _rewrites(tool, root, change):
            rewriters[capability, requirement].add((change, operation))
    return [
        Overlap(capability, requirement, tuple(sorted(rewrites)))
        for (capability, requirement), rewrites in sorted(rewriters.items())
        if len({change for change, _ in rewrites}) > 1
    ]
