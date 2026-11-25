"""The job grade report: the grade of each roadmap workflow from its result lines in Loki (#5165).

Each roadmap job logs one result line for each attempt (`roadmap/job_result.py`). The report reads
the lines with LogQL metric instant queries, so no line limit applies, and gives for each workflow
and repository: the attempts, `p`, the Wilson interval, the grade and its range
(`roadmap/job_grade.py`), the all-attempts ratio and the infrastructure share, the first-pass
ratio, the top failure classes, the action of the grade, the efficiency measures, the versions with
`_MIN_VERSION_ATTEMPTS` attempts or more, and the trend of 24 h and 6 h with two signals:

- broken: in 6 h, `_BROKEN_ATTEMPTS` attempts or more and no success;
- infrastructure: in 24 h, `_INFRA_ATTEMPTS` attempts or more and an infrastructure share over
  `_INFRA_SHARE`.

A plan of the queries (`plan_grade_queries`) is the dry run of the report: it sends no request.

For stage and implement the report also gives the verdicts of the pull requests that the bot of
`service.github_app.slug` opened in the window, and their score (`roadmap/pr_verdict.py`, #5968),
beside the attempt ratio. With no slug there is no bot, and the report reads no verdict.

The implement Job ends at its draft and logs `drafted` with the number of the draft in `pull`
(#6559), so its line is the hand-off and not the outcome. The report scores the `drafted` lines of
each pull request once, by the forge state of that pull request, from the same search of the bot
pull requests: a pull request that merged, or that is open and out of draft, is a success; one that
closed with no merge is a failure; a draft has no outcome yet, so its lines stay out of the
attempts and count in `drafts_pending`. With n lines on one pull request, a success counts 1
success and n - 1 failures, and a failure n failures. A line with no `pull` takes the forge state
of the newest delivery of its item. The window grade, its first passes and its efficiency per
success take this score. The versions and the trend count the
lines as written, and with no bot the report reads no delivery, so a `drafted` line counts as its
line says.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.config.settings import load_settings
from devops_cli.exceptions import ServiceRequestError
from devops_cli.exceptions.git import GitHubUnreadError
from devops_cli.github.repo_ref import RepoRef
from devops_cli.k8s.logql import query_loki_metrics
from devops_cli.lang import MESSAGES
from devops_cli.models.prometheus import PrometheusQueryResult, PrometheusSeries
from devops_cli.roadmap.job_grade import (
    EfficiencyWork,
    GradeMeasure,
    GradeWindow,
    grade_policy,
    measure_grade,
    share,
)
from devops_cli.roadmap.job_result import FIRST_PASS_LIMITS, LINE_PREFIX, CountLimit, RoadmapJob
from devops_cli.roadmap.pr_verdict import (
    KIND_JOBS,
    BotPull,
    ForgeOutcome,
    PullKind,
    Verdict,
    VerdictGrade,
    forge_outcome,
    grade_verdicts,
    read_bot_pulls,
    verdict_search,
)


class GradeQueryKind(StrEnum):
    """One metric query of the report."""

    COUNTS = "counts"
    CLASSES = "classes"
    FIRST_PASSES = "first_passes"
    TOKENS_P50 = "tokens_p50"
    TOKENS_P90 = "tokens_p90"
    TOKENS_MAX = "tokens_max"
    TOKENS_SUM = "tokens_sum"
    SECONDS_P50 = "seconds_p50"
    SECONDS_P90 = "seconds_p90"
    SECONDS_MAX = "seconds_max"
    SECONDS_SUM = "seconds_sum"
    DRAFTED = "drafted"


class GradeSignal(StrEnum):
    """A signal beside the grade: a broken workflow, or an infrastructure share."""

    BROKEN = "broken"
    INFRA = "infra"


@dataclass(frozen=True)
class GradeQuery:
    """One LogQL instant query of the report and the window that it counts."""

    kind: GradeQueryKind
    window: GradeWindow
    expr: str

    @property
    def key(self) -> str:
        """The name of the query: `<kind>@<window>`."""
        return f"{self.kind}@{self.window}"


TREND_WINDOWS: Final = (GradeWindow.H24, GradeWindow.H6)
_TOP_CLASSES: Final = 3
_MIN_VERSION_ATTEMPTS: Final = 10
_BROKEN_ATTEMPTS: Final = 5
_INFRA_ATTEMPTS: Final = 10
_INFRA_SHARE: Final = 0.20

# The streams of the result lines (`docs/roadmap/job-success.md`), by the container of each unit
# that writes them: the Service, a stage Job (#4559) and a fix-plan Job (#5363). A runner pod and
# the other pods that run a coding agent stay out, because their logs hold the output of tests. A
# stream that OpenTelemetry exports has no label `namespace`, so no line counts twice (#5556).
RESULT_LINE_SELECTOR: Final = '{namespace="devops", container=~"service|stage|fix-plan"}'
# The base of each query that reads the result lines, also on the dashboard: the Service logs a
# line as JSON with the line in `message`, and a Job pod logs the plain line. `json` gives the
# message, or an error label for a plain line, which `drop` removes so that Loki does not refuse
# the query. `line_format` then gives the message, or the full line, and the filter keeps only a
# line that starts with the prefix: a line that the field parse does not match still counts.
RESULT_LINES: Final = (
    f'{RESULT_LINE_SELECTOR} |= "{LINE_PREFIX}" | json message '
    "| drop __error__, __error_details__ "
    '| line_format "{{ or .message __line__ }}" '
    f'|~ "^{LINE_PREFIX} "'
)
# The fixed fields of a result line, and its version at the end.
_FIELDS: Final = (
    rf"^{LINE_PREFIX} job=(?P<roadmap_job>\S+) repo=(?P<repo>\S+) item=\S+ "
    r"result=(?P<result>\S+) success=(?P<success>\S+) class=(?P<failure_class>\S+) "
    r"infra=(?P<infra>\S+) .*version=(?P<version>\S+)$"
)
# The fields of a line with its item, for the `drafted` lines of implement (#6559) and the
# item cohort funnel (#5494).
ITEM_FIELDS: Final = _FIELDS.replace(r"item=\S+ ", r"item=#?(?P<item>[0-9]+) ")
_ITEM_FIELDS: Final = ITEM_FIELDS
_KEY: Final = "roadmap_job, repo"
# The counts of each efficiency query: the count of the line and the LogQL of the range.
_EFFICIENCY: Final[Mapping[GradeQueryKind, tuple[str, str]]] = {
    GradeQueryKind.TOKENS_P50: ("tokens", "quantile_over_time(0.5, {lines} [{window}]) by ({key})"),
    GradeQueryKind.TOKENS_P90: ("tokens", "quantile_over_time(0.9, {lines} [{window}]) by ({key})"),
    GradeQueryKind.TOKENS_MAX: ("tokens", "max_over_time({lines} [{window}]) by ({key})"),
    GradeQueryKind.TOKENS_SUM: ("tokens", "sum by ({key}) (sum_over_time({lines} [{window}]))"),
    GradeQueryKind.SECONDS_P50: (
        "seconds",
        "quantile_over_time(0.5, {lines} [{window}]) by ({key})",
    ),
    GradeQueryKind.SECONDS_P90: (
        "seconds",
        "quantile_over_time(0.9, {lines} [{window}]) by ({key})",
    ),
    GradeQueryKind.SECONDS_MAX: ("seconds", "max_over_time({lines} [{window}]) by ({key})"),
    GradeQueryKind.SECONDS_SUM: ("seconds", "sum by ({key}) (sum_over_time({lines} [{window}]))"),
}
_FIRST_PASS_COUNTS: Final = tuple(
    sorted({limit.count for limits in FIRST_PASS_LIMITS.values() for limit in limits})
)
_FIRST_PASS_KEEP: Final = f"{_KEY}, {', '.join(_FIRST_PASS_COUNTS)}"
_DRAFTED_KEEP: Final = "repo, item, pull, repair_rounds"
_COUNT_KINDS: Final = frozenset(
    {
        GradeQueryKind.COUNTS,
        GradeQueryKind.CLASSES,
        GradeQueryKind.FIRST_PASSES,
        GradeQueryKind.DRAFTED,
    }
)
_SERIES_LIMIT_ERROR: Final = "maximum number of series"
_MIN_SPLIT_SECONDS: Final = 3600
_HTTP_BAD_REQUEST: Final = 400

type _Key = tuple[str, str | None]


class ClassCount(BaseModel):
    """A failure class and the attempts that it ended."""

    model_config = ConfigDict(frozen=True)

    failure_class: str = Field(description="The class of `roadmap/failure.py`, or `none`")
    attempts: int = Field(description="Attempts with no infrastructure cut that it ended")


class Efficiency(BaseModel):
    """Tokens and seconds of the attempts of a workflow (owner direction 2026-11-12)."""

    model_config = ConfigDict(frozen=True)

    tokens_p50: float | None = Field(description="Median tokens of an attempt")
    tokens_p90: float | None = Field(description="p90 of the tokens of an attempt")
    tokens_max: float | None = Field(description="Most tokens of one attempt")
    tokens_per_success: float | None = Field(
        description="Tokens of all attempts / successes; None with no success"
    )
    seconds_p50: float | None = Field(description="Median seconds of an attempt")
    seconds_p90: float | None = Field(description="p90 of the seconds of an attempt")
    seconds_max: float | None = Field(description="Most seconds of one attempt")
    seconds_per_success: float | None = Field(
        description="Seconds of all attempts / successes; None with no success"
    )
    work: EfficiencyWork = Field(description="Optimize from grade 80 up, else report only")


class VersionGrade(BaseModel):
    """The measure of the attempts of one devops-cli version."""

    model_config = ConfigDict(frozen=True)

    version: str = Field(description="The devops-cli version that wrote the lines")
    measure: GradeMeasure = Field(description="Ratio, interval and grades of the version")
    all_attempts: int = Field(description="All attempts, infrastructure cuts included")
    infra_attempts: int = Field(description="Attempts that an infrastructure cut ended")
    infra_share: float | None = Field(description="Infrastructure cuts / all attempts")


class WindowGrade(BaseModel):
    """The measure of a workflow in a trend window."""

    model_config = ConfigDict(frozen=True)

    window: GradeWindow = Field(description="The trend window")
    measure: GradeMeasure = Field(description="Ratio, interval and grades in the window")
    all_attempts: int = Field(description="All attempts, infrastructure cuts included")
    infra_share: float | None = Field(description="Infrastructure cuts / all attempts")


class WorkflowGrade(BaseModel):
    """The report of one workflow and repository."""

    model_config = ConfigDict(frozen=True)

    job: str = Field(description="The roadmap job of the lines")
    repo: str | None = Field(description="The repository; None for a job with no line")
    measure: GradeMeasure = Field(description="Ratio, interval and grades of the window")
    all_attempts: int = Field(description="All attempts, infrastructure cuts included")
    all_ratio: float | None = Field(description="Successes / all attempts")
    infra_attempts: int = Field(description="Attempts that an infrastructure cut ended")
    infra_share: float | None = Field(description="Infrastructure cuts / all attempts")
    first_pass_ratio: float | None = Field(
        description="First passes / attempts; None when the line has no counts for the rule"
    )
    top_classes: list[ClassCount] = Field(description="The largest failure classes")
    action: str = Field(description="The owner action of the grade")
    efficiency: Efficiency | None = Field(description="None for a job with no tokens on its line")
    versions: list[VersionGrade] = Field(description="Versions with 10 attempts or more")
    trend: list[WindowGrade] = Field(description="The measure in 24 h and in 6 h")
    signals: list[GradeSignal] = Field(description="Broken in 6 h, infrastructure share in 24 h")
    verdicts: VerdictGrade | None = Field(
        default=None,
        description="The verdicts of the bot pull requests of stage or implement; None for "
        "another job, or when the report read no verdict",
    )
    drafts_pending: int | None = Field(
        default=None,
        description="Implement attempts that ended at a delivery that is still a draft, out of the "
        "attempts until it merges, is ready or closes; None for another job, or when the report "
        "read no pull request",
    )


class GradeReport(BaseModel):
    """The job grade report of one window."""

    model_config = ConfigDict(frozen=True)

    window: GradeWindow = Field(description="The window of the grade")
    repo: str | None = Field(description="The repository of `--repo`; None for all")
    loki_url: str = Field(description="The Loki that the queries read")
    workflows: list[WorkflowGrade] = Field(description="One row for each workflow and repository")
    verdict_bot: str | None = Field(
        default=None,
        description="The bot whose pull requests gave the verdicts; None when the report read no "
        "verdict, as with no `service.github_app.slug`",
    )
    verdict_partial_score: float | None = Field(
        default=None, description="The score of needs fix, `roadmap.verdict_partial_score`"
    )
    verdict_error: str | None = Field(
        default=None,
        description="Reason the GitHub verdict read failed, or None when verdicts were read or "
        "no bot is set",
    )


@dataclass(frozen=True)
class VerdictRead:
    """The pull requests of the bot in the window, with their first verdicts, and the score of
    needs fix."""

    bot: str
    partial_score: float
    pulls: Sequence[BotPull]
    # The start of the window: a pull request opened before it gives a forge outcome and no
    # verdict (#6559). None counts each pull request.
    opened_since: datetime | None = None

    def grade(self, job: str, repo: str | None) -> VerdictGrade | None:
        """The verdicts of the pull requests of `job` in `repo` that the bot opened in the window;
        None for a job that opens no pull request."""
        if job not in (RoadmapJob.STAGE, RoadmapJob.IMPLEMENT):
            return None
        since = self.opened_since
        pulls = [
            pull
            for pull in self.pulls
            if KIND_JOBS[pull.kind] == job
            and pull.repo.casefold() == (repo or "").casefold()
            and (since is None or pull.created is None or pull.created >= since)
        ]
        return grade_verdicts(
            RoadmapJob(job),
            [pull.verdict for pull in pulls if pull.unscored is None],
            partial_score=self.partial_score,
            unscored=sum(pull.unscored is not None for pull in pulls),
        )

    def keys(self) -> set[tuple[str, str | None]]:
        """The job and the repository of each pull request that the bot opened in the window, as
        `grade` counts them: a pull request opened before it gives only a forge outcome (#6559)."""
        since = self.opened_since
        return {
            (KIND_JOBS[pull.kind].value, pull.repo)
            for pull in self.pulls
            if since is None or pull.created is None or pull.created >= since
        }

    def pull(self, repo: str, number: int) -> BotPull | None:
        """The pull request `number` of `repo`, or None when the search did not find it."""
        return next(
            (
                pull
                for pull in self.pulls
                if pull.number == number and pull.repo.casefold() == repo.casefold()
            ),
            None,
        )

    def delivery(self, repo: str, item: int) -> BotPull | None:
        """The newest delivery of `item` in `repo`, or None when the search found none."""
        found = [
            pull
            for pull in self.pulls
            if pull.kind is PullKind.DELIVERY
            and pull.item == item
            and pull.repo.casefold() == repo.casefold()
        ]
        return max(found, key=lambda pull: pull.number) if found else None


def _lines(repo: RepoRef | None) -> str:
    """The log pipeline of the result lines, with the fields as labels."""
    pipeline = f"{RESULT_LINES} | regexp `{_FIELDS}`"
    if repo is not None:
        pipeline += f" | repo=~`(?i){re.escape(repo.display)}`"
    return pipeline


def count_label(count: str) -> str:
    """The LogQL regexp stage that extracts numeric count `count` from a result line."""
    return f"| regexp ` {count}=(?P<{count}>[0-9]+) `"


def _count_label(count: str) -> str:
    return count_label(count)


def _query_expr(kind: GradeQueryKind, duration: str, repo: RepoRef | None) -> str:
    """Build the LogQL metric expression for `kind` over `duration`, retaining only used labels."""
    lines = _lines(repo)
    match kind:
        case GradeQueryKind.COUNTS:
            keep = f"{_KEY}, version, success, infra"
            return f"sum by ({keep}) (count_over_time({lines} | keep {keep} [{duration}]))"
        case GradeQueryKind.CLASSES:
            by = f"{_KEY}, failure_class"
            return (
                f"sum by ({by}) (count_over_time("
                f'{lines} | success="false" | infra="false" | keep {by}, success, infra [{duration}]))'
            )
        case GradeQueryKind.DRAFTED:
            pipeline = f"{RESULT_LINES} | regexp `{_ITEM_FIELDS}`"
            if repo is not None:
                pipeline += f" | repo=~`(?i){re.escape(repo.display)}`"
            return (
                f"sum by ({_DRAFTED_KEEP}) (count_over_time("
                f'{pipeline} | roadmap_job="{RoadmapJob.IMPLEMENT}" | result="drafted" '
                f'| infra="false" {_count_label("repair_rounds")} {_count_label("pull")} '
                f"| keep {_DRAFTED_KEEP} [{duration}]))"
            )
        case GradeQueryKind.FIRST_PASSES:
            counts = " ".join(_count_label(count) for count in _FIRST_PASS_COUNTS)
            return (
                f"sum by ({_FIRST_PASS_KEEP}) (count_over_time("
                f'{lines} | success="true" | infra="false" {counts} '
                f"| keep {_FIRST_PASS_KEEP} [{duration}]))"
            )
        case _:
            count, template = _EFFICIENCY[kind]
            unwrapped = (
                f'{lines} |~ " {count}=[0-9]+ " {_count_label(count)} '
                f"| keep {_KEY}, {count} | unwrap {count}"
            )
            return template.format(lines=unwrapped, window=duration, key=_KEY)


def _query(kind: GradeQueryKind, window: GradeWindow, repo: RepoRef | None) -> GradeQuery:
    return GradeQuery(kind, window, _query_expr(kind, window.value, repo))


def plan_grade_queries(window: GradeWindow, repo: RepoRef | None = None) -> tuple[GradeQuery, ...]:
    """The queries of the report of `window`: each measure in `window`, then the counts of each
    trend window that is not `window`."""
    queries = [_query(kind, window, repo) for kind in GradeQueryKind]
    queries += [
        _query(GradeQueryKind.COUNTS, trend, repo) for trend in TREND_WINDOWS if trend != window
    ]
    return tuple(queries)


@dataclass
class _Counts:
    """The attempts of one workflow and repository in one window."""

    attempts: int = 0
    successes: int = 0
    infra: int = 0
    all_successes: int = 0

    def add(self, labels: Mapping[str, str], lines: int) -> None:
        infra = labels.get("infra") == "true"
        success = labels.get("success") == "true"
        self.infra += lines if infra else 0
        self.all_successes += lines if success else 0
        self.attempts += 0 if infra else lines
        self.successes += lines if success and not infra else 0

    @property
    def all_attempts(self) -> int:
        return self.attempts + self.infra


def _key(labels: Mapping[str, str]) -> _Key:
    return labels.get("roadmap_job", ""), labels.get("repo")


def _number(value: str) -> float:
    return float(value) if value else 0.0


def _counts(answer: PrometheusQueryResult) -> dict[_Key, _Counts]:
    counts: dict[_Key, _Counts] = defaultdict(_Counts)
    for series in answer.series:
        counts[_key(series.labels)].add(series.labels, round(_number(series.value)))
    return counts


def _versions(answer: PrometheusQueryResult) -> dict[_Key, dict[str, _Counts]]:
    versions: dict[_Key, dict[str, _Counts]] = defaultdict(lambda: defaultdict(_Counts))
    for series in answer.series:
        version = series.labels.get("version", "")
        versions[_key(series.labels)][version].add(series.labels, round(_number(series.value)))
    return versions


def _classes(answer: PrometheusQueryResult) -> dict[_Key, list[ClassCount]]:
    counted: dict[_Key, Counter[str]] = defaultdict(Counter)
    for series in answer.series:
        counted[_key(series.labels)][series.labels.get("failure_class", "")] += round(
            _number(series.value)
        )
    return {
        key: [
            ClassCount(failure_class=name, attempts=attempts)
            for name, attempts in sorted(classes.items(), key=lambda item: (-item[1], item[0]))[
                :_TOP_CLASSES
            ]
        ]
        for key, classes in counted.items()
    }


def _first_pass_limits(job: str) -> tuple[CountLimit, ...] | None:
    """The first-pass rule of `job`; None for a job with no rule or a name that is no job."""
    return FIRST_PASS_LIMITS.get(RoadmapJob(job)) if job in RoadmapJob else None


def _is_first_pass(labels: Mapping[str, str], limits: tuple[CountLimit, ...]) -> bool:
    return all(
        labels.get(limit.count, "").isdigit() and int(labels[limit.count]) <= limit.most
        for limit in limits
    )


def _first_passes(answer: PrometheusQueryResult) -> Counter[_Key]:
    passes: Counter[_Key] = Counter()
    for series in answer.series:
        limits = _first_pass_limits(series.labels.get("roadmap_job", ""))
        if limits and _is_first_pass(series.labels, limits):
            passes[_key(series.labels)] += round(_number(series.value))
    return passes


def _by_key(answer: PrometheusQueryResult) -> dict[_Key, float]:
    return {_key(series.labels): _number(series.value) for series in answer.series}


def _efficiency(
    key: _Key,
    answers: Mapping[GradeQueryKind, dict[_Key, float]],
    successes: int,
    work: EfficiencyWork,
) -> Efficiency | None:
    if not any(key in answers[kind] for kind in _EFFICIENCY):
        return None
    values = {kind: answers[kind].get(key) for kind in _EFFICIENCY}
    return Efficiency(
        tokens_p50=values[GradeQueryKind.TOKENS_P50],
        tokens_p90=values[GradeQueryKind.TOKENS_P90],
        tokens_max=values[GradeQueryKind.TOKENS_MAX],
        tokens_per_success=_per_success(values[GradeQueryKind.TOKENS_SUM], successes),
        seconds_p50=values[GradeQueryKind.SECONDS_P50],
        seconds_p90=values[GradeQueryKind.SECONDS_P90],
        seconds_max=values[GradeQueryKind.SECONDS_MAX],
        seconds_per_success=_per_success(values[GradeQueryKind.SECONDS_SUM], successes),
        work=work,
    )


def _per_success(total: float | None, successes: int) -> float | None:
    """The sum of all attempts over the successes, to 1 decimal; None with no success."""
    return round(total / successes, 1) if total is not None and successes else None


def _window_grade(window: GradeWindow, counts: _Counts) -> WindowGrade:
    return WindowGrade(
        window=window,
        measure=measure_grade(
            attempts=counts.attempts, successes=counts.successes, first_pass=None
        ),
        all_attempts=counts.all_attempts,
        infra_share=share(counts.infra, counts.all_attempts),
    )


def _signals(trend: Mapping[GradeWindow, _Counts]) -> list[GradeSignal]:
    broken = trend[GradeWindow.H6]
    infra = trend[GradeWindow.H24]
    signals = []
    if broken.attempts >= _BROKEN_ATTEMPTS and broken.successes == 0:
        signals.append(GradeSignal.BROKEN)
    if infra.all_attempts >= _INFRA_ATTEMPTS and infra.infra / infra.all_attempts > _INFRA_SHARE:
        signals.append(GradeSignal.INFRA)
    return signals


@dataclass(frozen=True)
class _Drafted:
    """The `drafted` lines of implement on one item: the count, the pull request that the lines
    name (None for a line written before the field), and whether they had no repair round, so a
    success of theirs is a first pass."""

    repo: str
    item: int
    lines: int
    first_pass: bool
    pull: int | None = None


@dataclass(frozen=True)
class _Answers:
    """The parsed answers of the queries of one report."""

    window: GradeWindow
    counts: Mapping[GradeWindow, dict[_Key, _Counts]]
    versions: dict[_Key, dict[str, _Counts]]
    classes: dict[_Key, list[ClassCount]]
    first_passes: Counter[_Key]
    efficiency: Mapping[GradeQueryKind, dict[_Key, float]]
    drafted: list[_Drafted]


def _drafted(answer: PrometheusQueryResult) -> list[_Drafted]:
    limits = _first_pass_limits(RoadmapJob.IMPLEMENT) or ()
    return [
        _Drafted(
            repo=series.labels.get("repo", ""),
            item=int(series.labels["item"]),
            lines=round(_number(series.value)),
            first_pass=_is_first_pass(series.labels, limits),
            pull=int(series.labels["pull"]) if series.labels.get("pull", "").isdigit() else None,
        )
        for series in answer.series
        if series.labels.get("item", "").isdigit()
    ]


@dataclass
class _Linked:
    """The forge outcome of the `drafted` lines of one repository (#6559): the lines whose
    delivery succeeded, failed or is a draft, and the first passes among the successes and among
    all the lines."""

    successes: int = 0
    failures: int = 0
    pending: int = 0
    first_successes: int = 0
    first_lines: int = 0


def _link(drafted: Sequence[_Drafted], repo: str | None, verdicts: VerdictRead) -> _Linked:
    """Score the `drafted` lines of `repo` by their forge outcome (#6559). The lines that name one
    pull request are scored once, by that pull request (`_score_pull`). A line written before the
    field takes the outcome of the newest delivery of its item."""
    linked = _Linked()
    by_pull: defaultdict[tuple[int, int], list[_Drafted]] = defaultdict(list)
    for lines in drafted:
        if lines.repo.casefold() != (repo or "").casefold():
            continue
        if lines.pull is not None:
            by_pull[lines.item, lines.pull].append(lines)
            continue
        pull = verdicts.delivery(lines.repo, lines.item)
        outcome = forge_outcome(pull) if pull is not None else None
        linked.first_lines += lines.lines if lines.first_pass else 0
        if outcome is ForgeOutcome.SUCCESS:
            linked.successes += lines.lines
            linked.first_successes += lines.lines if lines.first_pass else 0
        elif outcome is ForgeOutcome.FAILURE:
            linked.failures += lines.lines
        else:
            linked.pending += lines.lines
    for (_, number), group in by_pull.items():
        _score_pull(linked, group, verdicts.pull(group[0].repo, number))
    return linked


def _score_pull(linked: _Linked, group: Sequence[_Drafted], pull: BotPull | None) -> None:
    """Score the n `drafted` lines of one pull request once, by its forge outcome: a success
    counts 1 success and n - 1 failures, because an earlier Job of the same pull request did not
    reach the outcome alone; a failure counts n failures; a draft, or a pull request that the
    search did not find, keeps the n lines pending. The success is a first pass only for one line
    with no repair round."""
    count = sum(lines.lines for lines in group)
    linked.first_lines += sum(lines.lines for lines in group if lines.first_pass)
    outcome = forge_outcome(pull) if pull is not None else None
    if outcome is ForgeOutcome.SUCCESS:
        linked.successes += 1
        linked.failures += count - 1
        linked.first_successes += 1 if count == 1 and group[0].first_pass else 0
    elif outcome is ForgeOutcome.FAILURE:
        linked.failures += count
    else:
        linked.pending += count


def _forge_counts(counts: _Counts, linked: _Linked) -> _Counts:
    """`counts` with each `drafted` line scored by its forge outcome: a draft leaves the attempts,
    and a failed delivery takes its success back."""
    taken_back = linked.failures + linked.pending
    return _Counts(
        attempts=counts.attempts - linked.pending,
        successes=counts.successes - taken_back,
        infra=counts.infra,
        all_successes=counts.all_successes - taken_back,
    )


def _parse(window: GradeWindow, answers: Mapping[str, PrometheusQueryResult]) -> _Answers:
    def answer(kind: GradeQueryKind, at: GradeWindow = window) -> PrometheusQueryResult:
        return answers[f"{kind}@{at}"]

    return _Answers(
        window=window,
        counts={at: _counts(answer(GradeQueryKind.COUNTS, at)) for at in {window, *TREND_WINDOWS}},
        versions=_versions(answer(GradeQueryKind.COUNTS)),
        classes=_classes(answer(GradeQueryKind.CLASSES)),
        first_passes=_first_passes(answer(GradeQueryKind.FIRST_PASSES)),
        efficiency={kind: _by_key(answer(kind)) for kind in _EFFICIENCY},
        drafted=_drafted(answer(GradeQueryKind.DRAFTED)),
    )


def _workflow(key: _Key, parsed: _Answers, verdicts: VerdictRead | None) -> WorkflowGrade:
    job, repo = key
    counts = parsed.counts[parsed.window].get(key, _Counts())
    first_pass = parsed.first_passes[key] if _first_pass_limits(job) else None
    pending: int | None = None
    if job == RoadmapJob.IMPLEMENT and verdicts is not None:
        linked = _link(parsed.drafted, repo, verdicts)
        counts = _forge_counts(counts, linked)
        pending = linked.pending
        if first_pass is not None:
            first_pass += linked.first_successes - linked.first_lines
    measure = measure_grade(
        attempts=counts.attempts, successes=counts.successes, first_pass=first_pass
    )
    policy = grade_policy(measure.grade)
    trend = {at: parsed.counts[at].get(key, _Counts()) for at in TREND_WINDOWS}
    return WorkflowGrade(
        job=job,
        repo=repo,
        measure=measure,
        all_attempts=counts.all_attempts,
        all_ratio=share(counts.all_successes, counts.all_attempts),
        infra_attempts=counts.infra,
        infra_share=share(counts.infra, counts.all_attempts),
        first_pass_ratio=share(first_pass, counts.attempts) if first_pass is not None else None,
        top_classes=parsed.classes.get(key, []),
        action=policy.action,
        efficiency=_efficiency(key, parsed.efficiency, counts.all_successes, policy.efficiency),
        versions=[
            VersionGrade(
                version=version,
                measure=measure_grade(
                    attempts=version_counts.attempts,
                    successes=version_counts.successes,
                    first_pass=None,
                ),
                all_attempts=version_counts.all_attempts,
                infra_attempts=version_counts.infra,
                infra_share=share(version_counts.infra, version_counts.all_attempts),
            )
            for version, version_counts in sorted(parsed.versions.get(key, {}).items())
            if version_counts.all_attempts >= _MIN_VERSION_ATTEMPTS
        ],
        trend=[_window_grade(at, trend[at]) for at in TREND_WINDOWS],
        signals=_signals(trend),
        verdicts=verdicts.grade(job, repo) if verdicts is not None else None,
        drafts_pending=pending,
    )


def _job_order(job: str) -> tuple[int, str]:
    """The jobs in the order of `RoadmapJob`, then a name that is no job."""
    jobs = list(RoadmapJob)
    return (jobs.index(RoadmapJob(job)), job) if job in RoadmapJob else (len(jobs), job)


def _row_keys(parsed: _Answers, repo: RepoRef | None, verdicts: VerdictRead | None) -> list[_Key]:
    """Each workflow and repository with a line in a window or a bot pull request, and one row
    with no repository (or with `--repo`) for each job that has neither. A repository that Loki
    and GitHub spell in another case gives one row, with the spelling of Loki."""
    seen = {key for window_counts in parsed.counts.values() for key in window_counts}
    if verdicts is not None:
        spelled = {(job, (name or "").casefold()) for job, name in seen}
        seen |= {
            (job, name)
            for job, name in verdicts.keys()
            if (job, (name or "").casefold()) not in spelled
        }
    jobs = {job for job, _ in seen}
    empty = repo.display if repo is not None else None
    seen |= {(job.value, empty) for job in RoadmapJob if job.value not in jobs}
    return sorted(seen, key=lambda key: (_job_order(key[0]), key[1] or ""))


def build_grade_report(
    window: GradeWindow,
    repo: RepoRef | None,
    loki_url: str,
    answers: Mapping[str, PrometheusQueryResult],
    verdicts: VerdictRead | None = None,
    *,
    verdict_error: str | None = None,
) -> GradeReport:
    """The report from the answer of each planned query, by the key of the query, and the
    verdicts of the bot pull requests when the report read them."""
    parsed = _parse(window, answers)
    return GradeReport(
        window=window,
        repo=repo.display if repo is not None else None,
        loki_url=loki_url,
        workflows=[_workflow(key, parsed, verdicts) for key in _row_keys(parsed, repo, verdicts)],
        verdict_bot=verdicts.bot if verdicts is not None else None,
        verdict_partial_score=verdicts.partial_score if verdicts is not None else None,
        verdict_error=verdict_error,
    )


def plan_verdict_search(
    window: GradeWindow, repo: RepoRef | None, now: datetime | None = None
) -> str | None:
    """The GitHub search of the bot pull requests of the window; None with no
    `service.github_app.slug`, as then there is no bot."""
    slug = load_settings().service.github_app.slug
    if not slug:
        return None
    return verdict_search(window, repo, slug, now or datetime.now(UTC))


def _read_verdicts(search: str, since: datetime) -> VerdictRead:
    """The bot pull requests that `search` finds, read through the GitHub session. The verdicts
    count the pull requests opened at `since` or later."""
    from devops_cli.github.session import get_github_session

    settings = load_settings()
    return VerdictRead(
        bot=settings.service.github_app.bot_login or "",
        partial_score=settings.roadmap.verdict_partial_score,
        pulls=read_bot_pulls(get_github_session().client, search),
        opened_since=since,
    )


def _format_duration(seconds: int) -> str:
    """Format `seconds` as an integer LogQL range duration."""
    if seconds % 3600 == 0:
        return f"{seconds // 3600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def _utc_stamp(moment: datetime) -> str:
    """Format `moment` as RFC 3339 UTC for Loki's `time` parameter."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_series_limit(exc: ServiceRequestError) -> bool:
    """Whether `exc` reports Loki's HTTP 400 series-count limit."""
    return exc.status_code == _HTTP_BAD_REQUEST and _SERIES_LIMIT_ERROR in str(exc).casefold()


def _sum_query_results(
    left: PrometheusQueryResult, right: PrometheusQueryResult
) -> PrometheusQueryResult:
    """Sum two disjoint count query vectors by series label set."""
    totals: dict[tuple[tuple[str, str], ...], float] = defaultdict(float)
    labels_by_key: dict[tuple[tuple[str, str], ...], dict[str, str]] = {}
    for part in (left, right):
        for series in part.series:
            key = tuple(sorted(series.labels.items()))
            labels_by_key.setdefault(key, dict(series.labels))
            totals[key] += _number(series.value)
    merged = [
        PrometheusSeries(
            labels=labels_by_key[key],
            value=str(int(total)) if total.is_integer() else repr(total),
        )
        for key, total in totals.items()
    ]
    return PrometheusQueryResult(status=left.status, series=merged)


def _query_count_split(
    kind: GradeQueryKind,
    span_seconds: int,
    repo: RepoRef | None,
    loki_url: str,
    *,
    end: datetime,
    duration_text: str | None = None,
    eval_at: str | None = None,
) -> PrometheusQueryResult:
    """Run a count query, recursively halving its window down to `1h` on series-limit 400s."""
    expr = _query_expr(kind, duration_text or _format_duration(span_seconds), repo)
    try:
        return query_loki_metrics([expr], loki_url, at=eval_at)[0]
    except ServiceRequestError as exc:
        left_seconds = span_seconds // 2
        right_seconds = span_seconds - left_seconds
        if (
            not _is_series_limit(exc)
            or left_seconds < _MIN_SPLIT_SECONDS
            or right_seconds < _MIN_SPLIT_SECONDS
        ):
            raise
        first_end = end - timedelta(seconds=right_seconds)
        first = _query_count_split(
            kind, left_seconds, repo, loki_url, end=first_end, eval_at=_utc_stamp(first_end)
        )
        second = _query_count_split(
            kind, right_seconds, repo, loki_url, end=end, eval_at=_utc_stamp(end)
        )
        return _sum_query_results(first, second)


def _query_all(
    queries: Sequence[GradeQuery], repo: RepoRef | None, loki_url: str, *, end: datetime
) -> dict[str, PrometheusQueryResult]:
    """Execute planned grade queries, splitting rejected count queries by half-window."""
    answers: dict[str, PrometheusQueryResult] = {}
    for query in queries:
        if query.kind in _COUNT_KINDS:
            span_seconds = int(query.window.span.total_seconds())
            answers[query.key] = _query_count_split(
                query.kind,
                span_seconds,
                repo,
                loki_url,
                end=end,
                duration_text=query.window.value,
            )
        else:
            answers[query.key] = query_loki_metrics([query.expr], loki_url)[0]
    return answers


def grade_report(
    window: GradeWindow, repo: RepoRef | None, loki_url: str, *, now: datetime | None = None
) -> GradeReport:
    """Send the planned queries to Loki, read the verdicts of the bot pull requests from GitHub
    when a bot is set, and build the report."""
    at = now or datetime.now(UTC)
    queries = plan_grade_queries(window, repo)
    answers = _query_all(queries, repo, loki_url, end=at)
    search = plan_verdict_search(window, repo, at)
    verdicts: VerdictRead | None = None
    verdict_error: str | None = None
    if search is not None:
        try:
            verdicts = _read_verdicts(search, at - window.span)
        except GitHubUnreadError as exc:
            verdict_error = str(exc)
    return build_grade_report(
        window,
        repo,
        loki_url,
        answers,
        verdicts,
        verdict_error=verdict_error,
    )


def _number_text(value: float | None) -> str:
    return MESSAGES.roadmap.grades_none if value is None else f"{value:,.0f}"


def _ratio_text(value: float | None) -> str:
    return MESSAGES.roadmap.grades_none if value is None else f"{value:.2f}"


def _interval_text(measure: GradeMeasure) -> str:
    if measure.lower is None or measure.upper is None:
        return MESSAGES.roadmap.grades_none
    return f"[{measure.lower:.2f}, {measure.upper:.2f}]"


def _range_text(measure: GradeMeasure) -> str:
    if measure.range_low is None or measure.range_high is None:
        return MESSAGES.roadmap.grades_none
    return f"{measure.range_low}–{measure.range_high}"


def _trend_text(trend: WindowGrade) -> str:
    return f"{trend.measure.successes}/{trend.measure.attempts}"


def _cells(row: WorkflowGrade) -> list[str]:
    measure = row.measure
    return [
        row.job,
        row.repo or MESSAGES.roadmap.grades_none,
        str(measure.attempts),
        str(measure.successes),
        _ratio_text(measure.ratio),
        _interval_text(measure),
        str(measure.grade),
        str(measure.point_grade or MESSAGES.roadmap.grades_none),
        _range_text(measure),
        _ratio_text(row.first_pass_ratio),
        _ratio_text(row.infra_share),
        *(_trend_text(trend) for trend in row.trend),
    ]


def _table(rows: Sequence[list[str]]) -> list[str]:
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return [
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip()
        for row in rows
    ]


def _efficiency_text(efficiency: Efficiency) -> str:
    return MESSAGES.roadmap.grades_efficiency.format(
        work=efficiency.work,
        tokens_p50=_number_text(efficiency.tokens_p50),
        tokens_p90=_number_text(efficiency.tokens_p90),
        tokens_max=_number_text(efficiency.tokens_max),
        tokens_success=_number_text(efficiency.tokens_per_success),
        seconds_p50=_number_text(efficiency.seconds_p50),
        seconds_p90=_number_text(efficiency.seconds_p90),
        seconds_max=_number_text(efficiency.seconds_max),
        seconds_success=_number_text(efficiency.seconds_per_success),
    )


def _details(row: WorkflowGrade) -> list[str]:
    texts = MESSAGES.roadmap
    lines = [
        texts.grades_row.format(
            job=row.job,
            repo=row.repo or texts.grades_none,
            grade=row.measure.grade,
            name=grade_policy(row.measure.grade).name,
            action=row.action,
        )
    ]
    if row.top_classes:
        classes = ", ".join(f"{item.failure_class} {item.attempts}" for item in row.top_classes)
        lines.append(texts.grades_classes.format(classes=classes))
    if row.all_attempts:
        lines.append(
            texts.grades_all_attempts.format(
                attempts=row.all_attempts,
                ratio=_ratio_text(row.all_ratio),
                infra=row.infra_attempts,
            )
        )
    if row.drafts_pending:
        lines.append(texts.grades_drafts_pending.format(drafts=row.drafts_pending))
    lines += [
        texts.grades_version.format(
            version=version.version,
            successes=version.measure.successes,
            attempts=version.measure.attempts,
            ratio=_ratio_text(version.measure.ratio),
            interval=_interval_text(version.measure),
            all_attempts=version.all_attempts,
            infra=version.infra_attempts,
            infra_share=_ratio_text(version.infra_share),
        )
        for version in row.versions
    ]
    if row.efficiency is not None:
        lines.append(_efficiency_text(row.efficiency))
    signal_texts = {
        GradeSignal.BROKEN: texts.grades_signal_broken.format(attempts=_BROKEN_ATTEMPTS),
        GradeSignal.INFRA: texts.grades_signal_infra.format(
            share=_INFRA_SHARE, attempts=_INFRA_ATTEMPTS
        ),
    }
    lines += [signal_texts[signal] for signal in row.signals]
    return lines


def render_grade_report(report: GradeReport) -> str:
    """The report as text: one table line for each workflow and repository, then the details of
    each row that has attempts."""
    texts = MESSAGES.roadmap
    header = [
        texts.grades_column_job,
        texts.grades_column_repo,
        texts.grades_column_attempts,
        texts.grades_column_successes,
        texts.grades_column_ratio,
        texts.grades_column_interval,
        texts.grades_column_grade,
        texts.grades_column_point,
        texts.grades_column_range,
        texts.grades_column_first_pass,
        texts.grades_column_infra,
        *(texts.grades_column_trend.format(window=window) for window in TREND_WINDOWS),
    ]
    lines = [
        texts.grades_title.format(
            window=report.window,
            repo=report.repo or texts.grades_all_repos,
            url=report.loki_url,
        ),
        "",
        *_table([header, *(_cells(row) for row in report.workflows)]),
    ]
    for row in report.workflows:
        if row.all_attempts or any(trend.all_attempts for trend in row.trend):
            lines += ["", *_details(row)]
    lines += _verdict_lines(report)
    return "\n".join(lines) + "\n"


def _verdict_cell(grade: VerdictGrade, verdict: Verdict) -> str:
    return f"{grade.counts[verdict]} ({_ratio_text(grade.shares[verdict])})"


def _verdict_lines(report: GradeReport) -> list[str]:
    """The verdicts of the bot pull requests: one table line for each stage and implement row,
    with the attempt ratio `p` of the row beside the verdict score."""
    texts = MESSAGES.roadmap
    if report.verdict_error is not None:
        return ["", texts.grades_verdicts_error.format(reason=report.verdict_error)]
    if report.verdict_bot is None:
        return ["", texts.grades_verdicts_unread]
    header = [
        texts.grades_column_job,
        texts.grades_column_repo,
        texts.grades_column_ratio,
        texts.grades_column_pulls,
        texts.grades_column_open,
        texts.grades_column_unscored,
        texts.grades_column_mergeable,
        texts.grades_column_needs_fix,
        texts.grades_column_discard_plan,
        texts.grades_column_discard_implementation,
        texts.grades_column_issue_changed,
        texts.grades_column_score,
    ]
    rows = [
        [
            row.job,
            row.repo or texts.grades_none,
            _ratio_text(row.measure.ratio),
            str(row.verdicts.pulls),
            str(row.verdicts.open),
            str(row.verdicts.unscored),
            *(_verdict_cell(row.verdicts, verdict) for verdict in Verdict),
            _ratio_text(row.verdicts.score),
        ]
        for row in report.workflows
        if row.verdicts is not None
    ]
    title = texts.grades_verdicts_title.format(
        bot=report.verdict_bot, window=report.window, partial=report.verdict_partial_score
    )
    return ["", title, "", *_table([header, *rows])]


__all__ = [
    "ITEM_FIELDS",
    "RESULT_LINES",
    "RESULT_LINE_SELECTOR",
    "TREND_WINDOWS",
    "ClassCount",
    "Efficiency",
    "GradeQuery",
    "GradeQueryKind",
    "GradeReport",
    "GradeSignal",
    "GradeWindow",
    "VerdictRead",
    "VersionGrade",
    "WindowGrade",
    "WorkflowGrade",
    "build_grade_report",
    "count_label",
    "grade_report",
    "plan_grade_queries",
    "plan_verdict_search",
    "render_grade_report",
]
