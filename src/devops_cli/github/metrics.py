"""Project metrics and engineering velocity analytics subsystem.

Provides analysis and aggregations for:
- Release frequency and cadence (intervals in days between releases).
- Commits and merged pull requests per release.
- CI quality gate checks and workflow run pass rates.
- Roadmap Items counted by release, state, type and priority.
- Open issues grouped by taxonomy label (type, scope).
- OpenTelemetry instrumentation for Prometheus export and Grafana visualization.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import subprocess
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from devops_cli.dry_run.requests import PlannedRequest

from pydantic import BaseModel, Field

from devops_cli.config.commands import BIN_GIT
from devops_cli.config.constants import CONST_ROADMAP_TYPE_LABEL_PREFIX
from devops_cli.core.process import acts_as_github_app, run_subprocess
from devops_cli.core.repo import find_worktree_root, get_repo_origin_name
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.client import GhCliClient, parse_paginated_json
from devops_cli.github.error_classifier import is_gh_refused_by_token
from devops_cli.roadmap import store as roadmap_store
from devops_cli.roadmap.store import GitHubState, RoadmapStore
from devops_cli.telemetry.instruments import (
    PROJECT_CI_RUNS,
    PROJECT_COMMITS,
    PROJECT_FORKS,
    PROJECT_ITEM_LABELS,
    PROJECT_ITEMS,
    PROJECT_PRS,
    PROJECT_RELEASE_INTERVAL_DAYS,
    PROJECT_RELEASES,
    PROJECT_STARS,
    PROJECT_TRAFFIC_CLONES,
    PROJECT_TRAFFIC_CLONES_UNIQUES,
    PROJECT_TRAFFIC_PATHS,
    PROJECT_TRAFFIC_REFERRERS,
    PROJECT_TRAFFIC_VIEWS,
    PROJECT_TRAFFIC_VIEWS_UNIQUES,
    emit,
)

logger = logging.getLogger(__name__)

_PR_NUMBER_RE = re.compile(r"\(#(\d+)\)")
_CLOSING_REF_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?):?\s+#(\d+)", re.IGNORECASE
)
"""A closing keyword of GitHub and the issue it closes, as a commit footer writes it."""


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


class ItemCountMetric(BaseModel):
    """The roadmap Items that share a release, a state, a type and a priority.

    A value is empty when the Item has none: no release closed it, or it has no `type/*` label.
    Every Item holds a Priority.
    """

    release: str = ""
    state: str
    type: str = ""
    priority: str = ""
    count: int

    def labels(self) -> dict[str, str]:
        """The labels of this count on the `PROJECT_ITEMS` gauge."""
        return {label: getattr(self, label) for label in PROJECT_ITEM_LABELS}


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
    """Consolidated GitHub repository traffic and engagement analytics.

    `traffic_collected` is false when the process did not ask for the views, clones, referrers
    and paths, because its token cannot read them: the totals then hold 0 and mean "unknown"
    (#2752)."""

    traffic_collected: bool = True
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
    items: list[ItemCountMetric] = Field(default_factory=list)
    taxonomy_labels: list[LabelTaxonomyMetric] = Field(default_factory=list)
    traffic: TrafficSummaryMetric = Field(default_factory=TrafficSummaryMetric)


def parse_tag_datetime(date_str: str) -> datetime.datetime:
    """Parse git or ISO date string into UTC datetime object."""
    cleaned = date_str.strip()
    try:
        dt = datetime.datetime.fromisoformat(cleaned)
        return dt.astimezone(datetime.UTC)
    except ValueError:
        return datetime.datetime.now(datetime.UTC)


def _git_output(root: Path, *args: str, timeout: float) -> str | None:
    """The standard output of a local read of `git` in `root`, through the process seam, or None
    when git is missing, fails or runs out of time; the warning gives the cause, and the seam's
    error names a missing program (#1538)."""
    try:
        done = run_subprocess(
            [BIN_GIT, *args], cwd=root, timeout=timeout, local_read=True, quiet=True
        )
    except subprocess.TimeoutExpired as err:
        logger.warning("git %s timed out: %s", args[0], err)
        return None
    if done.returncode != 0:
        logger.warning("git %s failed: %s", args[0], done.stderr.strip())
        return None
    return done.stdout


def get_git_tag_entries(root: Path) -> list[tuple[str, datetime.datetime]]:
    """Return release git tags sorted chronologically by creation date."""
    output = _git_output(
        root, "tag", "-l", "v*", "--format=%(refname:short)|%(creatordate:iso8601)", timeout=15
    )
    if output is None:
        return []

    entries: list[tuple[str, datetime.datetime]] = []
    for line in output.splitlines():
        if "|" not in line:
            continue
        tag, raw_date = line.split("|", 1)
        tag = tag.strip()
        if not tag:
            continue
        entries.append((tag, parse_tag_datetime(raw_date)))

    entries.sort(key=lambda pair: pair[1])
    return entries


def count_bullet_commits(body: str) -> int:
    """Count bulleted commit items embedded within a squash merge commit message."""
    bullets = [
        line.strip()
        for line in body.splitlines()
        if line.strip().startswith("* ") and len(line.strip()) > 4
    ]
    return len(bullets)


def extract_commits_and_prs(root: Path, prev_tag: str | None, tag: str) -> tuple[int, int]:
    """Calculate commits count and merged pull requests count between two tags."""
    rev_range = f"{prev_tag}..{tag}" if prev_tag else tag
    count = _git_output(root, "rev-list", "--count", rev_range, timeout=10)
    try:
        commit_count = int(count.strip() or "0") if count is not None else 1
    except ValueError:
        commit_count = 1
    body = _git_output(root, "log", "--pretty=format:%s%n%b", rev_range, timeout=15) or ""

    bullet_count = count_bullet_commits(body)
    effective_commits = max(commit_count, bullet_count)
    prs = set(_PR_NUMBER_RE.findall(body))
    return effective_commits, len(prs)


def get_item_releases(root: Path) -> dict[int, str]:
    """The first `v*` tag whose commits close each issue with a closing keyword (#2702).

    release-please copies the `Closes #<issue>` footer of each squash commit into the release
    commit of the tag, so the tag ranges of the git repository at `root` give the release of
    each closed issue with no GitHub call. A commit after the last tag releases no issue.
    """
    releases: dict[int, str] = {}
    prev_tag: str | None = None
    for tag, _ in get_git_tag_entries(root):
        rev_range = f"{prev_tag}..{tag}" if prev_tag else tag
        body = _git_output(root, "log", "--format=%B", rev_range, timeout=15) or ""
        for number in _CLOSING_REF_RE.findall(body):
            releases.setdefault(int(number), tag)
        prev_tag = tag
    return releases


def get_release_cadence_metrics(root: Path, limit: int = 10) -> list[ReleaseCadenceMetric]:
    """Compute release frequency, interval cadence, and PR counts across releases."""
    tag_entries = get_git_tag_entries(root)
    if not tag_entries:
        return []

    metrics: list[ReleaseCadenceMetric] = []
    for idx, (tag, dt) in enumerate(tag_entries):
        prev_dt = tag_entries[idx - 1][1] if idx > 0 else dt
        prev_tag = tag_entries[idx - 1][0] if idx > 0 else None
        interval_days = round((dt - prev_dt).total_seconds() / 86400.0, 1) if idx > 0 else 0.0
        commits, prs = extract_commits_and_prs(root, prev_tag, tag)
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


def calculate_pass_rate(passed: int, failed: int) -> float:
    """Calculate pass rate percentage bounded between 0 and 100."""
    total = passed + failed
    if total <= 0:
        return 100.0
    return round((passed / total) * 100.0, 1)


def classify_workflow_conclusion(
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
        passed_delta, failed_delta, other_delta = classify_workflow_conclusion(conclusion)

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
                pass_rate=calculate_pass_rate(stats["passed"], stats["failed"]),
            )
        )

    results.sort(key=lambda item: item.total_runs, reverse=True)
    return results


def build_milestone_metric(raw: dict[str, Any]) -> MilestoneMetric:
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
        m = build_milestone_metric(item)
        if milestone_filter and m.milestone != milestone_filter:
            continue
        metrics.append(m)

    metrics.sort(key=lambda m: m.milestone)
    return metrics


def _item_type(labels: Iterable[str]) -> str:
    """The `type/*` label of an item without its prefix, or empty when it has none."""
    return next(
        (
            label.removeprefix(CONST_ROADMAP_TYPE_LABEL_PREFIX)
            for label in labels
            if label.startswith(CONST_ROADMAP_TYPE_LABEL_PREFIX)
        ),
        "",
    )


def get_item_metrics(
    store: RoadmapStore,
    releases: Mapping[int, str] | None = None,
    milestone_filter: str | None = None,
) -> list[ItemCountMetric]:
    """Count the Items of `store`, open and closed, by release, state, type and priority
    (#2263, #2702): the issues that hold a `priority/*` label. `releases` maps an issue number
    to the tag that closed it (`get_item_releases`); an open Item has no release. Raises when
    the issues cannot be read, so a failed read is no empty roadmap."""
    released = releases or {}
    counts = Counter(
        (
            released.get(item.number, "") if item.state is GitHubState.CLOSED else "",
            item.state.value,
            _item_type(item.labels),
            item.priority or "",
        )
        for item in store.items()
        if milestone_filter is None or item.milestone == milestone_filter
    )
    return [
        ItemCountMetric(release=release, state=state, type=kind, priority=priority, count=count)
        for (release, state, kind, priority), count in sorted(counts.items())
    ]


def get_label_taxonomy_metrics(repo: str) -> list[LabelTaxonomyMetric]:
    """Count open issues categorized by taxonomy label prefixes."""
    client = GhCliClient()
    endpoint = f"repos/{repo}/issues?state=open&per_page=100"
    try:
        raw_output = client.api(endpoint, paginate=True)
        issues = parse_paginated_json(raw_output)
    except Exception as err:
        logger.warning("Failed to query open issues for %s: %s", repo, err)
        return []

    counts: Counter[tuple[str, str]] = Counter()
    for issue in issues:
        if not isinstance(issue, dict) or "pull_request" in issue:
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


_refused_paths: set[str] = set()
_refused_integration_repos: set[str] = set()
"""The GitHub paths that answered this process with HTTP 403 "Resource not accessible by
integration": the token lacks the permission of the path and keeps lacking it until the process
restarts, so the collector does not ask again (#2752, #2626). A path holds the repository and the
endpoint."""


def reset_refused_paths() -> None:
    """Forget the refused paths, as a new process knows none."""
    _refused_paths.clear()
    _refused_integration_repos.clear()


def _is_integration_refusal(err: Exception) -> bool:
    """Whether `err` indicates an HTTP 403 "Resource not accessible by integration"."""
    if isinstance(err, GitHubOperationError):
        stderr = str(err.details.get("stderr", ""))
        if is_gh_refused_by_token(stderr):
            return True
    return "Resource not accessible by integration" in str(err)


def _read_json(client: GhCliClient, path: str, what: str) -> Any | None:
    """The JSON that GitHub answers for `path`, or None when the path was refused before, or
    when the read fails: the failure is logged as a warning naming `what`. A refusal by the
    token is kept, so the path is asked once."""
    if path in _refused_paths:
        return None
    try:
        return json.loads(client.api(path))
    except Exception as err:
        if _is_integration_refusal(err):
            _refused_paths.add(path)
        else:
            logger.warning("Failed to query %s: %s", what, err)
    return None


def _fetch_traffic_views(client: GhCliClient, repo: str) -> tuple[int, int]:
    """Fetch total 14-day pageviews count and unique visitors from GitHub traffic API."""
    data = _read_json(client, f"repos/{repo}/traffic/views", f"traffic views for {repo}")
    if isinstance(data, dict):
        return int(data.get("count", 0)), int(data.get("uniques", 0))
    return 0, 0


def _fetch_traffic_clones(client: GhCliClient, repo: str) -> tuple[int, int]:
    """Fetch total 14-day git clones count and unique cloners from GitHub traffic API."""
    data = _read_json(client, f"repos/{repo}/traffic/clones", f"traffic clones for {repo}")
    if isinstance(data, dict):
        return int(data.get("count", 0)), int(data.get("uniques", 0))
    return 0, 0


def _fetch_traffic_referrers(client: GhCliClient, repo: str) -> list[TrafficReferrerMetric]:
    """Fetch top referral domains from GitHub traffic API."""
    data = _read_json(
        client, f"repos/{repo}/traffic/popular/referrers", f"traffic referrers for {repo}"
    )
    if not isinstance(data, list):
        return []
    return [
        TrafficReferrerMetric(
            referrer=str(item.get("referrer", "")),
            count=int(item.get("count", 0)),
            uniques=int(item.get("uniques", 0)),
        )
        for item in data
        if isinstance(item, dict) and "referrer" in item
    ]


def _fetch_traffic_paths(client: GhCliClient, repo: str) -> list[TrafficPathMetric]:
    """Fetch top viewed paths from GitHub traffic API."""
    data = _read_json(client, f"repos/{repo}/traffic/popular/paths", f"popular paths for {repo}")
    if not isinstance(data, list):
        return []
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


def _fetch_repo_metadata(client: GhCliClient, repo: str) -> tuple[int, int, int]:
    """Fetch repository stars, forks, and open issues count."""
    data = _read_json(client, f"repos/{repo}", f"repo metadata for {repo}")
    if isinstance(data, dict):
        return (
            int(data.get("stargazers_count", 0)),
            int(data.get("forks_count", 0)),
            int(data.get("open_issues_count", 0)),
        )
    return 0, 0, 0


def get_repository_traffic_metrics(repo: str) -> TrafficSummaryMetric:
    """Aggregate traffic, engagement, and metadata analytics for a GitHub repository.

    A process that acts as the GitHub App asks for no traffic: the four endpoints need the
    Administration permission, which the installation token does not hold, so each answers HTTP
    403 and spends part of the hourly budget (#2752). The report then has `traffic_collected`
    false, and only the stars, forks and open issues.
    """
    client = GhCliClient()
    stars, forks, open_issues = _fetch_repo_metadata(client, repo)
    if acts_as_github_app() or repo in _refused_integration_repos:
        return TrafficSummaryMetric(
            traffic_collected=False, stars=stars, forks=forks, open_issues=open_issues
        )
    views_count, views_uniques = _fetch_traffic_views(client, repo)
    clones_count, clones_uniques = _fetch_traffic_clones(client, repo)
    referrers = _fetch_traffic_referrers(client, repo)
    paths = _fetch_traffic_paths(client, repo)

    traffic_paths = {
        f"repos/{repo}/traffic/views",
        f"repos/{repo}/traffic/clones",
        f"repos/{repo}/traffic/popular/referrers",
        f"repos/{repo}/traffic/popular/paths",
    }
    if traffic_paths & _refused_paths:
        if repo not in _refused_integration_repos:
            _refused_integration_repos.add(repo)
            logger.debug(
                "Traffic API not accessible by integration for %s: skipping traffic metrics", repo
            )
        return TrafficSummaryMetric(
            traffic_collected=False, stars=stars, forks=forks, open_issues=open_issues
        )

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
    store: RoadmapStore | None = None,
) -> ProjectMetricsReport:
    """Aggregate complete project metrics across releases, CI checks, milestones, and the
    roadmap's Items.

    The Items are read through `store`, the roadmap store of the job; without one, through the
    roadmap store of the repository. Issues that cannot be read raise.

    The releases are the `v*` tags of the git repository at `root`, taken as it is, so a clone
    nested in another checkout, as the roadmap jobs keep under the data directory, reports its
    own tags (#1358). Without `root` they are the tags of the working tree around the current
    directory (`find_worktree_root`).
    """
    project_root = root if root is not None else find_worktree_root()
    target_repo = repo or get_repo_origin_name(project_root) or "repository"
    now_str = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    roadmap = store if store is not None else roadmap_store.get_roadmap_store(target_repo)
    items = get_item_metrics(
        roadmap, get_item_releases(project_root), milestone_filter=milestone_filter
    )
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
        items=items,
        taxonomy_labels=taxonomy_labels,
        traffic=traffic,
    )


def project_metrics_requests(
    repo: str,
    ci_limit: int = 50,
) -> list[PlannedRequest]:
    """Planned requests for collecting project velocity metrics."""
    from devops_cli.roadmap.request_plan import StoreRequests, planned_gh

    requests: list[PlannedRequest] = []
    requests.extend(StoreRequests(repo).every_issue())
    requests.append(
        planned_gh(
            ["api", f"repos/{repo}/actions/runs?per_page={min(ci_limit, 100)}"],
            f"repos/{repo}/actions/runs",
        )
    )
    requests.append(
        planned_gh(
            ["api", f"repos/{repo}/milestones?state=all&per_page=100"],
            f"repos/{repo}/milestones",
        )
    )
    requests.append(
        planned_gh(
            ["api", f"repos/{repo}/issues?state=open&per_page=100", "--paginate"],
            f"repos/{repo}/issues",
        )
    )
    requests.append(planned_gh(["api", f"repos/{repo}"], f"repos/{repo}"))
    for endpoint in ("views", "clones", "popular/referrers", "popular/paths"):
        requests.append(
            planned_gh(
                ["api", f"repos/{repo}/traffic/{endpoint}"],
                f"repos/{repo}/traffic/{endpoint}",
            )
        )
    return requests


_sent_item_series: set[tuple[tuple[str, str], ...]] = set()
"""The labels of each items series that the last snapshot of this process sent."""


def reset_sent_item_series() -> None:
    """Forget the items series sent, as a new process has sent none."""
    _sent_item_series.clear()


def _emit_item_counts(items: list[ItemCountMetric]) -> None:
    """Send the item counts, and 0 once for each label set that the last snapshot sent and this
    one lacks: Prometheus keeps the last sample of a series that stops, so `last_over_time`
    would keep counting the items that left that label set (#2263)."""
    series = {tuple(item.labels().items()) for item in items}
    for gone in _sent_item_series - series:
        emit(PROJECT_ITEMS, 0.0, dict(gone))
    for item in items:
        emit(PROJECT_ITEMS, float(item.count), item.labels())
    _sent_item_series.clear()
    _sent_item_series.update(series)


def _emit_traffic(traffic: TrafficSummaryMetric) -> None:
    """Send the traffic gauges. A report that collected no traffic sends none, so a panel shows
    no data and not 0 visitors (#2752)."""
    emit(PROJECT_TRAFFIC_VIEWS, float(traffic.views_count))
    emit(PROJECT_TRAFFIC_VIEWS_UNIQUES, float(traffic.views_uniques))
    emit(PROJECT_TRAFFIC_CLONES, float(traffic.clones_count))
    emit(PROJECT_TRAFFIC_CLONES_UNIQUES, float(traffic.clones_uniques))
    for ref in traffic.referrers:
        emit(PROJECT_TRAFFIC_REFERRERS, float(ref.count), {"referrer": ref.referrer})
    for p in traffic.paths:
        emit(PROJECT_TRAFFIC_PATHS, float(p.count), {"path": p.path})


def emit_project_metrics_telemetry(report: ProjectMetricsReport) -> None:
    """Emit project and engineering velocity metrics over OpenTelemetry to Prometheus."""
    emit(PROJECT_RELEASES, float(report.total_releases))
    emit(PROJECT_STARS, float(report.traffic.stars))
    emit(PROJECT_FORKS, float(report.traffic.forks))
    if report.traffic.traffic_collected:
        _emit_traffic(report.traffic)

    for rel in report.releases:
        emit(PROJECT_COMMITS, float(rel.commit_count), {"release": rel.tag})
        emit(PROJECT_PRS, float(rel.pr_count), {"release": rel.tag})
        if rel.days_since_prev > 0:
            emit(
                PROJECT_RELEASE_INTERVAL_DAYS,
                rel.days_since_prev,
                {"release": rel.tag},
            )

    for run in report.workflow_runs:
        emit(
            PROJECT_CI_RUNS,
            float(run.passed),
            {"workflow": run.workflow, "status": "completed", "conclusion": "success"},
        )
        emit(
            PROJECT_CI_RUNS,
            float(run.failed),
            {"workflow": run.workflow, "status": "completed", "conclusion": "failure"},
        )

    _emit_item_counts(report.items)


__all__ = [
    "ItemCountMetric",
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
    "get_item_metrics",
    "get_item_releases",
    "get_label_taxonomy_metrics",
    "get_milestone_metrics",
    "get_release_cadence_metrics",
    "get_repository_traffic_metrics",
    "reset_refused_paths",
    "reset_sent_item_series",
]
