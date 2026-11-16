"""A stop of the Service after each write of the implement job leaves the next round no second
comment to post (ADR 0021, #4793, #5025).

The roadmap is the in-memory store, git runs on real clones, and the model is scripted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from devops_cli.roadmap.implement.implement import (
    parse_implement_filters,
    plan_implement,
)
from devops_cli.roadmap.implement.implement_run import apply_implement
from tests.support.implement_step import WINDOW
from tests.support.model_script import ModelScript, say
from tests.support.roadmap_stage import STAGE_REPO
from tests.support.write_stops import stop_after_each_write

if TYPE_CHECKING:
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
    from tests.support.roadmap_implement import JobWorld

pytestmark = pytest.mark.usefixtures("keyring_store")

PREMISE_REQUEST = (
    "```plan-request\n"
    "{\n"
    '  "kind": "premise",\n'
    '  "group": 1,\n'
    '  "defect": "the premise is false",\n'
    '  "evidence": "the feature was already removed in #1234"\n'
    "}\n"
    "```"
)


def test_a_stop_after_each_write_of_implement_returns_no_extra_comment(
    planned_world: JobWorld,
) -> None:
    """When a stop occurs after any write of an implement return-to-new, the next round
    leaves no comment that one whole run does not leave (StopReplay.extra_comments is empty)."""
    script = ModelScript(say(PREMISE_REQUEST))

    def _run_implement(copied_store: InMemoryRoadmapStore) -> None:
        plan = plan_implement(
            copied_store,
            repo=STAGE_REPO,
            source=planned_world.repo.clone,
            filters=parse_implement_filters(()),
            limit=1,
        )
        apply_implement(
            copied_store,
            plan,
            source=planned_world.repo.clone,
            rebase=False,
            model=script.model(),
            window=WINDOW,
        )

    replay = stop_after_each_write(planned_world.store, _run_implement)

    assert replay.extra_comments() == []
