"""The step `fix-plan` ends at its time budget (#5363).

The setting `roadmap.fix_plan.time_budget_seconds` starts with the step. Once it is spent, the
attempt makes no more model calls: it ends with the result and the class `timeout`, keeps the
branch and the label, and comments the open findings and the counts. Each review of an attempt
logs one progress line, so a pod that the deadline of its Job stops still leaves a line for each
round.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from devops_cli import __version__
from devops_cli.config.constants import CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER
from devops_cli.core import clock as clock_seam
from devops_cli.exceptions import ServiceStoppingError
from devops_cli.roadmap.attempt_kill import AttemptKill, AttemptKilled
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.service_stop import begin_service_stop
from devops_cli.roadmap.stage.stage_eval_cases import DefectType
from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
from devops_cli.roadmap.stage.stage_verify import PLAN_NEEDS_FIX_LABEL, Verification, finding_line
from devops_cli.roadmap.steps.fix_plan import FixPlanResult, FixPlanRun, run_fix_plan
from devops_cli.roadmap.stores.store import FixPlanRecordKey
from devops_cli.telemetry.instruments import ROADMAP_FIX_PLAN_TOTAL
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
from tests.support.roadmap_stage import GONE, HOLDS, STAGE_REPO, StageRepo, later_review

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.openspec import OpenSpecFake
    from tests.support.fakes.otlp import FakeCollector

pytestmark = pytest.mark.usefixtures("keyring_store")

NOW = datetime(2026, 11, 13, 4, 0, tzinfo=UTC)
BUDGET = 600
PROGRESS = "fix-plan progress:"


class StepClock:
    """The monotonic reading of the clock seam, moved only by the test.

    The `clock` fixture also routes `time.sleep`, which the wait for each git child process calls
    in a loop, so its reading moves with the real time of each git command. This reading moves
    only when a model answer of the test shifts it, so the budget ends where the test says."""

    def __init__(self) -> None:
        self._now = 0.0

    def monotonic(self) -> float:
        return self._now

    def shift(self, seconds: float) -> None:
        self._now += seconds


@pytest.fixture
def step_clock(monkeypatch: pytest.MonkeyPatch) -> StepClock:
    fake = StepClock()
    monkeypatch.setattr(clock_seam, "monotonic", fake.monotonic)
    return fake


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
    step_clock: StepClock,
    config: Callable[..., Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    config(roadmap={"fix_plan": {"time_budget_seconds": BUDGET}})
    plan = needs_fix_plan(store, stage_repo, github_api)
    open_finding = finding(DefectType.CRITERION_DROPPED)

    def slow_review(_prompt: str) -> Verification:
        step_clock.shift(BUDGET)
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


def test_a_budget_that_ends_after_the_plan_run_pushes_no_revision(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    step_clock: StepClock,
    config: Callable[..., Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The planner wrote a revision, but the budget ends before its review: the step pushes no
    half revision, and the branch stays at its head."""
    config(roadmap={"fix_plan": {"time_budget_seconds": BUDGET}})
    plan = needs_fix_plan(store, stage_repo, github_api)
    verifier.answer(Verification(findings=[finding(DefectType.CRITERION_DROPPED)]))

    def slow_plan(_prompt: str) -> object:
        step_clock.shift(BUDGET)
        return make_stage_proposal(why=REPAIRED_WHY)

    model_fake.answer(slow_plan)

    with caplog.at_level(logging.INFO):
        run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert (run.attempt.result, run.attempt.failure, run.attempt.after) == (
        FixPlanResult.TIMEOUT,
        FailureClass.TIMEOUT,
        None,
    )
    assert (model_fake.call_count, verifier.call_count) == (1, 1)
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head
    assert PLAN_NEEDS_FIX_LABEL in store._roadmap.issues[plan.pull].labels
    (line,) = result_fields(caplog)
    assert (line.get("result"), line.get("class"), line.get("step")) == (
        "timeout",
        "timeout",
        "plan",
    )


@pytest.mark.usefixtures("step_clock")
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
    verifier.answer(
        Verification(findings=[finding(DefectType.CRITERION_DROPPED)]), later_review(GONE)
    )
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


def _killed(
    store: InMemoryRoadmapStore, repo: StageRepo, verifier: ModelFake, now: datetime = NOW
) -> AttemptKilled:
    """The kill that ends a run of the step, which the test makes the verifier raise."""
    with pytest.raises(AttemptKilled) as killed:
        run_fix_plan(
            store,
            repo=STAGE_REPO,
            source=repo.clone,
            confirm=True,
            now=now,
            verifier=ToolboxModel(verifier),
        )
    return killed.value


def _fix_plan_record(store: InMemoryRoadmapStore) -> dict[str, str]:
    item = store.item(1)
    assert item is not None
    return {
        str(key): value
        for key, value in item.job_record.items()
        if str(key).startswith("fix_plan.") and value is not None
    }


@pytest.mark.usefixtures("step_clock")
def test_a_kill_before_the_budget_is_evicted_and_does_not_count(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    otlp: FakeCollector,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """SIGTERM before the budget is spent comes from an eviction, a node drain or a rollout: the
    record keeps the marks of the attempt before it, and the attempt writes no result line."""
    config(roadmap={"fix_plan": {"time_budget_seconds": BUDGET}})
    plan = needs_fix_plan(store, stage_repo, github_api)
    before = (NOW - timedelta(hours=7)).isoformat()
    item = store.item(plan.number)
    assert item is not None
    store.set_marks(
        item,
        {
            FixPlanRecordKey.KEY: f"{plan.pull}:{plan.head}",
            FixPlanRecordKey.ATTEMPTS: "1",
            FixPlanRecordKey.AT: before,
            FixPlanRecordKey.RESULT: "unchanged",
            FixPlanRecordKey.VERSION: "0.1.0",
        },
    )
    verifier.answer(AttemptKilled())

    with caplog.at_level(logging.INFO):
        killed = _killed(store, stage_repo, verifier)

    assert killed.kill is AttemptKill.EVICTED
    assert _fix_plan_record(store) == {
        "fix_plan.key": f"{plan.pull}:{plan.head}",
        "fix_plan.attempts": "1",
        "fix_plan.at": before,
        "fix_plan.version": "0.1.0",
        "fix_plan.evicted": "1",
        "fix_plan.result": "evicted",
    }
    assert result_fields(caplog) == []
    assert store.comments_on(plan.number) == []
    assert (model_fake.call_count, verifier.call_count) == (0, 1)
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head
    points = otlp.points(ROADMAP_FIX_PLAN_TOTAL.name)
    assert [(attrs["result"], value) for attrs, value in points] == [("evicted", 1.0)]


def test_a_kill_after_the_budget_is_a_deadline_and_counts(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    step_clock: StepClock,
    config: Callable[..., Path],
    otlp: FakeCollector,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The budget is below the deadline of the Job, so SIGTERM after the budget is the deadline:
    the attempt spent its tokens and counts, and its result line says so."""
    config(roadmap={"fix_plan": {"time_budget_seconds": BUDGET}})
    plan = needs_fix_plan(store, stage_repo, github_api)

    def slow_review(_prompt: str) -> object:
        step_clock.shift(BUDGET + 1)
        return AttemptKilled()

    verifier.answer(slow_review)

    with caplog.at_level(logging.INFO):
        killed = _killed(store, stage_repo, verifier)

    assert killed.kill is AttemptKill.DEADLINE
    assert _fix_plan_record(store) == {
        "fix_plan.key": f"{plan.pull}:{plan.head}",
        "fix_plan.attempts": "1",
        "fix_plan.at": NOW.isoformat(),
        "fix_plan.version": __version__,
        "fix_plan.result": "timeout",
    }
    (line,) = result_fields(caplog)
    assert {key: line.get(key) for key in ("result", "success", "class", "kill")} == {
        "result": "timeout",
        "success": "false",
        "class": "timeout",
        "kill": "deadline",
    }
    assert store.comments_on(plan.number) == []
    assert model_fake.call_count == 0
    points = otlp.points(ROADMAP_FIX_PLAN_TOTAL.name)
    assert [(attrs["result"], value) for attrs, value in points] == [("timeout", 1.0)]


@pytest.mark.usefixtures("step_clock")
def test_a_stop_of_the_service_during_the_attempt_is_evicted(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A rollout or a node drain stops the Service during the review of the head, and the planner
    stops before the next repair round: the attempt does not count, and the stop of the Service
    goes on."""
    plan = needs_fix_plan(store, stage_repo, github_api)

    def review_then_stop(_prompt: str) -> Verification:
        begin_service_stop()
        return Verification(findings=[finding(DefectType.CRITERION_DROPPED)])

    verifier.answer(review_then_stop, later_review(HOLDS))
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    with caplog.at_level(logging.INFO), pytest.raises(ServiceStoppingError) as stopped:
        run_fix_plan(
            store,
            repo=STAGE_REPO,
            source=stage_repo.clone,
            confirm=True,
            now=NOW,
            verifier=ToolboxModel(verifier),
        )

    assert stopped.value.error_code == "SERVICE_STOPPING"
    record = _fix_plan_record(store)
    assert (record["fix_plan.attempts"], record["fix_plan.evicted"]) == ("0", "1")
    assert (record["fix_plan.result"], "fix_plan.at" in record) == ("evicted", False)
    assert result_fields(caplog) == []
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head


@pytest.mark.usefixtures("step_clock")
def test_a_unit_that_a_kill_always_ends_stops_at_the_cap(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    """3 evicted attempts on one head are free, and each later one counts, so an attempt that a
    kill always ends stops at the cap of 2 attempts: 5 attempts on the head in all."""
    plan = needs_fix_plan(store, stage_repo, github_api)
    verifier.answer(AttemptKilled())

    kills = []
    for round_ in range(6):
        now = NOW + timedelta(hours=6 * round_)
        try:
            run = run_fix_plan(
                store,
                repo=STAGE_REPO,
                source=stage_repo.clone,
                confirm=True,
                now=now,
                verifier=ToolboxModel(verifier),
            )
        except AttemptKilled as killed:
            kills.append(killed.kill)
            continue
        assert (run.target, run.attempt) == (None, None)
        assert [left.number for left in run.left_out] == [plan.number]
        break

    assert kills == [AttemptKill.EVICTED] * 5
    record = _fix_plan_record(store)
    assert (record["fix_plan.attempts"], record["fix_plan.evicted"]) == ("2", "3")
    assert verifier.call_count == 5
