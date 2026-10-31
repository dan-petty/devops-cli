"""`devops roadmap stage`: a task group is measured with the files as the step reads them (#2838)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from devops_cli.ai.context_budget import count_tokens
from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS
from devops_cli.roadmap.stage_change import group_text, measure_groups
from devops_cli.roadmap.step_files import packed_file
from tests.support.roadmap_stage import heavy_group

if TYPE_CHECKING:
    from tests.support.roadmap_stage import StageRepo

SAMPLE_PATH = "src/devops_cli/sample.py"


def test_the_measure_of_a_group_counts_the_files_as_the_step_packs_them(
    stage_repo: StageRepo,
) -> None:
    heavy = heavy_group(stage_repo, files=2)
    group = heavy.model_copy(update={"changes": [SAMPLE_PATH]})

    (measured,) = measure_groups(stage_repo.clone, [group], shared=["The item."])

    packed = [packed_file(stage_repo.clone / path) for path in [*group.reads, SAMPLE_PATH]]
    assert measured.tokens == sum(
        count_tokens(text) for text in ["The item.", group_text(1, group), *packed]
    )
    assert all(count_tokens(text) <= CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS for text in packed)
