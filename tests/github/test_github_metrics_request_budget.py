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
from tests.support.roadmap_github_store import issue_payload

REPO = "example/test-repo"
NOW = datetime.datetime(2026, 11, 14, 12, 0, tzinfo=datetime.UTC)
MILESTONE = {"number": 1, "title": "2026-11-01", "state": "open"}
LISTING = f"/repos/{REPO}/issues?state=all&per_page=100"
RUNS = f"/repos/{REPO}/actions/runs?per_page=50"
MILESTONES = f"/repos/{REPO}/milestones?state=all&per_page=100"


def _repository() -> GitHubFake:
    github = GitHubFake(REPO, milestones=[MILESTONE])
    github.seed_issue(1, "fix: one", labels=("type/bug",))
    return github


def _store(github: GitHubFake) -> GitHubRoadmapStore:
    return GitHubRoadmapStore(REPO, runner=github, session=get_github_session())


def _warm_ages(github: GitHubFake) -> None:
    """Fill the age cache, so the counted round reads no label events."""
    get_item_age_metrics(_store(github), REPO, clock=lambda: NOW)


def _counted_round(
    tmp_path: Path, git_fake: GitFake, github: GitHubFake, otlp: FakeCollector
) -> int:
    root = tmp_path / "repo"
    root.mkdir(exist_ok=True)
    git_fake.answer(["git", "tag"], ProcessAnswer(stdout="v0.1.0|2026-10-01T00:00:00+00:00\n"))
    git_fake.answer(["git", "log"], ProcessAnswer(stdout="v0.1.0\n\nCloses #1\n"))
    git_fake.answer(["git", "rev-list"], ProcessAnswer(stdout="1\n"))
    _warm_ages(github)
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
