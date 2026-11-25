"""Item-cohort funnel evaluation (`devops roadmap eval funnel`, #5494).

Follows each item cohort by the ISO week of its latest active `status/ready` label event, splits
delivery into path `G1` (merged plan pull request before a new delivery branch) vs `continue`
(delivery on the plan branch), and joins GitHub issue timelines with Loki `RESULT_LINES` metric
queries.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.defaults import DEFAULT_GH_REST_PER_PAGE
from devops_cli.config.settings import load_settings
from devops_cli.dry_run import PlannedRequest
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.validation import ValidationError
from devops_cli.github.repo_ref import RepoRef
from devops_cli.k8s.logql import query_loki_metrics
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.job_grade import wilson_interval
from devops_cli.roadmap.job_grade_report import ITEM_FIELDS, RESULT_LINES, count_label
from devops_cli.roadmap.job_result import RoadmapJob
from devops_cli.roadmap.pr_verdict import PullKind, pull_kind

if TYPE_CHECKING:
    from devops_cli.github.session import GitHubSession
    from devops_cli.models.prometheus import PrometheusQueryResult


class FunnelPath(StrEnum):
    """The workflow path of a cohort item through planning and delivery."""

    G1 = "G1"
    CONTINUE = "continue"


class FunnelQueryKind(StrEnum):
    """The Loki instant queries that attribute result lines, tokens, and cost to items."""

    COUNTS = "counts"
    TOKENS = "tokens"
    COST = "cost"


@dataclass(frozen=True)
class FunnelQuery:
    """One planned LogQL instant query for `devops roadmap eval funnel`."""

    kind: FunnelQueryKind
    window: str
    expr: str


STEP_NEW_TO_READY: Final = "New (placed) to Ready"
STEP_READY_TO_PLAN_PR: Final = "Ready to plan PR open"
STEP_G1_PLAN_MERGED_TO_READY_DELIVERY: Final = "plan PR merged to ready delivery PR"
STEP_CONTINUE_PLAN_OPEN_TO_READY_DELIVERY: Final = "plan PR open to ready delivery PR"
STEP_READY_DELIVERY_TO_MERGE: Final = "ready delivery PR to merge"

StepSpec = tuple[str, FunnelPath | None]
FUNNEL_STEP_SPECS: Final[tuple[StepSpec, ...]] = (
    (STEP_NEW_TO_READY, None),
    (STEP_READY_TO_PLAN_PR, None),
    (STEP_G1_PLAN_MERGED_TO_READY_DELIVERY, FunnelPath.G1),
    (STEP_READY_DELIVERY_TO_MERGE, FunnelPath.G1),
    (STEP_CONTINUE_PLAN_OPEN_TO_READY_DELIVERY, FunnelPath.CONTINUE),
    (STEP_READY_DELIVERY_TO_MERGE, FunnelPath.CONTINUE),
)

_FORWARD_STATUS_LABELS: Final[frozenset[str]] = frozenset(
    {
        "status/planned",
        "status/in-progress",
        "status/in-review",
        "status/blocked",
    }
)
_NEW_TO_STAGED_JOBS: Final[frozenset[str]] = frozenset(
    {
        RoadmapJob.INTAKE.value,
        RoadmapJob.REFINE.value,
        RoadmapJob.REFINE_JUDGE.value,
        RoadmapJob.ALTERNATIVES.value,
        RoadmapJob.STAGE.value,
        RoadmapJob.RETITLE.value,
    }
)
_UNLABEL_FORWARD_WINDOW: Final = timedelta(seconds=60)
_RATIO_DECIMALS: Final = 4
_TIME_DECIMALS: Final = 1


class FunnelPull(BaseModel):
    """One pull request referenced by an issue timeline."""

    model_config = ConfigDict(frozen=True)

    number: int
    title: str
    head_ref: str | None = None
    state: str = "open"
    draft: bool = False
    created_at: datetime
    merged_at: datetime | None = None
    ready_at: datetime | None = None


class FunnelItem(BaseModel):
    """Normalized timeline summary for one roadmap item in its active Ready pass."""

    model_config = ConfigDict(frozen=True)

    repo: str
    number: int
    created_at: datetime
    new_at: datetime
    ready_at: datetime
    cohort: str
    state: str = "open"
    plan_pr: FunnelPull | None = None
    delivery_pr: FunnelPull | None = None

    @property
    def path(self) -> FunnelPath | None:
        """`continue` when delivery shares plan's head branch; `G1` on distinct branches or after
        plan merge; None before path determination."""
        if self.plan_pr is not None and self.delivery_pr is not None:
            if (
                self.plan_pr.head_ref
                and self.delivery_pr.head_ref
                and self.plan_pr.head_ref == self.delivery_pr.head_ref
            ):
                return FunnelPath.CONTINUE
            return FunnelPath.G1
        if self.plan_pr is not None and self.plan_pr.merged_at is not None:
            return FunnelPath.G1
        return None


class FunnelStepReport(BaseModel):
    """Conversion, interval, timing, and token/cost measures for one step of one cohort."""

    model_config = ConfigDict(frozen=True)

    step: str
    path: FunnelPath | None
    n: int
    passed: int
    failed: int
    in_progress: int
    share: float | None
    wilson_lower: float | None
    wilson_upper: float | None
    smallest_change: float | None
    median_seconds: float | None
    p90_seconds: float | None
    tokens_per_success: float | None
    cost_usd_micros_per_success: float | None


class FunnelItemReport(BaseModel):
    """Per-item cohort assignment, path, and Loki attribution."""

    model_config = ConfigDict(frozen=True)

    repo: str
    item: int
    cohort: str
    ready_at: datetime
    path: FunnelPath | None
    has_result_line: bool
    new_to_staged_tokens: int
    total_tokens: int
    total_cost_usd_micros: int


class FunnelCohortReport(BaseModel):
    """One ISO-week cohort of ready items and its step funnel."""

    model_config = ConfigDict(frozen=True)

    cohort: str
    items_count: int
    missing_result_lines: int
    total_tokens: int
    total_cost_usd_micros: int
    steps: list[FunnelStepReport]
    items: list[FunnelItemReport]


class FunnelReport(BaseModel):
    """Complete `devops roadmap eval funnel` output."""

    model_config = ConfigDict(frozen=True)

    since: datetime
    until: datetime
    repos: list[str]
    loki_url: str
    items_count: int
    missing_result_lines: int
    cohorts: list[FunnelCohortReport] = Field(default_factory=list)


@dataclass(frozen=True)
class LokiItemTotals:
    """Loki line counts, tokens, and cost attribution for all queried items."""

    line_counts: Mapping[tuple[str, int], int]
    tokens_by_job: Mapping[tuple[str, str, int], int]
    cost_by_job: Mapping[tuple[str, str, int], int]

    def has_line(self, repo: str, item: int) -> bool:
        return self.line_counts.get((repo.casefold(), item), 0) > 0

    def total_tokens(self, repo: str, item: int) -> int:
        key = repo.casefold()
        return sum(
            val for (r, _job, n), val in self.tokens_by_job.items() if r == key and n == item
        )

    def total_cost(self, repo: str, item: int) -> int:
        key = repo.casefold()
        return sum(val for (r, _job, n), val in self.cost_by_job.items() if r == key and n == item)

    def new_to_staged_tokens(self, repo: str, item: int) -> int:
        key = repo.casefold()
        return sum(
            val
            for (r, job, n), val in self.tokens_by_job.items()
            if r == key and n == item and job in _NEW_TO_STAGED_JOBS
        )


def parse_since(text: str) -> datetime:
    """Parse `--since` as an aware UTC datetime; naive dates map to midnight UTC."""
    try:
        parsed = datetime.fromisoformat(text.strip())
    except ValueError as exc:
        raise ValidationError(MESSAGES.roadmap.funnel_bad_since.format(text=text)) from exc
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def resolve_funnel_repos(repo: str | None) -> list[RepoRef]:
    """Validate `--repo` or fall back to `service.repos` before making network calls."""
    if repo is not None:
        return [RepoRef(repo)]
    configured = load_settings().service.repos
    if not configured:
        raise ConfigurationError(MESSAGES.roadmap.funnel_no_repos, key="service.repos")
    return [RepoRef(item) for item in configured]


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _iso_week(at: datetime) -> str:
    year, week, _ = at.isocalendar()
    return f"{year}-W{week:02d}"


def _quantile(values: Sequence[float], q: float) -> float | None:
    """Linear interpolation quantile matching `quantile_over_time`."""
    if not values:
        return None
    ordered = sorted(values)
    rank = q * (len(ordered) - 1)
    low, high = math.floor(rank), math.ceil(rank)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def _unlabel_cancels_ready(
    events: Sequence[tuple[datetime, str, Mapping[str, Any]]],
    index: int,
    unlabeled_at: datetime,
) -> bool:
    """True unless a forward workflow label arrives within `_UNLABEL_FORWARD_WINDOW` without an
    intervening `status/new` label (matching atomic `write_status` transitions)."""
    cutoff = unlabeled_at + _UNLABEL_FORWARD_WINDOW
    for later_at, later_kind, later_raw in events[index + 1 :]:
        if later_at > cutoff:
            break
        if later_kind != "labeled":
            continue
        label_name = _label_name(later_raw)
        if label_name == "status/new":
            return True
        if label_name in _FORWARD_STATUS_LABELS:
            return False
    return True


def _label_name(event: Mapping[str, Any]) -> str:
    label = event.get("label")
    return str(label.get("name", "")) if isinstance(label, Mapping) else ""


def _resolve_pr_ready_at(
    pr_events: Sequence[Mapping[str, Any]] | None,
    *,
    draft: bool,
    created_at: datetime,
    inline_ready_at: datetime | None,
) -> datetime | None:
    if inline_ready_at is not None:
        return inline_ready_at
    if pr_events:
        timed = sorted(
            (
                (ts, str(ev.get("event", "")))
                for ev in pr_events
                if (ts := _parse_dt(ev.get("created_at"))) is not None
            ),
            key=lambda pair: pair[0],
        )
        ready_at: datetime | None = None
        saw_draft_toggle = False
        for ts, kind in timed:
            if kind == "ready_for_review":
                ready_at = ts
                saw_draft_toggle = True
            elif kind == "convert_to_draft":
                ready_at = None
                saw_draft_toggle = True
        if saw_draft_toggle:
            return None if draft else ready_at
    return None if draft else created_at


def _build_pull(
    src_issue: Mapping[str, Any],
    pulls_by_number: Mapping[int, Mapping[str, Any]],
    pr_timelines: Mapping[int, Sequence[Mapping[str, Any]]],
) -> FunnelPull | None:
    pr_meta = src_issue.get("pull_request")
    if not isinstance(pr_meta, Mapping):
        return None
    raw_number = src_issue.get("number")
    if not isinstance(raw_number, int):
        return None
    full_pr = pulls_by_number.get(raw_number, {})
    title = str(full_pr.get("title") or src_issue.get("title") or "")
    head_src = src_issue.get("head")
    head_full = full_pr.get("head")
    head_ref = (
        str(head_full.get("ref"))
        if isinstance(head_full, Mapping) and head_full.get("ref")
        else (
            str(head_src.get("ref"))
            if isinstance(head_src, Mapping) and head_src.get("ref")
            else None
        )
    )
    state = str(full_pr.get("state") or src_issue.get("state") or "open")
    draft = bool(full_pr["draft"]) if "draft" in full_pr else bool(src_issue.get("draft", False))
    created_at = _parse_dt(full_pr.get("created_at")) or _parse_dt(src_issue.get("created_at"))
    if created_at is None:
        return None
    merged_at = _parse_dt(full_pr.get("merged_at")) or _parse_dt(pr_meta.get("merged_at"))
    inline_ready = _parse_dt(src_issue.get("ready_at")) or _parse_dt(full_pr.get("ready_at"))
    ready_at = _resolve_pr_ready_at(
        pr_timelines.get(raw_number),
        draft=draft and merged_at is None,
        created_at=created_at,
        inline_ready_at=inline_ready,
    )
    return FunnelPull(
        number=raw_number,
        title=title,
        head_ref=head_ref,
        state=state,
        draft=draft,
        created_at=created_at,
        merged_at=merged_at,
        ready_at=ready_at,
    )


def _pick_plan_pull(pulls: Sequence[FunnelPull]) -> FunnelPull | None:
    if not pulls:
        return None
    merged = [p for p in pulls if p.merged_at is not None]
    if merged:
        return max(merged, key=lambda p: p.created_at)
    opened = [p for p in pulls if p.state == "open"]
    if opened:
        return max(opened, key=lambda p: p.created_at)
    return max(pulls, key=lambda p: p.created_at)


def _pick_delivery_pull(pulls: Sequence[FunnelPull]) -> FunnelPull | None:
    if not pulls:
        return None
    merged = [p for p in pulls if p.merged_at is not None]
    if merged:
        return max(merged, key=lambda p: p.created_at)
    ready_open = [p for p in pulls if p.state == "open" and not p.draft]
    if ready_open:
        return max(ready_open, key=lambda p: p.created_at)
    opened = [p for p in pulls if p.state == "open"]
    if opened:
        return max(opened, key=lambda p: p.created_at)
    return max(pulls, key=lambda p: p.created_at)


def _collect_cross_ref(
    raw: Mapping[str, Any],
    pulls_map: Mapping[int, Mapping[str, Any]],
    pr_map: Mapping[int, Sequence[Mapping[str, Any]]],
    referenced_pulls: dict[int, FunnelPull],
) -> None:
    source = raw.get("source")
    src_issue = source.get("issue") if isinstance(source, Mapping) else None
    if isinstance(src_issue, Mapping):
        pull = _build_pull(src_issue, pulls_map, pr_map)
        if pull is not None:
            referenced_pulls[pull.number] = pull


def parse_issue_timeline(
    repo: str,
    number: int,
    *,
    created_at: datetime,
    state: str,
    events: Sequence[Mapping[str, Any]],
    pulls_by_number: Mapping[int, Mapping[str, Any]] | None = None,
    pr_timelines: Mapping[int, Sequence[Mapping[str, Any]]] | None = None,
) -> FunnelItem | None:
    """Extract an item's latest active `status/ready` cohort and PR milestones from its timeline."""
    pulls_map = pulls_by_number or {}
    pr_map = pr_timelines or {}

    timed = sorted(
        (
            (ts, str(ev.get("event", "")), ev)
            for ev in events
            if (ts := _parse_dt(ev.get("created_at"))) is not None
        ),
        key=lambda item: item[0],
    )

    pending_new_at: datetime | None = None
    active_new_at: datetime | None = None
    ready_at: datetime | None = None
    pass_reset_at: datetime | None = None
    referenced_pulls: dict[int, FunnelPull] = {}

    for idx, (ts, kind, raw) in enumerate(timed):
        label = _label_name(raw)
        if kind == "labeled" and label == "status/new":
            pending_new_at = ts
        elif kind == "labeled" and label == "status/ready":
            ready_at = ts
            active_new_at = pending_new_at if pending_new_at is not None else created_at
        elif (
            kind == "unlabeled"
            and label == "status/ready"
            and _unlabel_cancels_ready(timed, idx, ts)
        ):
            ready_at, pass_reset_at, pending_new_at = None, ts, ts
        elif kind == "cross-referenced":
            _collect_cross_ref(raw, pulls_map, pr_map, referenced_pulls)

    if ready_at is None:
        return None

    active_pulls = [
        pull
        for pull in referenced_pulls.values()
        if pass_reset_at is None or pull.created_at >= pass_reset_at
    ]
    return FunnelItem(
        repo=repo,
        number=number,
        created_at=created_at,
        new_at=active_new_at or created_at,
        ready_at=ready_at,
        cohort=_iso_week(ready_at),
        state=state,
        plan_pr=_pick_plan_pull([p for p in active_pulls if pull_kind(p.title) is PullKind.PLAN]),
        delivery_pr=_pick_delivery_pull(
            [p for p in active_pulls if pull_kind(p.title) is PullKind.DELIVERY]
        ),
    )


def _outcome_ready_delivery(
    item: FunnelItem, start: datetime, *, now: datetime
) -> tuple[bool, float | None, float | None]:
    if item.delivery_pr is not None and item.delivery_pr.ready_at is not None:
        return True, max((item.delivery_pr.ready_at - start).total_seconds(), 0.0), None
    still_open = item.state == "open" and (
        item.delivery_pr is None or item.delivery_pr.state == "open"
    )
    age = max((now - start).total_seconds(), 0.0) if still_open else None
    return True, None, age


def _outcome_new_to_ready(
    item: FunnelItem, _path: FunnelPath | None, _now: datetime
) -> tuple[bool, float | None, float | None]:
    return True, max((item.ready_at - item.new_at).total_seconds(), 0.0), None


def _outcome_ready_to_plan(
    item: FunnelItem, _path: FunnelPath | None, now: datetime
) -> tuple[bool, float | None, float | None]:
    if item.plan_pr is not None:
        return True, max((item.plan_pr.created_at - item.ready_at).total_seconds(), 0.0), None
    still_open = item.state == "open" and item.delivery_pr is None
    return True, None, max((now - item.ready_at).total_seconds(), 0.0) if still_open else None


def _outcome_g1_to_ready_delivery(
    item: FunnelItem, path: FunnelPath | None, now: datetime
) -> tuple[bool, float | None, float | None]:
    if item.path is not path or item.plan_pr is None or item.plan_pr.merged_at is None:
        return False, None, None
    return _outcome_ready_delivery(item, item.plan_pr.merged_at, now=now)


def _outcome_continue_to_ready_delivery(
    item: FunnelItem, path: FunnelPath | None, now: datetime
) -> tuple[bool, float | None, float | None]:
    if item.path is not path or item.plan_pr is None:
        return False, None, None
    return _outcome_ready_delivery(item, item.plan_pr.created_at, now=now)


def _outcome_ready_delivery_to_merge(
    item: FunnelItem, path: FunnelPath | None, now: datetime
) -> tuple[bool, float | None, float | None]:
    delivery = item.delivery_pr
    if item.path is not path or delivery is None or delivery.ready_at is None:
        return False, None, None
    if delivery.merged_at is not None:
        return True, max((delivery.merged_at - delivery.ready_at).total_seconds(), 0.0), None
    still_open = delivery.state == "open" and not delivery.draft
    return True, None, max((now - delivery.ready_at).total_seconds(), 0.0) if still_open else None


_STEP_EVALUATORS: Final = {
    STEP_NEW_TO_READY: _outcome_new_to_ready,
    STEP_READY_TO_PLAN_PR: _outcome_ready_to_plan,
    STEP_G1_PLAN_MERGED_TO_READY_DELIVERY: _outcome_g1_to_ready_delivery,
    STEP_CONTINUE_PLAN_OPEN_TO_READY_DELIVERY: _outcome_continue_to_ready_delivery,
    STEP_READY_DELIVERY_TO_MERGE: _outcome_ready_delivery_to_merge,
}


def _step_item_outcome(
    item: FunnelItem, spec: StepSpec, *, now: datetime
) -> tuple[bool, float | None, float | None]:
    """Return `(entered, pass_duration_s, open_age_s)` for `item` on funnel step `spec`."""
    step, path = spec
    return _STEP_EVALUATORS[step](item, path, now)


def _summarize_step(
    items: Sequence[FunnelItem],
    spec: StepSpec,
    *,
    now: datetime,
    window_p90: float | None,
    cohort_tokens: int,
    cohort_cost: int,
) -> FunnelStepReport:
    step, path = spec
    pass_durations: list[float] = []
    failed = 0
    in_progress = 0
    for item in items:
        entered, pass_s, open_age_s = _step_item_outcome(item, spec, now=now)
        if not entered:
            continue
        if pass_s is not None:
            pass_durations.append(pass_s)
        elif open_age_s is not None and (window_p90 is None or open_age_s < window_p90):
            in_progress += 1
        else:
            failed += 1
    passed = len(pass_durations)
    n = passed + failed
    interval = wilson_interval(passed, n)
    median_s = _quantile(pass_durations, 0.5)
    p90_s = _quantile(pass_durations, 0.9)
    return FunnelStepReport(
        step=step,
        path=path,
        n=n,
        passed=passed,
        failed=failed,
        in_progress=in_progress,
        share=round(passed / n, _RATIO_DECIMALS) if n else None,
        wilson_lower=round(interval[0], _RATIO_DECIMALS) if interval else None,
        wilson_upper=round(interval[1], _RATIO_DECIMALS) if interval else None,
        smallest_change=(
            round((interval[1] - interval[0]) / 2, _RATIO_DECIMALS) if interval else None
        ),
        median_seconds=round(median_s, _TIME_DECIMALS) if median_s is not None else None,
        p90_seconds=round(p90_s, _TIME_DECIMALS) if p90_s is not None else None,
        tokens_per_success=round(cohort_tokens / passed, _TIME_DECIMALS) if passed else None,
        cost_usd_micros_per_success=(
            round(cohort_cost / passed, _TIME_DECIMALS) if passed else None
        ),
    )


def build_funnel_report(
    items: Sequence[FunnelItem],
    *,
    since: datetime,
    until: datetime,
    loki_url: str,
    repos: Sequence[str],
    loki_totals: LokiItemTotals | None = None,
) -> FunnelReport:
    """Aggregate normalized timeline items and Loki totals into an ISO-week cohort report."""
    totals = loki_totals or LokiItemTotals(line_counts={}, tokens_by_job={}, cost_by_job={})
    in_window = [item for item in items if item.ready_at >= since]

    window_p90: dict[StepSpec, float | None] = {}
    for spec in FUNNEL_STEP_SPECS:
        passed_s = [
            dur
            for item in in_window
            for entered, dur, _ in [_step_item_outcome(item, spec, now=until)]
            if entered and dur is not None
        ]
        window_p90[spec] = _quantile(passed_s, 0.9)

    by_cohort: dict[str, list[FunnelItem]] = defaultdict(list)
    for item in in_window:
        by_cohort[item.cohort].append(item)

    cohorts: list[FunnelCohortReport] = []
    for cohort_name in sorted(by_cohort):
        cohort_items = sorted(by_cohort[cohort_name], key=lambda it: (it.repo, it.number))
        item_reports = [
            FunnelItemReport(
                repo=it.repo,
                item=it.number,
                cohort=cohort_name,
                ready_at=it.ready_at,
                path=it.path,
                has_result_line=totals.has_line(it.repo, it.number),
                new_to_staged_tokens=totals.new_to_staged_tokens(it.repo, it.number),
                total_tokens=totals.total_tokens(it.repo, it.number),
                total_cost_usd_micros=totals.total_cost(it.repo, it.number),
            )
            for it in cohort_items
        ]
        cohort_tokens = sum(r.total_tokens for r in item_reports)
        cohort_cost = sum(r.total_cost_usd_micros for r in item_reports)
        missing = sum(1 for r in item_reports if not r.has_result_line)
        steps = [
            _summarize_step(
                cohort_items,
                spec,
                now=until,
                window_p90=window_p90[spec],
                cohort_tokens=cohort_tokens,
                cohort_cost=cohort_cost,
            )
            for spec in FUNNEL_STEP_SPECS
        ]
        cohorts.append(
            FunnelCohortReport(
                cohort=cohort_name,
                items_count=len(item_reports),
                missing_result_lines=missing,
                total_tokens=cohort_tokens,
                total_cost_usd_micros=cohort_cost,
                steps=steps,
                items=item_reports,
            )
        )

    return FunnelReport(
        since=since,
        until=until,
        repos=list(repos),
        loki_url=loki_url,
        items_count=len(in_window),
        missing_result_lines=sum(c.missing_result_lines for c in cohorts),
        cohorts=cohorts,
    )


def loki_window_for(since: datetime, until: datetime) -> str:
    """Range duration string (`<N>h`) spanning `since..until` for LogQL instant queries."""
    hours = max(math.ceil((until - since).total_seconds() / 3600), 1)
    return f"{hours}h"


def _item_pipeline(repo: RepoRef | None) -> str:
    pipeline = f"{RESULT_LINES} | regexp `{ITEM_FIELDS}`"
    if repo is not None:
        pipeline += f" | repo=~`(?i){re.escape(repo.display)}`"
    return pipeline


def plan_funnel_queries(repo: RepoRef | None, *, window: str) -> tuple[FunnelQuery, ...]:
    """Build the LogQL metric queries that count item result lines, `tokens`, and `cost_usd_micros`."""
    base = _item_pipeline(repo)
    counts = FunnelQuery(
        FunnelQueryKind.COUNTS,
        window,
        f"sum by (repo, roadmap_job, item) (count_over_time({base} [{window}]))",
    )
    tokens = FunnelQuery(
        FunnelQueryKind.TOKENS,
        window,
        f'sum by (repo, roadmap_job, item) (sum_over_time({base} |~ " tokens=[0-9]+ " '
        f"{count_label('tokens')} | unwrap tokens [{window}]))",
    )
    cost = FunnelQuery(
        FunnelQueryKind.COST,
        window,
        "sum by (repo, roadmap_job, item) "
        f'(sum_over_time({base} |~ " cost_usd_micros=[0-9]+ " '
        f"{count_label('cost_usd_micros')} | unwrap cost_usd_micros [{window}]))",
    )
    return (counts, tokens, cost)


def _parse_job_item_totals(answer: PrometheusQueryResult) -> dict[tuple[str, str, int], int]:
    totals: dict[tuple[str, str, int], int] = defaultdict(int)
    for series in answer.series:
        item_text = series.labels.get("item", "")
        if not item_text.isdigit():
            continue
        repo_key = series.labels.get("repo", "").casefold()
        job = series.labels.get("roadmap_job", "")
        totals[(repo_key, job, int(item_text))] += round(float(series.value))
    return dict(totals)


def _parse_item_line_counts(answer: PrometheusQueryResult) -> dict[tuple[str, int], int]:
    counts: dict[tuple[str, int], int] = defaultdict(int)
    for series in answer.series:
        item_text = series.labels.get("item", "")
        if not item_text.isdigit():
            continue
        repo_key = series.labels.get("repo", "").casefold()
        counts[(repo_key, int(item_text))] += round(float(series.value))
    return dict(counts)


def read_loki_funnel_totals(
    repo: RepoRef | None, *, since: datetime, until: datetime, loki_url: str
) -> LokiItemTotals:
    """Query Loki instant metrics once for item result-line counts, `tokens`, and `cost_usd_micros`."""
    queries = plan_funnel_queries(repo, window=loki_window_for(since, until))
    answers = query_loki_metrics([query.expr for query in queries], loki_url)
    by_kind = {query.kind: answer for query, answer in zip(queries, answers, strict=True)}
    return LokiItemTotals(
        line_counts=_parse_item_line_counts(by_kind[FunnelQueryKind.COUNTS]),
        tokens_by_job=_parse_job_item_totals(by_kind[FunnelQueryKind.TOKENS]),
        cost_by_job=_parse_job_item_totals(by_kind[FunnelQueryKind.COST]),
    )


def plan_funnel_github_requests(
    repos: Sequence[RepoRef], *, since: datetime
) -> list[PlannedRequest]:
    """Describe the paced GitHub REST requests `read_repo_funnel_items` sends, for `--dry-run`."""
    since_iso = f"{since.astimezone(UTC):%Y-%m-%dT%H:%M:%SZ}"
    requests: list[PlannedRequest] = []
    for ref in repos:
        requests.extend(
            (
                PlannedRequest(
                    method="GET",
                    target=(
                        f"https://api.github.com/repos/{ref.display}/issues"
                        f"?state=all&sort=updated&direction=desc&since={since_iso}"
                        f"&per_page={DEFAULT_GH_REST_PER_PAGE}"
                    ),
                ),
                PlannedRequest(
                    method="GET",
                    target=(
                        f"https://api.github.com/repos/{ref.display}/pulls"
                        f"?state=all&sort=updated&direction=desc&per_page={DEFAULT_GH_REST_PER_PAGE}"
                    ),
                ),
                PlannedRequest(
                    method="GET",
                    target=(
                        f"https://api.github.com/repos/{ref.display}/issues/<number>/timeline"
                        f"?per_page={DEFAULT_GH_REST_PER_PAGE}"
                    ),
                ),
            )
        )
    return requests


def _read_issues_since(
    session: GitHubSession, repo: RepoRef, since: datetime
) -> list[dict[str, Any]]:
    since_iso = f"{since.astimezone(UTC):%Y-%m-%dT%H:%M:%SZ}"
    path = (
        f"/repos/{repo.display}/issues"
        f"?state=all&sort=updated&direction=desc&since={since_iso}&per_page={DEFAULT_GH_REST_PER_PAGE}"
    )
    issues: list[dict[str, Any]] = []
    for page in session.pages(path):
        if not isinstance(page, list) or not page:
            break
        all_before_since = True
        for raw in page:
            if not isinstance(raw, Mapping):
                continue
            updated = _parse_dt(raw.get("updated_at"))
            if updated is None or updated >= since:
                all_before_since = False
            if "pull_request" not in raw and isinstance(raw.get("number"), int):
                issues.append(dict(raw))
        if all_before_since:
            break
    return issues


def _read_pulls_since(
    session: GitHubSession, repo: RepoRef, since: datetime
) -> dict[int, dict[str, Any]]:
    path = (
        f"/repos/{repo.display}/pulls"
        f"?state=all&sort=updated&direction=desc&per_page={DEFAULT_GH_REST_PER_PAGE}"
    )
    pulls: dict[int, dict[str, Any]] = {}
    for page in session.pages(path):
        if not isinstance(page, list) or not page:
            break
        all_before_since = True
        for raw in page:
            if not isinstance(raw, Mapping):
                continue
            updated = _parse_dt(raw.get("updated_at"))
            if updated is None or updated >= since:
                all_before_since = False
            num = raw.get("number")
            if isinstance(num, int):
                pulls[num] = dict(raw)
        if all_before_since:
            break
    return pulls


def _collect_cross_ref_prs(events: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    for ev in events:
        if ev.get("event") != "cross-referenced":
            continue
        source = ev.get("source")
        src_issue = source.get("issue") if isinstance(source, Mapping) else None
        if isinstance(src_issue, Mapping) and isinstance(src_issue.get("pull_request"), Mapping):
            found.append(src_issue)
    return found


def _has_head_ref(ref_issue: Mapping[str, Any]) -> bool:
    head = ref_issue.get("head")
    return isinstance(head, Mapping) and bool(head.get("ref"))


def _resolve_pulls_for_refs(
    session: GitHubSession,
    repo: RepoRef,
    since: datetime,
    referenced: Sequence[Mapping[str, Any]],
) -> dict[int, dict[str, Any]]:
    if all(_has_head_ref(ref) for ref in referenced):
        return {}
    pulls = _read_pulls_since(session, repo, since)
    for ref in referenced:
        pr_num = ref.get("number")
        if isinstance(pr_num, int) and pr_num not in pulls and not _has_head_ref(ref):
            detail = session.rest("GET", f"/repos/{repo.display}/pulls/{pr_num}")
            if isinstance(detail, Mapping):
                pulls[pr_num] = dict(detail)
    return pulls


def _needs_pr_timeline(ref_issue: Mapping[str, Any], full_pr: Mapping[str, Any]) -> bool:
    title = str(full_pr.get("title") or ref_issue.get("title") or "")
    if pull_kind(title) is not PullKind.DELIVERY:
        return False
    inline_ready = _parse_dt(ref_issue.get("ready_at")) or _parse_dt(full_pr.get("ready_at"))
    pr_meta = ref_issue.get("pull_request")
    merged_at = _parse_dt(full_pr.get("merged_at")) or _parse_dt(
        pr_meta.get("merged_at") if isinstance(pr_meta, Mapping) else None
    )
    draft = bool(full_pr["draft"]) if "draft" in full_pr else bool(ref_issue.get("draft", False))
    return inline_ready is None and not (draft and merged_at is None)


def _read_delivery_timelines(
    session: GitHubSession,
    repo: RepoRef,
    referenced: Sequence[Mapping[str, Any]],
    pulls_by_number: Mapping[int, Mapping[str, Any]],
) -> dict[int, list[dict[str, Any]]]:
    timelines: dict[int, list[dict[str, Any]]] = {}
    for ref in referenced:
        pr_num = ref.get("number")
        if not isinstance(pr_num, int) or pr_num in timelines:
            continue
        if not _needs_pr_timeline(ref, pulls_by_number.get(pr_num, {})):
            continue
        pr_path = (
            f"/repos/{repo.display}/issues/{pr_num}/timeline?per_page={DEFAULT_GH_REST_PER_PAGE}"
        )
        timelines[pr_num] = [
            dict(item) for item in session.paginate(pr_path) if isinstance(item, Mapping)
        ]
    return timelines


def read_repo_funnel_items(
    repo: RepoRef, *, since: datetime, session: GitHubSession | None = None
) -> list[FunnelItem]:
    """Read issues, timelines, PR heads, and delivery `ready_for_review` events via `GitHubSession`."""
    if session is None:
        from devops_cli.github.session import get_github_session

        session = get_github_session()

    raw_issues = _read_issues_since(session, repo, since)
    issue_timelines: dict[int, list[dict[str, Any]]] = {}
    referenced_pr_issues: list[Mapping[str, Any]] = []
    for raw in raw_issues:
        number = int(raw["number"])
        timeline_path = (
            f"/repos/{repo.display}/issues/{number}/timeline?per_page={DEFAULT_GH_REST_PER_PAGE}"
        )
        events = [
            dict(item) for item in session.paginate(timeline_path) if isinstance(item, Mapping)
        ]
        issue_timelines[number] = events
        referenced_pr_issues.extend(_collect_cross_ref_prs(events))

    pulls_by_number = _resolve_pulls_for_refs(session, repo, since, referenced_pr_issues)
    pr_timelines = _read_delivery_timelines(session, repo, referenced_pr_issues, pulls_by_number)

    parsed: list[FunnelItem] = []
    for raw in raw_issues:
        created_at = _parse_dt(raw.get("created_at"))
        if created_at is None:
            continue
        number = int(raw["number"])
        item = parse_issue_timeline(
            repo.display,
            number,
            created_at=created_at,
            state=str(raw.get("state") or "open"),
            events=issue_timelines[number],
            pulls_by_number=pulls_by_number,
            pr_timelines=pr_timelines,
        )
        if item is not None:
            parsed.append(item)
    return parsed


def funnel_report(
    repos: Sequence[RepoRef],
    *,
    since: datetime,
    loki_url: str,
    now: datetime | None = None,
) -> FunnelReport:
    """Fetch GitHub timelines and Loki totals, then build the complete funnel report."""
    until = now or datetime.now(UTC)
    all_items: list[FunnelItem] = []
    for ref in repos:
        all_items.extend(read_repo_funnel_items(ref, since=since))
    earliest = min([since, *(it.new_at for it in all_items if it.ready_at >= since)])
    repo_filter = repos[0] if len(repos) == 1 else None
    totals = read_loki_funnel_totals(repo_filter, since=earliest, until=until, loki_url=loki_url)
    return build_funnel_report(
        all_items,
        since=since,
        until=until,
        loki_url=loki_url,
        repos=[ref.display for ref in repos],
        loki_totals=totals,
    )


def _fmt_ratio(val: float | None, decimals: int = 3) -> str:
    return MESSAGES.roadmap.funnel_none if val is None else f"{val:.{decimals}f}"


def _fmt_num(val: float | None) -> str:
    return MESSAGES.roadmap.funnel_none if val is None else f"{val:,.1f}"


def _table(rows: Sequence[list[str]]) -> list[str]:
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return [
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip()
        for row in rows
    ]


def render_funnel_report(report: FunnelReport) -> str:
    """Format `FunnelReport` as human-readable tables grouped by ISO week."""
    texts = MESSAGES.roadmap
    lines = [
        texts.funnel_title.format(
            since=report.since.isoformat(),
            until=report.until.isoformat(),
            repos=", ".join(report.repos),
            url=report.loki_url,
        )
    ]
    if not report.cohorts:
        lines.extend(["", texts.funnel_empty.format(since=report.since.isoformat())])
        return "\n".join(lines) + "\n"

    header = [
        texts.funnel_column_step,
        texts.funnel_column_path,
        texts.funnel_column_n,
        texts.funnel_column_passed,
        texts.funnel_column_in_progress,
        texts.funnel_column_share,
        texts.funnel_column_interval,
        texts.funnel_column_min_change,
        texts.funnel_column_median_s,
        texts.funnel_column_p90_s,
        texts.funnel_column_tokens_ok,
        texts.funnel_column_cost_ok,
    ]
    for cohort in report.cohorts:
        lines.extend(
            [
                "",
                texts.funnel_cohort_header.format(
                    cohort=cohort.cohort,
                    items=cohort.items_count,
                    tokens=f"{cohort.total_tokens:,}",
                    cost=f"{cohort.total_cost_usd_micros:,}",
                    missing=cohort.missing_result_lines,
                ),
                "",
            ]
        )
        rows = [
            [
                step.step,
                str(step.path or "both"),
                str(step.n),
                str(step.passed),
                str(step.in_progress),
                _fmt_ratio(step.share),
                (
                    f"[{_fmt_ratio(step.wilson_lower)}, {_fmt_ratio(step.wilson_upper)}]"
                    if step.wilson_lower is not None
                    else texts.funnel_none
                ),
                _fmt_ratio(step.smallest_change),
                _fmt_num(step.median_seconds),
                _fmt_num(step.p90_seconds),
                _fmt_num(step.tokens_per_success),
                _fmt_num(step.cost_usd_micros_per_success),
            ]
            for step in cohort.steps
        ]
        lines.extend(_table([header, *rows]))
        lines.extend(
            texts.funnel_item_line.format(
                repo=it.repo,
                item=it.item,
                path=it.path or texts.funnel_none,
                ready=it.ready_at.isoformat(),
                new_tokens=f"{it.new_to_staged_tokens:,}",
                tokens=f"{it.total_tokens:,}",
                cost=f"{it.total_cost_usd_micros:,}",
                has_line=str(it.has_result_line).lower(),
            )
            for it in cohort.items
        )
    lines.extend(["", texts.funnel_summary_missing.format(missing=report.missing_result_lines)])
    return "\n".join(lines) + "\n"


__all__ = [
    "FUNNEL_STEP_SPECS",
    "STEP_CONTINUE_PLAN_OPEN_TO_READY_DELIVERY",
    "STEP_G1_PLAN_MERGED_TO_READY_DELIVERY",
    "STEP_NEW_TO_READY",
    "STEP_READY_DELIVERY_TO_MERGE",
    "STEP_READY_TO_PLAN_PR",
    "FunnelCohortReport",
    "FunnelItem",
    "FunnelItemReport",
    "FunnelPath",
    "FunnelPull",
    "FunnelQuery",
    "FunnelQueryKind",
    "FunnelReport",
    "FunnelStepReport",
    "LokiItemTotals",
    "build_funnel_report",
    "funnel_report",
    "loki_window_for",
    "parse_issue_timeline",
    "parse_since",
    "plan_funnel_github_requests",
    "plan_funnel_queries",
    "read_loki_funnel_totals",
    "read_repo_funnel_items",
    "render_funnel_report",
    "resolve_funnel_repos",
]
