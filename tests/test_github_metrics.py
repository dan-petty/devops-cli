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
from devops_cli.github.metrics import (
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
    get_label_taxonomy_metrics,
    get_milestone_metrics,
    get_release_cadence_metrics,
    get_repository_traffic_metrics,
    record_project_metrics_in_registry,
)
from devops_cli.telemetry.metrics import InMemoryMetricsRegistry
from tests.roadmap_board_fake import GitHubFake

runner = CliRunner()


def test_parse_tag_datetime_valid_and_invalid() -> None:
    """Verify ISO string parsing and fallback behavior."""
    iso_date = "2026-09-28T12:00:00+00:00"
    parsed_utc = _parse_tag_datetime(iso_date)
    fallback = _parse_tag_datetime("not-a-date")

    assert (
        parsed_utc.year,
        parsed_utc.month,
        parsed_utc.day,
        isinstance(fallback, datetime.datetime),
    ) == (
        2026,
        9,
        28,
        True,
    )


def test_get_git_tag_entries_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify git tag discovery and chronological sorting."""
    raw_output = "v0.2.20|2026-09-19T10:00:00Z\nv0.2.21|2026-09-20T10:00:00Z\n"
    mock_run = MagicMock(
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout=raw_output)
    )
    monkeypatch.setattr(subprocess, "run", mock_run)

    entries = _get_git_tag_entries(tmp_path)
    assert len(entries) == 2
    assert (entries[0][0], entries[1][0]) == ("v0.2.20", "v0.2.21")


def test_get_git_tag_entries_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify git tag discovery handles subprocess failures gracefully."""
    mock_run = MagicMock(side_effect=subprocess.SubprocessError("git error"))
    monkeypatch.setattr(subprocess, "run", mock_run)

    entries = _get_git_tag_entries(tmp_path)
    assert entries == []


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


def test_extract_commits_and_prs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify calculation of commit counts and unique PR numbers between tags."""

    def fake_subprocess_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "rev-list" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="1\n")
        body = (
            "* feat(core): item 1 (#101)\n* fix(core): item 2 (#102)\n* fix(core): item 3 (#101)\n"
        )
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=body)

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)
    commits, prs = _extract_commits_and_prs(tmp_path, "v0.2.20", "v0.2.21")
    assert (commits, prs) == (3, 2)


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
    raw_open = {"title": "v0.2.25", "state": "open", "open_issues": 3, "closed_issues": 7}
    raw_closed = {"title": "v0.2.24", "state": "closed", "open_issues": 0, "closed_issues": 10}
    raw_empty = {"title": "v0.2.26", "state": "open", "open_issues": 0, "closed_issues": 0}

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

    filtered = get_milestone_metrics("example/repo", milestone_filter="v0.2.25")
    assert len(filtered) == 1
    assert (filtered[0].milestone, filtered[0].open_items, filtered[0].closed_items) == (
        "v0.2.25",
        3,
        7,
    )


def test_get_label_taxonomy_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify label taxonomy extraction and aggregation."""
    issues = [
        {"labels": [{"name": "priority/p1-high"}, {"name": "scope/cli"}]},
        {"labels": [{"name": "priority/p1-high"}, {"name": "priority/p2-medium"}]},
        {"labels": ["scope/cli", "unscoped-label"]},
    ]
    mock_client = MagicMock()
    mock_client.api.return_value = json.dumps(issues)
    monkeypatch.setattr("devops_cli.github.metrics.GhCliClient", lambda: mock_client)

    metrics = get_label_taxonomy_metrics("example/repo")
    p1 = next((m for m in metrics if m.label == "priority/p1-high"), None)
    cli_scope = next((m for m in metrics if m.label == "scope/cli"), None)

    assert (p1 is not None, cli_scope is not None) == (True, True)
    assert (p1.count, cli_scope.count) == (2, 2)


def test_collect_project_metrics_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, git: Callable[..., None]
) -> None:
    """The report takes its releases from the repository's tags and its milestones and open
    issues' labels from GitHub, each read at its process edge."""
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "--quiet", "--initial-branch=main")
    for tag, day in (
        ("v0.2.23", "2026-09-26"),
        ("v0.2.24", "2026-09-28"),
        ("v0.2.25", "2026-10-01"),
    ):
        monkeypatch.setenv("GIT_COMMITTER_DATE", f"{day}T12:00:00+00:00")
        git(root, "commit", "--quiet", "--allow-empty", "-m", f"release {tag}")
        git(root, "tag", tag)
    milestone = {"title": "v0.2.25", "state": "closed", "open_issues": 1, "closed_issues": 3}
    github = GitHubFake("example/test-repo", milestones=[milestone])
    github.seed_issue(1, "feat: export", labels=("type/feature",))
    monkeypatch.setattr(subprocess, "run", github.process(subprocess.run))

    report = collect_project_metrics_report(root=root, repo="example/test-repo")
    assert (
        report.repo,
        [release.tag for release in report.releases],
        report.average_cadence_days,
        [(found.milestone, found.completion_rate) for found in report.milestones],
        [(found.label, found.count) for found in report.taxonomy_labels],
    ) == (
        "example/test-repo",
        ["v0.2.25", "v0.2.24", "v0.2.23"],
        2.5,
        [("v0.2.25", 75.0)],
        [("type/feature", 1)],
    )


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
        report = collect_project_metrics_report(root=clone, repo="example/roadmap")
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
                milestone="v0.2.25",
                state="open",
                open_items=3,
                closed_items=7,
                total_items=10,
                completion_rate=70.0,
            )
        ],
        taxonomy_labels=[
            LabelTaxonomyMetric(category="priority", label="priority/p1-high", count=2)
        ],
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
        "devops_cli_project_releases_total",
        "devops_cli_project_commits_total",
        "devops_cli_project_prs_total",
        "devops_cli_project_release_interval_days",
        "devops_cli_project_ci_runs_total",
        "devops_cli_project_items_total",
        "devops_cli_project_traffic_views_total",
        "devops_cli_project_traffic_views_uniques_total",
        "devops_cli_project_traffic_clones_total",
        "devops_cli_project_traffic_clones_uniques_total",
        "devops_cli_project_stars_total",
        "devops_cli_project_forks_total",
        "devops_cli_project_traffic_referrers_total",
        "devops_cli_project_traffic_paths_total",
    }
    assert expected_instruments.issubset(set(instrument_names))


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
                milestone="v0.2.25",
                state="open",
                open_items=2,
                closed_items=8,
                total_items=10,
                completion_rate=80.0,
            )
        ],
        taxonomy_labels=[
            LabelTaxonomyMetric(category="priority", label="priority/p1-high", count=5)
        ],
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


def test_record_project_metrics_in_registry() -> None:
    """Verify in-memory metrics registry is populated with gauges and exports Prometheus text."""
    reg = InMemoryMetricsRegistry()
    report = ProjectMetricsReport(
        repo="example/repo",
        generated_at="2026-10-02 00:00:00 UTC",
        total_releases=2,
        average_cadence_days=3.0,
        releases=[
            ReleaseCadenceMetric(
                tag="v0.2.25",
                published_at="2026-10-01",
                days_since_prev=3.0,
                commit_count=12,
                pr_count=8,
            )
        ],
        workflow_runs=[
            WorkflowRunMetric(
                workflow="CI Quality Gate",
                total_runs=2,
                passed=2,
                failed=0,
                other=0,
                pass_rate=100.0,
            )
        ],
        milestones=[
            MilestoneMetric(
                milestone="v0.2.25",
                state="open",
                open_items=3,
                closed_items=7,
                total_items=10,
                completion_rate=70.0,
            )
        ],
        taxonomy_labels=[
            LabelTaxonomyMetric(category="priority", label="priority/p1-high", count=2)
        ],
        traffic=TrafficSummaryMetric(
            views_count=150,
            views_uniques=45,
            clones_count=80,
            clones_uniques=20,
            stars=25,
            forks=5,
            open_issues=12,
            referrers=[TrafficReferrerMetric(referrer="github.com", count=60, uniques=30)],
            paths=[TrafficPathMetric(path="/repo", title="Repo", count=100, uniques=40)],
        ),
    )

    record_project_metrics_in_registry(report, registry=reg)

    assert (
        reg.get_gauge("devops_cli_project_releases_total"),
        reg.get_gauge("devops_cli_project_traffic_views_total"),
        reg.get_gauge("devops_cli_project_traffic_views_uniques_total"),
        reg.get_gauge("devops_cli_project_traffic_clones_total"),
        reg.get_gauge("devops_cli_project_traffic_clones_uniques_total"),
        reg.get_gauge("devops_cli_project_stars_total"),
        reg.get_gauge("devops_cli_project_forks_total"),
        reg.get_gauge("devops_cli_project_traffic_referrers_total", {"referrer": "github.com"}),
        reg.get_gauge("devops_cli_project_traffic_paths_total", {"path": "/repo"}),
        reg.get_gauge("devops_cli_project_commits_total", {"release": "v0.2.25"}),
        reg.get_gauge("devops_cli_project_prs_total", {"release": "v0.2.25"}),
        reg.get_gauge("devops_cli_project_items_total", {"milestone": "v0.2.25", "state": "open"}),
        reg.get_gauge(
            "devops_cli_project_items_total", {"milestone": "v0.2.25", "state": "closed"}
        ),
    ) == (
        2.0,
        150.0,
        45.0,
        80.0,
        20.0,
        25.0,
        5.0,
        60.0,
        100.0,
        12.0,
        8.0,
        3.0,
        7.0,
    )

    prom_text = reg.export_prometheus_text()
    assert (
        "devops_cli_project_releases_total 2.0" in prom_text,
        "devops_cli_project_traffic_views_total 150.0" in prom_text,
        'devops_cli_project_traffic_referrers_total{referrer="github.com"} 60.0' in prom_text,
        'devops_cli_project_traffic_paths_total{path="/repo"} 100.0' in prom_text,
    ) == (
        True,
        True,
        True,
        True,
    )
