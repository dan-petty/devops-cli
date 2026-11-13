"""The step `fix-plan` repairs an open plan pull request that holds `plan/needs-fix` (#5061).

Git is real in `tmp_path`: the plan branch is on a bare `origin`, and the step pushes to it. The
planner is the model edge of the `stage` task and the verifier a model edge of its own. GitHub's
REST API answers the read of the pull request.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli import __version__
from devops_cli.ai.client.models import AIClientError
from devops_cli.config.constants import CONST_AI_JEV_MODEL, CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER
from devops_cli.exceptions import ServiceStoppingError
from devops_cli.roadmap.run import MODEL_LANE_ROWS
from devops_cli.roadmap.service_stop import begin_service_stop
from devops_cli.roadmap.stage.stage_eval_cases import DefectType
from devops_cli.roadmap.stage.stage_jev_screen import QUESTIONS, VERIFY_SCREEN
from devops_cli.roadmap.stage.stage_toolbox import ToolboxModel
from devops_cli.roadmap.stage.stage_verify import PLAN_NEEDS_FIX_LABEL, Verification
from devops_cli.roadmap.steps.fix_plan import (
    FixPlanResult,
    FixPlanRun,
    render_fix_plan,
    run_fix_plan,
)
from devops_cli.roadmap.stores.store import (
    FixPlanRecordKey,
    ImplementRecordKey,
    ItemField,
)
from devops_cli.telemetry.instruments import ROADMAP_FIX_PLAN_TOTAL
from tests.support.builders import make_stage_proposal
from tests.support.fakes.model import ModelFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.paths import FIXTURES
from tests.support.roadmap_fix_plan import (
    PLAN_BRANCH,
    PLAN_CHANGE,
    PLAN_PATH,
    REPAIRED_WHY,
    SAMPLE_QUOTE,
    finding,
    head_files,
    needs_fix_plan,
    no_open_pulls,
    plan_files,
    planner_requests,
    route_plan_pull,
    stage_comment,
    valid_changes,
)
from tests.support.roadmap_implement import merge_plan
from tests.support.roadmap_job_result import result_fields
from tests.support.roadmap_stage import (
    GONE,
    HOLDS,
    STAGE_REPO,
    StageRepo,
    advance_origin,
    heavy_group,
    later_review,
    route_reviews,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from devops_cli.roadmap.decision_point import DecisionPoint
    from devops_cli.roadmap.stage.stage_change import StageProposal
    from devops_cli.roadmap.stage.stage_jev_screen import ScreenCase
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.jev import JevFake
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
    verifier.answer(Verification(findings=[open_finding]), later_review(GONE))
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
        FixPlanRecordKey.VERSION: __version__,
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
    verifier.answer(Verification(findings=[dropped, order]), later_review(GONE, GONE))
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
    verifier.answer(Verification(findings=[dropped, order]), later_review(HOLDS, GONE))
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


def test_a_revision_that_fixes_the_head_finding_is_kept(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    """The case of Job `fix-plan-validate-4917-r2` (#5409): the review of the revision marks the
    finding of the head `gone` and opens a finding on text that the revision did not change. That
    finding is advice, so the step keeps the revision and the label goes."""
    plan = needs_fix_plan(store, stage_repo, github_api)
    head_finding = finding(DefectType.SPEC_DELTA_WRONG)
    unchanged = finding(DefectType.FALSE_PREMISE, SAMPLE_QUOTE)
    verifier.answer(Verification(findings=[head_finding]), later_review(GONE, findings=[unchanged]))
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert (run.attempt.result, run.attempt.before, run.attempt.after) == (
        FixPlanResult.CLEARED,
        1,
        0,
    )
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) != plan.head
    assert REPAIRED_WHY in _origin_file(stage_repo, "proposal.md")
    assert PLAN_NEEDS_FIX_LABEL not in store._roadmap.issues[plan.pull].labels
    # The review of the revision judged the finding of the head against the changed text.
    later = json.loads(verifier.calls[1].prompt)
    assert later["earlier"][0]["type"] == "spec_delta_wrong"
    assert any(REPAIRED_WHY in block for block in later["answer"])
    assert not any(SAMPLE_QUOTE in block for block in later["answer"])


def test_a_revision_that_is_not_better_writes_nothing_to_github_but_the_record(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api)
    dropped = finding(DefectType.CRITERION_DROPPED)
    verifier.answer(Verification(findings=[dropped]), later_review(HOLDS))
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
        FixPlanRecordKey.VERSION: __version__,
    }


def test_a_clean_head_with_listed_findings_is_dismissed(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api)
    listed = finding(DefectType.CRITERION_DROPPED, where="criteria (criterion 2)")
    store.seed_comment(plan.number, stage_comment(plan.pull, [listed]))
    verifier.answer(Verification())

    with caplog.at_level(logging.INFO):
        run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert (run.attempt.result, run.attempt.before, run.attempt.after) == (
        FixPlanResult.DISMISSED,
        0,
        None,
    )
    assert model_fake.call_count == 0
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head
    assert PLAN_NEEDS_FIX_LABEL not in store._roadmap.issues[plan.pull].labels
    (line,) = result_fields(caplog)
    assert (line["result"], line["success"], line["before"]) == ("dismissed", "false", "0")
    assert "after" not in line
    (_, comment) = _comments(store)
    assert "dismisses" in comment
    assert "criteria (criterion 2)" in comment


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
    verifier.answer(
        Verification(findings=[finding(DefectType.CRITERION_DROPPED)]), later_review(GONE)
    )
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
    route_reviews(
        verifier,
        Verification(findings=[finding(DefectType.CRITERION_DROPPED)]),
        later_review(HOLDS),
    )
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
    assert run.attempt.result is FixPlanResult.DISMISSED
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


def _named(
    store: InMemoryRoadmapStore,
    repo: StageRepo,
    verifier: ModelFake,
    pull: int,
    *,
    confirm: bool = False,
) -> FixPlanRun:
    """A run that names plan pull request `pull` with `skip_wait`, as `--pull <n> --skip-wait`
    gives it (#5413)."""
    return run_fix_plan(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        confirm=confirm,
        pull=pull,
        skip_wait=True,
        now=NOW,
        verifier=ToolboxModel(verifier),
    )


def _mark_head(
    store: InMemoryRoadmapStore, pull: int, head: str, marks: Mapping[str, str | None]
) -> None:
    """Give item #1 the fix-plan marks `marks` on head `head` of plan pull request `pull`."""
    item = store.item(1)
    assert item is not None
    keyed = {FixPlanRecordKey(key): value for key, value in marks.items()}
    store.set_marks(item, {FixPlanRecordKey.KEY: f"{pull}:{head}", **keyed})


def test_skip_wait_selects_a_named_plan_within_the_wait(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api)
    _mark_head(
        store,
        plan.pull,
        plan.head,
        {
            FixPlanRecordKey.ATTEMPTS: "1",
            FixPlanRecordKey.AT: (NOW - timedelta(hours=1)).isoformat(),
        },
    )

    plain = run_fix_plan(
        store, repo=STAGE_REPO, source=stage_repo.clone, confirm=False, pull=plan.pull, now=NOW
    )
    named = _named(store, stage_repo, verifier, plan.pull)

    assert plain.target is None
    assert [left.number for left in plain.left_out] == [plan.number]
    assert named.target is not None
    assert (named.target.pull, named.target.extra, named.left_out) == (plan.pull, "", ())
    assert (model_fake.call_count, verifier.call_count) == (0, 0)


@pytest.mark.parametrize(
    "marks",
    [
        {"fix_plan.attempts": "2", "fix_plan.version": __version__},
        {"fix_plan.revisions": "3"},
    ],
    ids=["attempts", "revisions"],
)
def test_skip_wait_keeps_the_attempt_cap(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    marks: dict[str, str | None],
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api)
    _mark_head(
        store,
        plan.pull,
        plan.head,
        {FixPlanRecordKey.AT: (NOW - timedelta(hours=1)).isoformat(), **marks},
    )

    run = _named(store, stage_repo, verifier, plan.pull, confirm=True)

    assert (run.target, run.attempt) == (None, None)
    assert [left.number for left in run.left_out] == [plan.number]
    assert (model_fake.call_count, verifier.call_count) == (0, 0)
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head


def test_the_row_keeps_the_wait(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
) -> None:
    """The row of the Service names no item and passes no `skip_wait`, so an attempt 1 hour old
    holds the plan, also in mode `on`."""
    plan = needs_fix_plan(store, stage_repo, github_api)
    at = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    _mark_head(store, plan.pull, plan.head, {FixPlanRecordKey.AT: at})
    config(roadmap={"fix_plan": {"mode": "on"}})
    row = next(each for each in MODEL_LANE_ROWS if each.name == "fix_plan")

    row.runner(store=store, repo=STAGE_REPO, clone_path=stage_repo.clone)

    assert model_fake.call_count == 0
    assert github_api.requested == []
    assert _record(store)[FixPlanRecordKey.AT] == at
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head


@pytest.mark.parametrize(
    ("version", "selected"),
    [(None, True), ("0.1.0", True), (__version__, False), ("not a release", False)],
    ids=["no release", "older release", "this release", "unreadable release"],
)
def test_skip_wait_takes_one_more_attempt_on_a_head_of_an_older_release(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    caplog: pytest.LogCaptureFixture,
    version: str | None,
    selected: bool,
) -> None:
    """The record of #5272 held 2 attempts on the head of #5390 from releases before 0.129.1, and
    no `fix_plan.version`. A named run with `skip_wait` takes such a head once more, and logs why."""
    plan = needs_fix_plan(store, stage_repo, github_api)
    _mark_head(
        store,
        plan.pull,
        plan.head,
        {
            FixPlanRecordKey.ATTEMPTS: "2",
            FixPlanRecordKey.AT: (NOW - timedelta(hours=1)).isoformat(),
            FixPlanRecordKey.RESULT: "timeout",
            FixPlanRecordKey.VERSION: version,
        },
    )

    with caplog.at_level(logging.INFO):
        named = _named(store, stage_repo, verifier, plan.pull)
    plain = run_fix_plan(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        confirm=False,
        pull=plan.pull,
        now=NOW + timedelta(hours=6),
    )

    assert (named.target is not None) is selected
    assert plain.target is None
    extra = [
        record.getMessage()
        for record in caplog.records
        if "one more attempt" in record.getMessage()
    ]
    if selected:
        assert named.target is not None
        assert extra == [named.target.extra]
        assert f"#{plan.pull}" in named.target.extra
        assert __version__ in named.target.extra
        assert named.target.extra in render_fix_plan(named).splitlines()
    else:
        assert extra == []
        assert [left.number for left in named.left_out] == [plan.number]


def test_an_attempt_records_its_release(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    needs_fix_plan(store, stage_repo, github_api)
    verifier.answer(Verification())

    run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert _record(store)[FixPlanRecordKey.VERSION] == __version__
    assert _record(store)[FixPlanRecordKey.ATTEMPTS] == "1"


# A group that changes a path that is no file of the default branch and that no group creates: the
# checks refuse a plan with it (`stage_paths`).
MISSING_PATH = "tests/test_missing.py"
# A path that the plan of another open item on the default branch creates (#3418).
NEW_MODULE = "src/devops_cli/roadmap/stage_constants.py"
OPEN_PLAN = f"""\
# Tasks

## 1. The constants

Reads: `src/devops_cli/sample.py`. Changes: `{NEW_MODULE}` (new).

- [ ] Add `{NEW_MODULE}`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_constants.py`
"""
PLAN_HEADS = FIXTURES / "roadmap" / "plan_heads"
COMMENTS = FIXTURES / "roadmap_fix_plan"


def _missing() -> StageProposal:
    """A plan whose group changes `MISSING_PATH`, which the checks refuse."""
    group = make_stage_proposal().groups[0]
    return make_stage_proposal(
        groups=[group.model_copy(update={"changes": [*group.changes, MISSING_PATH]})]
    )


def _attempt_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("The fix-plan attempt")
    ]


def _unreadable_files() -> dict[str, str]:
    """The change folder of a plan whose `behavior` group changes no path under `src/`: the plan
    reader refuses its `tasks.md`, as it refused the heads of #4963 and #5032 before #5205."""
    files = plan_files()
    tasks = f"openspec/changes/{PLAN_CHANGE}/tasks.md"
    files[tasks] = files[tasks].replace(
        "Changes: `src/devops_cli/sample.py`, ", "Changes: `docs/sample.md`, "
    )
    return files


def test_an_unreadable_head_writes_no_result_line_and_uses_no_attempt(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    otlp: FakeCollector,
    caplog: pytest.LogCaptureFixture,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api, files=_unreadable_files())

    with caplog.at_level(logging.INFO):
        run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert run.attempt.result is FixPlanResult.UNREADABLE
    (warning,) = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert "tasks.md" in warning
    assert "changes no path under src/" in warning
    assert f"#{plan.pull}" in warning
    assert result_fields(caplog) == []
    assert (model_fake.call_count, verifier.call_count) == (0, 0)
    assert _record(store) == {
        FixPlanRecordKey.AT: NOW.isoformat(),
        FixPlanRecordKey.RESULT: "unreadable",
    }
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head
    assert PLAN_NEEDS_FIX_LABEL in store._roadmap.issues[plan.pull].labels
    assert _comments(store) == []
    points = otlp.points(ROADMAP_FIX_PLAN_TOTAL.name)
    assert [(attrs["result"], value) for attrs, value in points] == [("unreadable", 1.0)]


def test_an_unreadable_head_waits_six_hours(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api, files=_unreadable_files())

    _run(store, stage_repo, verifier)
    later = _run(store, stage_repo, verifier, now=NOW + timedelta(hours=5))

    assert (later.target, later.attempt) == (None, None)
    assert [left.number for left in later.left_out] == [plan.number]
    assert (model_fake.call_count, verifier.call_count) == (0, 0)


def test_a_failed_repair_keeps_the_findings_of_the_head_review(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api)
    verifier.answer(Verification(findings=[finding(DefectType.CRITERION_DROPPED)]))
    model_fake.answer(_missing())

    with caplog.at_level(logging.INFO):
        run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert (run.attempt.result, run.attempt.before, run.attempt.after) == (
        FixPlanResult.FAILED,
        1,
        None,
    )
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head
    (line,) = result_fields(caplog)
    assert (line["result"], line["class"], line["step"], line["before"]) == (
        "failed",
        "plan_defect",
        "plan",
        "1",
    )
    assert "after" not in line
    (shown,) = _attempt_lines(caplog)
    assert "found 1 open finding(s), and then the step `plan` failed" in shown
    assert "plan_defect" in shown


def test_a_gate_failure_before_the_review_has_no_review_counts(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api, files=plan_files(_missing()))
    model_fake.answer(_missing())

    with caplog.at_level(logging.INFO):
        run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert (run.attempt.result, run.attempt.before, run.attempt.after) == (
        FixPlanResult.FAILED,
        None,
        None,
    )
    assert verifier.call_count == 0
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head
    assert PLAN_NEEDS_FIX_LABEL in store._roadmap.issues[plan.pull].labels
    (line,) = result_fields(caplog)
    assert (line["result"], line["class"], line["step"]) == ("failed", "plan_defect", "gate")
    assert "before" not in line
    assert "after" not in line
    (shown,) = _attempt_lines(caplog)
    assert "the step `gate` failed before the review of the head" in shown


@pytest.mark.parametrize("stop", ["premise", "blocked", "over_budget"])
def test_a_stop_before_the_review_is_stopped_with_its_name(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    config: Callable[..., Path],
    caplog: pytest.LogCaptureFixture,
    stop: str,
) -> None:
    from devops_cli.roadmap.stage.stage_change import StageSplit

    body, files, evidence = None, None, ""
    if stop == "premise":
        stage_repo.track(
            {"src/devops_cli/model.py": "class PullStatus:\n    labels: tuple[str, ...] = ()\n"}
        )
        body = "The class `PullStatus` defines no `labels`."
        evidence = "src/devops_cli/model.py:2"
    elif stop == "blocked":
        body = f"The job needs `{NEW_MODULE}`."
        no_open_pulls(github_api)
    else:
        heavy = heavy_group(stage_repo)
        files = plan_files(make_stage_proposal(groups=[heavy]))
        model_fake.answer(StageSplit(groups=[heavy]))
        config(roadmap={"stage": {"step_tokens": 6000}})
        evidence = "over the budget of 6000 tokens"
    plan = needs_fix_plan(store, stage_repo, github_api, files=files, body=body)
    if stop == "blocked":
        blocker = store.seed_issue(
            "fix(roadmap): add the stage constants",
            fields={ItemField.STATUS: "Planned", ItemField.PRIORITY: "P1-High"},
        )
        merge_plan(stage_repo, blocker, tasks=OPEN_PLAN, slug="add-the-stage-constants")
        evidence = f"#{blocker}"

    with caplog.at_level(logging.INFO):
        run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert (run.attempt.result, run.attempt.before, run.attempt.after) == (
        FixPlanResult.STOPPED,
        None,
        None,
    )
    assert verifier.call_count == 0
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head
    assert PLAN_NEEDS_FIX_LABEL in store._roadmap.issues[plan.pull].labels
    (line,) = result_fields(caplog)
    assert (line["result"], line["stop"], line["success"]) == ("stopped", stop, "false")
    assert line["class"] == ("premise_false" if stop == "premise" else "none")
    assert "before" not in line
    item = store.item(plan.number)
    assert item is not None
    assert item.status == "Ready"
    (comment,) = _comments(store)
    assert CONST_ROADMAP_FIX_PLAN_COMMENT_MARKER in comment
    assert evidence in comment


def test_a_gated_plan_is_pushed_when_the_repair_fails(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api, files=plan_files(_missing()))
    verifier.answer(Verification(findings=[finding(DefectType.CRITERION_DROPPED)]))
    model_fake.answer(
        make_stage_proposal(why=REPAIRED_WHY), AIClientError("gateway returned 502", status=502)
    )

    with caplog.at_level(logging.INFO):
        run = _run(store, stage_repo, verifier)

    head = stage_repo.origin_git("rev-parse", PLAN_BRANCH)
    assert run.attempt is not None
    assert (run.attempt.result, run.attempt.before, run.attempt.head) == (
        FixPlanResult.REGATED,
        1,
        head,
    )
    assert head != plan.head
    assert stage_repo.origin_git("rev-parse", f"{PLAN_BRANCH}^") == stage_repo.origin_git(
        "rev-parse", "main"
    )
    assert MISSING_PATH not in _origin_file(stage_repo, "tasks.md")
    assert PLAN_NEEDS_FIX_LABEL in store._roadmap.issues[plan.pull].labels
    (line,) = result_fields(caplog)
    assert (line["result"], line["class"], line["success"], line["before"]) == (
        "regated",
        "provider",
        "false",
        "1",
    )
    assert _record(store)[FixPlanRecordKey.KEY] == f"{plan.pull}:{head}"
    (comment,) = _comments(store)
    assert "Problem of criterion_dropped." in comment


def test_a_gated_plan_that_differs_is_pushed_after_a_clean_review(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    tmp_path: Path,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api, files=plan_files(_missing()))
    advance_origin(stage_repo, tmp_path, {"NEWS.md": "main moved\n"})
    verifier.answer(Verification())
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    run = _run(store, stage_repo, verifier)

    head = stage_repo.origin_git("rev-parse", PLAN_BRANCH)
    assert run.attempt is not None
    assert (run.attempt.result, run.attempt.before, run.attempt.after) == (
        FixPlanResult.REGATED,
        0,
        None,
    )
    assert head != plan.head
    assert stage_repo.origin_git("rev-parse", f"{PLAN_BRANCH}^") == stage_repo.origin_git(
        "rev-parse", "main"
    )
    assert REPAIRED_WHY in _origin_file(stage_repo, "proposal.md")
    assert PLAN_NEEDS_FIX_LABEL not in store._roadmap.issues[plan.pull].labels
    assert _record(store)[FixPlanRecordKey.RESULT] == "regated"
    assert _record(store)[FixPlanRecordKey.REVISIONS] == "1"
    (comment,) = _comments(store)
    assert "The checks refused the plan of the old head" in comment
    assert "loses the label" in comment


def test_a_repair_that_returns_the_same_plan_is_unchanged(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    plan = needs_fix_plan(store, stage_repo, github_api)
    verifier.answer(
        Verification(findings=[finding(DefectType.CRITERION_DROPPED)]), later_review(GONE)
    )
    model_fake.answer(make_stage_proposal())

    with caplog.at_level(logging.INFO):
        run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert (run.attempt.result, run.attempt.before, run.attempt.after) == (
        FixPlanResult.UNCHANGED,
        1,
        0,
    )
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) == plan.head
    assert PLAN_NEEDS_FIX_LABEL in store._roadmap.issues[plan.pull].labels
    (line,) = result_fields(caplog)
    assert (line["result"], line["success"], line["before"], line["after"]) == (
        "unchanged",
        "false",
        "1",
        "0",
    )
    assert _comments(store) == []


@pytest.fixture
def screen_point(tmp_path: Path) -> DecisionPoint[ScreenCase]:
    """The point of the screen with cuts of 0.3 and 0.8 for each question, so a Jev answer of a
    clear no gives the band `continue`."""
    path = tmp_path / "cuts.json"
    path.write_text(
        json.dumps(
            {
                "step": "stage.verify_screen",
                "model": CONST_AI_JEV_MODEL,
                "fitted": "2026-11-10",
                "cases": 2,
                "cuts": {name: {"continue_below": 0.3, "flag_at": 0.8} for name in QUESTIONS},
                "report": {},
            }
        ),
        encoding="utf-8",
    )
    return replace(VERIFY_SCREEN, cuts=path)


def test_the_head_review_does_not_take_the_screen(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    jev: JevFake,
    screen_point: DecisionPoint[ScreenCase],
) -> None:
    from devops_cli.roadmap.decision_point import Mode, ResolverChain

    plan = needs_fix_plan(store, stage_repo, github_api)
    verifier.answer(Verification(findings=[finding(DefectType.CRITERION_DROPPED)]))
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))
    screen = ResolverChain(screen_point, Mode.ON, model_name=CONST_AI_JEV_MODEL, model=jev.model)

    run = run_fix_plan(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        confirm=True,
        now=NOW,
        verifier=ToolboxModel(verifier),
        screen=screen,
    )

    assert run.attempt is not None
    assert (verifier.call_count, run.attempt.before) == (1, 1)
    assert len(jev.requests) == 1
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) != plan.head


def _replay(
    store: InMemoryRoadmapStore,
    repo: StageRepo,
    api: GitHubApiFake,
    openspec: OpenSpecFake,
    head: str,
    comment: str,
) -> int:
    """Push the real change folder of the plan head `head` as the plan of item #1, seed the real
    stage comment `comment` with its pull request renamed to #5, and answer each validation of the
    change; the plan pull request."""
    (folder,) = (PLAN_HEADS / head).iterdir()
    files = head_files(folder)
    plan = needs_fix_plan(store, repo, api, files=files)
    change = next(iter(files)).split("/")[2]
    valid_changes(openspec, change=change)
    text = (COMMENTS / comment).read_text(encoding="utf-8")
    pull = int(text.split("draft pull request #", 1)[1].split(".", 1)[0])
    store.seed_comment(plan.number, text.replace(f"#{pull}", f"#{plan.pull}"))
    return plan.pull


def test_the_replay_of_4917_is_regated_with_a_push(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    openspec: OpenSpecFake,
) -> None:
    """The head of #4917 (ba8cc66fd2f4) and the stage comment of #4472: the checks refuse the
    head, the planner writes a plan that they pass, and its review is clean. On 2026-11-12 the
    attempt ended `cleared` with no push, and the branch kept the refused plan."""
    pull = _replay(
        store, stage_repo, github_api, openspec, "4917-ba8cc66fd2f4", "stage_comment_4472.txt"
    )
    before = stage_repo.origin_git("rev-parse", PLAN_BRANCH)
    verifier.answer(Verification())
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert (run.attempt.result, run.attempt.comment) == (FixPlanResult.REGATED, 1)
    assert stage_repo.origin_git("rev-parse", PLAN_BRANCH) != before
    assert PLAN_NEEDS_FIX_LABEL not in store._roadmap.issues[pull].labels


@pytest.mark.parametrize(
    ("head", "comment", "listed"),
    [
        ("4963-9c4b2cf75c64", "stage_comment_2968.txt", 2),
        ("5032-7fd165f69611", "stage_comment_4697.txt", 1),
    ],
)
def test_the_replay_of_a_head_that_the_reader_refused_reads_and_reviews(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    verifier: ModelFake,
    github_api: GitHubApiFake,
    openspec: OpenSpecFake,
    head: str,
    comment: str,
    listed: int,
) -> None:
    """The heads of #4963 and #5032 with the stage comments of #2968 and #4697. On 2026-11-12 the
    reader refused both heads, and the attempt on #4963 logged a review that did not run."""
    _replay(store, stage_repo, github_api, openspec, head, comment)
    verifier.answer(Verification())
    model_fake.answer(make_stage_proposal(why=REPAIRED_WHY))

    run = _run(store, stage_repo, verifier)

    assert run.attempt is not None
    assert run.attempt.comment == listed
    assert run.attempt.result.value not in {"failed", "unreadable"}
    assert verifier.call_count == 1
