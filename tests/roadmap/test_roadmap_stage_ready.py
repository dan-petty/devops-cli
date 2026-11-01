"""The row `stage_ready` of the Service's status lane: a green draft pull request that the stage
job recorded is marked ready, and nothing else is (#2865).

GitHub's REST API and `gh` are faked at their edges. The pull request is read through the
session, its check runs are read through the session, and `gh pr ready` is the call that marks it.
"""

from __future__ import annotations

import subprocess
from datetime import timedelta
from typing import Any

import pytest

from devops_cli.exceptions import GitHubRateLimitError, RoadmapStageError
from devops_cli.github.client import GitHubClient
from devops_cli.roadmap import stage_ready
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.run import MODEL_LANE_ROWS, STATUS_LANE_ROWS, JobOutcome
from devops_cli.roadmap.stage_ready import StageDraft, mark_stage_ready, ready_to_mark
from devops_cli.roadmap.store import (
    CloseReason,
    GitHubState,
    ImplementRecordKey,
    Item,
    StageRecordKey,
)
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.roadmap_implement import FAIL, PASS, PULL, RUNNING, seed_staged
from tests.support.roadmap_stage import STAGE_REPO

pytestmark = pytest.mark.usefixtures("keyring_store")

HEAD = "a" * 40
SECOND_PULL = 6


def _pull(
    api: GitHubApiFake,
    number: int = PULL,
    *,
    state: str = "open",
    draft: bool = True,
    merged: bool = False,
    head: str = HEAD,
) -> None:
    """GitHub's answer to the read of pull request `number`."""
    payload = {"state": state, "draft": draft, "merged": merged, "head": {"sha": head}}
    api.route("GET", f"/repos/{STAGE_REPO}/pulls/{number}", github_json(payload))


def _checks(api: GitHubApiFake, *runs: dict[str, Any], head: str = HEAD) -> None:
    """GitHub's answer to the read of the check runs of commit `head`."""
    path = f"/repos/{STAGE_REPO}/commits/{head}/check-runs?per_page=100"
    api.route("GET", path, github_json({"total_count": len(runs), "check_runs": list(runs)}))


class _Ready:
    """The `gh pr ready` calls that the fake `gh` receives, and the pull requests it refuses."""

    def __init__(self, gh: ProcessFake) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.refused: set[str] = set()
        gh.answer(lambda call: call.argv[1:3] == ("pr", "ready"), ProcessAnswer(side_effect=self))

    def __call__(self, call: ProcessCall) -> subprocess.CompletedProcess[str]:
        self.calls.append(call.argv[1:])
        code = 1 if call.argv[3] in self.refused else 0
        stderr = "GraphQL: Resource not accessible by integration" if code else ""
        return subprocess.CompletedProcess(call.argv, code, stdout="", stderr=stderr)


@pytest.fixture
def api(github_api_and_gh: tuple[GitHubApiFake, ProcessFake]) -> GitHubApiFake:
    return github_api_and_gh[0]


@pytest.fixture
def ready(github_api_and_gh: tuple[GitHubApiFake, ProcessFake]) -> _Ready:
    return _Ready(github_api_and_gh[1])


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


def _item(store: InMemoryRoadmapStore, number: int = 1) -> Item:
    item = store.item(number)
    assert item is not None
    return item


def _record(store: InMemoryRoadmapStore, number: int = 1) -> dict[str, str | None]:
    return {str(key): value for key, value in _item(store, number).job_record.items()}


def test_a_green_draft_is_marked_ready_once_and_recorded(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready
) -> None:
    number = seed_staged(store)
    _pull(api)
    _checks(api, PASS, {**PASS, "name": "Lint"})

    applied = mark_stage_ready(store, repo=STAGE_REPO)

    assert (
        applied.marked,
        ready.calls,
        _record(store, number)[StageRecordKey.READY],
        _item(store, number).status,
    ) == ((number,), [("pr", "ready", str(PULL), "--repo", STAGE_REPO)], str(PULL), "Ready")


@pytest.mark.parametrize(
    "runs",
    [[PASS, FAIL], [PASS, RUNNING], [{**PASS, "conclusion": "cancelled"}], []],
    ids=["failed", "running", "cancelled", "no-check-run"],
)
def test_a_draft_with_a_check_that_did_not_pass_stays_a_draft_and_is_not_recorded(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready, runs: list[dict[str, Any]]
) -> None:
    number = seed_staged(store)
    _pull(api)
    _checks(api, *runs)

    applied = mark_stage_ready(store, repo=STAGE_REPO)

    assert (
        applied.marked,
        applied.waiting,
        ready.calls,
        StageRecordKey.READY in _record(store, number),
    ) == ((), (number,), [], False)


def test_a_draft_that_no_item_records_is_never_read_or_marked(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready
) -> None:
    store.seed_issue("fix(roadmap): a person's own work", labels=("type/bug",))
    _pull(api, 9)
    _checks(api, PASS)

    applied = mark_stage_ready(store, repo=STAGE_REPO)

    assert (applied.marked, api.requested, ready.calls) == ((), [], [])


def test_a_second_round_sends_no_request_for_a_pull_request_it_marked(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready
) -> None:
    seed_staged(store)
    _pull(api)
    _checks(api, PASS)
    mark_stage_ready(store, repo=STAGE_REPO)
    sent = len(api.sent)

    second = mark_stage_ready(store, repo=STAGE_REPO)

    assert (second.marked, len(api.sent), len(ready.calls)) == ((), sent, 1)


@pytest.mark.parametrize(
    "state",
    [
        {"state": "open", "draft": False},
        {"state": "closed", "draft": True, "merged": False},
        {"state": "closed", "draft": False, "merged": True},
    ],
    ids=["ready", "closed", "merged"],
)
def test_a_pull_request_that_left_the_draft_state_is_recorded_and_not_marked(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready, state: dict[str, Any]
) -> None:
    number = seed_staged(store)
    _pull(api, **state)
    _checks(api, PASS)

    applied = mark_stage_ready(store, repo=STAGE_REPO)
    again = mark_stage_ready(store, repo=STAGE_REPO)

    assert (
        applied.settled,
        again.settled,
        ready.calls,
        len(api.sent),
        _record(store, number)[StageRecordKey.READY],
    ) == ((number,), (), [], 1, str(PULL))


def test_a_round_with_no_recorded_draft_sends_no_request(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready
) -> None:
    seed_staged(store, record=False)
    closed = seed_staged(store)
    store.close_by_hand(closed, CloseReason.COMPLETED)
    recorded = seed_staged(store, pull=SECOND_PULL)
    store.set_marks(_item(store, recorded), {StageRecordKey.READY: str(SECOND_PULL)})

    applied = mark_stage_ready(store, repo=STAGE_REPO)

    assert (applied.marked, api.requested, ready.calls, _item(store, closed).state) == (
        (),
        [],
        [],
        GitHubState.CLOSED,
    )


def test_a_draft_that_a_runner_job_works_on_stays_a_draft(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready
) -> None:
    number = seed_staged(store)
    store.set_marks(_item(store, number), {ImplementRecordKey.JOB: "devops-cli-runner-1"})
    _pull(api)
    _checks(api, PASS)

    applied = mark_stage_ready(store, repo=STAGE_REPO)

    assert (applied.marked, api.requested, ready.calls) == ((), [], [])


def test_one_refused_pull_request_does_not_stop_the_next_and_fails_the_round_naming_it(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready
) -> None:
    first = seed_staged(store)
    second = seed_staged(store, pull=SECOND_PULL)
    for number in (PULL, SECOND_PULL):
        _pull(api, number, head=str(number) * 40)
        _checks(api, PASS, head=str(number) * 40)
    ready.refused.add(str(PULL))

    with pytest.raises(RoadmapStageError) as raised:
        mark_stage_ready(store, repo=STAGE_REPO)

    assert (
        raised.value.failed_items,
        f"#{first}" in str(raised.value),
        [call[2] for call in ready.calls],
        _record(store, second)[StageRecordKey.READY],
        StageRecordKey.READY in _record(store, first),
    ) == ((first,), True, [str(PULL), str(SECOND_PULL)], str(SECOND_PULL), False)


def test_a_pull_request_that_github_cannot_find_fails_its_item_and_is_read_again(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready
) -> None:
    """GitHub also answers 404 for a repository the token cannot see, so the answer is no proof
    that the pull request is gone: the row records nothing and the next round reads it again."""
    number = seed_staged(store)

    with pytest.raises(RoadmapStageError) as raised:
        mark_stage_ready(store, repo=STAGE_REPO)
    sent = len(api.sent)
    with pytest.raises(RoadmapStageError) as again:
        mark_stage_ready(store, repo=STAGE_REPO)

    assert (
        raised.value.failed_items,
        again.value.failed_items,
        StageRecordKey.READY in _record(store, number),
        ready.calls,
        len(api.sent) > sent,
    ) == ((number,), (number,), False, [], True)


def test_a_rate_limit_stops_the_round_at_the_first_pull_request(
    store: InMemoryRoadmapStore,
    api: GitHubApiFake,
    ready: _Ready,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every later read would be refused too, and each would spend the budget of the Service."""
    for pull in (PULL, SECOND_PULL, SECOND_PULL + 1):
        seed_staged(store, pull=pull)
    read: list[int] = []

    def refuse(self: GitHubClient, repo: str, number: int) -> None:
        read.append(number)
        raise GitHubRateLimitError("No requests are left.", operation="roadmap.read")

    monkeypatch.setattr(GitHubClient, "get_pull_status", refuse)

    with pytest.raises(GitHubRateLimitError, match="No requests are left"):
        mark_stage_ready(store, repo=STAGE_REPO)

    assert (read, ready.calls) == ([PULL], [])


def test_a_head_that_moved_after_the_checks_stays_a_draft_and_is_read_again(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready
) -> None:
    """A push after the read of the checks is a head that no check judged."""
    number = seed_staged(store)
    opened = {"state": "open", "draft": True, "merged": False}
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/pulls/{PULL}",
        github_json({**opened, "head": {"sha": HEAD}}),
        github_json({**opened, "head": {"sha": "b" * 40}}),
    )
    _checks(api, PASS)

    applied = mark_stage_ready(store, repo=STAGE_REPO)

    assert (
        applied.marked,
        applied.waiting,
        ready.calls,
        StageRecordKey.READY in _record(store, number),
    ) == (
        (),
        (number,),
        [],
        False,
    )


def test_the_round_never_calls_the_commit_status_endpoint(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready
) -> None:
    seed_staged(store)
    _pull(api)
    _checks(api, PASS)

    mark_stage_ready(store, repo=STAGE_REPO)

    assert [url for url in api.requested if "/status" in url] == []


def test_the_decision_of_one_function_rules_the_round(
    store: InMemoryRoadmapStore,
    api: GitHubApiFake,
    ready: _Ready,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_staged(store)
    _pull(api)
    _checks(api, PASS)
    monkeypatch.setattr(stage_ready, "ready_to_mark", lambda draft: False)

    applied = mark_stage_ready(store, repo=STAGE_REPO)

    assert (applied.marked, ready.calls) == ((), [])


def test_ready_to_mark_is_true_for_passing_checks_only(store: InMemoryRoadmapStore) -> None:
    from devops_cli.github.check_verdict import CheckBucket, CheckVerdictSummary, PRCheckItem
    from devops_cli.github.client import PullStatus

    item = _item(store, seed_staged(store))
    pull = PullStatus(state="open", draft=True)

    def verdict(*buckets: CheckBucket) -> bool:
        items = [PRCheckItem(name=str(i), bucket=b) for i, b in enumerate(buckets)]
        return ready_to_mark(StageDraft(item, pull, CheckVerdictSummary(items=items)))

    assert (
        verdict(CheckBucket.PASS, CheckBucket.SKIPPING),
        verdict(CheckBucket.PASS, CheckBucket.PENDING),
        verdict(CheckBucket.FAIL),
        verdict(CheckBucket.UNREAD),
    ) == (True, False, False, False)


STAGE_READY_ROW = next(row for row in STATUS_LANE_ROWS if row.name == "stage_ready")


def test_the_row_follows_implement_on_the_status_lane_needs_no_clone_and_is_due_every_three_minutes() -> (
    None
):
    """The row calls no model, so a long model-lane round never delays it."""
    assert (
        [row.name for row in STATUS_LANE_ROWS],
        "stage_ready" in [row.name for row in MODEL_LANE_ROWS],
        STAGE_READY_ROW.needs_clone,
        STAGE_READY_ROW.first_run_due,
        STAGE_READY_ROW.interval,
    ) == (["metrics", "implement", "stage_ready"], False, False, True, timedelta(minutes=3))


def test_a_round_of_the_row_marks_the_green_draft_ready(
    store: InMemoryRoadmapStore, api: GitHubApiFake, ready: _Ready
) -> None:
    seed_staged(store)
    _pull(api)
    _checks(api, PASS)

    outcome = STAGE_READY_ROW.runner(store=store, repo=STAGE_REPO)

    assert (outcome, ready.calls) == (
        JobOutcome(),
        [("pr", "ready", str(PULL), "--repo", STAGE_REPO)],
    )
