"""Surface scoped tests in stage plan reads (#3993).

When stage plans a task group, it runs `plan_tests()` against the group's planned
`Changes:` list and adds each selected test module to the group's `Reads:` list.
Missing test paths are omitted from reads and recorded as plan warnings.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement.implement_scoped_ci import ScopedTests, plan_tests
from devops_cli.roadmap.stage.stage_change import StageGroup, StageProposal


def apply_scoped_tests_to_groups(
    source: Path,
    groups: Sequence[StageGroup],
    *,
    planner: Callable[[Path, Iterable[str]], ScopedTests] = plan_tests,
) -> tuple[list[StageGroup], tuple[str, ...]]:
    """Add scoped test modules to each task group reads and collect missing test warnings."""
    texts = MESSAGES.roadmap
    updated_groups: list[StageGroup] = []
    warnings: list[str] = []

    for group in groups:
        scoped = planner(source, group.changes)
        new_reads = list(group.reads)
        for test_path in scoped.paths:
            if (source / test_path).is_file():
                if test_path not in new_reads:
                    new_reads.append(test_path)
            else:
                if test_path in new_reads:
                    new_reads.remove(test_path)
                warning = texts.stage_warning_missing_scoped_test.format(path=test_path)
                if warning not in warnings:
                    warnings.append(warning)
        if new_reads != group.reads:
            group = group.model_copy(update={"reads": new_reads})
        updated_groups.append(group)

    return updated_groups, tuple(warnings)


def apply_scoped_tests(
    source: Path,
    proposal: StageProposal,
    *,
    planner: Callable[[Path, Iterable[str]], ScopedTests] = plan_tests,
) -> tuple[StageProposal, tuple[str, ...]]:
    """Surface scoped tests in each group reads and collect missing test warnings."""
    updated_groups, warnings = apply_scoped_tests_to_groups(
        source, proposal.groups, planner=planner
    )
    return proposal.model_copy(update={"groups": updated_groups}), warnings
