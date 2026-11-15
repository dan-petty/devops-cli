"""The strategy of each attempt of an implement step (#3569).

A repair round sent the same inputs again with the text of the failure, so a second failure of the
same kind repeated the strategy that failed. Each attempt now tries something that an earlier
attempt did not: the first runs as planned, the second adds the repository map of the files that
the failure names, and the third and each later attempt run on the next healthy tier of the
ladder. An attempt that follows a failure which selects `change_tier` runs on another tier, so its
strategy is `tier` too.
"""

from __future__ import annotations

import os
import re
from enum import StrEnum
from pathlib import Path
from typing import Final

from devops_cli.ai.repomap import FileMapNode, parse_file_symbols
from devops_cli.config.constants import CONST_ROADMAP_STAGE_MAP_MAX_FILES
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.step_files import TaskGroup, named_files

__all__ = ["AttemptStrategy", "repo_map_section", "strategy_for"]

# A word of a reason that ends in a location such as `:12` or `:1:8` names the file before that
# location, as `tests/test_sample.py:1:8` does (#3569).
_LOCATION: Final[re.Pattern[str]] = re.compile(r"(?::\d+(?:-\d+)?)+$")


class AttemptStrategy(StrEnum):
    """What an attempt of a step tries that the earlier attempts did not."""

    PLANNED = "planned"
    REPO_MAP = "repo_map"
    TIER = "tier"


def strategy_for(number: int, moves_tier: bool = False) -> AttemptStrategy:
    """The strategy of attempt `number`: the planned run first, the repository map on the second,
    and the next tier on the third and each later one. `moves_tier` says that the failure of the
    attempt before selected `change_tier`, so this attempt runs on another tier."""
    if moves_tier or number >= 3:
        return AttemptStrategy.TIER
    if number == 2:
        return AttemptStrategy.REPO_MAP
    return AttemptStrategy.PLANNED


def repo_map_section(source: Path, reason: str, group: TaskGroup) -> str:
    """The `# Repository map` section of the second attempt (#3569): one line for each file that
    `reason` names and each file that `group` names, in the form of the `repo_map` tool, at most
    `CONST_ROADMAP_STAGE_MAP_MAX_FILES` files. Empty when no such file holds a symbol."""
    lines = [_map_line(node) for node in _map_nodes(source, reason, group) if node.symbols]
    if not lines:
        return ""
    texts = MESSAGES.roadmap
    return texts.implement_map_heading.format(note=texts.implement_map_note, lines="\n".join(lines))


def _map_nodes(source: Path, reason: str, group: TaskGroup) -> list[FileMapNode]:
    """The parsed files of the map, sorted by path: each file that a word of `reason` names and
    each file that `group` names, at most `CONST_ROADMAP_STAGE_MAP_MAX_FILES` of them."""
    root = source.resolve()
    named = [path for word in reason.split() if (path := _reason_file(root, word))]
    files = sorted({*named, *named_files(root, group)})
    nodes = (parse_file_symbols(path, root) for path in files[:CONST_ROADMAP_STAGE_MAP_MAX_FILES])
    return [node for node in nodes if node is not None]


def _reason_file(root: Path, word: str) -> Path | None:
    """The file of the checkout at `root` that `word` of a reason names, or None: a word with no
    folder, a word outside the checkout and a word that names no file are no file."""
    path = _LOCATION.sub("", word)
    if "/" not in path or path.startswith("/"):
        return None
    found = Path(os.path.normpath(root / path))
    return found if found.is_relative_to(root) and os.path.isfile(found) else None


def _map_line(node: FileMapNode) -> str:
    """One line of the map: the path and the names of the top-level symbols, as the `repo_map`
    tool of the stage planner renders it."""
    return f"{node.path}: {', '.join(symbol.name for symbol in node.symbols)}"
