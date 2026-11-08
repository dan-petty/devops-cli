"""The answer of the planner's tool `references` (#3238): every file of the staged commit that holds
a text, with the count of lines in the file and the first of their numbers.

The search is `git grep -n -F` over the whole commit and has no cap for a file, so a count is exact.
The cap is on the files. A rename touches the specs, the tests, the documents and the generated
files as well as the code, so the files that an answer keeps are taken in turn from each of these
groups and not in path order: a long list of one group never hides another. A living spec comes
before the source, the tests and the documents, because it states what the change must update.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Final

from pydantic_ai.messages import ToolReturn

from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_TOOL_MAX_CHARS,
    CONST_ROADMAP_STAGE_REFERENCE_LINES_PER_FILE,
    CONST_ROADMAP_STAGE_REFERENCE_MAX_FILES,
)
from devops_cli.roadmap.agent_run import empty_answer, ok_answer

# `path:line:text` of one match, the path as git prints it. The path ends at the first `:<digits>:`.
_MATCH: Final[re.Pattern[str]] = re.compile(r"(?P<path>.+?):(?P<line>\d+):")
# The groups, in the order that the answer lists them and that the cap takes files from them: a
# living spec first, then the source, the tests, the documents, the change folders and the rest.
_GROUPS: Final[tuple[str, ...]] = ("specs", "source", "tests", "docs", "changes", "other")


def _group_of(path: str) -> str:
    """The group of a file: the specs, the change folders, the tests (fixtures included), the
    documents (generated ones included), the source, or any other file."""
    if path.startswith("openspec/specs/"):
        return "specs"
    if path.startswith("openspec/"):
        return "changes"
    if path.startswith(("tests/", "test/")) or "/tests/" in path:
        return "tests"
    if path.startswith("docs/") or path.endswith((".md", ".rst")):
        return "docs"
    if path.startswith("src/"):
        return "source"
    return "other"


def _file_line(path: str, lines: list[int]) -> str:
    shown = lines[:CONST_ROADMAP_STAGE_REFERENCE_LINES_PER_FILE]
    more = ", ..." if len(lines) > len(shown) else ""
    label = "line" if len(shown) == 1 and not more else "lines"
    return f"{path}: {len(lines)} ({label} {', '.join(str(n) for n in shown)}{more})"


def reference_answer(name: str, output: str, sha: str) -> ToolReturn:
    """The answer for `name` from the output of `git grep -n` on the commit `sha`, or the `empty`
    answer that says no line holds it."""
    found: dict[str, list[int]] = defaultdict(list)
    for raw in output.splitlines():
        match = _MATCH.match(raw.removeprefix(f"{sha}:"))
        if match is not None:
            found[match["path"]].append(int(match["line"]))
    if not found:
        return empty_answer(f"No line of the commit holds {name!r}.")
    grouped: dict[str, list[str]] = {group: [] for group in _GROUPS}
    for path in sorted(found):
        grouped[_group_of(path)].append(path)
    total = sum(len(lines) for lines in found.values())
    header = f"References to {name!r}: files {len(found)}, lines {total}."
    budget = CONST_ROADMAP_REFINE_TOOL_MAX_CHARS - len(header) - 120
    kept: set[str] = set()
    queues = [list(reversed(paths)) for paths in grouped.values()]
    while len(kept) < CONST_ROADMAP_STAGE_REFERENCE_MAX_FILES and any(queues):
        for queue in queues:
            if not queue or len(kept) >= CONST_ROADMAP_STAGE_REFERENCE_MAX_FILES:
                continue
            path = queue[-1]
            budget -= len(_file_line(path, found[path])) + 1
            if budget < 0:
                return ok_answer(_answer(header, grouped, found, kept))
            kept.add(queue.pop())
    return ok_answer(_answer(header, grouped, found, kept))


def reference_files(output: str, sha: str) -> list[str]:
    """The path of each file in the output of `git grep -n` on the commit `sha`, with no cap."""
    found: list[str] = []
    seen: set[str] = set()
    for raw in output.splitlines():
        match = _MATCH.match(raw.removeprefix(f"{sha}:"))
        if match is not None and match["path"] not in seen:
            seen.add(match["path"])
            found.append(match["path"])
    return found


def _answer(
    header: str, grouped: dict[str, list[str]], found: dict[str, list[int]], kept: set[str]
) -> str:
    lines = [header]
    for paths in grouped.values():
        lines += [_file_line(path, found[path]) for path in paths if path in kept]
    left_out = len(found) - len(kept)
    if left_out:
        lines.append(f"Files left out: {left_out}. Ask for a longer name to see them.")
    return "\n".join(lines)
