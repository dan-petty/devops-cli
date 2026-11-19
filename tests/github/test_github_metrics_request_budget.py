"""The GitHub request budget of one metrics-row round (#3794).

One round with one page of each listing may send at most four GitHub requests: the every-issue
listing, the CI runs and the milestones through the session, and the repository metadata through
gh (#3794, #3941). A test that runs the round over the fake GitHub edges pins the budget, so a new
read or an extra page of the listing fails offline in CI.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from devops_cli.github.item_label_times import item_label_times_path
from devops_cli.github.metrics import (
    METRICS_ROW_GITHUB_REQUEST_BUDGET,
    collect_project_metrics_report,
    get_item_age_metrics,
)
from devops_cli.github.request_scope import request_scope
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.telemetry.instruments import GITHUB_REQUESTS_TOTAL
from tests.support.fakes.git import GitFake
from tests.support.fakes.github import GitHubApiFake, github_json, next_page
from tests.support.fakes.github_repository import GitHubFake
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.process import ProcessAnswer
from tests.support.roadmap_github_store import issue_payload, labeled

REPO = "example/test-repo"
NOW = datetime.datetime(2026, 11, 14, 12, 0, tzinfo=datetime.UTC)
MILESTONE = {"number": 1, "title": "2026-11-01", "state": "open"}
LISTING = f"/repos/{REPO}/issues?state=all&per_page=100"
RUNS = f"/repos/{REPO}/actions/runs?per_page=50"
MILESTONES = f"/repos/{REPO}/milestones?state=all&per_page=100"
ITEM_AGE_READS_PER_ROUND = 20
"""The most label-event reads that the cap of one metrics-row round allows (#3634)."""
NEW_POD_ITEMS = 30
"""The open Items of the new-pod measurement: more than the cap, so a round defers some
(#3634)."""


def _repository() -> GitHubFake:
    github = GitHubFake(REPO, milestones=[MILESTONE])
    github.seed_issue(1, "fix: one", labels=("type/bug",))
    return github


def _store(github: GitHubFake) -> GitHubRoadmapStore:
    return GitHubRoadmapStore(REPO, runner=github, session=get_github_session())


def _warm_ages(github: GitHubFake, record: Path) -> None:
    """Fill the record of the label times, so the counted round reads no label events."""
    get_item_age_metrics(_store(github), REPO, clock=lambda: NOW, label_times_record=record)


def _counted_round(
    tmp_path: Path,
    git_fake: GitFake,
    github: GitHubFake,
    otlp: FakeCollector,
    *,
    warm: bool = True,
) -> int:
    """The requests of one counted metrics-row round over `github`, after `_warm_ages` fills the
    record of its label times unless `warm` is false."""
    root = tmp_path / "repo"
    root.mkdir(exist_ok=True)
    git_fake.answer(["git", "tag"], ProcessAnswer(stdout="v0.1.0|2026-10-01T00:00:00+00:00\n"))
    git_fake.answer(["git", "log"], ProcessAnswer(stdout="v0.1.0\n\nCloses #1\n"))
    git_fake.answer(["git", "rev-list"], ProcessAnswer(stdout="1\n"))
    record = item_label_times_path(tmp_path)
    if warm:
        _warm_ages(github, record)
    from devops_cli.github import metrics as metrics_module

    metrics_module._refused_integration_repos.add(REPO)
    otlp.clear()
    with request_scope(row="metrics"):
        collect_project_metrics_report(
            root=root,
            repo=REPO,
            store=_store(github),
            item_ages=True,
            clock=lambda: NOW,
            label_times_record=record,
        )
    return int(
        sum(
            value
            for labels, value in otlp.points(GITHUB_REQUESTS_TOTAL.name)
            if labels.get("row") == "metrics"
        )
    )


def _one_page(github_api: GitHubApiFake) -> None:
    github_api.route("GET", LISTING, github_json([issue_payload(1)]))
    github_api.route(
        "GET",
        RUNS,
        github_json({"total_count": 0, "workflow_runs": []}),
    )
    github_api.route(
        "GET",
        MILESTONES,
        github_json([MILESTONE]),
    )


def test_one_round_of_one_page_stays_within_the_request_budget(
    tmp_path: Path,
    git_fake: GitFake,
    monkeypatch: pytest.MonkeyPatch,
    github_api: GitHubApiFake,
    otlp: FakeCollector,
) -> None:
    """One metrics-row round with one page of each listing sends the four reads of the baseline
    and no more (#3794, #3941)."""
    github = _repository()
    github.answer_children(monkeypatch)
    _one_page(github_api)
    count = _counted_round(tmp_path, git_fake, github, otlp)
    assert count == METRICS_ROW_GITHUB_REQUEST_BUDGET, (
        f"the metrics row sent {count} GitHub requests against a budget of "
        f"{METRICS_ROW_GITHUB_REQUEST_BUDGET}"
    )


def test_one_more_page_of_open_items_fails_the_budget(
    tmp_path: Path,
    git_fake: GitFake,
    monkeypatch: pytest.MonkeyPatch,
    github_api: GitHubApiFake,
    otlp: FakeCollector,
) -> None:
    """A second page of open items makes one request over the budget, so the test fails with the
    recorded count and the budget constant (#3794, #3941)."""
    github = _repository()
    github.answer_children(monkeypatch)
    second = f"{LISTING}&page=2"
    _one_page(github_api)
    github_api.route("GET", LISTING, github_json([issue_payload(1)], headers=next_page(second)))
    github_api.route("GET", second, github_json([issue_payload(2)]))
    count = _counted_round(tmp_path, git_fake, github, otlp)
    with pytest.raises(AssertionError) as raised:
        assert count <= METRICS_ROW_GITHUB_REQUEST_BUDGET, (
            f"the metrics row sent {count} GitHub requests against a budget of "
            f"{METRICS_ROW_GITHUB_REQUEST_BUDGET}"
        )
    assert str(METRICS_ROW_GITHUB_REQUEST_BUDGET) in str(raised.value)
    assert str(count) in str(raised.value)


def _thirty_open_items(github_api: GitHubApiFake) -> None:
    """One page of 30 open Items that hold a Priority, the CI runs, the milestones and the label
    events of each Item, so a round with no record reads 20 of them and no other read fails
    (#3634)."""
    items = [
        labeled(issue_payload(number), "priority/p2-medium")
        for number in range(1, NEW_POD_ITEMS + 1)
    ]
    github_api.route("GET", LISTING, github_json(items))
    github_api.route("GET", RUNS, github_json({"total_count": 0, "workflow_runs": []}))
    github_api.route("GET", MILESTONES, github_json([MILESTONE]))
    for number in range(1, NEW_POD_ITEMS + 1):
        github_api.route(
            "GET",
            f"/repos/{REPO}/issues/{number}/events?per_page=100",
            github_json(
                [
                    {
                        "event": "labeled",
                        "created_at": "2026-11-01T12:00:00Z",
                        "actor": {"login": "dan-petty"},
                        "label": {"name": "priority/p2-medium"},
                    }
                ]
            ),
        )


def test_a_new_pod_sends_24_requests_in_its_first_round(
    tmp_path: Path,
    git_fake: GitFake,
    monkeypatch: pytest.MonkeyPatch,
    github_api: GitHubApiFake,
    otlp: FakeCollector,
) -> None:
    """A new pod whose record is not there reads the label events of 20 of the 30 open Items, so
    its first round sends the 4 fixed reads of the row and the 20 reads of the cap: 24 requests.
    The budget was 5 when #3634 was planned, so that plan counts 25; #6095 lowered it to 4
    (#3634)."""
    github = _repository()
    for number in range(2, NEW_POD_ITEMS + 1):
        github.seed_issue(number, f"fix: {number}", labels=("priority/p2-medium",))
    github.answer_children(monkeypatch)
    _thirty_open_items(github_api)
    count = _counted_round(tmp_path, git_fake, github, otlp, warm=False)
    events = [url for url in github_api.requested if "/events?" in url]
    assert (len(events), count) == (
        ITEM_AGE_READS_PER_ROUND,
        METRICS_ROW_GITHUB_REQUEST_BUDGET + ITEM_AGE_READS_PER_ROUND,
    ), (
        f"one new pod read the label events of {len(events)} Items and sent {count} GitHub "
        f"requests in its first round, against the {ITEM_AGE_READS_PER_ROUND} reads of the cap "
        f"and the {METRICS_ROW_GITHUB_REQUEST_BUDGET} fixed reads of the row"
    )
