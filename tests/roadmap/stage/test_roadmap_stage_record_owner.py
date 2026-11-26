"""`devops roadmap stage`: a round replaces a record that was written for another issue, and takes
a recorded pull request or branch as the one of an item only with proof (#7347).

A person can transfer an issue to another repository, and the issue keeps its body with the record
block of the repository that it left. The store reads such a block as an empty record, and the
round replaces it with one write. A row also proves each recorded name before it writes: a pull
request is the plan of an item only when its head branch is the recorded branch, and a recorded
branch is the branch of an item only when it names the item.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.roadmap.open_row import open_candidates
from devops_cli.roadmap.stage.stage import (
    StageApplied,
    StagePlan,
    StageWriter,
    parse_filters,
    plan_stage,
    render_stage_plan,
)
from devops_cli.roadmap.stage.stage_pending import PendingStage
from devops_cli.roadmap.stores import store as record_store
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.store import (
    GitHubState,
    ImplementRecordKey,
    ItemField,
    RoadmapStore,
    StageRecordKey,
    encode_job_record,
    split_record,
)
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import API, RunnerSession, github_json
from tests.support.fakes.github_repository import GitHubFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    STAGE_NAME,
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    apply_stage,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

TEXT = "The job drops the last comment of a thread."
BRANCH = "fix/1-the-job-drops-a-comment"
OTHER_BRANCH = "feat/4107-add-the-rows"
"""The head branch of a pull request that is not the plan of the item."""
NO_ITEM_BRANCH = "docs/release-notes"
"""A branch that names no issue number."""
LATER = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
# What a job of another repository wrote for its issue 4107. The repository of the round holds
# no pull request 4110.
SOURCE_KEYS: dict[str, str] = {
    "Status": "Staged",
    "stage.branch": OTHER_BRANCH,
    "stage.pr": "4110",
    "stage.ready": "4110",
    "stage.sha": "a" * 40,
    "implement.job": "devops-cli-implement-source-4107-0123456789",
    "refine.blocked_by": "4001",
}


def _plan(store: RoadmapStore, repo: StageRepo, *, now: datetime | None = None) -> StagePlan:
    """The plan of a round whose filter names no item to stage, so only the cleanup runs."""
    return plan_stage(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_filters(("status=ready", "type=docs")),
        now=now,
    )


def _round(store: RoadmapStore, repo: StageRepo) -> tuple[StagePlan, StageApplied]:
    """One round with its writes, as `devops roadmap stage --confirm` runs it."""
    writer = StageWriter(store, repo.clone)
    plan = plan_stage(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_filters(("status=ready", "type=docs")),
        writer=writer,
    )
    return plan, writer.applied()


def _branches(repo: StageRepo) -> list[str]:
    return repo.origin_git("branch", "--format=%(refname:short)").split()


def _held(body: str) -> dict[str, Any]:
    return split_record(body)[1]


def _item(store: InMemoryRoadmapStore, state: GitHubState, status: str = "Ready") -> int:
    return store.seed_issue(
        "fix(roadmap): the job drops a comment",
        body=TEXT,
        state=state,
        labels=("type/bug",),
        fields={ItemField.STATUS: status, ItemField.PRIORITY: "P1-High"},
    )


def _mark(store: InMemoryRoadmapStore, number: int, marks: dict[Any, str]) -> None:
    item = store.item(number)
    assert item is not None
    store.set_marks(item, marks)


def _record(store: InMemoryRoadmapStore, number: int) -> dict[str, str]:
    item = store.item(number)
    assert item is not None
    return {key.value: value for key, value in item.job_record.items() if value is not None}


# ── The round replaces the record of another issue ────────────────────────────


def test_a_round_with_a_record_of_another_issue_ends_with_no_failure_and_replaces_the_record(
    stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    """Two rounds on GitHub: item 7 holds the record of an issue of another repository, and item
    8 holds its own staged plan. No round fails or reads a pull request for item 7, the body of
    item 7 holds no key of the old record after the first round, the second round sends no write,
    and item 8 stays as it is."""
    own = {"Status": "New", "stage.branch": "fix/8-the-other-item", "stage.pr": "12"}
    github = GitHubFake(STAGE_REPO)
    labels = ("priority/p1-high", "status/new", "type/bug")
    github.seed_issue(7, labels=labels, body=f"{TEXT}\n\n{encode_job_record(SOURCE_KEYS, {})}")
    github.seed_issue(8, labels=labels, body=f"{TEXT}\n\n{encode_job_record(own, {})}")
    github_api.route(
        "GET",
        f"/repos/{STAGE_REPO}/pulls/12",
        github_json(
            {"state": "open", "draft": True, "head": {"sha": "abc", "ref": own["stage.branch"]}}
        ),
    )

    rounds = []
    bodies = []
    writes = []
    for _ in range(2):
        store = GitHubRoadmapStore(STAGE_REPO, runner=github, session=RunnerSession(github))
        plan, applied = _round(store, stage_repo)
        rounds.append((plan.failed, applied.failed))
        bodies.append(github.body(7))
        writes.append(len(github.writes()))

    assert rounds == [((), ()), ((), ())]
    assert bodies == [TEXT, TEXT]
    # The first round sends the one write that replaces the record, and the second round sends
    # no write.
    assert writes == [1, 1]
    assert _held(github.body(8)) == own
    assert github_api.requested == [f"GET {API}/repos/{STAGE_REPO}/pulls/12"] * 2


def test_the_plan_of_a_round_lists_the_record_that_it_replaces_and_writes_nothing(
    stage_repo: StageRepo,
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = store.seed_issue(
        "fix(roadmap): the job drops a comment",
        body=f"{TEXT}\n\n{encode_job_record(SOURCE_KEYS, {})}",
        fields={ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"},
    )

    plan = _plan(store, stage_repo)

    assert [item.number for item in plan.resets] == [number]
    assert f"- #{number}: the record in the body was written for another issue" in (
        render_stage_plan(plan)
    )
    assert _held(store.raw_body(number)) == SOURCE_KEYS


# ── The plan that the stage job records ───────────────────────────────────────


def test_the_record_that_the_stage_job_writes_names_its_plan_by_number_and_head_branch(
    stage_repo: StageRepo,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
    model_fake: ModelFake,
) -> None:
    """The stage job records `stage.branch` and `stage.pr` in one write, and opens the pull
    request from that branch. So the record of an item that the job staged names its plan
    (`recorded_plan`), and the pull request has the recorded branch as its head."""
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_stageable(store)
    store.seed_file(".github/labels.yml", '- name: "type/docs"\n  color: "0075ca"\n')
    pulls = f"/repos/{STAGE_REPO}/pulls"
    opened = github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201)
    github_api.route("POST", pulls, opened)
    github_api.route(
        "POST", f"{pulls}/5/requested_reviewers", github_json({"requested_reviewers": []})
    )
    openspec_fake.script_sequence(validate_args("1-the-job-drops-a-comment"), (0, VALID_REPORT))
    model_fake.answer(make_stage_proposal())

    plan = plan_stage(
        store, repo=STAGE_REPO, source=stage_repo.clone, filters=parse_filters(()), now=LATER
    )
    applied = apply_stage(store, plan, source=stage_repo.clone, now=LATER)

    sent = next(
        json.loads(request.content)
        for request in github_api.sent
        if request.method == "POST" and request.url.path.endswith("/pulls")
    )
    item = store.item(number)
    assert item is not None
    recorded = record_store.recorded_plan(item)
    assert (applied.staged, recorded and tuple(recorded)) == ((number,), (5, BRANCH))
    assert recorded is not None
    assert recorded.is_pull(5, sent["head"])


# ── The cleanup of a closed item ──────────────────────────────────────────────


def _closed_staged(store: InMemoryRoadmapStore, *, head_ref: str, branch: str = BRANCH) -> int:
    """A closed item whose record names the staged branch `branch` and an open pull request with
    the head branch `head_ref`. The number of the pull request."""
    number = _item(store, GitHubState.CLOSED)
    pull = store.seed_pull("docs(spec): a plan", head_ref=head_ref, draft=True)
    _mark(
        store,
        number,
        {StageRecordKey.BRANCH: branch, StageRecordKey.PR: str(pull), StageRecordKey.SHA: "abc"},
    )
    return pull


def test_the_cleanup_of_a_closed_item_closes_the_draft_on_the_recorded_branch(
    stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    pull = _closed_staged(store, head_ref=BRANCH)
    github_api.route("PATCH", f"/repos/{STAGE_REPO}/pulls/{pull}", github_json({"number": pull}))

    _, applied = _round(store, stage_repo)

    assert (applied.removed, _branches(stage_repo), github_api.requested) == (
        (1,),
        ["main"],
        [f"PATCH {API}/repos/{STAGE_REPO}/pulls/{pull}"],
    )


def test_a_pull_request_on_another_branch_is_not_the_draft_of_a_closed_item(
    stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    """The record names the number of a pull request whose head branch is not the recorded one:
    it is not the draft of the item, and the cleanup of the staged branch sends no request for
    it."""
    stage_repo.push_branch(BRANCH, author=STAGE_NAME)
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    pull = _closed_staged(store, head_ref=OTHER_BRANCH)
    github_api.route("PATCH", f"/repos/{STAGE_REPO}/pulls/{pull}", github_json({"number": pull}))

    _, applied = _round(store, stage_repo)

    assert (applied.removed, _branches(stage_repo), github_api.requested) == ((1,), ["main"], [])


def test_a_recorded_branch_that_does_not_name_a_closed_item_is_no_staged_branch_of_it(
    stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    """Only the session wrote to the branch, and the branch names no issue number: it is no staged
    branch of the item, and the round sends no write for it."""
    stage_repo.push_branch(NO_ITEM_BRANCH, author=STAGE_NAME)
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    pull = _closed_staged(store, head_ref=NO_ITEM_BRANCH, branch=NO_ITEM_BRANCH)
    github_api.route("PATCH", f"/repos/{STAGE_REPO}/pulls/{pull}", github_json({"number": pull}))

    plan, applied = _round(store, stage_repo)

    assert (plan.removals, applied.removed, github_api.requested) == ((), (), [])
    assert NO_ITEM_BRANCH in _branches(stage_repo)
    assert _record(store, 1)["stage.branch"] == NO_ITEM_BRANCH


# ── A plan that closed with no merge ──────────────────────────────────────────


def _pull_closed(api: GitHubApiFake, pull: int, head_ref: str) -> None:
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/pulls/{pull}",
        github_json(
            {
                "state": "closed",
                "merged": False,
                "draft": False,
                "closed_at": "2026-11-02T20:22:45+00:00",
                "head": {"sha": "abc", "ref": head_ref},
            }
        ),
    )


@pytest.mark.parametrize(
    ("head_ref", "rejected"), [(BRANCH, [1]), (OTHER_BRANCH, [])], ids=["recorded", "another"]
)
def test_a_closed_pull_request_is_a_rejected_plan_only_on_the_recorded_branch(
    stage_repo: StageRepo, github_api: GitHubApiFake, head_ref: str, rejected: list[int]
) -> None:
    """A pull request that closed with no merge on another branch is not the plan of the item,
    so its close is no rejection."""
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = _item(store, GitHubState.OPEN)
    pull = store.seed_pull("docs(spec): a plan", head_ref=head_ref)
    marks = {StageRecordKey.BRANCH: BRANCH, StageRecordKey.PR: str(pull)}
    _mark(store, number, marks)
    _pull_closed(github_api, pull, head_ref)

    plan, applied = _round(store, stage_repo)

    item = store.item(number)
    assert item is not None
    assert ([r.number for r in plan.rejections], list(applied.rejected)) == (rejected, rejected)
    assert (len(store.comments_on(number)), item.status) == (
        (1, "New") if rejected else (0, "Ready")
    )


def test_a_recorded_number_with_no_recorded_branch_reads_no_pull_request(
    stage_repo: StageRepo, github_api: GitHubApiFake
) -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = _item(store, GitHubState.OPEN)
    _mark(store, number, {StageRecordKey.PR: "4110"})

    plan, applied = _round(store, stage_repo)

    assert (plan.failed, applied.failed, github_api.requested) == ((), (), [])


# ── The orphan of an intent mark ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("branch", "left"), [(BRANCH, ["main"]), (NO_ITEM_BRANCH, ["main", NO_ITEM_BRANCH])]
)
def test_an_old_intent_mark_gives_an_orphan_only_when_its_branch_names_the_item(
    stage_repo: StageRepo, github_api: GitHubApiFake, branch: str, left: list[str]
) -> None:
    stage_repo.push_branch(branch, author=STAGE_NAME)
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = _item(store, GitHubState.OPEN, status="New")
    mark = PendingStage(branch=branch, time=LATER - timedelta(days=1)).record
    _mark(store, number, {StageRecordKey.PENDING: mark})

    writer = StageWriter(store, stage_repo.clone, now=LATER)
    plan = _plan(store, stage_repo, now=LATER)
    writer.begin(plan, set())

    assert sorted(_branches(stage_repo)) == sorted(left)
    assert [removal.branch for removal in plan.removals] == ([BRANCH] if branch == BRANCH else [])


# ── The open row ──────────────────────────────────────────────────────────────


def test_the_open_row_takes_only_a_recorded_branch_that_names_the_item() -> None:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    named = store.seed_issue("test: one", fields={ItemField.PRIORITY: "P2-Medium"})
    other = store.seed_issue("test: two", fields={ItemField.PRIORITY: "P2-Medium"})
    _mark(store, named, {ImplementRecordKey.BRANCH: f"test/{named}-one"})
    _mark(store, other, {ImplementRecordKey.BRANCH: NO_ITEM_BRANCH})
    heads = f"{1:040x}\trefs/heads/test/{named}-one\n{2:040x}\trefs/heads/{NO_ITEM_BRANCH}"

    found = open_candidates(store, heads)

    assert [(c.item.number, c.branch) for c in found] == [(named, f"test/{named}-one")]
