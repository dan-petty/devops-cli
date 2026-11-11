"""The `stage` row of the Service logs one line with counts for each item that its round failed
(#4535)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from devops_cli.exceptions import RoadmapStageError
from devops_cli.roadmap.run import MODEL_LANE_ROWS
from tests.support.builders import make_stage_proposal
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

STAGE_ROW = next(row for row in MODEL_LANE_ROWS if row.name == "stage")


@pytest.fixture(autouse=True)
def valid_openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    openspec_fake.script_sequence(validate_args("1-the-job-drops-a-comment"), (0, VALID_REPORT))
    return openspec_fake


def test_each_item_that_a_round_failed_logs_one_line_with_its_step_and_class(
    stage_repo: StageRepo, model_fake: ModelFake, caplog: pytest.LogCaptureFixture
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_stageable(store)
    group = make_stage_proposal().groups[0]
    missing = make_stage_proposal(
        groups=[group.model_copy(update={"changes": [*group.changes, "tests/test_missing.py"]})]
    )
    model_fake.answer(missing, missing)

    with caplog.at_level(logging.INFO), pytest.raises(RoadmapStageError) as raised:
        STAGE_ROW.runner(store=store, repo=STAGE_REPO, clone_path=stage_repo.clone)

    assert raised.value.failed_items == (number,)
    lines = [
        r.getMessage() for r in caplog.records if r.getMessage().startswith("stage item failed")
    ]
    assert [line.rsplit(" version=", 1)[0] for line in lines] == [
        f"stage item failed: repo={STAGE_REPO} item=#{number} step=plan class=plan_defect"
    ]
