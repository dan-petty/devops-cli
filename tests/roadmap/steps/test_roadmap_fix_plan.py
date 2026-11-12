"""The step `fix-plan` repairs an open plan pull request that holds `plan/needs-fix` (#5061).

Git is real in `tmp_path`: the plan branch is on a bare `origin`, and the step pushes to it. The
planner is the model edge of the `stage` task and the verifier a model edge of its own. GitHub's
REST API answers the read of the pull request.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.config.constants import CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER
from devops_cli.exceptions import ServiceStoppingError
from devops_cli.roadmap.service_stop import begin_service_stop
from devops_cli.roadmap.stage.stage_eval_cases import DefectType
from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
from devops_cli.roadmap.stage.stage_verify import PLAN_NEEDS_FIX_LABEL, Verification
from devops_cli.roadmap.steps.fix_plan import FixPlanResult, FixPlanRun, run_fix_plan
from devops_cli.roadmap.stores.store import (
    FixPlanRecordKey,
    ImplementRecordKey,
    ItemField,
)
from devops_cli.telemetry.instruments import ROADMAP_FIX_PLAN_TOTAL
from tests.support.builders import make_stage_proposal
from tests.support.fakes.model import ModelFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_fix_plan import (
    PLAN_BRANCH,
    PLAN_CHANGE,
    PLAN_PATH,
    REPAIRED_WHY,
    SAMPLE_QUOTE,
    finding,
    needs_fix_plan,
    planner_requests,
    route_plan_pull,
    valid_changes,
)
from tests.support.roadmap_job_result import result_fields
from tests.support.roadmap_stage import STAGE_REPO, StageRepo, advance_origin

if TYPE_CHECKING:
    from pathlib import Path

    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.openspec import OpenSpecFake
    from tests.support.fakes.otlp import FakeCollector

pytestmark = pytest.mark.usefixtures("keyring_store")

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)


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


def _run(
    store: InMemoryRoadmapStore,
    repo: StageRepo,
    verifier: ModelFake,
    *,
    confirm: bool = True,
    item: int | None = None,
    now: datetime = NOW,
) -> FixPlanRun:
    return run_fix_plan(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        confirm=confirm,
        item=item,
        now=now,
        verifier=ToolboxModel(verifier),
    )


def _record(store: InMemoryRoadmapStore, number: int = 1) -> dict[str, str | None]:
    item = store.item(number)
    assert item is not None
    return {
        str(key): value
        for key, value in item.job_record.items()
        if "fix_plan" in str(key) and value is not None
    }


def _origin_file(repo: StageRepo, path: str) -> str:
    return repo.origin_git("show", f"{PLAN_BRANCH}:openspec/changes/{PLAN_CHANGE}/{path}")


def _comments(store: InMemoryRoadmapStore, number: int = 1) -> list[str]:
    return [comment.body for comment in store.comments_on(number)]


def test_a_revision_with_no_open_finding_is_pushed_on_the_latest_main_and_clears_the_label(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    tmp_path: Path,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api)
    advance_origin(stage_repo, tmp_path, {"NEWS.md": "main moved\n"})
    open_finding = finding(DefectType.CRITERION_DROPPED)
    verifier.answer(Verification(findings=[open_finding]), Verification())
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    run = _run(store, stage_repo, verifier)

    head = stage_repo.origin_git("rev-parse", PLAN_BRANCH)
    assert run.attempt is not None
    assert (run.attempt.result, run.attempt.before, run.attempt.after) == (
        FixPlanResult.CLEARED,
        1,
        0,
    )
    assert head != plan.head
    assert stage_repo.origin_git("rev-parse", f"{PLAN_BRANCH}^") == stage_repo.origin_git(
        "rev-parse", "main"
    )
    assert REPAIRED_WHY in _origin_file(stage_repo, "proposal.md")
    assert PLAN_NEEDS_FIX_LABEL not in store._roadmap.issues[plan.pull].labels
    assert _record(store) == {
        FixPlanRecordKey.KEY: f"{plan.pull}:{head}",
        FixPlanRecordKey.ATTEMPTS: "0",
        FixPlanRecordKey.REVISIONS: "1",
        FixPlanRecordKey.AT: NOW.isoformat(),
        FixPlanRecordKey.RESULT: "cleared",
    }
    (comment,) = _comments(store)
    assert CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER in comment
    assert f"#{plan.pull}" in comment


def test_the_planner_gets_the_head_plan_as_previous_and_each_open_finding_as_problem(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    needs_fix_plan(store, stage_repo, github_api)
    dropped = finding(DefectType.CRITERION_DROPPED)
    order = finding(DefectType.TASK_ORDER, SAMPLE_QUOTE)
    verifier.answer(Verification(findings=[dropped, order]), Verification())
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    _run(store, stage_repo, verifier)

    (request,) = planner_requests(model_fake)
    assert request["previous"]["summary"] == "Stop the job dropping a comment"
    assert request["previous"]["why"] == make_stage_proposal().why
    assert "criterion_dropped" in request["problem"]
    assert "task_order" in request["problem"]


def test_a_revision_with_fewer_open_findings_is_pushed_and_keeps_the_label(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api)
    dropped = finding(DefectType.CRITERION_DROPPED)
    order = finding(DefectType.TASK_ORDER, SAMPLE_QUOTE)
    verifier.answer(Verification(findings=[dropped, order]), Verification(findings=[dropped]))
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    run = _run(store, stage_repo, verifier)

    head = stage_repo.origin_git("rev-parse", PLAN_BRANCH)
    assert run.attempt is not None
    assert (run.attempt.result, run.attempt.before, run.attempt.after) == (
        FixPlanResult.REVISED,
        2,
        1,
    )
    assert head != plan.head
    assert PLAN_NEEDS_FIX_LABEL in store._roadmap.issues[plan.pull].labels
    assert _record(store)[FixPlanRecordKey.KEY] == f"{plan.pull}:{head}"
    assert _record(store)[FixPlanRecordKey.RESULT] == "revised"
    assert len(_comments(store)) == 1


def test_a_revision_that_is_not_better_writes_nothing_to_github_but_the_record(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api)
    dropped = finding(DefectType.CRITERION_DROPPED)
    verifier.answer(Verification(findings=[dropped]))
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert (run.attempt.result, run.attempt.before, run.attempt.after) == (
        FixPlanResult.UNCHANGED,
        1,
        1,
    )
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head
    assert PLAN_NEEDS_FIX_LABEL in store._roadmap.issues[plan.pull].labels
    assert _comments(store) == []
    assert github_api.requested == [f"GET https://api.github.com{PLAN_PATH}"]
    assert _record(store) == {
        FixPlanRecordKey.KEY: f"{plan.pull}:{plan.head}",
        FixPlanRecordKey.ATTEMPTS: "1",
        FixPlanRecordKey.AT: NOW.isoformat(),
        FixPlanRecordKey.RESULT: "unchanged",
    }


def test_a_head_plan_with_no_open_finding_loses_the_label_and_gets_no_commit(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api)
    verifier.answer(Verification())

    run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert (run.attempt.result, run.attempt.before, run.attempt.after) == (
        FixPlanResult.CLEARED,
        0,
        0,
    )
    assert model_fake.call_count == 0
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head
    assert PLAN_NEEDS_FIX_LABEL not in store._roadmap.issues[plan.pull].labels
    assert len(_comments(store)) == 1


@pytest.mark.parametrize(
    ("marks", "why"),
    [
        ({FixPlanRecordKey.KEY: "5:{head}", FixPlanRecordKey.ATTEMPTS: "2"}, "attempts"),
        ({FixPlanRecordKey.AT: (NOW - timedelta(hours=5)).isoformat()}, "recent"),
        ({FixPlanRecordKey.KEY: "5:" + "b" * 40, FixPlanRecordKey.REVISIONS: "3"}, "revisions"),
        ({ImplementRecordKey.JOB: "devops-cli-runner-1"}, "runner job"),
    ],
)
def test_the_bounds_and_the_record_leave_the_plan_out_with_no_model_call(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    marks: dict[Any, str],
    why: str,
) -> None:
    del why
    plan = needs_fix_plan(store, stage_repo, github_api)
    item = store.item(plan.number)
    assert item is not None
    store.set_marks(item, {key: value.format(head=plan.head) for key, value in marks.items()})

    run = _run(store, stage_repo, verifier)

    assert (run.target, run.attempt) == (None, None)
    assert [left.number for left in run.left_out] == [plan.number]
    assert (model_fake.call_count, verifier.call_count) == (0, 0)
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head


def test_an_attempt_six_hours_old_does_not_hold_the_plan(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    plan = needs_fix_plan(
        store,
        stage_repo,
        github_api,
        marks={FixPlanRecordKey.AT: (NOW - timedelta(hours=6)).isoformat()},
    )
    verifier.answer(Verification())

    run = _run(store, stage_repo, verifier)

    assert run.target is not None
    assert run.target.pull == plan.pull


@pytest.mark.parametrize(
    ("field", "value"),
    [(ItemField.OWNER, "Human"), (ItemField.OWNER, "Agent"), (ItemField.STATUS, "New")],
)
def test_a_claimed_item_or_an_item_that_is_not_staged_is_left_out(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    field: ItemField,
    value: str,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api)
    item = store.item(plan.number)
    assert item is not None
    store.set_field(item, field, value)

    run = _run(store, stage_repo, verifier)

    assert (run.target, model_fake.call_count, verifier.call_count) == (None, 0, 0)


@pytest.mark.parametrize(("labels", "draft"), [((), True), ((PLAN_NEEDS_FIX_LABEL,), False)])
def test_a_pull_request_without_the_label_or_out_of_draft_is_left_out(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    labels: tuple[str, ...],
    draft: bool,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api, labels=labels, draft=draft)

    run = _run(store, stage_repo, verifier)

    assert (run.target, run.attempt, verifier.call_count) == (None, None, 0)
    assert [left.number for left in run.left_out] == [plan.number]


def test_a_commit_of_a_person_on_the_branch_stops_the_attempt_before_any_write(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api)
    stage_repo.push_branch(PLAN_BRANCH, author="Person")
    head = stage_repo.origin_git("rev-parse", PLAN_BRANCH)
    route_plan_pull(github_api, head)

    run = _run(store, stage_repo, verifier)

    assert (run.attempt, verifier.call_count, _record(store)) == (None, 0, {})
    assert [left.number for left in run.left_out] == [plan.number]
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == head


def test_a_head_that_moved_after_the_read_stops_the_attempt_before_any_write(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api)
    route_plan_pull(github_api, "c" * 40)

    run = _run(store, stage_repo, verifier)

    assert (run.attempt, verifier.call_count, _record(store)) == (None, 0, {})
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head


def test_without_confirm_the_step_selects_and_makes_no_model_call_and_no_write(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api)

    run = _run(store, stage_repo, verifier, confirm=False)

    assert run.target is not None
    assert (run.target.item.number, run.target.pull, run.attempt) == (
        plan.number,
        plan.pull,
        None,
    )
    assert (model_fake.call_count, verifier.call_count, _record(store)) == (0, 0, {})
    assert github_api.requested == [f"GET https://api.github.com{PLAN_PATH}"]


def test_no_attempt_starts_once_the_service_stops(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    needs_fix_plan(store, stage_repo, github_api)
    begin_service_stop()

    with pytest.raises(ServiceStoppingError) as stopped:
        _run(store, stage_repo, verifier)

    assert stopped.value.error_code == "SERVICE_STOPPING"
    assert (model_fake.call_count, verifier.call_count, _record(store)) == (0, 0, {})


def test_item_names_the_one_item_to_judge(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api)
    other = store.seed_issue("fix(roadmap): another item")

    run = _run(store, stage_repo, verifier, confirm=False, item=other)

    assert run.target is None
    assert [left.number for left in run.left_out] == [other]
    assert _run(store, stage_repo, verifier, confirm=False, item=plan.number).target is not None


def test_each_attempt_logs_one_result_line_and_counts_its_result(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    otlp: FakeCollector,
    caplog: pytest.LogCaptureFixture,
) -> None:
    needs_fix_plan(store, stage_repo, github_api)
    verifier.answer(Verification(findings=[finding(DefectType.CRITERION_DROPPED)]), Verification())
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    with caplog.at_level(logging.INFO):
        _run(store, stage_repo, verifier)

    (line,) = result_fields(caplog)
    assert {key: line[key] for key in ("job", "repo", "item", "result", "success", "class")} == {
        "job": "fix_plan",
        "repo": STAGE_REPO,
        "item": "#1",
        "result": "cleared",
        "success": "true",
        "class": "none",
    }
    assert (line["comment"], line["before"], line["after"]) == ("0", "1", "0")
    assert {"plan_calls", "gate_returns", "verify_rounds", "tokens", "seconds"} <= set(line)
    points = otlp.points(ROADMAP_FIX_PLAN_TOTAL.name)
    assert [(attrs["repo"], attrs["result"], value) for attrs, value in points] == [
        (STAGE_REPO, "cleared", 1.0)
    ]


def test_a_failed_plan_run_records_the_attempt_and_writes_nothing_else(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api)
    group = make_stage_proposal().groups[0]
    missing = make_stage_proposal(
        groups=[group.model_copy(update={"changes": [*group.changes, "tests/test_missing.py"]})]
    )
    verifier.answer(Verification(findings=[finding(DefectType.CRITERION_DROPPED)]))
    model_fake.answer(missing)

    with caplog.at_level(logging.INFO):
        run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert run.attempt.result is FixPlanResult.FAILED
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head
    assert _record(store)[FixPlanRecordKey.RESULT] == "failed"
    assert _record(store)[FixPlanRecordKey.ATTEMPTS] == "1"
    assert _comments(store) == []
    (line,) = result_fields(caplog)
    assert (line["result"], line["class"]) == ("failed", "plan_defect")


def test_the_record_counts_a_second_attempt_on_the_same_head(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api)
    verifier.answer(Verification(findings=[finding(DefectType.CRITERION_DROPPED)]))
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    _run(store, stage_repo, verifier)
    _run(store, stage_repo, verifier, now=NOW + timedelta(hours=6))
    third = _run(store, stage_repo, verifier, now=NOW + timedelta(hours=12))

    assert _record(store)[FixPlanRecordKey.ATTEMPTS] == "2"
    assert (third.target, third.attempt) == (None, None)
    assert [left.number for left in third.left_out] == [plan.number]


def test_the_revisions_of_an_earlier_plan_pull_request_do_not_count(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    plan = needs_fix_plan(
        store,
        stage_repo,
        github_api,
        marks={FixPlanRecordKey.KEY: "4:" + "b" * 40, FixPlanRecordKey.REVISIONS: "3"},
    )
    verifier.answer(Verification())

    run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert run.attempt.result is FixPlanResult.CLEARED
    assert FixPlanRecordKey.REVISIONS not in _record(store)
    assert _record(store)[FixPlanRecordKey.KEY] == f"{plan.pull}:{plan.head}"


def test_pull_names_the_one_plan_pull_request_to_judge(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api)

    named = run_fix_plan(
        store, repo=STAGE_REPO, source=stage_repo.clone, confirm=False, pull=plan.pull, now=NOW
    )
    other = run_fix_plan(
        store, repo=STAGE_REPO, source=stage_repo.clone, confirm=False, pull=6, now=NOW
    )

    assert named.target is not None
    assert (named.target.item.number, other.target) == (plan.number, None)
    assert [left.number for left in other.left_out] == [6]
