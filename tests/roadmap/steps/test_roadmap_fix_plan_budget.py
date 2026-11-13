"""The step `fix-plan` ends at its time budget (#5363).

The setting `roadmap.fix_plan.time_budget_seconds` starts with the step. Once it is spent, the
attempt makes no more model calls: it ends with the result and the class `timeout`, keeps the
branch and the label, and comments the open findings and the counts. Each review of an attempt
logs one progress line, so a pod that the deadline of its Job stops still leaves a line for each
round.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from devops_cli.config.constants import CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.stage.stage_eval_cases import DefectType
from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
from devops_cli.roadmap.stage.stage_verify import PLAN_NEEDS_FIX_LABEL, Verification, finding_line
from devops_cli.roadmap.steps.fix_plan import FixPlanResult, FixPlanRun, run_fix_plan
from devops_cli.roadmap.stores.store import FixPlanRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.model import ModelFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_fix_plan import (
    PLAN_BRANCH,
    REPAIRED_WHY,
    finding,
    needs_fix_plan,
    valid_changes,
)
from tests.support.roadmap_job_result import result_fields
from tests.support.roadmap_stage import STAGE_REPO, StageRepo

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.support.fakes.clock import ClockFake
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

NOW = datetime(2026, 11, 13, 4, 0, tzinfo=UTC)
BUDGET = 600
PROGRESS = "fix-plan progress:"


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def verifier() -> ModelFake:
    """The model edge of the verification task, apart from the model edge of the planner."""
    return ModelFake()


@pytest.fixture(autouse=True)
def openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    valid_changes(openspec_fake)
    return openspec_fake


def _run(store: InMemoryRoadmapStore, repo: StageRepo, verifier: ModelFake) -> FixPlanRun:
    return run_fix_plan(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        confirm=True,
        now=NOW,
        verifier=ToolboxModel(verifier),
    )


def _progress(caplog: pytest.LogCaptureFixture) -> list[dict[str, str]]:
    """The fields of each progress line that `caplog` holds, in order, with no version."""
    lines = [
        dict(field.split("=", 1) for field in message.removeprefix(PROGRESS).split())
        for record in caplog.records
        if (message := record.getMessage()).startswith(PROGRESS)
    ]
    for each in lines:
        each.pop("version")
    return lines


def test_a_spent_budget_ends_the_attempt_with_a_timeout_comment_and_no_push(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    clock: ClockFake,
    config: Callable[..., Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    config(roadmap={"fix_plan": {"time_budget_seconds": BUDGET}})
    plan = needs_fix_plan(store, stage_repo, github_api)
    open_finding = finding(DefectType.CRITERION_DROPPED)

    def slow_review(_prompt: str) -> Verification:
        clock.shift(BUDGET)
        return Verification(findings=[open_finding])

    verifier.answer(slow_review)
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    with caplog.at_level(logging.INFO):
        run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    attempt = run.attempt
    assert (attempt.result, attempt.failure, attempt.before, attempt.after) == (
        FixPlanResult.TIMEOUT,
        FailureClass.TIMEOUT,
        1,
        None,
    )
    assert model_fake.call_count == 0
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head
    assert PLAN_NEEDS_FIX_LABEL in store._roadmap.issues[plan.pull].labels
    item = store.item(plan.number)
    assert item is not None
    assert (
        item.job_record.get(FixPlanRecordKey.RESULT),
        item.job_record.get(FixPlanRecordKey.ATTEMPTS),
    ) == ("timeout", "1")
    (comment,) = [each.body for each in store.comments_on(plan.number)]
    assert CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER in comment
    assert f"#{plan.pull}" in comment
    assert f"{BUDGET} seconds" in comment
    assert "verify_rounds 1" in comment
    assert finding_line(open_finding) in comment
    (line,) = result_fields(caplog)
    assert {key: line.get(key) for key in ("result", "success", "class", "step", "before")} == {
        "result": "timeout",
        "success": "false",
        "class": "timeout",
        "step": "plan",
        "before": "1",
    }
    assert "after" not in line


def test_each_review_of_an_attempt_logs_one_progress_line(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    config(roadmap={"fix_plan": {"time_budget_seconds": BUDGET}})
    needs_fix_plan(store, stage_repo, github_api)
    verifier.answer(Verification(findings=[finding(DefectType.CRITERION_DROPPED)]), Verification())
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    with caplog.at_level(logging.INFO):
        run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert run.attempt.result is FixPlanResult.CLEARED
    lines = _progress(caplog)
    assert [(line["repo"], line["item"], line["round"], line["open"]) for line in lines] == [
        (STAGE_REPO, "#1", "0", "1"),
        (STAGE_REPO, "#1", "1", "0"),
    ]
    assert all(line["budget"] == str(BUDGET) for line in lines)
    assert all({"tokens", "seconds"} <= set(line) for line in lines)
