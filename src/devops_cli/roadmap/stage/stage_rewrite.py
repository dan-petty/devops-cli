"""Mechanical rewrites of refused stage proposals (#4853)."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from typing import Final

from devops_cli.roadmap.stage.stage_change import StageProposal
from devops_cli.roadmap.stage.stage_findings import _MECHANICAL, StageFinding
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.telemetry.instruments import ROADMAP_FIX_CHECKS_TOTAL, emit

logger = logging.getLogger(__name__)

_DEPENDENCIES_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"open pull request #(?P<pull>\d+) changes `(?P<path>[^`]+)`"
)
_PERIMETER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"changes `(?P<path>[^`]+)` and leaves out `(?P<test>[^`]+)`"
)
_MODULE_TEST_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"Group (?P<group>\d+) changes `(?P<path>[^`]+)` and names no existing test of that module\. Add `(?P<test>[^`]+)` to `reads`"
)
_REGISTRY_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"names no task for `(?P<path>[^`]+)` \((?P<location>[^)]+)\)"
)


def _record_rewrite(code: str, path: str) -> None:
    logger.info("Rewrite mechanical finding %s for %s.", code, path)
    emit(ROADMAP_FIX_CHECKS_TOTAL, 1, {"site": "stage.gate", "path": "mechanical"})


def _rewrite_dependencies(proposal: StageProposal, finding: StageFinding) -> int:
    match = _DEPENDENCIES_PATTERN.search(finding.text)
    if not match:
        return 0
    pull = match.group("pull")
    path = match.group("path")
    if any(f"#{pull}" in entry and path in entry for entry in proposal.dependencies):
        return 0
    proposal.dependencies.append(f"#{pull}: changes `{path}`.")
    _record_rewrite(finding.code, path)
    return 1


def _rewrite_perimeter_test(
    proposal: StageProposal, finding: StageFinding, tree: StagedTree
) -> int:
    match = _PERIMETER_PATTERN.search(finding.text)
    if not match:
        return 0
    path = match.group("path")
    test = match.group("test")
    if not tree.has(test):
        return 0
    for group in proposal.groups:
        if path in group.changes and test not in group.changes:
            group.changes.append(test)
            _record_rewrite(finding.code, test)
            return 1
    return 0


def _rewrite_module_test(proposal: StageProposal, finding: StageFinding, tree: StagedTree) -> int:
    match = _MODULE_TEST_PATTERN.search(finding.text)
    if not match:
        return 0
    group_idx = int(match.group("group")) - 1
    test = match.group("test")
    if not tree.has(test) or not (0 <= group_idx < len(proposal.groups)):
        return 0
    group = proposal.groups[group_idx]
    if test in group.reads:
        return 0
    group.reads.append(test)
    _record_rewrite(finding.code, test)
    return 1


def _rewrite_registry(proposal: StageProposal, finding: StageFinding, tree: StagedTree) -> int:
    path = finding.path
    location = ""
    if not path:
        match = _REGISTRY_PATTERN.search(finding.text)
        if match:
            path = match.group("path")
            location = match.group("location")
    else:
        loc_match = re.search(r"\((?P<location>[^)]+)\)", finding.text)
        location = loc_match.group("location") if loc_match else ""

    if not path or not tree.has(path):
        return 0

    task_texts = [
        t for g in proposal.groups for t in (g.test, g.implementation, g.documentation) if t
    ]
    if any(path in t for t in task_texts):
        return 0

    declaring_path = location.split(":")[0] if location else ""
    target_group = next(
        (g for g in proposal.groups if declaring_path and declaring_path in g.changes),
        proposal.groups[-1],
    )
    if target_group.documentation is None:
        target_group.documentation = f"Update `{path}`"
    else:
        doc = target_group.documentation.rstrip(". ")
        target_group.documentation = f"{doc}. Update `{path}`"
    _record_rewrite(finding.code, path)
    return 1


def apply_mechanical_rewrites(
    proposal: StageProposal,
    findings: Sequence[StageFinding],
    tree: StagedTree,
) -> tuple[StageProposal, int]:
    """Apply mechanical rewrites to `proposal` for the given `findings` of `_MECHANICAL`.

    Returns the updated proposal and the number of edits applied.
    """
    updated = proposal.model_copy(deep=True)
    count = 0
    for finding in findings:
        if finding.code not in _MECHANICAL:
            continue
        match finding.code:
            case "stage_problem_dependencies":
                count += _rewrite_dependencies(updated, finding)
            case "stage_problem_missing_perimeter_test":
                count += _rewrite_perimeter_test(updated, finding, tree)
            case "stage_problem_missing_module_test":
                count += _rewrite_module_test(updated, finding, tree)
            case "stage_problem_registry":
                count += _rewrite_registry(updated, finding, tree)
    return updated, count


__all__ = ["apply_mechanical_rewrites"]
