"""Scan for references to entities that an OpenSpec plan removes (#3324).

When a plan proposes removing a public entity (command, tool, constant or model),
existing tests and source files often reference that symbol. The stage job scans
`tests/` and `src/` for each removed name before opening a draft pull request.
Unhandled test references stop staging with `RoadmapStageError`. Unhandled source
references produce warnings in the staged issue comment.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

# Removal verbs governing direct object identifiers in proposals and designs.
REMOVAL_VERBS: Final[tuple[str, ...]] = (
    "remove",
    "removes",
    "removed",
    "removing",
    "delete",
    "deletes",
    "deleted",
    "deleting",
    "deprecate",
    "deprecates",
    "deprecated",
    "deprecating",
    "drop",
    "drops",
    "dropped",
    "dropping",
    "retire",
    "retires",
    "retired",
    "retiring",
)

_VERB_GROUP = "|".join(REMOVAL_VERBS)
_ACTIVE_RE = re.compile(rf"\b({_VERB_GROUP})\b", re.IGNORECASE)
_PREP_OR_END_RE = re.compile(r"\b(from|in|of)\b|[;!?\n]", re.IGNORECASE)
_CODE_SPAN_RE = re.compile(r"`([^`]+)`")

_PASSIVE_RE = re.compile(
    rf"`([^`]+)`\s+(?:is|are|was|were|has\s+been|have\s+been)\s+(?:{_VERB_GROUP})\b",
    re.IGNORECASE,
)

_IGNORE_DIRS: Final[frozenset[str]] = frozenset(
    {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "node_modules",
        ".data",
    }
)


def find_removed_names(text: str) -> set[str]:
    """Return each backticked identifier that a removal verb governs in `text`.

    Prepositional phrases (such as `from ...`) specify containers and are excluded.
    """
    removed: set[str] = set()

    for match in _PASSIVE_RE.finditer(text):
        span = match.group(1).strip()
        if span.isidentifier():
            removed.add(span)

    for line in text.splitlines():
        for verb_match in _ACTIVE_RE.finditer(line):
            subtext = line[verb_match.end() :]
            prep_match = _PREP_OR_END_RE.search(subtext)
            governed_text = subtext[: prep_match.start()] if prep_match else subtext
            for span in _CODE_SPAN_RE.findall(governed_text):
                ident = span.strip()
                if ident.isidentifier():
                    removed.add(ident)

    return removed


def is_accounted_for(path: str, tasks_content: str) -> bool:
    """Return True if `tasks_content` names `path`."""
    pattern = rf"(?:^|[^\w./-]){re.escape(path)}(?:[^\w./-]|$)"
    return re.search(pattern, tasks_content) is not None


@dataclass(frozen=True)
class RemovalScanResult:
    """Findings from scanning references to removed names."""

    unhandled_tests: dict[str, list[str]] = field(default_factory=dict)
    unhandled_sources: dict[str, list[str]] = field(default_factory=dict)

    @property
    def has_test_failures(self) -> bool:
        return any(self.unhandled_tests.values())

    @property
    def has_source_warnings(self) -> bool:
        return any(self.unhandled_sources.values())


def _read_change_contents(
    change_folder: Path | Mapping[str, str],
) -> tuple[str, str]:
    """Return (proposal_and_design_text, tasks_text) from a directory or files mapping."""
    if isinstance(change_folder, Path):
        texts: list[str] = []
        for filename in ("proposal.md", "design.md"):
            doc_path = change_folder / filename
            if doc_path.is_file():
                texts.append(doc_path.read_text(encoding="utf-8"))
        proposal_and_design = "\n\n".join(texts)
        tasks_path = change_folder / "tasks.md"
        tasks_text = tasks_path.read_text(encoding="utf-8") if tasks_path.is_file() else ""
        return proposal_and_design, tasks_text

    proposal_design_texts: list[str] = []
    tasks_content = ""
    for rel_path, content in change_folder.items():
        if rel_path.endswith(("/proposal.md", "/design.md")) or rel_path in (
            "proposal.md",
            "design.md",
        ):
            proposal_design_texts.append(content)
        elif rel_path.endswith("/tasks.md") or rel_path == "tasks.md":
            tasks_content = content
    return "\n\n".join(proposal_design_texts), tasks_content


def _candidate_files(repo_root: Path) -> Iterator[Path]:
    for rel in ("tests", "test", "src"):
        d = repo_root / rel
        if not d.is_dir():
            continue
        for file_path in d.rglob("*"):
            if not file_path.is_file():
                continue
            if any(part in _IGNORE_DIRS for part in file_path.parts):
                continue
            yield file_path


def _record_references(
    content: str,
    rel_path: str,
    name_patterns: Mapping[str, re.Pattern[str]],
    tasks_text: str,
    unhandled_tests: dict[str, list[str]],
    unhandled_sources: dict[str, list[str]],
) -> None:
    is_test = rel_path.startswith(("tests/", "test/")) or "/tests/" in rel_path
    for name, pattern in name_patterns.items():
        if not pattern.search(content):
            continue
        if is_accounted_for(rel_path, tasks_text):
            continue
        if is_test:
            unhandled_tests[name].append(rel_path)
        elif rel_path.startswith("src/"):
            unhandled_sources[name].append(rel_path)


def scan_removal_references(
    repo_root: Path,
    change_folder: Path | Mapping[str, str],
) -> RemovalScanResult:
    """Scan `tests/` and `src/` under `repo_root` for references to entities removed by `change_folder`."""
    plan_text, tasks_text = _read_change_contents(change_folder)
    removed_names = find_removed_names(plan_text)
    if not removed_names:
        return RemovalScanResult()

    unhandled_tests: dict[str, list[str]] = defaultdict(list)
    unhandled_sources: dict[str, list[str]] = defaultdict(list)
    name_patterns = {name: re.compile(rf"\b{re.escape(name)}\b") for name in removed_names}

    for file_path in _candidate_files(repo_root):
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError, OSError:
            continue
        rel_path = file_path.relative_to(repo_root).as_posix()
        _record_references(
            content,
            rel_path,
            name_patterns,
            tasks_text,
            unhandled_tests,
            unhandled_sources,
        )

    for name in unhandled_tests:
        unhandled_tests[name].sort()
    for name in unhandled_sources:
        unhandled_sources[name].sort()

    return RemovalScanResult(
        unhandled_tests=dict(unhandled_tests),
        unhandled_sources=dict(unhandled_sources),
    )
