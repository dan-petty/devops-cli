"""Find a requirement that two active changes both rewrite (ADR 0010).

Two active changes that `MODIFY` one requirement both archive, the spec keeps the later text, and
neither `openspec validate` nor `openspec doctor` says so. OpenSpec's bulk-archive conflict
detection is an agent skill, not a command, so the gate cannot call it and this check is ours.
Delete this module when OpenSpec ships a deterministic check for it (the ADR's Revisit
Conditions).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
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


def show_args(change: str) -> tuple[str, ...]:
    """The arguments of the run that gives the deltas of `change`."""
    return ("show", change, "--json", "--deltas-only")


def _delta_rewrites(delta: Mapping[str, Any]) -> tuple[str, str, str] | None:
    """The (capability, requirement, operation) triple if `delta` rewrites a requirement."""
    if delta["operation"] not in CONST_OPENSPEC_REWRITING_OPERATIONS:
        return None
    return (delta["spec"], _rewritten_requirement(dict(delta)), delta["operation"])


def change_deltas(
    tool: OpenSpecTool, root: Path, changes: Iterable[str]
) -> dict[str, list[dict[str, Any]]]:
    """Read `openspec show --json --deltas-only` deltas once per active change (#5378)."""
    return {change: list(tool.read_json(show_args(change), root)["deltas"]) for change in changes}


def overlapping_deltas(
    deltas_by_change: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[Overlap]:
    """Each requirement that more than one change in `deltas_by_change` rewrites."""
    rewriters: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for change, deltas in deltas_by_change.items():
        for delta in deltas:
            rewrite = _delta_rewrites(delta)
            if rewrite is None:
                continue
            capability, requirement, operation = rewrite
            rewriters[capability, requirement].add((change, operation))
    return [
        Overlap(capability, requirement, tuple(sorted(rewrites)))
        for (capability, requirement), rewrites in sorted(rewriters.items())
        if len({change for change, _ in rewrites}) > 1
    ]


def overlapping_requirements(
    tool: OpenSpecTool, root: Path, changes: Iterable[str]
) -> list[Overlap]:
    """Each requirement that more than one of the active `changes` under `root` rewrites."""
    return overlapping_deltas(change_deltas(tool, root, changes))
