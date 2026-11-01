"""`devops roadmap stage`: a task group is measured with the files its step reads (#2838)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from devops_cli.ai.context_budget import count_tokens
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS
from devops_cli.roadmap.implement_step import _files_section
from devops_cli.roadmap.stage_change import StageGroup, group_text, measure_groups
from devops_cli.roadmap.step_files import named_files, packed_file, parse_task_groups
from devops_cli.roadmap.step_rules import RULES_HEADING, route_heading
from tests.support.builders import make_stage_proposal
from tests.support.roadmap_stage import heavy_group

if TYPE_CHECKING:
    from pathlib import Path

    from tests.support.roadmap_stage import StageRepo

SHARED = "The item."
FILE_CAP = CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS


def _file_tokens(clone: Path, group: StageGroup) -> int:
    """The tokens of a group that are none of the shared text and none of the group text."""
    (measured,) = measure_groups(clone, [group], shared=[SHARED])
    return measured.tokens - count_tokens(SHARED) - count_tokens(group_text(1, group))


def test_a_file_that_the_tasks_name_counts_at_most_the_file_cap_of_the_step(
    stage_repo: StageRepo,
) -> None:
    group = heavy_group(stage_repo, files=2)

    assert FILE_CAP < _file_tokens(stage_repo.clone, group) <= 2 * FILE_CAP


def test_a_file_that_no_task_names_costs_nothing_as_the_step_reads_it_not(
    stage_repo: StageRepo,
) -> None:
    group = heavy_group(stage_repo, files=2).model_copy(
        update={"implementation": "Keep the last comment"}
    )

    assert _file_tokens(stage_repo.clone, group) == 0


def test_a_file_that_a_task_names_counts_though_the_group_does_not_read_it(
    stage_repo: StageRepo,
) -> None:
    group = heavy_group(stage_repo, files=2)
    unlisted = group.model_copy(update={"reads": []})

    assert _file_tokens(stage_repo.clone, unlisted) == _file_tokens(stage_repo.clone, group)
    assert _file_tokens(stage_repo.clone, unlisted) > FILE_CAP


def test_the_measure_and_the_step_read_the_same_files_with_the_same_text(
    stage_repo: StageRepo,
) -> None:
    group = heavy_group(stage_repo, files=2)
    (parsed,) = parse_task_groups(group_text(1, group))

    section = _files_section(stage_repo.clone, parsed)

    paths = named_files(stage_repo.clone, parsed)
    assert len(paths) == 2
    assert all(packed_file(path) in section for path in paths)
    file_tokens = _file_tokens(stage_repo.clone, group)
    assert file_tokens <= count_tokens(section) <= file_tokens + 100


def test_the_measure_counts_agents_md_and_the_routed_sections_that_the_step_reads(
    stage_repo: StageRepo,
) -> None:
    """The default group names `src/devops_cli/sample.py` and `tests/test_sample.py`, so the step
    reads `AGENTS.md` and the testing sections (#3097)."""
    clone = stage_repo.clone
    group = make_stage_proposal().groups[0]
    (before,) = measure_groups(clone, [group], shared=[SHARED])
    (clone / "AGENTS.md").write_text("# Agents\n\nBe brief.\n", encoding="utf-8")
    (clone / "docs").mkdir()
    (clone / "docs" / "TESTING.md").write_text(
        "# Testing\n\n## Conventions\n\n### Doubles\n\nDouble the edges.\n", encoding="utf-8"
    )

    (after,) = measure_groups(clone, [group], shared=[SHARED])

    rules = f"# {RULES_HEADING}\n\n# Agents\n\nBe brief."
    testing = f"{route_heading('docs/TESTING.md')}\n\n### Doubles\n\nDouble the edges."
    assert after.tokens - before.tokens == count_tokens(rules) + count_tokens(testing)
