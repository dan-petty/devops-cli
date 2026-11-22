"""Decide change file sets and conflicts for parallel implement Jobs (#3064)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Final

from devops_cli.roadmap.plan_read import PlanReadError, group_files
from devops_cli.roadmap.step_files import parse_task_groups

_GENERATED_CONFIG_DOCS: Final[frozenset[str]] = frozenset(
    {"docs/CONFIGURATION.md", "docs/ENV_VARS.md"}
)
_GENERATED_COMMAND_DOCS: Final[frozenset[str]] = frozenset({"docs/CLI_REFERENCE.md"})

_CHANGES_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"Changes:\s*(?P<changes>[^\n]+)", re.IGNORECASE
)
_CODE_SPAN: Final[re.Pattern[str]] = re.compile(r"`(?P<path>[^`]+)`")


def _paths_of_group(text: str) -> set[str]:
    try:
        files = group_files(text)
        return set(files.changes)
    except PlanReadError:
        match = _CHANGES_PATTERN.search(text)
        if not match:
            return set()
        return {m.group("path").strip() for m in _CODE_SPAN.finditer(match.group("changes"))}


def _extract_paths_from_tasks(tasks_md: str) -> set[str]:
    if not tasks_md:
        return set()
    paths: set[str] = set()
    groups = parse_task_groups(tasks_md)
    for group in groups:
        paths.update(_paths_of_group(group.text))
    return paths


def _specs_from_change_path(change_path: Path | str | None) -> set[str]:
    specs: set[str] = set()
    if change_path is not None:
        specs_dir = Path(change_path) / "specs"
        if specs_dir.is_dir():
            for child in specs_dir.iterdir():
                if child.is_dir():
                    specs.add(f"openspec/specs/{child.name}/spec.md")
    return specs


def _specs_from_files(files: Iterable[str] | None) -> set[str]:
    specs: set[str] = set()
    if files is not None:
        for f in files:
            if f.startswith("openspec/changes/") and "/specs/" in f:
                parts = f.split("/specs/", 1)[1].split("/")
                if parts and parts[0]:
                    specs.add(f"openspec/specs/{parts[0]}/spec.md")
    return specs


def _specs_from_paths(paths: Iterable[str]) -> set[str]:
    specs: set[str] = set()
    for p in paths:
        if p.startswith("specs/"):
            parts = Path(p).parts
            if len(parts) >= 2:
                specs.add(f"openspec/specs/{parts[1]}/spec.md")
        elif p.startswith("openspec/changes/") and "/specs/" in p:
            spec_parts = p.split("/specs/", 1)[1].split("/")
            if spec_parts and spec_parts[0]:
                specs.add(f"openspec/specs/{spec_parts[0]}/spec.md")
    return specs


def _add_capability_specs(
    paths: set[str], change_path: Path | str | None, files: Iterable[str] | None
) -> None:
    paths.update(_specs_from_change_path(change_path))
    paths.update(_specs_from_files(files))
    paths.update(_specs_from_paths(list(paths)))


def _add_generated_docs(paths: set[str]) -> None:
    if any(p.startswith("src/devops_cli/config/") for p in paths):
        paths.update(_GENERATED_CONFIG_DOCS)
    if any(p.startswith("src/devops_cli/commands/") for p in paths):
        paths.update(_GENERATED_COMMAND_DOCS)


def change_files(
    tasks_md: str,
    change_path: Path | str | None = None,
    files: Iterable[str] | None = None,
) -> frozenset[str]:
    """Return the set of paths that the plan changes.

    The set includes paths from Changes lines in tasks.md, capability specs
    under openspec/specs/ for each capability folder under specs/, and generated
    docs when configuration or commands change. If the plan cannot be read or
    names no changes, an empty set is returned.
    """
    paths = _extract_paths_from_tasks(tasks_md)
    if not paths:
        return frozenset()

    _add_capability_specs(paths, change_path, files)
    _add_generated_docs(paths)
    return frozenset(paths)


def conflicts(one: frozenset[str], other: frozenset[str]) -> bool:
    """Return True if two items conflict and cannot run together.

    An empty set conflicts with everything so an item with no change set runs alone.
    Two non-empty sets conflict if they share an exact path or if any path in one set
    is an ancestor or descendant of a path in the other set.
    """
    if not one or not other:
        return True

    for a in one:
        norm_a = a.rstrip("/")
        for b in other:
            norm_b = b.rstrip("/")
            if (
                norm_a == norm_b
                or norm_a.startswith(norm_b + "/")
                or norm_b.startswith(norm_a + "/")
            ):
                return True

    return False
