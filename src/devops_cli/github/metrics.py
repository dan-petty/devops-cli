"""Project metrics and engineering velocity analytics subsystem.

Provides analysis and aggregations for:
- Release frequency and cadence (intervals in days between releases).
- Commits and merged pull requests per release.
- CI quality gate checks and workflow run pass rates.
- Items grouped by milestone and taxonomy labels (priority, type, scope).
- OpenTelemetry instrumentation for Prometheus export and Grafana visualization.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.core.repo import find_worktree_root, get_repo_origin_name
from devops_cli.github.client import GhCliClient
from devops_cli.telemetry.instruments import (
    PROJECT_CI_RUNS_TOTAL,
    PROJECT_COMMITS_TOTAL,
    PROJECT_FORKS_TOTAL,
    PROJECT_ITEMS_TOTAL,
    PROJECT_PRS_TOTAL,
    PROJECT_RELEASE_INTERVAL_DAYS,
    PROJECT_RELEASES_TOTAL,
    PROJECT_STARS_TOTAL,
    PROJECT_TRAFFIC_CLONES_TOTAL,
    PROJECT_TRAFFIC_CLONES_UNIQUES_TOTAL,
    PROJECT_TRAFFIC_PATHS_TOTAL,
    PROJECT_TRAFFIC_REFERRERS_TOTAL,
    PROJECT_TRAFFIC_VIEWS_TOTAL,
    PROJECT_TRAFFIC_VIEWS_UNIQUES_TOTAL,
    emit,
)

logger = logging.getLogger(__name__)

_PR_NUMBER_RE = re.compile(r"\(#(\d+)\)")


class ReleaseCadenceMetric(BaseModel):
    """Metrics tracking velocity, cadence, and volume for a single release."""

    tag: str
    published_at: str
    days_since_prev: float = 0.0
    commit_count: int = 0
    pr_count: int = 0


class WorkflowRunMetric(BaseModel):
    """Metrics tracking CI workflow runs and pass rate."""

    workflow: str
    total_runs: int = 0
    passed: int = 0
    failed: int = 0
    other: int = 0
    pass_rate: float = 100.0


class MilestoneMetric(BaseModel):
    """Metrics tracking items and completion status per milestone."""

    milestone: str
    state: str = "open"
    open_items: int = 0
    closed_items: int = 0
    total_items: int = 0
    completion_rate: float = 0.0


class LabelTaxonomyMetric(BaseModel):
    """Metrics tracking items categorized by taxonomy label."""

    category: str
    label: str
    count: int = 0


class TrafficReferrerMetric(BaseModel):
    """Metrics tracking traffic referral sources."""

    referrer: str
    count: int = 0
    uniques: int = 0


class TrafficPathMetric(BaseModel):
    """Metrics tracking popular content paths."""

    path: str
    title: str = ""
    count: int = 0
    uniques: int = 0


class TrafficSummaryMetric(BaseModel):
    """Consolidated GitHub repository traffic and engagement analytics."""

    views_count: int = 0
    views_uniques: int = 0
    clones_count: int = 0
    clones_uniques: int = 0
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    referrers: list[TrafficReferrerMetric] = Field(default_factory=list)
    paths: list[TrafficPathMetric] = Field(default_factory=list)


class ProjectMetricsReport(BaseModel):
    """Consolidated project engineering metrics report."""

    repo: str
    generated_at: str
    total_releases: int = 0
    average_cadence_days: float = 0.0
    releases: list[ReleaseCadenceMetric] = Field(default_factory=list)
    workflow_runs: list[WorkflowRunMetric] = Field(default_factory=list)
    milestones: list[MilestoneMetric] = Field(default_factory=list)
    taxonomy_labels: list[LabelTaxonomyMetric] = Field(default_factory=list)
    traffic: TrafficSummaryMetric = Field(default_factory=TrafficSummaryMetric)


def _parse_tag_datetime(date_str: str) -> datetime.datetime:
    """Parse git or ISO date string into UTC datetime object."""
    cleaned = date_str.strip()
    try:
        dt = datetime.datetime.fromisoformat(cleaned)
        return dt.astimezone(datetime.UTC)
    except ValueError:
        return datetime.datetime.now(datetime.UTC)


def _get_git_tag_entries(root: Path) -> list[tuple[str, datetime.datetime]]:
    """Return release git tags sorted chronologically by creation date."""
    try:
        proc = subprocess.run(
            ["git", "tag", "-l", "v*", "--format=%(refname:short)|%(creatordate:iso8601)"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
    except (subprocess.SubprocessError, OSError) as err:
        logger.warning("Failed to inspect git tags: %s", err)
        return []

    entries: list[tuple[str, datetime.datetime]] = []
    for line in proc.stdout.splitlines():
        if "|" not in line:
            continue
        tag, raw_date = line.split("|", 1)
        tag = tag.strip()
        if not tag:
            continue
        entries.append((tag, _parse_tag_datetime(raw_date)))

    entries.sort(key=lambda pair: pair[1])
    return entries


def _count_bullet_commits(body: str) -> int:
    """Count bulleted commit items embedded within a squash merge commit message."""
    bullets = [
        line.strip()
        for line in body.splitlines()
        if line.strip().startswith("* ") and len(line.strip()) > 4
    ]
    return len(bullets)


def _extract_commits_and_prs(root: Path, prev_tag: str | None, tag: str) -> tuple[int, int]:
    """Calculate commits count and merged pull requests count between two tags."""
    rev_range = f"{prev_tag}..{tag}" if prev_tag else tag
    commit_count = 0
    body = ""

    try:
        proc = subprocess.run(
            ["git", "rev-list", "--count", rev_range],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        commit_count = int(proc.stdout.strip() or "0")
    except subprocess.SubprocessError, ValueError, OSError:
        commit_count = 1

    try:
        log_cmd = ["git", "log", "--pretty=format:%s%n%b", rev_range]
        log_proc = subprocess.run(
            log_cmd,
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        body = log_proc.stdout
    except subprocess.SubprocessError, OSError:
        body = ""

    bullet_count = _count_bullet_commits(body)
    effective_commits = max(commit_count, bullet_count)
    prs = set(_PR_NUMBER_RE.findall(body))
    return effective_commits, len(prs)


def get_release_cadence_metrics(root: Path, limit: int = 10) -> list[ReleaseCadenceMetric]:
    """Compute release frequency, interval cadence, and PR counts across releases."""
    tag_entries = _get_git_tag_entries(root)
    if not tag_entries:
        return []

    metrics: list[ReleaseCadenceMetric] = []
    for idx, (tag, dt) in enumerate(tag_entries):
        prev_dt = tag_entries[idx - 1][1] if idx > 0 else dt
        prev_tag = tag_entries[idx - 1][0] if idx > 0 else None
        interval_days = round((dt - prev_dt).total_seconds() / 86400.0, 1) if idx > 0 else 0.0
        commits, prs = _extract_commits_and_prs(root, prev_tag, tag)
        metrics.append(
            ReleaseCadenceMetric(
                tag=tag,
                published_at=dt.strftime("%Y-%m-%d"),
                days_since_prev=interval_days,
                commit_count=commits,
                pr_count=prs,
            )
        )

    # Return latest releases first
    return list(reversed(metrics[-limit:]))


def _calculate_pass_rate(passed: int, failed: int) -> float:
    """Calculate pass rate percentage bounded between 0 and 100."""
    total = passed + failed
    if total <= 0:
        return 100.0
    return round((passed / total) * 100.0, 1)


def _classify_workflow_conclusion(
    conclusion: str,
) -> tuple[int, int, int]:
    """Map workflow run conclusion to (passed, failed, other) deltas."""
    if conclusion == "success":
        return 1, 0, 0
    if conclusion in ("failure", "timed_out", "startup_failure"):
        return 0, 1, 0
    return 0, 0, 1


def get_ci_workflow_metrics(repo: str, limit: int = 50) -> list[WorkflowRunMetric]:
    """Collect CI workflow runs and calculate pass/fail rates per workflow."""
    client = GhCliClient()
    endpoint = f"repos/{repo}/actions/runs?per_page={min(limit, 100)}"
    try:
        raw_output = client.api(endpoint)
        data = json.loads(raw_output)
    except Exception as err:
        logger.warning("Failed to query GitHub Actions runs for %s: %s", repo, err)
        return []

    runs = data.get("workflow_runs", [])
    aggregates: dict[str, dict[str, int]] = {}

    for run in runs:
        name = run.get("name") or "Workflow"
        conclusion = str(run.get("conclusion") or "").lower()
        passed_delta, failed_delta, other_delta = _classify_workflow_conclusion(conclusion)

        if name not in aggregates:
            aggregates[name] = {"total": 0, "passed": 0, "failed": 0, "other": 0}

        entry = aggregates[name]
        entry["total"] += 1
        entry["passed"] += passed_delta
        entry["failed"] += failed_delta
        entry["other"] += other_delta

    results: list[WorkflowRunMetric] = []
    for name, stats in aggregates.items():
        results.append(
            WorkflowRunMetric(
                workflow=name,
                total_runs=stats["total"],
                passed=stats["passed"],
                failed=stats["failed"],
                other=stats["other"],
                pass_rate=_calculate_pass_rate(stats["passed"], stats["failed"]),
            )
        )

    results.sort(key=lambda item: item.total_runs, reverse=True)
    return results


def _build_milestone_metric(raw: dict[str, Any]) -> MilestoneMetric:
    """Transform raw GitHub milestone payload into MilestoneMetric model."""
    title = str(raw.get("title", ""))
    state = str(raw.get("state", "open"))
    open_c = int(raw.get("open_issues", 0))
    closed_c = int(raw.get("closed_issues", 0))
    total = open_c + closed_c
    if total > 0:
        completion = round((closed_c / total) * 100.0, 1)
    elif state == "closed":
        completion = 100.0
    else:
        completion = 0.0

    return MilestoneMetric(
        milestone=title,
        state=state,
        open_items=open_c,
        closed_items=closed_c,
        total_items=total,
        completion_rate=completion,
    )


def get_milestone_metrics(repo: str, milestone_filter: str | None = None) -> list[MilestoneMetric]:
    """Query milestones and calculate item counts and completion percentages."""
    client = GhCliClient()
    endpoint = f"repos/{repo}/milestones?state=all&per_page=100"
    try:
        raw_output = client.api(endpoint)
        payload = json.loads(raw_output)
    except Exception as err:
        logger.warning("Failed to query milestones for %s: %s", repo, err)
        return []

    if not isinstance(payload, list):
        return []

    metrics: list[MilestoneMetric] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        m = _build_milestone_metric(item)
        if milestone_filter and m.milestone != milestone_filter:
            continue
        metrics.append(m)

    metrics.sort(key=lambda m: m.milestone)
    return metrics


def get_label_taxonomy_metrics(repo: str) -> list[LabelTaxonomyMetric]:
    """Count open issues categorized by taxonomy label prefixes."""
    client = GhCliClient()
    endpoint = f"repos/{repo}/issues?state=open&per_page=100"
    try:
        raw_output = client.api(endpoint)
        issues = json.loads(raw_output)
    except Exception as err:
        logger.warning("Failed to query open issues for %s: %s", repo, err)
        return []

    if not isinstance(issues, list):
        return []

    counts: Counter[tuple[str, str]] = Counter()
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        labels = issue.get("labels", [])
        for lbl in labels:
            name = lbl.get("name", "") if isinstance(lbl, dict) else str(lbl)
            if "/" in name:
                cat, _val = name.split("/", 1)
                counts[(cat, name)] += 1

    metrics = [
        LabelTaxonomyMetric(category=cat, label=label, count=cnt)
        for (cat, label), cnt in counts.items()
    ]
    metrics.sort(key=lambda x: (x.category, -x.count))
    return metrics


def _fetch_traffic_views(client: GhCliClient, repo: str) -> tuple[int, int]:
    """Fetch total 14-day pageviews count and unique visitors from GitHub traffic API."""
    try:
        data = json.loads(client.api(f"repos/{repo}/traffic/views"))
        if isinstance(data, dict):
            return int(data.get("count", 0)), int(data.get("uniques", 0))
    except Exception as err:
        logger.warning("Failed to query traffic views for %s: %s", repo, err)
    return 0, 0


def _fetch_traffic_clones(client: GhCliClient, repo: str) -> tuple[int, int]:
    """Fetch total 14-day git clones count and unique cloners from GitHub traffic API."""
    try:
        data = json.loads(client.api(f"repos/{repo}/traffic/clones"))
        if isinstance(data, dict):
            return int(data.get("count", 0)), int(data.get("uniques", 0))
    except Exception as err:
        logger.warning("Failed to query traffic clones for %s: %s", repo, err)
    return 0, 0


def _fetch_traffic_referrers(client: GhCliClient, repo: str) -> list[TrafficReferrerMetric]:
    """Fetch top referral domains from GitHub traffic API."""
    try:
        data = json.loads(client.api(f"repos/{repo}/traffic/popular/referrers"))
        if isinstance(data, list):
            return [
                TrafficReferrerMetric(
                    referrer=str(item.get("referrer", "")),
                    count=int(item.get("count", 0)),
                    uniques=int(item.get("uniques", 0)),
                )
                for item in data
                if isinstance(item, dict) and "referrer" in item
            ]
    except Exception as err:
        logger.warning("Failed to query traffic referrers for %s: %s", repo, err)
    return []


def _fetch_traffic_paths(client: GhCliClient, repo: str) -> list[TrafficPathMetric]:
    """Fetch top viewed paths from GitHub traffic API."""
    try:
        data = json.loads(client.api(f"repos/{repo}/traffic/popular/paths"))
        if isinstance(data, list):
            return [
                TrafficPathMetric(
                    path=str(item.get("path", "")),
                    title=str(item.get("title", "")),
                    count=int(item.get("count", 0)),
                    uniques=int(item.get("uniques", 0)),
                )
                for item in data
                if isinstance(item, dict) and "path" in item
            ]
    except Exception as err:
        logger.warning("Failed to query popular paths for %s: %s", repo, err)
    return []


def _fetch_repo_metadata(client: GhCliClient, repo: str) -> tuple[int, int, int]:
    """Fetch repository stars, forks, and open issues count."""
    try:
        data = json.loads(client.api(f"repos/{repo}"))
        if isinstance(data, dict):
            return (
                int(data.get("stargazers_count", 0)),
                int(data.get("forks_count", 0)),
                int(data.get("open_issues_count", 0)),
            )
    except Exception as err:
        logger.warning("Failed to query repo metadata for %s: %s", repo, err)
    return 0, 0, 0


def get_repository_traffic_metrics(repo: str) -> TrafficSummaryMetric:
    """Aggregate traffic, engagement, and metadata analytics for a GitHub repository."""
    client = GhCliClient()
    views_count, views_uniques = _fetch_traffic_views(client, repo)
    clones_count, clones_uniques = _fetch_traffic_clones(client, repo)
    referrers = _fetch_traffic_referrers(client, repo)
    paths = _fetch_traffic_paths(client, repo)
    stars, forks, open_issues = _fetch_repo_metadata(client, repo)

    return TrafficSummaryMetric(
        views_count=views_count,
        views_uniques=views_uniques,
        clones_count=clones_count,
        clones_uniques=clones_uniques,
        stars=stars,
        forks=forks,
        open_issues=open_issues,
        referrers=referrers,
        paths=paths,
    )


def collect_project_metrics_report(
    root: Path | None = None,
    repo: str | None = None,
    release_limit: int = 10,
    ci_limit: int = 50,
    milestone_filter: str | None = None,
) -> ProjectMetricsReport:
    """Aggregate complete project metrics across releases, CI checks, and milestones.

    The releases are the `v*` tags of the git repository at `root`, taken as it is, so a clone
    nested in another checkout, as the roadmap jobs keep under the data directory, reports its
    own tags (#1358). Without `root` they are the tags of the working tree around the current
    directory (`find_worktree_root`).
    """
    project_root = root if root is not None else find_worktree_root()
    target_repo = repo or get_repo_origin_name(project_root) or "repository"
    now_str = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    releases = get_release_cadence_metrics(project_root, limit=release_limit)
    workflow_runs = get_ci_workflow_metrics(target_repo, limit=ci_limit)
    milestones = get_milestone_metrics(target_repo, milestone_filter=milestone_filter)
    taxonomy_labels = get_label_taxonomy_metrics(target_repo)
    traffic = get_repository_traffic_metrics(target_repo)

    interval_sum = sum(r.days_since_prev for r in releases if r.days_since_prev > 0)
    interval_count = sum(1 for r in releases if r.days_since_prev > 0)
    avg_cadence = round(interval_sum / max(1, interval_count), 1)

    return ProjectMetricsReport(
        repo=target_repo,
        generated_at=now_str,
        total_releases=len(releases),
        average_cadence_days=avg_cadence,
        releases=releases,
        workflow_runs=workflow_runs,
        milestones=milestones,
        taxonomy_labels=taxonomy_labels,
        traffic=traffic,
    )


def emit_project_metrics_telemetry(report: ProjectMetricsReport) -> None:
    """Emit project and engineering velocity metrics over OpenTelemetry to Prometheus."""
    emit(PROJECT_RELEASES_TOTAL, float(report.total_releases))
    emit(PROJECT_TRAFFIC_VIEWS_TOTAL, float(report.traffic.views_count))
    emit(PROJECT_TRAFFIC_VIEWS_UNIQUES_TOTAL, float(report.traffic.views_uniques))
    emit(PROJECT_TRAFFIC_CLONES_TOTAL, float(report.traffic.clones_count))
    emit(PROJECT_TRAFFIC_CLONES_UNIQUES_TOTAL, float(report.traffic.clones_uniques))
    emit(PROJECT_STARS_TOTAL, float(report.traffic.stars))
    emit(PROJECT_FORKS_TOTAL, float(report.traffic.forks))

    for ref in report.traffic.referrers:
        emit(PROJECT_TRAFFIC_REFERRERS_TOTAL, float(ref.count), {"referrer": ref.referrer})

    for p in report.traffic.paths:
        emit(PROJECT_TRAFFIC_PATHS_TOTAL, float(p.count), {"path": p.path})

    for rel in report.releases:
        emit(PROJECT_COMMITS_TOTAL, float(rel.commit_count), {"release": rel.tag})
        emit(PROJECT_PRS_TOTAL, float(rel.pr_count), {"release": rel.tag})
        if rel.days_since_prev > 0:
            emit(
                PROJECT_RELEASE_INTERVAL_DAYS,
                rel.days_since_prev,
                {"release": rel.tag},
            )

    for run in report.workflow_runs:
        emit(
            PROJECT_CI_RUNS_TOTAL,
            float(run.passed),
            {"workflow": run.workflow, "status": "completed", "conclusion": "success"},
        )
        emit(
            PROJECT_CI_RUNS_TOTAL,
            float(run.failed),
            {"workflow": run.workflow, "status": "completed", "conclusion": "failure"},
        )

    for ms in report.milestones:
        emit(
            PROJECT_ITEMS_TOTAL,
            float(ms.open_items),
            {"milestone": ms.milestone, "state": "open"},
        )
        emit(
            PROJECT_ITEMS_TOTAL,
            float(ms.closed_items),
            {"milestone": ms.milestone, "state": "closed"},
        )


def _record_releases_and_traffic(
    reg: Any,
    report: ProjectMetricsReport,
) -> None:
    """Record top-level release and traffic metrics in in-memory registry."""
    reg.set_gauge(PROJECT_RELEASES_TOTAL.name, float(report.total_releases))
    reg.set_gauge(PROJECT_TRAFFIC_VIEWS_TOTAL.name, float(report.traffic.views_count))
    reg.set_gauge(PROJECT_TRAFFIC_VIEWS_UNIQUES_TOTAL.name, float(report.traffic.views_uniques))
    reg.set_gauge(PROJECT_TRAFFIC_CLONES_TOTAL.name, float(report.traffic.clones_count))
    reg.set_gauge(PROJECT_TRAFFIC_CLONES_UNIQUES_TOTAL.name, float(report.traffic.clones_uniques))
    reg.set_gauge(PROJECT_STARS_TOTAL.name, float(report.traffic.stars))
    reg.set_gauge(PROJECT_FORKS_TOTAL.name, float(report.traffic.forks))

    reg.clear_metric(PROJECT_TRAFFIC_REFERRERS_TOTAL.name)
    for ref in report.traffic.referrers:
        reg.set_gauge(
            PROJECT_TRAFFIC_REFERRERS_TOTAL.name,
            float(ref.count),
            {"referrer": ref.referrer},
        )

    reg.clear_metric(PROJECT_TRAFFIC_PATHS_TOTAL.name)
    for p in report.traffic.paths:
        reg.set_gauge(
            PROJECT_TRAFFIC_PATHS_TOTAL.name,
            float(p.count),
            {"path": p.path},
        )


def _record_releases_breakdown(
    reg: Any,
    report: ProjectMetricsReport,
) -> None:
    """Record commits and PRs per release in in-memory registry."""
    reg.clear_metric(PROJECT_COMMITS_TOTAL.name)
    reg.clear_metric(PROJECT_PRS_TOTAL.name)
    for rel in report.releases:
        reg.set_gauge(PROJECT_COMMITS_TOTAL.name, float(rel.commit_count), {"release": rel.tag})
        reg.set_gauge(PROJECT_PRS_TOTAL.name, float(rel.pr_count), {"release": rel.tag})


def _record_workflow_and_milestone_metrics(
    reg: Any,
    report: ProjectMetricsReport,
) -> None:
    """Record CI workflow runs and milestone items in in-memory registry."""
    reg.clear_metric(PROJECT_CI_RUNS_TOTAL.name)
    for run in report.workflow_runs:
        reg.set_gauge(
            PROJECT_CI_RUNS_TOTAL.name,
            float(run.passed),
            {"workflow": run.workflow, "status": "completed", "conclusion": "success"},
        )
        reg.set_gauge(
            PROJECT_CI_RUNS_TOTAL.name,
            float(run.failed),
            {"workflow": run.workflow, "status": "completed", "conclusion": "failure"},
        )

    reg.clear_metric(PROJECT_ITEMS_TOTAL.name)
    for ms in report.milestones:
        reg.set_gauge(
            PROJECT_ITEMS_TOTAL.name,
            float(ms.open_items),
            {"milestone": ms.milestone, "state": "open"},
        )
        reg.set_gauge(
            PROJECT_ITEMS_TOTAL.name,
            float(ms.closed_items),
            {"milestone": ms.milestone, "state": "closed"},
        )


def record_project_metrics_in_registry(
    report: ProjectMetricsReport,
    registry: Any = None,
) -> None:
    """Record project and engineering velocity metrics into InMemoryMetricsRegistry for Prometheus scraping."""
    from devops_cli.telemetry.metrics import GLOBAL_METRICS

    reg = registry if registry is not None else GLOBAL_METRICS
    _record_releases_and_traffic(reg, report)
    _record_releases_breakdown(reg, report)
    _record_workflow_and_milestone_metrics(reg, report)


__all__ = [
    "LabelTaxonomyMetric",
    "MilestoneMetric",
    "ProjectMetricsReport",
    "ReleaseCadenceMetric",
    "TrafficPathMetric",
    "TrafficReferrerMetric",
    "TrafficSummaryMetric",
    "WorkflowRunMetric",
    "collect_project_metrics_report",
    "emit_project_metrics_telemetry",
    "get_ci_workflow_metrics",
    "get_label_taxonomy_metrics",
    "get_milestone_metrics",
    "get_release_cadence_metrics",
    "get_repository_traffic_metrics",
    "record_project_metrics_in_registry",
]
