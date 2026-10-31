"""Unit tests for GitHub project & release metrics analytics engine and CLI."""

from __future__ import annotations

import datetime
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.config.constants import CONST_GITHUB_APP_PRIVATE_KEY_ENV
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.github.metrics import (
    ItemCountMetric,
    LabelTaxonomyMetric,
    MilestoneMetric,
    ProjectMetricsReport,
    ReleaseCadenceMetric,
    TrafficPathMetric,
    TrafficReferrerMetric,
    TrafficSummaryMetric,
    WorkflowRunMetric,
    build_milestone_metric,
    calculate_pass_rate,
    classify_workflow_conclusion,
    collect_project_metrics_report,
    count_bullet_commits,
    emit_project_metrics_telemetry,
    extract_commits_and_prs,
    get_ci_workflow_metrics,
    get_git_tag_entries,
    get_item_metrics,
    get_item_releases,
    get_label_taxonomy_metrics,
    get_milestone_metrics,
    get_release_cadence_metrics,
    get_repository_traffic_metrics,
    parse_tag_datetime,
    reset_refused_paths,
)
from devops_cli.roadmap.github_store import GitHubRoadmapStore
from devops_cli.telemetry.instruments import (
    PROJECT_FORKS,
    PROJECT_ITEM_LABELS,
    PROJECT_ITEMS,
    PROJECT_STARS,
    PROJECT_TRAFFIC_CLONES,
    PROJECT_TRAFFIC_CLONES_UNIQUES,
    PROJECT_TRAFFIC_PATHS,
    PROJECT_TRAFFIC_REFERRERS,
    PROJECT_TRAFFIC_VIEWS,
    PROJECT_TRAFFIC_VIEWS_UNIQUES,
)
from tests.roadmap_github_fake import GitHubFake
from tests.support.fakes.git import GitFake
from tests.support.fakes.github import RunnerSession
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

if TYPE_CHECKING:
    from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
    from tests.support.cli import CliRunnerFixture

REPO = "example/test-repo"
PLANNED = "2026-11-01"


def _fresh_quota_payload() -> str:
    fresh_quota = {"limit": 5000, "remaining": 5000, "reset": time.time() + 60}
    return json.dumps({"resources": {"core": fresh_quota, "graphql": fresh_quota}})


def _roadmap_store(github: GitHubFake) -> GitHubRoadmapStore:
    """The roadmap store of `github`'s repository, as the Service opens it."""
    return GitHubRoadmapStore(github.repo, runner=github, session=RunnerSession(github))


def _repository_with_items() -> GitHubFake:
    """Five Items: two open bugs with P1-High in no milestone, an open and a closed feature with
    P2-Medium in the planned milestone, and an open Item with P3-Low and no type or milestone.
    It also holds an open bug with no priority label, a Candidate, and a pull request with a
    priority label."""
    github = GitHubFake(REPO, milestones=[{"number": 1, "title": PLANNED, "state": "open"}])
    for number in (1, 2):
        github.seed_issue(number, labels=("type/bug", "priority/p1-high", "status/new"))
    feature = ("type/feature", "priority/p2-medium")
    github.seed_issue(3, labels=(*feature, "status/in-progress"), milestone=PLANNED)
    github.seed_issue(4, state="closed", labels=feature, milestone=PLANNED)
    github.seed_issue(5, labels=("priority/p3-low",))
    github.seed_issue(6, labels=("type/bug",))
    github.seed_issue(7, labels=("type/bug", "priority/p1-high"), pull_request=True)
    return github


def test_parse_tag_datetime_valid_and_invalid() -> None:
    """Verify ISO string parsing and fallback behavior."""
    iso_date = "2026-09-28T12:00:00+00:00"
    parsed_utc = parse_tag_datetime(iso_date)
    fallback = parse_tag_datetime("not-a-date")

    assert (
        parsed_utc.year,
        parsed_utc.month,
        parsed_utc.day,
    ) == (
        2026,
        9,
        28,
    )
    assert isinstance(fallback, datetime.datetime)


def test_get_git_tag_entries_returns_chronological_tags(
    process_fake: ProcessFake, tmp_path: Path
) -> None:
    """Verify git tag discovery, as a local read in the root, and chronological sorting."""
    raw_output = "v0.2.21|2026-09-20T10:00:00Z\nv0.2.20|2026-09-19T10:00:00Z\n"
    process_fake.answer(["git", "tag"], ProcessAnswer(stdout=raw_output))

    entries = get_git_tag_entries(tmp_path)

    call = process_fake.calls[0]
    assert ([tag for tag, _ in entries], call.argv[:3], call.cwd, call.local_read) == (
        ["v0.2.20", "v0.2.21"],
        ("git", "tag", "-l"),
        tmp_path,
        True,
    )


def test_get_git_tag_entries_without_git_logs_the_missing_program(
    process_fake: ProcessFake, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A missing `git` gives no tags, and the warning names the program (#1538)."""
    process_fake.answer(
        "git", ProcessAnswer(returncode=127, stderr="Executable 'git' not found in PATH")
    )

    with caplog.at_level(logging.WARNING, logger="devops_cli.github.metrics"):
        entries = get_git_tag_entries(tmp_path)

    assert (entries, "Executable 'git' not found" in caplog.text) == ([], True)


def test_count_bullet_commits() -> None:
    """Verify extraction of bulleted commits embedded in squash merge commit bodies."""
    body = (
        "Squash merge PR #920\n\n"
        "* feat(gh): add analytics engine (#921)\n"
        "* fix(ci): resolve quality gate timeout\n"
        "* docs: update changelog\n"
        "* a\n"
    )
    count = count_bullet_commits(body)
    assert count == 3


def test_extract_commits_and_prs(process_fake: ProcessFake, tmp_path: Path) -> None:
    """Verify calculation of commit counts and unique PR numbers between tags, from local reads
    of git in the root."""
    process_fake.answer(["git", "rev-list"], ProcessAnswer(stdout="1\n"))
    body = "* feat(core): item 1 (#101)\n* fix(core): item 2 (#102)\n* fix(core): item 3 (#101)\n"
    process_fake.answer(["git", "log"], ProcessAnswer(stdout=body))

    commits, prs = extract_commits_and_prs(tmp_path, "v0.2.20", "v0.2.21")

    assert (
        (commits, prs),
        [call.argv[:2] for call in process_fake.calls],
        {(call.cwd, call.local_read) for call in process_fake.calls},
    ) == ((3, 2), [("git", "rev-list"), ("git", "log")], {(tmp_path, True)})


def test_extract_commits_and_prs_without_git(process_fake: ProcessFake, tmp_path: Path) -> None:
    """A missing `git` counts one commit and no pull request, as a failed read did (#1538)."""
    process_fake.answer(
        "git", ProcessAnswer(returncode=127, stderr="Executable 'git' not found in PATH")
    )

    assert extract_commits_and_prs(tmp_path, "v0.2.20", "v0.2.21") == (1, 0)


def test_get_release_cadence_metrics(process_fake: ProcessFake, tmp_path: Path) -> None:
    """Verify release cadence interval calculation and reverse-chronological ordering."""
    tag_output = (
        "v0.2.20|2026-09-10T00:00:00+00:00\n"
        "v0.2.21|2026-09-12T12:00:00+00:00\n"
        "v0.2.22|2026-09-15T00:00:00+00:00\n"
    )
    process_fake.answer(["git", "tag"], ProcessAnswer(stdout=tag_output))
    process_fake.answer(["git", "rev-list"], ProcessAnswer(stdout="10\n"))
    body = "* item 1 (#1)\n* item 2 (#2)\n* item 3 (#3)\n* item 4 (#4)\n* item 5 (#5)\n"
    process_fake.answer(["git", "log"], ProcessAnswer(stdout=body))

    metrics = get_release_cadence_metrics(tmp_path, limit=2)
    assert len(metrics) == 2
    assert (
        metrics[0].tag,
        metrics[0].days_since_prev,
        metrics[1].tag,
        metrics[1].days_since_prev,
    ) == (
        "v0.2.22",
        2.5,
        "v0.2.21",
        2.5,
    )
    assert (metrics[0].commit_count, metrics[0].pr_count) == (10, 5)


def test_calculate_pass_rate_and_conclusion() -> None:
    """Verify pass rate percentage calculation and conclusion classification."""
    rate_100 = calculate_pass_rate(10, 0)
    rate_50 = calculate_pass_rate(5, 5)
    rate_zero = calculate_pass_rate(0, 0)

    c_success = classify_workflow_conclusion("success")
    c_failure = classify_workflow_conclusion("failure")
    c_timed_out = classify_workflow_conclusion("timed_out")
    c_other = classify_workflow_conclusion("cancelled")

    assert (rate_100, rate_50, rate_zero) == (100.0, 50.0, 100.0)
    assert (c_success, c_failure, c_timed_out, c_other) == (
        (1, 0, 0),
        (0, 1, 0),
        (0, 1, 0),
        (0, 0, 1),
    )


def test_get_ci_workflow_metrics(process_fake: ProcessFake) -> None:
    """Verify CI workflow aggregation and pass rate calculation."""
    fake_runs = {
        "workflow_runs": [
            {"name": "CI Quality Gate", "conclusion": "success"},
            {"name": "CI Quality Gate", "conclusion": "failure"},
            {"name": "Deploy", "conclusion": "success"},
        ]
    }
    process_fake.answer(
        ["gh", "api", "rate_limit"],
        ProcessAnswer(stdout=_fresh_quota_payload()),
    )
    process_fake.answer(
        ["gh", "api", "repos/example/repo/actions/runs?per_page=10"],
        ProcessAnswer(stdout=json.dumps(fake_runs)),
    )

    results = get_ci_workflow_metrics("example/repo", limit=10)
    assert len(results) == 2
    ci_metric = next(r for r in results if r.workflow == "CI Quality Gate")
    deploy_metric = next(r for r in results if r.workflow == "Deploy")

    assert (ci_metric.total_runs, ci_metric.passed, ci_metric.failed, ci_metric.pass_rate) == (
        2,
        1,
        1,
        50.0,
    )
    assert (
        deploy_metric.total_runs,
        deploy_metric.passed,
        deploy_metric.failed,
        deploy_metric.pass_rate,
    ) == (
        1,
        1,
        0,
        100.0,
    )


def test_get_ci_workflow_metrics_error(process_fake: ProcessFake) -> None:
    """Verify get_ci_workflow_metrics returns empty list on API error."""
    process_fake.answer(
        ["gh", "api", "rate_limit"],
        ProcessAnswer(stdout=_fresh_quota_payload()),
    )
    process_fake.answer(
        ["gh", "api", "repos/example/repo/actions/runs?per_page=50"],
        ProcessAnswer(returncode=1, stderr="network error"),
    )

    results = get_ci_workflow_metrics("example/repo")
    assert results == []


def test_build_milestone_metric_and_filter(process_fake: ProcessFake) -> None:
    """Verify milestone metric extraction, completion percentage, and filtering."""
    raw_open = {"title": "2026-10-01", "state": "open", "open_issues": 3, "closed_issues": 7}
    raw_closed = {"title": "2026-09-24", "state": "closed", "open_issues": 0, "closed_issues": 10}
    raw_empty = {"title": "2026-10-08", "state": "open", "open_issues": 0, "closed_issues": 0}

    m_open = build_milestone_metric(raw_open)
    m_closed = build_milestone_metric(raw_closed)
    m_empty = build_milestone_metric(raw_empty)

    assert (m_open.completion_rate, m_closed.completion_rate, m_empty.completion_rate) == (
        70.0,
        100.0,
        0.0,
    )

    process_fake.answer(
        ["gh", "api", "rate_limit"],
        ProcessAnswer(stdout=_fresh_quota_payload()),
    )
    process_fake.answer(
        ["gh", "api", "repos/example/repo/milestones?state=all&per_page=100"],
        ProcessAnswer(stdout=json.dumps([raw_open, raw_closed])),
    )

    filtered = get_milestone_metrics("example/repo", milestone_filter="2026-10-01")
    assert len(filtered) == 1
    assert (filtered[0].milestone, filtered[0].open_items, filtered[0].closed_items) == (
        "2026-10-01",
        3,
        7,
    )


def test_get_label_taxonomy_metrics(process_fake: ProcessFake) -> None:
    """Verify label taxonomy extraction and aggregation."""
    issues = [
        {"labels": [{"name": "team/core"}, {"name": "scope/cli"}]},
        {"labels": [{"name": "team/core"}, {"name": "team/infra"}]},
        {"labels": ["scope/cli", "unscoped-label"]},
    ]
    process_fake.answer(
        ["gh", "api", "rate_limit"],
        ProcessAnswer(stdout=_fresh_quota_payload()),
    )
    process_fake.answer(
        ["gh", "api", "--paginate", "repos/example/repo/issues?state=open&per_page=100"],
        ProcessAnswer(stdout=json.dumps(issues)),
    )

    metrics = get_label_taxonomy_metrics("example/repo")
    team_core = next((m for m in metrics if m.label == "team/core"), None)
    cli_scope = next((m for m in metrics if m.label == "scope/cli"), None)

    assert (team_core is not None, cli_scope is not None) == (True, True)
    assert (team_core.count, cli_scope.count) == (2, 2)


def test_label_taxonomy_metrics_counts_all_pages_and_skips_pull_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The taxonomy metrics count every open issue across all pages and no pull requests (#1541)."""
    github = GitHubFake("example/test-repo")
    for i in range(1, 251):
        github.seed_issue(i, f"Issue {i}", labels=["type/bug"])
    github.seed_issue(251, "PR 251", labels=["type/bug"], pull_request=True)
    github.seed_issue(252, "PR 252", labels=["scope/cli"], pull_request=True)
    monkeypatch.setattr(subprocess, "run", github.process(subprocess.run))

    metrics = get_label_taxonomy_metrics("example/test-repo")
    assert [(m.label, m.count) for m in metrics] == [("type/bug", 250)]


def test_collect_project_metrics_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, git_fake: GitFake
) -> None:
    """The report takes its releases from the repository's tags and its milestones and open
    issues' labels from GitHub, each read at its process edge. An Item counts under the release
    whose commits close it (#2702)."""
    root = tmp_path / "repo"
    root.mkdir()
    tag_output = (
        "v0.2.23|2026-09-26T12:00:00+00:00\n"
        "v0.2.24|2026-09-28T12:00:00+00:00\n"
        "v0.2.25|2026-10-01T12:00:00+00:00\n"
    )
    git_fake.answer(["git", "tag"], ProcessAnswer(stdout=tag_output))

    def _handle_log(call: ProcessCall) -> ProcessAnswer:
        argv = call.argv
        if "v0.2.23..v0.2.24" in argv:
            return ProcessAnswer(stdout="release v0.2.24\n\nCloses #2\n")
        return ProcessAnswer(stdout="release\n\nNo issue\n")

    git_fake.answer(["git", "log"], _handle_log)
    git_fake.answer(["git", "rev-list"], ProcessAnswer(stdout="1\n"))
    milestone = {"title": "2026-10-01", "state": "closed", "open_issues": 1, "closed_issues": 3}
    github = GitHubFake("example/test-repo", milestones=[milestone])
    github.seed_issue(1, "feat: export", labels=("type/feature", "priority/p2-medium"))
    github.seed_issue(2, "fix: import", state="closed", labels=("type/bug", "priority/p1-high"))
    monkeypatch.setattr(subprocess, "run", github.process(subprocess.run))

    report = collect_project_metrics_report(
        root=root, repo="example/test-repo", store=_roadmap_store(github)
    )
    assert (
        report.repo,
        [release.tag for release in report.releases],
        report.average_cadence_days,
        [(found.milestone, found.completion_rate) for found in report.milestones],
        [(found.label, found.count) for found in report.taxonomy_labels],
        report.items,
    ) == (
        "example/test-repo",
        ["v0.2.25", "v0.2.24", "v0.2.23"],
        2.5,
        [("2026-10-01", 75.0)],
        [("priority/p2-medium", 1), ("type/feature", 1)],
        [
            ItemCountMetric(state="open", type="feature", priority="P2-Medium", count=1),
            ItemCountMetric(
                release="v0.2.24", state="closed", type="bug", priority="P1-High", count=1
            ),
        ],
    )


def test_the_items_are_counted_by_release_state_type_and_priority() -> None:
    """The Items are counted by release, state, type and priority (#2263, #2702); a release and
    a type are empty when the Item has none. An open Item has no release, and a closed Item has
    the release that closed it. An issue with no priority label and a pull request are no Items
    (#2399)."""
    releases = {4: "v0.2.25", 6: "v0.2.25", 7: "v0.2.25"}
    assert get_item_metrics(_roadmap_store(_repository_with_items()), releases) == [
        ItemCountMetric(state="open", priority="P3-Low", count=1),
        ItemCountMetric(state="open", type="bug", priority="P1-High", count=2),
        ItemCountMetric(state="open", type="feature", priority="P2-Medium", count=1),
        ItemCountMetric(
            release="v0.2.25", state="closed", type="feature", priority="P2-Medium", count=1
        ),
    ]


def test_the_items_of_one_milestone_are_counted() -> None:
    """`--milestone` limits the item counts to the milestone, as it limits the milestones."""
    store = _roadmap_store(_repository_with_items())
    assert get_item_metrics(store, {4: "v0.2.25"}, milestone_filter=PLANNED) == [
        ItemCountMetric(state="open", type="feature", priority="P2-Medium", count=1),
        ItemCountMetric(
            release="v0.2.25", state="closed", type="feature", priority="P2-Medium", count=1
        ),
    ]


def test_each_issue_is_released_by_the_first_tag_whose_commits_close_it(
    tmp_path: Path, git_fake: GitFake
) -> None:
    """An issue that a commit closes with a closing keyword belongs to the first `v*` tag that
    holds the commit (#2702). A later commit that closes it again does not move it. A pull
    request reference and a commit after the last tag release no issue."""
    root = tmp_path / "repo"
    root.mkdir()
    tag_output = "v0.1.0|2026-10-01T00:00:00+00:00\nv0.2.0|2026-10-02T00:00:00+00:00\n"
    git_fake.answer(["git", "tag"], ProcessAnswer(stdout=tag_output))

    def _handle_log(call: ProcessCall) -> ProcessAnswer:
        argv = call.argv
        if "v0.1.0..v0.2.0" in argv:
            return ProcessAnswer(stdout="fix: export again\n\nfixes #4\nResolves: #9\n")
        if "v0.1.0" in argv:
            return ProcessAnswer(stdout="feat: export (#12)\n\nCloses #4\n")
        return ProcessAnswer(stdout="")

    git_fake.answer(["git", "log"], _handle_log)

    assert get_item_releases(root) == {4: "v0.1.0", 9: "v0.2.0"}


def test_issues_that_cannot_be_read_stop_the_collection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, git_fake: GitFake
) -> None:
    """A failed read of the issues raises. It is no empty roadmap: the 0 for each label set that
    left the last snapshot would otherwise erase every count."""
    root = tmp_path / "repo"
    root.mkdir()
    git_fake.answer(["git", "tag"], ProcessAnswer(stdout="v0.2.25|2026-10-01T00:00:00+00:00\n"))
    git_fake.answer(["git", "log"], ProcessAnswer(stdout=""))
    git_fake.answer(["git", "rev-list"], ProcessAnswer(stdout="1\n"))
    github = GitHubFake(REPO)
    monkeypatch.setattr(subprocess, "run", github.process(subprocess.run))

    def unavailable(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 1, "", "HTTP 503: Service Unavailable")

    store = GitHubRoadmapStore(REPO, runner=unavailable, session=RunnerSession(unavailable))
    with pytest.raises(DevOpsCLIError) as raised:
        collect_project_metrics_report(root=root, repo=REPO, store=store)
    assert raised.value.error_code == "GITHUB_UNREAD"


def test_a_given_root_is_walked_as_it_is_even_inside_another_checkout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    git_fake: GitFake,
) -> None:
    """A local `devops roadmap run` keeps each repository's clone under `.data/`, inside the
    workspace checkout (#1358). The report walks the tags of the clone it is given, not those of
    the checkout around it, and every read it makes succeeds."""
    workspace = tmp_path / "workspace"
    clone = workspace / ".data" / "roadmap" / "example" / "roadmap" / "clone"
    clone.mkdir(parents=True)

    def _handle_tag(call: ProcessCall) -> ProcessAnswer:
        if call.cwd == clone:
            return ProcessAnswer(
                stdout="v0.1.0|2026-10-01T00:00:00+00:00\nv0.2.0|2026-10-02T00:00:00+00:00\n"
            )
        return ProcessAnswer(
            stdout="v9.0.0|2026-10-01T00:00:00+00:00\nv9.1.0|2026-10-02T00:00:00+00:00\n"
        )

    git_fake.answer(["git", "tag"], _handle_tag)
    git_fake.answer(["git", "log"], ProcessAnswer(stdout=""))
    git_fake.answer(["git", "rev-list"], ProcessAnswer(stdout="1\n"))
    github = GitHubFake("example/roadmap")
    monkeypatch.setattr(subprocess, "run", github.process(subprocess.run))
    with caplog.at_level(logging.WARNING):
        report = collect_project_metrics_report(
            root=clone, repo="example/roadmap", store=_roadmap_store(github)
        )
    assert (
        [release.tag for release in report.releases],
        [record.getMessage() for record in caplog.records if record.levelno >= logging.WARNING],
    ) == (["v0.2.0", "v0.1.0"], [])


def test_emit_project_metrics_telemetry(otlp: FakeCollector) -> None:
    """Verify OpenTelemetry emission for all project metric series."""
    report = ProjectMetricsReport(
        repo="example/repo",
        generated_at="2026-10-02 00:00:00 UTC",
        total_releases=1,
        average_cadence_days=2.0,
        releases=[
            ReleaseCadenceMetric(
                tag="v0.2.25",
                published_at="2026-10-01",
                days_since_prev=2.0,
                commit_count=5,
                pr_count=4,
            )
        ],
        workflow_runs=[
            WorkflowRunMetric(
                workflow="CI", total_runs=2, passed=2, failed=0, other=0, pass_rate=100.0
            )
        ],
        milestones=[
            MilestoneMetric(
                milestone="2026-10-01",
                state="open",
                open_items=3,
                closed_items=7,
                total_items=10,
                completion_rate=70.0,
            )
        ],
        items=[ItemCountMetric(release="v0.2.25", state="closed", type="bug", count=3)],
        taxonomy_labels=[LabelTaxonomyMetric(category="type", label="type/bug", count=2)],
        traffic=TrafficSummaryMetric(
            views_count=100,
            views_uniques=40,
            clones_count=50,
            clones_uniques=20,
            stars=15,
            forks=4,
            referrers=[TrafficReferrerMetric(referrer="github.com", count=30, uniques=15)],
            paths=[TrafficPathMetric(path="/docs", title="Docs", count=45, uniques=20)],
        ),
    )

    emit_project_metrics_telemetry(report)
    instrument_names = {m["name"] for m in otlp.metrics}

    expected_instruments = {
        "devops_cli_project_releases",
        "devops_cli_project_commits",
        "devops_cli_project_prs",
        "devops_cli_project_release_interval_days",
        "devops_cli_project_ci_runs",
        "devops_cli_project_items",
        "devops_cli_project_traffic_views",
        "devops_cli_project_traffic_views_uniques",
        "devops_cli_project_traffic_clones",
        "devops_cli_project_traffic_clones_uniques",
        "devops_cli_project_stars",
        "devops_cli_project_forks",
        "devops_cli_project_traffic_referrers",
        "devops_cli_project_traffic_paths",
    }
    assert expected_instruments.issubset(instrument_names)


def _snapshot(*items: ItemCountMetric) -> ProjectMetricsReport:
    """A report that holds only `items`."""
    return ProjectMetricsReport(
        repo=REPO, generated_at="2026-10-26 00:00:00 UTC", items=list(items)
    )


def _sent_items(otlp: FakeCollector, already_read: int = 0) -> dict[tuple[str, ...], float]:
    """The value of each items series that the client sent after the first `already_read`
    points, by its label values in the order of `PROJECT_ITEM_LABELS`."""
    points = otlp.points(PROJECT_ITEMS.name)[already_read:]
    return {tuple(attrs[label] for label in PROJECT_ITEM_LABELS): value for attrs, value in points}


def test_the_items_gauge_is_sent_with_the_labels_of_its_description(otlp: FakeCollector) -> None:
    """The gauge carries the labels that its instrument names, and an item in no release has
    an empty `release`."""
    emit_project_metrics_telemetry(
        _snapshot(
            ItemCountMetric(state="open", type="bug", priority="P1-High", count=2),
            ItemCountMetric(release="v0.2.25", state="closed", type="feature", count=5),
        )
    )

    assert PROJECT_ITEM_LABELS == ("release", "state", "type", "priority")
    assert _sent_items(otlp) == {
        ("", "open", "bug", "P1-High"): 2.0,
        ("v0.2.25", "closed", "feature", ""): 5.0,
    }


def test_a_label_set_with_no_items_is_sent_as_zero_once(otlp: FakeCollector) -> None:
    """A series that is not sent again keeps its last value in `last_over_time`, so an item
    that closes would stay in the open count. The set it left is sent as 0, once."""
    opened = ItemCountMetric(state="open", type="bug", count=1)
    closed = ItemCountMetric(state="closed", type="bug", count=1)

    emit_project_metrics_telemetry(_snapshot(opened))
    first = _sent_items(otlp)
    sent = len(otlp.points(PROJECT_ITEMS.name))
    emit_project_metrics_telemetry(_snapshot(closed))
    second = _sent_items(otlp, sent)
    sent = len(otlp.points(PROJECT_ITEMS.name))
    emit_project_metrics_telemetry(_snapshot(closed))
    third = _sent_items(otlp, sent)

    assert (first, second, third) == (
        {("", "open", "bug", ""): 1.0},
        {("", "open", "bug", ""): 0.0, ("", "closed", "bug", ""): 1.0},
        {("", "closed", "bug", ""): 1.0},
    )


def test_cli_gh_metrics_formats_tables_and_json(
    cli: CliRunnerFixture, process_fake: ProcessFake, roadmap_store: InMemoryRoadmapStore
) -> None:
    """Verify devops gh metrics execution with interactive and JSON outputs."""
    process_fake.answer(
        ["gh", "api", "rate_limit"],
        ProcessAnswer(stdout=_fresh_quota_payload()),
    )
    tag_output = "v0.2.25|2026-10-01T00:00:00+00:00\n"
    process_fake.answer(["git", "tag"], ProcessAnswer(stdout=tag_output))
    process_fake.answer(["git", "rev-list"], ProcessAnswer(stdout="10\n"))
    process_fake.answer(["git", "log"], ProcessAnswer(stdout="* item (#1)\n"))
    process_fake.answer(
        ["gh", "api", "repos/example/repo/actions/runs"],
        ProcessAnswer(
            stdout=json.dumps(
                {"workflow_runs": [{"name": "CI Quality Gate", "conclusion": "success"}]}
            )
        ),
    )
    process_fake.answer(
        ["gh", "api", "repos/example/repo/milestones"],
        ProcessAnswer(
            stdout=json.dumps(
                [{"title": "2026-10-01", "state": "open", "open_issues": 2, "closed_issues": 8}]
            )
        ),
    )
    process_fake.answer(
        ["gh", "api", "--paginate", "repos/example/repo/issues"],
        ProcessAnswer(stdout=json.dumps([{"labels": [{"name": "type/bug"}]}])),
    )
    process_fake.answer(
        ["gh", "api", "repos/example/repo/traffic/views"],
        ProcessAnswer(stdout=json.dumps({"count": 100, "uniques": 40})),
    )
    process_fake.answer(
        ["gh", "api", "repos/example/repo/traffic/clones"],
        ProcessAnswer(stdout=json.dumps({"count": 50, "uniques": 20})),
    )
    process_fake.answer(
        ["gh", "api", "repos/example/repo/traffic/popular/referrers"],
        ProcessAnswer(stdout=json.dumps([{"referrer": "github.com", "count": 30, "uniques": 15}])),
    )
    process_fake.answer(
        ["gh", "api", "repos/example/repo/traffic/popular/paths"],
        ProcessAnswer(
            stdout=json.dumps([{"path": "/docs", "title": "Docs", "count": 45, "uniques": 20}])
        ),
    )
    process_fake.answer(
        ["gh", "api", "repos/example/repo"],
        ProcessAnswer(
            stdout=json.dumps({"stargazers_count": 15, "forks_count": 4, "open_issues_count": 10})
        ),
    )

    # 1. Plain text / tables
    result_tables = cli("gh", "metrics", "--repo", "example/repo", "--emit-telemetry")
    assert result_tables.exit_code == 0
    assert (
        "Engineering Velocity & Project Metrics" in result_tables.output,
        "v0.2.25" in result_tables.output,
        "Top Referral Sources" in result_tables.output,
        "Popular Content Paths" in result_tables.output,
        "GitHub Stars:" in result_tables.output,
        "14-Day Traffic:" in result_tables.output,
    ) == (
        True,
        True,
        True,
        True,
        True,
        True,
    )

    # 2. JSON output
    result_json = cli("gh", "metrics", "--repo", "example/repo", "--json")
    assert result_json.exit_code == 0
    parsed = json.loads(result_json.output)
    assert (parsed["repo"], parsed["total_releases"], parsed["average_cadence_days"]) == (
        "example/repo",
        1,
        0.0,
    )


def test_get_repository_traffic_metrics_falls_back_when_not_permitted(
    process_fake: ProcessFake,
) -> None:
    """Verify repository traffic queries and resilient fallback on API error."""
    process_fake.answer(
        ["gh", "api", "rate_limit"],
        ProcessAnswer(stdout=_fresh_quota_payload()),
    )
    process_fake.answer(
        ["gh", "api", "repos/example/repo/traffic/views"],
        ProcessAnswer(stdout=json.dumps({"count": 150, "uniques": 45, "views": []})),
    )
    process_fake.answer(
        ["gh", "api", "repos/example/repo/traffic/clones"],
        ProcessAnswer(stdout=json.dumps({"count": 80, "uniques": 20, "clones": []})),
    )
    process_fake.answer(
        ["gh", "api", "repos/example/repo/traffic/popular/referrers"],
        ProcessAnswer(stdout=json.dumps([{"referrer": "github.com", "count": 60, "uniques": 30}])),
    )
    process_fake.answer(
        ["gh", "api", "repos/example/repo/traffic/popular/paths"],
        ProcessAnswer(
            stdout=json.dumps([{"path": "/repo", "title": "Repo", "count": 100, "uniques": 40}])
        ),
    )
    process_fake.answer(
        ["gh", "api", "repos/example/repo"],
        ProcessAnswer(
            stdout=json.dumps({"stargazers_count": 25, "forks_count": 5, "open_issues_count": 12})
        ),
    )

    traffic = get_repository_traffic_metrics("example/repo")
    assert (
        traffic.views_count,
        traffic.views_uniques,
        traffic.clones_count,
        traffic.clones_uniques,
        traffic.stars,
        traffic.forks,
        traffic.open_issues,
        len(traffic.referrers),
        len(traffic.paths),
    ) == (
        150,
        45,
        80,
        20,
        25,
        5,
        12,
        1,
        1,
    )

    # Test fallback on API error
    reset_refused_paths()
    process_fake.answer(
        ["gh", "api"],
        ProcessAnswer(returncode=1, stderr="API rate limited"),
    )
    process_fake.answer(
        ["gh", "api", "rate_limit"],
        ProcessAnswer(stdout=_fresh_quota_payload()),
    )
    fallback = get_repository_traffic_metrics("example/repo")
    assert (
        fallback.views_count,
        fallback.views_uniques,
        fallback.clones_count,
        fallback.clones_uniques,
        fallback.stars,
        fallback.forks,
        fallback.referrers,
        fallback.paths,
    ) == (
        0,
        0,
        0,
        0,
        0,
        0,
        [],
        [],
    )


def test_get_git_tag_entries_when_git_runs_out_of_time(
    process_fake: ProcessFake, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A `git` read that runs out of time gives no tags, and the warning says so (#1538)."""
    process_fake.answer(
        "git", ProcessAnswer(side_effect=subprocess.TimeoutExpired(cmd=["git", "tag"], timeout=15))
    )

    with caplog.at_level(logging.WARNING, logger="devops_cli.github.metrics"):
        entries = get_git_tag_entries(tmp_path)

    assert (entries, "git tag timed out" in caplog.text) == ([], True)


def test_extract_commits_and_prs_counts_one_commit_for_a_count_git_does_not_give(
    process_fake: ProcessFake, tmp_path: Path
) -> None:
    """A commit count that is not a number counts as one commit, as a failed read does (#1538)."""
    process_fake.answer(["git", "rev-list"], ProcessAnswer(stdout="not-a-number\n"))
    process_fake.answer(["git", "log"], ProcessAnswer(stdout=""))

    assert extract_commits_and_prs(tmp_path, "v0.2.20", "v0.2.21") == (1, 0)


# ── The traffic of a repository under the App (#2752) ─────────────────────────

REFUSED_BY_TOKEN = (1, "gh: Resource not accessible by integration (HTTP 403)")
"""What `gh api` writes when an installation token lacks the permission of the path."""
TRAFFIC_ENDPOINTS = (
    "traffic/views",
    "traffic/clones",
    "traffic/popular/referrers",
    "traffic/popular/paths",
)
TRAFFIC_SERIES = (
    PROJECT_TRAFFIC_VIEWS,
    PROJECT_TRAFFIC_VIEWS_UNIQUES,
    PROJECT_TRAFFIC_CLONES,
    PROJECT_TRAFFIC_CLONES_UNIQUES,
    PROJECT_TRAFFIC_REFERRERS,
    PROJECT_TRAFFIC_PATHS,
)


def _traffic_paths(repo: str, *, only: str | None = None) -> list[str]:
    """The paths of the traffic endpoints of `repo`, or those that end with `only`."""
    return [f"repos/{repo}/{e}" for e in TRAFFIC_ENDPOINTS if only is None or e.endswith(only)]


def _github(
    monkeypatch: pytest.MonkeyPatch,
    *,
    app: bool,
    traffic_answer: tuple[int, str] | None = None,
) -> GitHubFake:
    """A fake GitHub at the `gh` edge, with the process acting as the App or as a person."""
    github = GitHubFake("example/repo", traffic_answer=traffic_answer)
    monkeypatch.setattr(subprocess, "run", github.process(subprocess.run))
    if app:
        monkeypatch.setenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, "mock-app-key")
    else:
        monkeypatch.delenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, raising=False)
    return github


def test_a_workstation_asks_the_four_traffic_endpoints(monkeypatch: pytest.MonkeyPatch) -> None:
    """A process with a person's login collects the traffic, as before."""
    github = _github(monkeypatch, app=False)

    traffic = get_repository_traffic_metrics("example/repo")

    assert (github.traffic_calls(), traffic.traffic_collected) == (
        _traffic_paths("example/repo"),
        True,
    )


def test_the_app_asks_no_traffic_endpoint_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """The installation token has no Administration permission, so a process that acts as the
    App sends no traffic request. The stars and forks still come from the repository read."""
    github = _github(monkeypatch, app=True)

    traffic = get_repository_traffic_metrics("example/repo")

    assert (github.traffic_calls(), traffic.traffic_collected, traffic.open_issues) == (
        [],
        False,
        0,
    )


def test_a_report_without_traffic_sends_no_traffic_series(
    monkeypatch: pytest.MonkeyPatch, otlp: FakeCollector
) -> None:
    """The panels show no data for a series that nothing sends, not a 0 for no visitors. The
    stars and forks are still sent."""
    _github(monkeypatch, app=True)
    report = ProjectMetricsReport(
        repo="example/repo",
        generated_at="2026-10-30 00:00:00 UTC",
        traffic=get_repository_traffic_metrics("example/repo"),
    )

    emit_project_metrics_telemetry(report)

    assert (
        {s.name: otlp.points(s.name) for s in TRAFFIC_SERIES},
        [otlp.points(s.name) for s in (PROJECT_STARS, PROJECT_FORKS)],
    ) == ({s.name: [] for s in TRAFFIC_SERIES}, [[({}, 0.0)], [({}, 0.0)]])


def test_a_report_with_traffic_sends_the_traffic_series(
    monkeypatch: pytest.MonkeyPatch, otlp: FakeCollector
) -> None:
    """A workstation sends the four totals. The referrer and path series have a point for each
    referrer and path, and the fake repository has none."""
    _github(monkeypatch, app=False)
    report = ProjectMetricsReport(
        repo="example/repo",
        generated_at="2026-10-30 00:00:00 UTC",
        traffic=get_repository_traffic_metrics("example/repo"),
    )

    emit_project_metrics_telemetry(report)

    assert {s.name for s in TRAFFIC_SERIES if otlp.points(s.name)} == {
        s.name
        for s in (
            PROJECT_TRAFFIC_VIEWS,
            PROJECT_TRAFFIC_VIEWS_UNIQUES,
            PROJECT_TRAFFIC_CLONES,
            PROJECT_TRAFFIC_CLONES_UNIQUES,
        )
    }


def test_a_path_that_the_token_cannot_read_is_asked_once(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """After one 403 "Resource not accessible by integration" for a repository and an endpoint,
    the process does not ask that path again. The refusal logs zero warnings and one debug line (#2626)."""
    github = _github(monkeypatch, app=False, traffic_answer=REFUSED_BY_TOKEN)

    with caplog.at_level(logging.DEBUG, logger="devops_cli.github.metrics"):
        get_repository_traffic_metrics("example/repo")
        get_repository_traffic_metrics("example/repo")

    warnings = [
        r
        for r in caplog.records
        if r.levelno >= logging.WARNING and "traffic" in r.getMessage().lower()
    ]
    debugs = [
        r
        for r in caplog.records
        if r.levelno == logging.DEBUG and "integration" in r.getMessage().lower()
    ]

    assert (
        github.traffic_calls(),
        warnings,
        len(debugs),
    ) == (_traffic_paths("example/repo"), [], 1)


def test_traffic_api_integration_403_skips_gauges(
    monkeypatch: pytest.MonkeyPatch, otlp: FakeCollector
) -> None:
    """When the traffic API returns 403 integration refusal, no traffic gauges are emitted (#2626)."""
    _github(monkeypatch, app=False, traffic_answer=REFUSED_BY_TOKEN)

    traffic = get_repository_traffic_metrics("example/repo")
    assert traffic.traffic_collected is False

    report = ProjectMetricsReport(
        repo="example/repo",
        generated_at="2026-10-30 00:00:00 UTC",
        traffic=traffic,
    )
    emit_project_metrics_telemetry(report)
    assert [otlp.points(s.name) for s in TRAFFIC_SERIES] == [[] for _ in TRAFFIC_SERIES]


def test_a_refusal_for_one_repository_does_not_stop_the_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The guard keys on the whole path, so another repository is asked."""
    github = _github(monkeypatch, app=False, traffic_answer=REFUSED_BY_TOKEN)

    get_repository_traffic_metrics("example/one")
    get_repository_traffic_metrics("example/two")

    assert github.traffic_calls() == _traffic_paths("example/one") + _traffic_paths("example/two")


@pytest.mark.parametrize(
    "answer",
    [
        (1, "gh: Bad Gateway (HTTP 502)"),
        (1, "gh: Must have push access to view repository traffic (HTTP 403)"),
    ],
)
def test_a_failure_that_is_not_a_refusal_by_the_token_is_asked_again(
    monkeypatch: pytest.MonkeyPatch, answer: tuple[int, str]
) -> None:
    """A 502 and a 403 for a person without push access pass: the guard is for the refusal that an
    installation token gets, and the rate limiter owns the waits for a rate limit."""
    github = _github(monkeypatch, app=False, traffic_answer=answer)

    get_repository_traffic_metrics("example/repo")
    get_repository_traffic_metrics("example/repo")

    assert github.traffic_calls() == _traffic_paths("example/repo") * 2


def test_a_new_process_asks_a_refused_path_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """The guard lasts for the process: a restart sends the path again."""
    github = _github(monkeypatch, app=False, traffic_answer=REFUSED_BY_TOKEN)
    get_repository_traffic_metrics("example/repo")

    reset_refused_paths()
    get_repository_traffic_metrics("example/repo")

    assert github.traffic_calls() == _traffic_paths("example/repo") * 2


def test_the_command_prints_that_the_app_collected_no_traffic(
    cli: CliRunnerFixture,
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
    roadmap_store: InMemoryRoadmapStore,
) -> None:
    """A report with no traffic prints "not collected" and no count of views."""
    monkeypatch.setenv(CONST_GITHUB_APP_PRIVATE_KEY_ENV, "mock-app-key")
    process_fake.answer(
        ["gh", "api", "rate_limit"],
        ProcessAnswer(stdout=_fresh_quota_payload()),
    )
    process_fake.answer(["git", "tag"], ProcessAnswer(stdout=""))
    process_fake.answer(
        ["gh", "api", "repos/example/repo/actions/runs"],
        ProcessAnswer(stdout=json.dumps({"workflow_runs": []})),
    )
    process_fake.answer(
        ["gh", "api", "repos/example/repo/milestones"],
        ProcessAnswer(stdout=json.dumps([])),
    )
    process_fake.answer(
        ["gh", "api", "--paginate", "repos/example/repo/issues"],
        ProcessAnswer(stdout=json.dumps([])),
    )
    process_fake.answer(
        ["gh", "api", "repos/example/repo"],
        ProcessAnswer(
            stdout=json.dumps({"stargazers_count": 3, "forks_count": 0, "open_issues_count": 0})
        ),
    )

    result = cli("gh", "metrics", "--repo", "example/repo")

    assert (result.exit_code, "not collected" in result.output, "0 views" in result.output) == (
        0,
        True,
        False,
    )
