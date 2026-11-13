"""`devops roadmap step fix-plan`: the attempts on a head and the revisions of a pull request are
the settings `roadmap.fix_plan.head_attempts` and `roadmap.fix_plan.revisions` (#5440). The step
reads them at each selection, so a changed ConfigMap needs no restart."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
from devops_cli.roadmap.steps.fix_plan import FixPlanRun, run_fix_plan
from devops_cli.roadmap.stores.store import FixPlanRecordKey
from tests.support.fakes.model import ModelFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_fix_plan import needs_fix_plan, valid_changes
from tests.support.roadmap_stage import STAGE_REPO, StageRepo

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
# The marks of an item at the old bounds: 2 attempts on the head, or 3 revisions of the pull
# request.
AT_THE_OLD_BOUNDS = [
    pytest.param({FixPlanRecordKey.KEY: "5:{head}", FixPlanRecordKey.ATTEMPTS: "2"}, id="attempts"),
    pytest.param(
        {FixPlanRecordKey.KEY: "5:" + "b" * 40, FixPlanRecordKey.REVISIONS: "3"}, id="revisions"
    ),
]


@pytest.fixture(autouse=True)
def openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    valid_changes(openspec_fake)
    return openspec_fake


def _select(
    store: InMemoryRoadmapStore,
    repo: StageRepo,
    api: GitHubApiFake,
    marks: dict[Any, str],
) -> FixPlanRun:
    """Seed the plan pull request with `marks` and run the selection with no attempt."""
    plan = needs_fix_plan(store, repo, api)
    item = store.item(plan.number)
    assert item is not None
    store.set_marks(item, {key: value.format(head=plan.head) for key, value in marks.items()})
    return run_fix_plan(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        confirm=False,
        now=NOW,
        verifier=ToolboxModel(ModelFake()),
    )


@pytest.mark.parametrize("marks", AT_THE_OLD_BOUNDS)
def test_the_defaults_leave_a_plan_out_at_the_old_bounds(
    stage_repo: StageRepo, github_api: GitHubApiFake, marks: dict[Any, str]
) -> None:
    run = _select(InMemoryRoadmapStore(repo=STAGE_REPO), stage_repo, github_api, marks)

    assert (run.target, [left.number for left in run.left_out]) == (None, [1])


@pytest.mark.parametrize("marks", AT_THE_OLD_BOUNDS)
def test_doubled_settings_select_a_plan_at_the_old_bounds(
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    marks: dict[Any, str],
) -> None:
    config(roadmap={"fix_plan": {"head_attempts": 4, "revisions": 6}})

    run = _select(InMemoryRoadmapStore(repo=STAGE_REPO), stage_repo, github_api, marks)

    assert run.target is not None
    assert (run.target.item.number, run.left_out) == (1, ())
