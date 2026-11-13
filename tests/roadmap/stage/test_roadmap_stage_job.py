"""The `stage` row of the Service's status lane and the stage Job of each item (#2659, #4559).

A round of the row submits one stage Job for each Ready item and counts the items that it leaves
out. The stage Job of an item plans it, writes it, and counts it once by its result. Git runs for
real on a clone with an `origin`, GitHub and the Kubernetes API are faked at their edges.
"""

from __future__ import annotations

import copy
import logging
import re
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
import yaml

from devops_cli.config.constants import CONST_ROADMAP_STATUS_NEW
from devops_cli.exceptions import GitOperationError
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.roadmap import run
from devops_cli.roadmap.refine.refine import NextStep
from devops_cli.roadmap.run import STATUS_LANE_ROWS, FailureLedger, JobOutcome, run_due_jobs
from devops_cli.roadmap.stage.stage import LeftOut, StageApplied, StagePlan, emit_stage_results
from devops_cli.roadmap.stage.stage_change import StageSplit
from devops_cli.roadmap.stage.stage_job import StageJobExit
from devops_cli.roadmap.stores.store import ItemField, RefineRecordKey, StageRecordKey
from devops_cli.telemetry.instruments import ROADMAP_STAGE_TOTAL
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_implement import merge_plan
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    heavy_group,
    no_findings,
    run_stage_jobs,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.kubernetes import FakeCluster
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake
    from tests.support.fakes.otlp import FakeCollector

pytestmark = pytest.mark.usefixtures("keyring_store")

STAGE_ROW = next(row for row in STATUS_LANE_ROWS if row.name == "stage")
OPENED = github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201)
CRONJOBS = ("batch", "v1", "cronjobs")
JOBS = ("batch", "v1", "jobs")


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture(autouse=True)
def valid_openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    for name in ("1-the-job-drops-a-comment", "2-the-job-drops-a-label", "3-the-job-drops-a-tag"):
        openspec_fake.script_sequence(validate_args(name), (0, VALID_REPORT))
    return openspec_fake


@pytest.fixture
def kube(cluster: FakeCluster) -> FakeCluster:
    """The fake cluster with CronJob roadmap-stage of the committed manifest."""
    manifest = yaml.safe_load((REPO_ROOT / "k8s/devops/cronjob-stage.yaml").read_text("utf-8"))
    cluster.custom_objects.objects[CRONJOBS] = [copy.deepcopy(manifest)]
    return cluster


def _round(store: InMemoryRoadmapStore, repo: StageRepo) -> JobOutcome:
    """One round of the row, as the Service runs it in its status clone."""
    return STAGE_ROW.runner(store=store, repo=STAGE_REPO, clone_path=repo.clone)


def _job_items(kube: FakeCluster) -> list[str]:
    """The item of each stage Job that the rounds created."""
    return [
        job["metadata"]["labels"]["roadmap.devops-cli/item"]
        for job in kube.custom_objects.objects.get(JOBS, [])
    ]


def _counted(otlp: FakeCollector) -> list[tuple[str, float]]:
    """Each point of the stage counter as (result, value), by result."""
    return sorted(
        (attrs["result"], value) for attrs, value in otlp.points(ROADMAP_STAGE_TOTAL.name)
    )


def _pushed(repo: StageRepo) -> list[str]:
    return repo.origin_git("branch", "--format=%(refname:short)").split()


# ── The row ───────────────────────────────────────────────────────────────────


def test_a_round_submits_the_job_of_the_item_that_the_settings_name(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    kube: FakeCluster,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_stageable(store)
    store.seed_issue(
        "feat(roadmap): the job drops a label",
        labels=("type/feature",),
        fields={ItemField.STATUS: "Ready", ItemField.PRIORITY: "P1-High"},
    )
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_FILTER", "status=ready,type=feature")

    outcome = _round(store, stage_repo)

    assert (outcome, _job_items(kube), _pushed(stage_repo)) == (
        JobOutcome(queue=1),
        ["2"],
        ["main"],
    )


def test_a_round_with_nothing_to_stage_counts_nothing(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, kube: FakeCluster, otlp: FakeCollector
) -> None:
    assert _round(store, stage_repo) == JobOutcome(queue=0)
    assert (_counted(otlp), _job_items(kube)) == ([], [])


def test_a_round_sets_planned_for_an_item_whose_plan_is_on_the_default_branch(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, kube: FakeCluster
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
    assert (outcome, held.status, _job_items(kube)) == (JobOutcome(queue=1), "Planned", [])


def test_a_round_without_a_clone_fails_naming_the_job(store: InMemoryRoadmapStore) -> None:
    with pytest.raises(GitOperationError, match="stage"):
        STAGE_ROW.runner(store=store, repo=STAGE_REPO, clone_path=None)


POLL_KEY = ("poll", "", "")
FIRST_ROUND = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def test_three_rounds_that_fail_outside_any_item_suspend_the_row(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    seed_stageable(store)

    def outage(*_: Any, **__: Any) -> Any:
        raise GitOperationError("origin is down", operation="fetch")

    monkeypatch.setattr(run, "run_stage_round", outage)
    monkeypatch.setattr(run, "ensure_checkout", lambda *_, **__: stage_repo.clone)
    ledger = FailureLedger()
    outcomes: list[str] = []
    for index in range(3):
        try:
            run_due_jobs(
                STAGE_REPO,
                store,
                batch={POLL_KEY: 1},
                table=(STAGE_ROW,),
                data_dir=tmp_path,
                remote_url=str(stage_repo.origin),
                clone_dirname="clone",
                now=FIRST_ROUND + timedelta(hours=index),
                failures=ledger,
            )
            outcomes.append("ok")
        except Exception as exc:
            outcomes.append(type(exc).__name__)

    assert outcomes == ["RoadmapRunError"] * 3
    assert ledger.causes(STAGE_REPO, "stage") == ("ci_infra",) * 3


# ── The stage Job of each item ────────────────────────────────────────────────


def test_the_job_counts_its_item_with_the_repository(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    otlp: FakeCollector,
) -> None:
    github_api.route("POST", f"/repos/{STAGE_REPO}/pulls", OPENED)
    number = seed_stageable(store)
    no_findings(model_fake)
    model_fake.answer(make_stage_proposal())

    run_stage_jobs(store, stage_repo, number)

    points = otlp.points(ROADMAP_STAGE_TOTAL.name)
    assert len(points) == 1
    attrs, value = points[0]
    assert (attrs["repo"], attrs["result"], value) == (STAGE_REPO, "staged", 1.0)


def test_the_jobs_count_staged_needs_split_failed_and_skipped_items_once_each(
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

    runs = run_stage_jobs(store, stage_repo, 1, 2, 3, 4)

    failed = store.item(3)
    assert failed is not None
    assert (
        [run.exit_code for run in runs],
        failed.job_record[StageRecordKey.FAILED_ERROR],
    ) == (
        [StageJobExit.RESULT, StageJobExit.RESULT, StageJobExit.FAILURE, StageJobExit.RESULT],
        "RoadmapStageError",
    )
    assert _pushed(stage_repo) == ["fix/1-the-job-drops-a-comment", "main"]
    assert _counted(otlp) == [
        ("failed", 1.0),
        ("needs_split", 1.0),
        ("skipped", 1.0),
        ("staged", 1.0),
    ]


NEW_MODULE = "src/devops_cli/roadmap/stage_constants.py"
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
    github_api.route(
        "POST",
        "/graphql",
        github_json(
            {
                "data": {
                    "repository": {
                        "pullRequests": {
                            "nodes": [],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            }
        ),
    )
    open_plan = store.seed_issue(
        "fix(roadmap): add the stage constants",
        body="The stage job reads constants.",
        labels=("type/bug",),
        fields={ItemField.STATUS: "Planned", ItemField.PRIORITY: "P1-High"},
    )
    merge_plan(stage_repo, open_plan, tasks=OPEN_PLAN)
    target = seed_stageable(store, body=f"The job needs `{NEW_MODULE}`.")

    run_stage_jobs(store, stage_repo, target)

    held = store.item(target)
    assert held is not None
    assert model_fake.calls == []
    assert held.status == CONST_ROADMAP_STATUS_NEW
    assert held.job_record[RefineRecordKey.BLOCKED_BY] == str(open_plan)
    assert held.job_record[RefineRecordKey.NEXT_STEP] == NextStep.BLOCKED.value
    assert any(f"#{open_plan}" in comment.body for comment in store.comments_on(target))


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

    run_stage_jobs(store, stage_repo, target)

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
    kube: FakeCluster,
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
    kube: FakeCluster,
    model_fake: ModelFake,
    otlp: FakeCollector,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A default branch with no `openspec/config.yaml` gets no plan (#4629): the round creates no
    stage Job, pushes no branch and calls no model, it records the hold of each item, and its
    outcome names the file for onboarding."""
    stage_repo.untrack("openspec/config.yaml")
    number = seed_stageable(store)

    with caplog.at_level(logging.INFO):
        outcome = _round(store, stage_repo)

    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("stage left out")]
    assert outcome == JobOutcome(missing=("openspec/config.yaml",), queue=1)
    assert (_pushed(stage_repo), _job_items(kube)) == (["main"], [])
    assert model_fake.calls == []
    assert _labelled(otlp) == [("skipped", "no_openspec", 1.0)]
    assert [re.findall(r"(?:item|reason)=(\S+)", line) for line in lines] == [
        [f"#{number}", "no_openspec"]
    ]
    assert "openspec/config.yaml" in lines[0]
