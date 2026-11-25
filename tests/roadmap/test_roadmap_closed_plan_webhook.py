"""The two rows that a closed plan pull request makes due (#4414): the `implement` row of a plan
that a person merged, which syncs `status/planned` and submits the runner Job, and the `stage` row
of a plan that a person closed with no merge, which records `stage.rejected`, comments the reason,
deletes the session-only branch and returns the item to New.

Each round is the round that the closed delivery starts: every row of the due table is stamped as
a success, so only the rows that declare `("webhook", "pull_request", "closed")` are due. Git runs
for real on the clone of `stage_repo`, GitHub and the Kubernetes API are faked at their edges, and
the CronJob templates are built by `tests/support/job_templates.py`, so a test reads no committed
manifest.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.k8s.cluster_job import ITEM_LABEL, RUNNER_TEMPLATE, STAGE_TEMPLATE
from devops_cli.roadmap.run import DEFAULT_DUE_TABLE, JobOutcome, JobRow, build_stub_table
from devops_cli.roadmap.stage.stage_rejected import recorded_rejection
from devops_cli.roadmap.stores.store import (
    ChangeKind,
    ImplementRecordKey,
    Item,
    ItemField,
    StageRecordKey,
)
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.kubernetes import FakeCluster
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.job_templates import cronjob_template
from tests.support.roadmap_implement import PULL, branch_of, merge_plan, seed_staged
from tests.support.roadmap_run import NOW, poll_round, stamp_successes
from tests.support.roadmap_stage import STAGE_REPO, StageRepo

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake

pytestmark = pytest.mark.usefixtures("keyring_store", "app_slug")

IMPLEMENT_ROW = next(row for row in DEFAULT_DUE_TABLE if row.name == "implement")
STAGE_ROW = next(row for row in DEFAULT_DUE_TABLE if row.name == "stage")
ROWS = tuple(row.name for row in DEFAULT_DUE_TABLE)
# The batch key of the closed plan pull request that this change adds to the two rows.
CLOSED = ("webhook", "pull_request", "closed")
CRONJOBS = ("batch", "v1", "cronjobs")
RUNNER_JOB = "devops-cli-implement-"
# The number of the pull request of the closed delivery that no open item records.
UNRELATED_PULL = 99
CLOSED_AT = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
# A reason of more than `EVIDENCE_MIN_CHARS` characters, so that it is a reason of a rejection.
REASON = (
    "The plan adds a second watcher of the same file, and the watcher of the item that closed last "
    "week already holds that state, so this plan repeats the work and the tests of that item."
)


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def kube(cluster: FakeCluster) -> FakeCluster:
    """The fake cluster with the two CronJob templates that the rows read, built by the test."""
    cluster.custom_objects.objects[CRONJOBS] = [
        cronjob_template(RUNNER_TEMPLATE),
        cronjob_template(STAGE_TEMPLATE),
    ]
    return cluster


def _held(store: InMemoryRoadmapStore, number: int) -> Item:
    item = store.item(number)
    assert item is not None
    return item


def _creates(cluster: FakeCluster) -> list[dict[str, Any]]:
    """The body of each custom object that the round created."""
    return [
        call[1]["body"]
        for call in cluster.custom_objects.calls
        if call[0] == "create_namespaced_custom_object"
    ]


def _branches(repo: StageRepo) -> list[str]:
    """The branches of `origin`."""
    return sorted(repo.origin_git("branch", "--format=%(refname:short)").split())


def _comments(store: InMemoryRoadmapStore, number: int) -> list[str]:
    return [comment.body for comment in store.comments_on(number)]


def _status_labels(store: InMemoryRoadmapStore, number: int) -> list[str | None]:
    """The `status/*` labels that the writes of the round put on issue `number`, oldest first."""
    return [
        change.label
        for change in store.label_changes(number)
        if change.kind is ChangeKind.LABELED and (change.label or "").startswith("status/")
    ]


def _row_runner(
    row: JobRow, store: InMemoryRoadmapStore, repo: StageRepo
) -> Callable[..., JobOutcome]:
    """The runner of `row`, on the clone of the test, as the Service runs it in its lane."""

    def run_row(**_: Any) -> JobOutcome:
        return row.runner(store=store, repo=STAGE_REPO, clone_path=repo.clone)

    return run_row


def _closed_round(
    store: InMemoryRoadmapStore, repo: StageRepo, tmp_path: Path, *rows: JobRow
) -> tuple[str, ...]:
    """The rows that the closed batch starts: each of `rows` runs on the clone of the test, and
    every other row is stamped as a success of its interval, so the batch makes only these due."""
    stamp_successes(tmp_path, **{name: NOW for name in ROWS})
    table = build_stub_table({row.name: _row_runner(row, store, repo) for row in rows})
    return poll_round(store, tmp_path, table=table, batch={CLOSED: 1})


def _staged(store: InMemoryRoadmapStore) -> tuple[int, int]:
    """A staged item and its open plan pull request, whose record names that pull request."""
    number = seed_staged(store)
    branch = branch_of(number)
    pull = store.seed_pull("docs(spec): plan #1 the job drops a comment", head_ref=branch)
    store.set_marks(_held(store, number), {StageRecordKey.PR: str(pull)})
    return number, pull


def _pull_state(api: GitHubApiFake, *, merged: bool, pull: int, branch: str) -> None:
    """Answer the read of the plan pull request `pull` that closed with `merged`."""
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/pulls/{pull}",
        github_json(
            {
                "state": "closed",
                "merged": merged,
                "draft": False,
                "closed_at": CLOSED_AT.isoformat(),
                "head": {"ref": branch, "sha": ""},
            }
        ),
    )


def test_a_merged_plan_sets_planned_and_submits_one_job(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    kube: FakeCluster,
    tmp_path: Path,
) -> None:
    """A closed plan pull request that a person merged makes the `implement` row of the closed
    batch set `status/planned` and create one runner Job for the item (#4414). The Job holds the
    item, so its label is `status/in-progress` once the round has recorded the Job."""
    number = seed_staged(store)
    store.set_field(_held(store, number), ItemField.STATUS, "Ready")
    merge_plan(stage_repo, number)
    _pull_state(github_api, merged=True, pull=PULL, branch=branch_of(number))

    ran = _closed_round(store, stage_repo, tmp_path, IMPLEMENT_ROW)

    (job,) = _creates(kube)
    record = _held(store, number).job_record
    assert (
        ran,
        _status_labels(store, number),
        job["metadata"]["name"].startswith(RUNNER_JOB),
        job["metadata"]["labels"][ITEM_LABEL],
        record.get(ImplementRecordKey.JOB) == job["metadata"]["name"],
    ) == (
        ("implement",),
        ["status/planned", "status/in-progress"],
        True,
        str(number),
        True,
    )


def test_an_unmerged_plan_records_the_rejection(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    github_api: GitHubApiFake,
    kube: FakeCluster,
    tmp_path: Path,
) -> None:
    """A closed plan pull request that no person merged makes the `stage` row of the closed batch
    record `stage.rejected`, comment the reason, delete the session-only branch and set
    `status/new` (#4414)."""
    number, pull = _staged(store)
    branch = branch_of(number)
    store.seed_comment(pull, REASON, author_association="OWNER", author_login="alice")
    _pull_state(github_api, merged=False, pull=pull, branch=branch)

    ran = _closed_round(store, staged_repo, tmp_path, STAGE_ROW)

    item = _held(store, number)
    rejected = recorded_rejection(item)
    assert rejected is not None
    assert (ran, item.status, rejected.pull, branch in _branches(staged_repo)) == (
        ("stage",),
        "New",
        pull,
        False,
    )
    newest = _comments(store, number)[-1]
    assert (REASON[:40] in newest, len(_creates(kube))) == (True, 0)


def test_a_closed_pull_request_of_no_item_changes_nothing(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    kube: FakeCluster,
    model_fake: ModelFake,
    tmp_path: Path,
) -> None:
    """A closed pull request that no open item records leaves every item as it is, creates no Job
    and calls no model (#4414). The round reads no state of pull request `UNRELATED_PULL`, since
    no item records it."""
    number = store.seed_issue(
        "fix(roadmap): a plan that waits for a person",
        fields={ItemField.STATUS: "Blocked", ItemField.PRIORITY: "P1-High"},
    )
    _pull_state(github_api, merged=False, pull=UNRELATED_PULL, branch="main")

    ran = _closed_round(store, stage_repo, tmp_path, IMPLEMENT_ROW, STAGE_ROW)

    assert (
        ran,
        store.job_writes(),
        _creates(kube),
        _comments(store, number),
        model_fake.call_count,
        [request for request in github_api.sent if f"/pulls/{UNRELATED_PULL}" in str(request.url)],
    ) == (("implement", "stage"), [], [], [], 0, [])
