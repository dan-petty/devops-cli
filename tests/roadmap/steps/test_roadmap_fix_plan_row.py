"""The row `fix_plan` of the model lane of the Service runs the step `fix-plan` in the mode of
`roadmap.fix_plan.mode` (#5061)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from devops_cli.roadmap.run import MODEL_LANE_ROWS
from devops_cli.roadmap.stage.stage_verify import PLAN_NEEDS_FIX_LABEL, Verification
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_fix_plan import PLAN_BRANCH, PLAN_PATH, needs_fix_plan, valid_changes
from tests.support.roadmap_stage import STAGE_REPO, StageRepo

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

FIX_PLAN_ROW = next(row for row in MODEL_LANE_ROWS if row.name == "fix_plan")


@pytest.fixture(autouse=True)
def openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    valid_changes(openspec_fake)
    return openspec_fake


def test_the_row_follows_retitle_needs_a_clone_and_is_due_on_a_first_run() -> None:
    """Stage left the model lane for the status lane (#4559), so fix_plan follows retitle."""
    names = [row.name for row in MODEL_LANE_ROWS]

    assert names[names.index("retitle") + 1] == "fix_plan"
    assert (FIX_PLAN_ROW.needs_clone, FIX_PLAN_ROW.first_run_due) == (True, True)


def test_mode_off_sends_no_request(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    needs_fix_plan(store, stage_repo, github_api)
    config(roadmap={"fix_plan": {"mode": "off"}})

    FIX_PLAN_ROW.runner(store=store, repo=STAGE_REPO, clone_path=stage_repo.clone)

    assert (github_api.requested, model_fake.call_count) == ([], 0)


def test_mode_plan_logs_the_selection_and_makes_no_model_call_and_no_write(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    plan = needs_fix_plan(store, stage_repo, github_api)
    config(roadmap={"fix_plan": {"mode": "plan"}})

    with caplog.at_level(logging.INFO):
        FIX_PLAN_ROW.runner(store=store, repo=STAGE_REPO, clone_path=stage_repo.clone)

    item = store.item(plan.number)
    assert item is not None
    assert model_fake.call_count == 0
    assert github_api.requested == [f"GET https://api.github.com{PLAN_PATH}"]
    assert not any("fix_plan" in str(key) for key in item.job_record)
    assert any(f"#{plan.pull}" in record.getMessage() for record in caplog.records)


def test_the_default_mode_is_plan(
    stage_repo: StageRepo, model_fake: ModelFake, github_api: GitHubApiFake
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    needs_fix_plan(store, stage_repo, github_api)

    FIX_PLAN_ROW.runner(store=store, repo=STAGE_REPO, clone_path=stage_repo.clone)

    assert model_fake.call_count == 0


def test_mode_on_runs_the_attempt(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    plan = needs_fix_plan(store, stage_repo, github_api)
    model_fake.answer(Verification())
    config(roadmap={"fix_plan": {"mode": "on"}})

    FIX_PLAN_ROW.runner(store=store, repo=STAGE_REPO, clone_path=stage_repo.clone)

    assert PLAN_NEEDS_FIX_LABEL not in store._roadmap.issues[plan.pull].labels
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head
