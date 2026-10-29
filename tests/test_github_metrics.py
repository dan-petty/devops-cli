"""Unit tests for GitHub project & release metrics analytics engine and CLI."""

from __future__ import annotations

import datetime
import json
import logging
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from devops_cli.commands.gh import app as gh_app
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
    _build_milestone_metric,
    _calculate_pass_rate,
    _classify_workflow_conclusion,
    _count_bullet_commits,
    _extract_commits_and_prs,
    _get_git_tag_entries,
    _parse_tag_datetime,
    collect_project_metrics_report,
    emit_project_metrics_telemetry,
    get_ci_workflow_metrics,
    get_item_metrics,
    get_item_releases,
    get_label_taxonomy_metrics,
    get_milestone_metrics,
    get_release_cadence_metrics,
    get_repository_traffic_metrics,
)
from devops_cli.roadmap.github_store import GitHubRoadmapStore
from devops_cli.telemetry.instruments import PROJECT_ITEM_LABELS, PROJECT_ITEMS
from tests.roadmap_github_fake import GitHubFake
from tests.support.fakes.github import RunnerSession
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.process import ProcessAnswer, ProcessFake

runner = CliRunner()
REPO = "example/test-repo"
PLANNED = "2026-11-01"


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
    parsed_utc = _parse_tag_datetime(iso_date)
    fallback = _parse_tag_datetime("not-a-date")

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


def test_get_git_tag_entries_success(process_fake: ProcessFake, tmp_path: Path) -> None:
    """Verify git tag discovery, as a local read in the root, and chronological sorting."""
    raw_output = "v0.2.21|2026-09-20T10:00:00Z\nv0.2.20|2026-09-19T10:00:00Z\n"
    process_fake.answer(["git", "tag"], ProcessAnswer(stdout=raw_output))

    entries = _get_git_tag_entries(tmp_path)

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
        entries = _get_git_tag_entries(tmp_path)

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
    count = _count_bullet_commits(body)
    assert count == 3


def test_extract_commits_and_prs(process_fake: ProcessFake, tmp_path: Path) -> None:
    """Verify calculation of commit counts and unique PR numbers between tags, from local reads
    of git in the root."""
    process_fake.answer(["git", "rev-list"], ProcessAnswer(stdout="1\n"))
    body = "* feat(core): item 1 (#101)\n* fix(core): item 2 (#102)\n* fix(core): item 3 (#101)\n"
    process_fake.answer(["git", "log"], ProcessAnswer(stdout=body))

    commits, prs = _extract_commits_and_prs(tmp_path, "v0.2.20", "v0.2.21")

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

    assert _extract_commits_and_prs(tmp_path, "v0.2.20", "v0.2.21") == (1, 0)


def test_get_release_cadence_metrics(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify release cadence interval calculation and reverse-chronological ordering."""
    entries = [
        ("v0.2.20", datetime.datetime(2026, 9, 10, 0, 0, tzinfo=datetime.UTC)),
        ("v0.2.21", datetime.datetime(2026, 9, 12, 12, 0, tzinfo=datetime.UTC)),
        ("v0.2.22", datetime.datetime(2026, 9, 15, 0, 0, tzinfo=datetime.UTC)),
    ]
    monkeypatch.setattr("devops_cli.github.metrics._get_git_tag_entries", lambda _: entries)
    monkeypatch.setattr("devops_cli.github.metrics._extract_commits_and_prs", lambda *_: (10, 5))

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


def test_calculate_pass_rate_and_conclusion() -> None:
    """Verify pass rate percentage calculation and conclusion classification."""
    rate_100 = _calculate_pass_rate(10, 0)
    rate_50 = _calculate_pass_rate(5, 5)
    rate_zero = _calculate_pass_rate(0, 0)

    c_success = _classify_workflow_conclusion("success")
    c_failure = _classify_workflow_conclusion("failure")
    c_timed_out = _classify_workflow_conclusion("timed_out")
    c_other = _classify_workflow_conclusion("cancelled")

    assert (rate_100, rate_50, rate_zero) == (100.0, 50.0, 100.0)
    assert (c_success, c_failure, c_timed_out, c_other) == (
        (1, 0, 0),
        (0, 1, 0),
        (0, 1, 0),
        (0, 0, 1),
    )


def test_get_ci_workflow_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify CI workflow aggregation and pass rate calculation."""
    fake_runs = {
        "workflow_runs": [
            {"name": "CI Quality Gate", "conclusion": "success"},
            {"name": "CI Quality Gate", "conclusion": "failure"},
            {"name": "Deploy", "conclusion": "success"},
        ]
    }
    mock_client = MagicMock()
    mock_client.api.return_value = json.dumps(fake_runs)
    monkeypatch.setattr("devops_cli.github.metrics.GhCliClient", lambda: mock_client)

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


def test_get_ci_workflow_metrics_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_ci_workflow_metrics returns empty list on API error."""
    mock_client = MagicMock()
    mock_client.api.side_effect = RuntimeError("network error")
    monkeypatch.setattr("devops_cli.github.metrics.GhCliClient", lambda: mock_client)

    results = get_ci_workflow_metrics("example/repo")
    assert results == []


def test_build_milestone_metric_and_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify milestone metric extraction, completion percentage, and filtering."""
    raw_open = {"title": "2026-10-01", "state": "open", "open_issues": 3, "closed_issues": 7}
    raw_closed = {"title": "2026-09-24", "state": "closed", "open_issues": 0, "closed_issues": 10}
    raw_empty = {"title": "2026-10-08", "state": "open", "open_issues": 0, "closed_issues": 0}

    m_open = _build_milestone_metric(raw_open)
    m_closed = _build_milestone_metric(raw_closed)
    m_empty = _build_milestone_metric(raw_empty)

    assert (m_open.completion_rate, m_closed.completion_rate, m_empty.completion_rate) == (
        70.0,
        100.0,
        0.0,
    )

    mock_client = MagicMock()
    mock_client.api.return_value = json.dumps([raw_open, raw_closed])
    monkeypatch.setattr("devops_cli.github.metrics.GhCliClient", lambda: mock_client)

    filtered = get_milestone_metrics("example/repo", milestone_filter="2026-10-01")
    assert len(filtered) == 1
    assert (filtered[0].milestone, filtered[0].open_items, filtered[0].closed_items) == (
        "2026-10-01",
        3,
        7,
    )


def test_get_label_taxonomy_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify label taxonomy extraction and aggregation."""
    issues = [
        {"labels": [{"name": "team/core"}, {"name": "scope/cli"}]},
        {"labels": [{"name": "team/core"}, {"name": "team/infra"}]},
        {"labels": ["scope/cli", "unscoped-label"]},
    ]
    mock_client = MagicMock()
    mock_client.api.return_value = json.dumps(issues)
    monkeypatch.setattr("devops_cli.github.metrics.GhCliClient", lambda: mock_client)

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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, git: Callable[..., None]
) -> None:
    """The report takes its releases from the repository's tags and its milestones and open
    issues' labels from GitHub, each read at its process edge. An Item counts under the release
    whose commits close it (#2702)."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "--quiet", "--initial-branch=main")
    for tag, day in (
        ("v0.2.23", "2026-09-26"),
        ("v0.2.24", "2026-09-28"),
        ("v0.2.25", "2026-10-01"),
    ):
        monkeypatch.setenv("GIT_COMMITTER_DATE", f"{day}T12:00:00+00:00")
        closes = "Closes #2" if tag == "v0.2.24" else "No issue"
        git(root, "commit", "--quiet", "--allow-empty", "-m", f"release {tag}", "-m", closes)
        git(root, "tag", tag)
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
    tmp_path: Path, git: Callable[..., None]
) -> None:
    """An issue that a commit closes with a closing keyword belongs to the first `v*` tag that
    holds the commit (#2702). A later commit that closes it again does not move it. A pull
    request reference and a commit after the last tag release no issue."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "--quiet", "--initial-branch=main")
    for message, tag in (
        ("feat: export (#12)\n\nCloses #4", "v0.1.0"),
        ("fix: export again\n\nfixes #4\nResolves: #9", "v0.2.0"),
        ("fix: import\n\nCloses #7", None),
    ):
        git(root, "commit", "--quiet", "--allow-empty", "-m", message)
        if tag:
            git(root, "tag", tag)

    assert get_item_releases(root) == {4: "v0.1.0", 9: "v0.2.0"}


def test_issues_that_cannot_be_read_stop_the_collection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, git: Callable[..., None]
) -> None:
    """A failed read of the issues raises. It is no empty roadmap: the 0 for each label set that
    left the last snapshot would otherwise erase every count."""
    _tagged_repository(git, tmp_path / "repo", ("v0.2.25",))
    github = GitHubFake(REPO)
    monkeypatch.setattr(subprocess, "run", github.process(subprocess.run))

    def unavailable(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 1, "", "HTTP 503: Service Unavailable")

    store = GitHubRoadmapStore(REPO, runner=unavailable, session=RunnerSession(unavailable))
    with pytest.raises(DevOpsCLIError):
        collect_project_metrics_report(root=tmp_path / "repo", repo=REPO, store=store)


def _tagged_repository(git: Callable[..., None], repo: Path, tags: Sequence[str]) -> None:
    """A repository at `repo` with one commit for each of `tags`, each tagged by name."""
    repo.mkdir(parents=True)
    git(repo, "init", "--quiet", "--initial-branch=main")
    for tag in tags:
        git(repo, "commit", "--quiet", "--allow-empty", "-m", f"release {tag}")
        git(repo, "tag", tag)


def test_a_given_root_is_walked_as_it_is_even_inside_another_checkout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    git: Callable[..., None],
) -> None:
    """A local `devops roadmap run` keeps each repository's clone under `.data/`, inside the
    workspace checkout (#1358). The report walks the tags of the clone it is given, not those of
    the checkout around it, and every read it makes succeeds."""
    workspace = tmp_path / "workspace"
    clone = workspace / ".data" / "roadmap" / "example" / "roadmap" / "clone"
    _tagged_repository(git, workspace, ("v9.0.0", "v9.1.0"))
    _tagged_repository(git, clone, ("v0.1.0", "v0.2.0"))
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


def test_emit_project_metrics_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify OpenTelemetry emission for all project metric series."""
    emitted: list[tuple[Any, float, dict[str, str] | None]] = []

    def fake_emit(instrument: Any, value: float, attributes: dict[str, str] | None = None) -> None:
        emitted.append((instrument.name, value, attributes))

    monkeypatch.setattr("devops_cli.github.metrics.emit", fake_emit)

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
    instrument_names = [e[0] for e in emitted]

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
    assert expected_instruments.issubset(set(instrument_names))


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


def test_cli_gh_metrics_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify devops gh metrics execution with interactive and JSON outputs."""
    report = ProjectMetricsReport(
        repo="example/repo",
        generated_at="2026-10-02 00:00:00 UTC",
        total_releases=1,
        average_cadence_days=2.5,
        releases=[
            ReleaseCadenceMetric(
                tag="v0.2.25",
                published_at="2026-10-01",
                days_since_prev=2.5,
                commit_count=10,
                pr_count=8,
            )
        ],
        workflow_runs=[
            WorkflowRunMetric(
                workflow="CI Quality Gate",
                total_runs=1,
                passed=1,
                failed=0,
                other=0,
                pass_rate=100.0,
            )
        ],
        milestones=[
            MilestoneMetric(
                milestone="2026-10-01",
                state="open",
                open_items=2,
                closed_items=8,
                total_items=10,
                completion_rate=80.0,
            )
        ],
        taxonomy_labels=[LabelTaxonomyMetric(category="type", label="type/bug", count=5)],
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

    monkeypatch.setattr("devops_cli.commands.gh.collect_project_metrics_report", lambda **_: report)
    monkeypatch.setattr("devops_cli.commands.gh.emit_project_metrics_telemetry", lambda _: None)

    # 1. Plain text / tables
    result_tables = runner.invoke(gh_app, ["metrics", "--repo", "example/repo", "--emit-telemetry"])
    assert result_tables.exit_code == 0
    assert (
        "Engineering Velocity & Project Metrics" in result_tables.stdout,
        "v0.2.25" in result_tables.stdout,
        "Top Referral Sources" in result_tables.stdout,
        "Popular Content Paths" in result_tables.stdout,
        "GitHub Stars:" in result_tables.stdout,
        "14-Day Traffic:" in result_tables.stdout,
    ) == (
        True,
        True,
        True,
        True,
        True,
        True,
    )

    # 2. JSON output
    result_json = runner.invoke(gh_app, ["metrics", "--repo", "example/repo", "--json"])
    assert result_json.exit_code == 0
    parsed = json.loads(result_json.stdout)
    assert (parsed["repo"], parsed["total_releases"], parsed["average_cadence_days"]) == (
        "example/repo",
        1,
        2.5,
    )


def test_get_repository_traffic_metrics_success_and_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify repository traffic queries and resilient fallback on API error."""
    from devops_cli.github.client import GhCliClient

    def mock_api_success(self: GhCliClient, endpoint: str) -> str:
        if endpoint == "repos/example/repo/traffic/views":
            return json.dumps({"count": 150, "uniques": 45, "views": []})
        if endpoint == "repos/example/repo/traffic/clones":
            return json.dumps({"count": 80, "uniques": 20, "clones": []})
        if endpoint == "repos/example/repo/traffic/popular/referrers":
            return json.dumps([{"referrer": "github.com", "count": 60, "uniques": 30}])
        if endpoint == "repos/example/repo/traffic/popular/paths":
            return json.dumps([{"path": "/repo", "title": "Repo", "count": 100, "uniques": 40}])
        if endpoint == "repos/example/repo":
            return json.dumps({"stargazers_count": 25, "forks_count": 5, "open_issues_count": 12})
        return "{}"

    monkeypatch.setattr(GhCliClient, "api", mock_api_success)
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
    def mock_api_fail(self: GhCliClient, endpoint: str) -> str:
        raise RuntimeError("API rate limited")

    monkeypatch.setattr(GhCliClient, "api", mock_api_fail)
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
        entries = _get_git_tag_entries(tmp_path)

    assert (entries, "git tag timed out" in caplog.text) == ([], True)


def test_extract_commits_and_prs_counts_one_commit_for_a_count_git_does_not_give(
    process_fake: ProcessFake, tmp_path: Path
) -> None:
    """A commit count that is not a number counts as one commit, as a failed read does (#1538)."""
    process_fake.answer(["git", "rev-list"], ProcessAnswer(stdout="not-a-number\n"))
    process_fake.answer(["git", "log"], ProcessAnswer(stdout=""))

    assert _extract_commits_and_prs(tmp_path, "v0.2.20", "v0.2.21") == (1, 0)
