"""The `stage` row of the Service's model lane: a round plans with the settings, writes, counts
each item once by its result, and fails for the items that failed (#2659)."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.ai.client.models import AIClientError
from devops_cli.config.constants import CONST_ROADMAP_STATUS_NEW
from devops_cli.exceptions import GitOperationError
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.roadmap import run
from devops_cli.roadmap.refine.refine import NextStep
from devops_cli.roadmap.run import MODEL_LANE_ROWS, FailureLedger, JobOutcome, run_due_jobs
from devops_cli.roadmap.stage.stage import LeftOut, StageApplied, StagePlan, emit_stage_results
from devops_cli.roadmap.stage.stage_change import StageSplit
from devops_cli.roadmap.stage.stage_verify import Verification
from devops_cli.roadmap.stores.store import ItemField, RefineRecordKey, StageRecordKey
from devops_cli.telemetry.instruments import ROADMAP_STAGE_TOTAL
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_implement import merge_plan
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    heavy_group,
    no_findings,
    seed_stageable,
    validate_args,
)
from tests.support.scripted_model import Script, call
from tests.support.write_stops import stop_after_each_write

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake
    from tests.support.fakes.otlp import FakeCollector

pytestmark = pytest.mark.usefixtures("keyring_store")

STAGE_ROW = next(row for row in MODEL_LANE_ROWS if row.name == "stage")
OPENED = github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture(autouse=True)
def valid_openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    for name in ("1-the-job-drops-a-comment", "2-the-job-drops-a-label", "3-the-job-drops-a-tag"):
        openspec_fake.script_sequence(validate_args(name), (0, VALID_REPORT))
    return openspec_fake


def _round(store: InMemoryRoadmapStore, repo: StageRepo) -> JobOutcome:
    """One round of the row, as the Service runs it in its model clone."""
    return STAGE_ROW.runner(store=store, repo=STAGE_REPO, clone_path=repo.clone)


def _counted(otlp: FakeCollector) -> list[tuple[str, float]]:
    """Each point of the stage counter as (result, value), by result."""
    return sorted(
        (attrs["result"], value) for attrs, value in otlp.points(ROADMAP_STAGE_TOTAL.name)
    )


def _pushed(repo: StageRepo) -> list[str]:
    return repo.origin_git("branch", "--format=%(refname:short)").split()


def test_the_row_follows_retitle_before_refine_runs_on_a_clone_and_is_due_every_37_minutes() -> (
    None
):
    """The stage row runs after retitle and before refine, so a new pod's first round stages
    first; a refine that set an item Ready makes it due through `stage_due`, not in the same
    round (#2659, #4796)."""
    names = [row.name for row in MODEL_LANE_ROWS]
    assert (
        names[names.index("retitle") + 1],
        names[names.index("stage") + 1],
        STAGE_ROW.needs_clone,
        STAGE_ROW.first_run_due,
        STAGE_ROW.interval,
        STAGE_ROW.cross_job_predicate,
    ) == ("stage", "refine", True, True, timedelta(minutes=37), None)


def test_a_round_stages_the_items_the_settings_name_and_counts_each_once(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    otlp: FakeCollector,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    github_api.route("POST", f"/repos/{STAGE_REPO}/pulls", OPENED)
    seed_stageable(store)
    store.seed_issue(
        "feat(roadmap): the job drops a label",
        labels=("type/feature",),
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_FILTER", "status=ready,type=feature")
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_LIMIT", "1")
    no_findings(model_fake)
    model_fake.answer(make_stage_proposal())

    outcome = _round(store, stage_repo)

    assert outcome == JobOutcome()
    assert _pushed(stage_repo) == ["feat/2-the-job-drops-a-label", "main"]
    assert _counted(otlp) == [("staged", 1.0)]


def test_stage_total_metric_carries_repo_attribute(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    monkeypatch: pytest.MonkeyPatch,
    otlp: FakeCollector,
) -> None:
    github_api.route("POST", f"/repos/{STAGE_REPO}/pulls", OPENED)
    seed_stageable(store)
    no_findings(model_fake)
    model_fake.answer(make_stage_proposal())

    _round(store, stage_repo)

    points = otlp.points(ROADMAP_STAGE_TOTAL.name)
    assert len(points) == 1
    attrs, value = points[0]
    assert attrs["repo"] == STAGE_REPO
    assert attrs["result"] == "staged"
    assert value == 1.0


def test_a_round_plans_with_the_model_of_the_stage_task_as_a_toolbox_model(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    github_api.route("POST", f"/repos/{STAGE_REPO}/pulls", OPENED)
    seed_stageable(store)
    script = Script(call("read_file", path="src/devops_cli/sample.py"), make_stage_proposal())
    review = Script(Verification())
    models = {"stage": script, "verification": review}
    tasks: list[str] = []

    def task_model(task: str) -> Any:
        tasks.append(task)
        return models[task].model()

    monkeypatch.setattr(run, "get_task_model", task_model)

    outcome = _round(store, stage_repo)

    assert (outcome, tasks, script.tools_offered[0][:2], review.tools_offered[0][:1]) == (
        JobOutcome(),
        ["stage", "verification"],
        ["list_files", "read_file"],
        ["list_files"],
    )
    assert _pushed(stage_repo) == ["fix/1-the-job-drops-a-comment", "main"]


def test_a_round_counts_staged_needs_split_failed_and_skipped_items_once_each(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    otlp: FakeCollector,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    github_api.route("POST", f"/repos/{STAGE_REPO}/pulls", OPENED)
    seed_stageable(store)
    seed_stageable(store, "fix(roadmap): the job drops a label")
    seed_stageable(store, "fix(roadmap): the job drops a tag")
    seed_stageable(store, "wip: no type")
    heavy = heavy_group(stage_repo)
    stuck = make_stage_proposal(groups=[heavy])
    no_findings(model_fake)
    model_fake.answer(
        make_stage_proposal(),
        stuck,
        StageSplit(groups=[heavy]),
        make_stage_proposal(pull_request_body="Closes #12 when it merges."),
    )
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_STEP_TOKENS", "6000")
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_LIMIT", "4")

    outcome = _round(store, stage_repo)

    failed = store.item(3)
    assert failed is not None
    assert (outcome, failed.job_record[StageRecordKey.FAILED_ERROR]) == (
        JobOutcome(),
        "RoadmapStageError",
    )
    assert _pushed(stage_repo) == ["fix/1-the-job-drops-a-comment", "main"]
    assert _counted(otlp) == [
        ("failed", 1.0),
        ("needs_split", 1.0),
        ("skipped", 1.0),
        ("staged", 1.0),
    ]


def test_a_round_with_nothing_to_stage_counts_nothing(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, otlp: FakeCollector
) -> None:
    assert _round(store, stage_repo) == JobOutcome()
    assert _counted(otlp) == []


def test_a_round_sets_planned_for_an_item_whose_plan_is_on_the_default_branch(
    store: InMemoryRoadmapStore, stage_repo: StageRepo
) -> None:
    """The round reads the plans once for its selection and for the Status of the items (#2920)."""
    number = seed_stageable(store)
    item = store.item(number)
    assert item is not None
    store.set_field(item, ItemField.STATUS, "Ready")
    merge_plan(stage_repo, number)

    outcome = _round(store, stage_repo)

    held = store.item(number)
    assert held is not None
    assert (outcome, held.status) == (JobOutcome(), "Planned")


def test_a_round_without_a_clone_fails_naming_the_job(store: InMemoryRoadmapStore) -> None:
    with pytest.raises(GitOperationError, match="stage"):
        STAGE_ROW.runner(store=store, repo=STAGE_REPO, clone_path=None)


# ── The ledger of the row (#3493) ─────────────────────────────────────────────

POLL_KEY = ("poll", "", "")
FIRST_ROUND = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
LABELS = ("comment", "label", "tag", "note", "mark", "flag")


def _seed_six(store: InMemoryRoadmapStore, openspec: OpenSpecFake) -> None:
    """Six Ready items, #1 to #6, and the valid validation of each change."""
    for word in LABELS:
        number = seed_stageable(store, f"fix(roadmap): the job drops a {word}")
        openspec.script_sequence(
            validate_args(f"{number}-the-job-drops-a-{word}"), (0, VALID_REPORT)
        )


def _about(number: int) -> Any:
    return lambda prompt: _item_number(prompt) == number


def _item_number(prompt: str) -> int | None:
    try:
        return json.loads(prompt).get("number")
    except ValueError:
        return None


def _rounds(
    store: InMemoryRoadmapStore,
    repo: StageRepo,
    ledger: FailureLedger,
    data_dir: Any,
    count: int,
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    """Run `count` rounds of the row as the Service does, in order; the outcome of each:
    `ok` or the class of its error. The clone of the row is the repository's clone."""
    outcomes: list[str] = []
    monkeypatch.setattr(run, "ensure_checkout", lambda *_, **__: repo.clone)
    for index in range(count):
        try:
            run_due_jobs(
                STAGE_REPO,
                store,
                batch={POLL_KEY: 1},
                table=(STAGE_ROW,),
                data_dir=data_dir,
                remote_url=str(repo.origin),
                clone_dirname="model-clone",
                now=FIRST_ROUND + timedelta(hours=index),
                failures=ledger,
            )
            outcomes.append("ok")
        except Exception as exc:
            outcomes.append(type(exc).__name__)
    return outcomes


def test_three_rounds_that_fail_one_item_while_another_stages_do_not_suspend_the_row(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    github_api.route("POST", f"/repos/{STAGE_REPO}/pulls", OPENED)
    _seed_six(store, openspec_fake)
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_LIMIT", "2")
    no_findings(model_fake)
    for number in (1, 3, 5):
        model_fake.route_error(_about(number), AIClientError("the model is down"))
    for number in (2, 4, 6):
        model_fake.route(_about(number), make_stage_proposal())
    ledger = FailureLedger()

    outcomes = _rounds(store, stage_repo, ledger, tmp_path, 3, monkeypatch)

    assert (
        outcomes,
        ledger.suspended(STAGE_REPO, "stage", "any", FIRST_ROUND),
        ledger.causes(STAGE_REPO, "stage"),
    ) == (
        ["ok"] * 3,
        False,
        (),
    )
    held = [store.item(number) for number in (1, 3, 5)]
    assert [item.job_record[StageRecordKey.FAILED_ERROR] for item in held if item] == [
        "AIClientError"
    ] * 3


def test_three_rounds_that_try_items_and_plan_none_suspend_the_row(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    _seed_six(store, openspec_fake)
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_LIMIT", "1")
    model_fake.answer(AIClientError("the model is down"))
    ledger = FailureLedger(limit=3)

    outcomes = _rounds(store, stage_repo, ledger, tmp_path, 3, monkeypatch)

    assert outcomes == ["RoadmapRunError"] * 3
    assert ledger.causes(STAGE_REPO, "stage") == ("plan_defect",) * 3


def test_three_rounds_that_fail_outside_any_item_suspend_the_row(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    openspec_fake: OpenSpecFake,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    _seed_six(store, openspec_fake)

    def outage(*_: Any, **__: Any) -> Any:
        raise GitOperationError("origin is down", operation="fetch")

    monkeypatch.setattr(run, "plan_stage", outage)
    ledger = FailureLedger()

    outcomes = _rounds(store, stage_repo, ledger, tmp_path, 3, monkeypatch)

    assert outcomes == ["RoadmapRunError"] * 3
    assert ledger.causes(STAGE_REPO, "stage") == ("ci_infra",) * 3


NEW_MODULE = "src/devops_cli/roadmap/stage_constants.py"
# The GraphQL answer of a repository with no open pull request.
NO_OPEN_PULLS = {
    "data": {
        "repository": {
            "pullRequests": {
                "nodes": [],
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }
        }
    }
}
OPEN_PLAN = f"""\
# Tasks

## 1. The constants

Reads: `src/devops_cli/shout.py`. Changes: `{NEW_MODULE}` (new).

- [ ] Add `{NEW_MODULE}`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_stage_constants.py`
"""


def test_dependency_returns_item_without_model_call(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    """An item that cites a path which an open plan creates goes back to New with that plan's
    item in `refine.blocked_by`, and the round makes no model call (#3418)."""
    get_github_rate_limiter().update_quota(
        "graphql", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0
    )
    github_api.route("POST", "/graphql", github_json(NO_OPEN_PULLS))
    open_plan = store.seed_issue(
        "fix(roadmap): add the stage constants",
        body="The stage job reads constants.",
        labels=("type/bug",),
        fields={ItemField.STATUS: "Planned", ItemField.PRIORITY: "P1-High"},
    )
    merge_plan(stage_repo, open_plan, tasks=OPEN_PLAN)
    target = seed_stageable(store, body=f"The job needs `{NEW_MODULE}`.")

    _round(store, stage_repo)

    held = store.item(target)
    assert held is not None
    assert model_fake.calls == []
    assert held.status == CONST_ROADMAP_STATUS_NEW
    assert held.job_record[RefineRecordKey.BLOCKED_BY] == str(open_plan)
    assert held.job_record[RefineRecordKey.NEXT_STEP] == NextStep.BLOCKED.value
    assert any(f"#{open_plan}" in comment.body for comment in store.comments_on(target))


def test_a_stop_after_each_write_of_a_dependency_return_posts_no_second_comment(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
) -> None:
    """The return of an item to New writes its comment, then its Status. A stop of the Service
    after either write leaves the next round no second comment to post (ADR 0021, #4793)."""
    get_github_rate_limiter().update_quota(
        "graphql", remaining=5000, limit=5000, reset_epoch=time.time() + 600.0
    )
    github_api.route("POST", "/graphql", github_json(NO_OPEN_PULLS))
    open_plan = store.seed_issue(
        "fix(roadmap): add the stage constants",
        body="The stage job reads constants.",
        labels=("type/bug",),
        fields={ItemField.STATUS: "Planned", ItemField.PRIORITY: "P1-High"},
    )
    merge_plan(stage_repo, open_plan, tasks=OPEN_PLAN)
    seed_stageable(store, body=f"The job needs `{NEW_MODULE}`.")

    replay = stop_after_each_write(store, lambda copied: _round(copied, stage_repo))

    assert (
        replay.whole,
        [(run.at, run.again) for run in replay.runs],
        replay.extra_comments(),
        model_fake.calls,
    ) == (("comment", "set_field"), [(1, ("set_field",)), (2, ())], [], [])


def test_a_false_field_absence_returns_the_item_without_model_call(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
) -> None:
    """An item whose body says a class defines no field that the staging commit defines goes back
    to New with the probe line, and the round makes no model call (#3406)."""
    stage_repo.track(
        {"src/devops_cli/model.py": "class PullStatus:\n    labels: tuple[str, ...] = ()\n"}
    )
    target = seed_stageable(store, body="The class `PullStatus` defines no `labels`.")

    _round(store, stage_repo)

    held = store.item(target)
    assert held is not None
    assert model_fake.calls == []
    assert held.status == CONST_ROADMAP_STATUS_NEW
    assert held.job_record[RefineRecordKey.NEXT_STEP] == NextStep.EDIT.value
    assert any(
        "defines the field `labels` at src/devops_cli/model.py:2" in comment.body
        for comment in store.comments_on(target)
    )


def _labelled(otlp: FakeCollector) -> list[tuple[str, str, float]]:
    """Each point of the stage counter as (result, reason, value), sorted."""
    return sorted(
        (attrs["result"], attrs["reason"], value)
        for attrs, value in otlp.points(ROADMAP_STAGE_TOTAL.name)
    )


def test_a_skipped_item_counts_under_the_kind_of_its_reason(otlp: FakeCollector) -> None:
    """A left-out, returned or rejected item names its reason; another result has none (#4521)."""
    from devops_cli.roadmap.stage.stage_left_out import LeftOutKind

    plan = StagePlan(STAGE_REPO, left_out=(LeftOut(1, "", kind=LeftOutKind.TITLE_TYPE),))

    emit_stage_results(plan, StageApplied(staged=(2,), returned=(3,), rejected=(4,)), STAGE_REPO)

    assert _labelled(otlp) == [
        ("skipped", "rejected", 1.0),
        ("skipped", "returned", 1.0),
        ("skipped", "title_type", 1.0),
        ("staged", "none", 1.0),
    ]


def test_a_round_logs_the_reason_of_a_left_out_item_once_until_it_changes(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    otlp: FakeCollector,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Three rounds leave one item out; the third for another reason (#4521). Each round counts
    the item, and only a new reason writes a log line."""
    number = seed_stageable(store, "security(roadmap): the job drops a comment")

    with caplog.at_level(logging.INFO):
        _round(store, stage_repo)
        _round(store, stage_repo)
        store.add_label(number, "needs-split")
        _round(store, stage_repo)

    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("stage left out")]
    assert [re.findall(r"(?:item|reason)=(\S+)", line) for line in lines] == [
        [f"#{number}", "title_type"],
        [f"#{number}", "needs_split"],
    ]
    assert _labelled(otlp) == [("skipped", "needs_split", 1.0), ("skipped", "title_type", 2.0)]


def test_a_round_in_a_repository_without_openspec_holds_each_item_and_reports_the_file(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    otlp: FakeCollector,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A default branch with no `openspec/config.yaml` gets no plan (#4629): the round pushes no
    branch and calls no model, it records the hold of each item, and its outcome names the file
    for onboarding."""
    stage_repo.untrack("openspec/config.yaml")
    number = seed_stageable(store)

    with caplog.at_level(logging.INFO):
        outcome = _round(store, stage_repo)

    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("stage left out")]
    assert outcome == JobOutcome(missing=("openspec/config.yaml",))
    assert _pushed(stage_repo) == ["main"]
    assert model_fake.calls == []
    assert _labelled(otlp) == [("skipped", "no_openspec", 1.0)]
    assert [re.findall(r"(?:item|reason)=(\S+)", line) for line in lines] == [
        [f"#{number}", "no_openspec"]
    ]
    assert "openspec/config.yaml" in lines[0]
