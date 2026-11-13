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
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from devops_cli.github.repo_ref import RepoRef
from devops_cli.k8s.logql import query_loki_metrics
from devops_cli.lang import MESSAGES
from devops_cli.models.prometheus import PrometheusQueryResult
from devops_cli.roadmap.job_grade import (
    EfficiencyWork,
    GradeMeasure,
    GradeWindow,
    grade_policy,
    measure_grade,
    share,
)
from devops_cli.roadmap.job_result import FIRST_PASS_LIMITS, LINE_PREFIX, CountLimit, RoadmapJob


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


class GradeReport(BaseModel):
    """The job grade report of one window."""

    model_config = ConfigDict(frozen=True)

    window: GradeWindow = Field(description="The window of the grade")
    repo: str | None = Field(description="The repository of `--repo`; None for all")
    loki_url: str = Field(description="The Loki that the queries read")
    workflows: list[WorkflowGrade] = Field(description="One row for each workflow and repository")


def _lines(repo: RepoRef | None) -> str:
    """The log pipeline of the result lines, with the fields as labels."""
    pipeline = f"{RESULT_LINES} | regexp `{_FIELDS}`"
    if repo is not None:
        pipeline += f" | repo=~`(?i){re.escape(repo.display)}`"
    return pipeline


def _count_label(count: str) -> str:
    return f"| regexp ` {count}=(?P<{count}>[0-9]+) `"


def _query(kind: GradeQueryKind, window: GradeWindow, repo: RepoRef | None) -> GradeQuery:
    lines = _lines(repo)
    match kind:
        case GradeQueryKind.COUNTS:
            expr = f"sum by ({_KEY}, version, success, infra) (count_over_time({lines} [{window}]))"
        case GradeQueryKind.CLASSES:
            expr = (
                f"sum by ({_KEY}, failure_class) "
                f'(count_over_time({lines} | success="false" | infra="false" [{window}]))'
            )
        case GradeQueryKind.FIRST_PASSES:
            counts = " ".join(_count_label(count) for count in _FIRST_PASS_COUNTS)
            expr = (
                f"sum by ({_KEY}, {', '.join(_FIRST_PASS_COUNTS)}) "
                f'(count_over_time({lines} | success="true" | infra="false" {counts} [{window}]))'
            )
        case _:
            count, template = _EFFICIENCY[kind]
            unwrapped = f'{lines} |~ " {count}=[0-9]+ " {_count_label(count)} | unwrap {count}'
            expr = template.format(lines=unwrapped, window=window, key=_KEY)
    return GradeQuery(kind, window, expr)


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
class _Answers:
    """The parsed answers of the queries of one report."""

    window: GradeWindow
    counts: Mapping[GradeWindow, dict[_Key, _Counts]]
    versions: dict[_Key, dict[str, _Counts]]
    classes: dict[_Key, list[ClassCount]]
    first_passes: Counter[_Key]
    efficiency: Mapping[GradeQueryKind, dict[_Key, float]]


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
    )


def _workflow(key: _Key, parsed: _Answers) -> WorkflowGrade:
    job, repo = key
    counts = parsed.counts[parsed.window].get(key, _Counts())
    first_pass = parsed.first_passes[key] if _first_pass_limits(job) else None
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
            )
            for version, version_counts in sorted(parsed.versions.get(key, {}).items())
            if version_counts.attempts >= _MIN_VERSION_ATTEMPTS
        ],
        trend=[_window_grade(at, trend[at]) for at in TREND_WINDOWS],
        signals=_signals(trend),
    )


def _job_order(job: str) -> tuple[int, str]:
    """The jobs in the order of `RoadmapJob`, then a name that is no job."""
    jobs = list(RoadmapJob)
    return (jobs.index(RoadmapJob(job)), job) if job in RoadmapJob else (len(jobs), job)


def _row_keys(parsed: _Answers, repo: RepoRef | None) -> list[_Key]:
    """Each workflow and repository with a line in a window, and one row with no repository (or
    with `--repo`) for each job that has no line."""
    seen = {key for window_counts in parsed.counts.values() for key in window_counts}
    jobs = {job for job, _ in seen}
    empty = repo.display if repo is not None else None
    seen |= {(job.value, empty) for job in RoadmapJob if job.value not in jobs}
    return sorted(seen, key=lambda key: (_job_order(key[0]), key[1] or ""))


def build_grade_report(
    window: GradeWindow,
    repo: RepoRef | None,
    loki_url: str,
    answers: Mapping[str, PrometheusQueryResult],
) -> GradeReport:
    """The report from the answer of each planned query, by the key of the query."""
    parsed = _parse(window, answers)
    return GradeReport(
        window=window,
        repo=repo.display if repo is not None else None,
        loki_url=loki_url,
        workflows=[_workflow(key, parsed) for key in _row_keys(parsed, repo)],
    )


def grade_report(window: GradeWindow, repo: RepoRef | None, loki_url: str) -> GradeReport:
    """Send the planned queries to Loki and build the report."""
    queries = plan_grade_queries(window, repo)
    answers = query_loki_metrics([query.expr for query in queries], loki_url)
    return build_grade_report(
        window,
        repo,
        loki_url,
        {query.key: answer for query, answer in zip(queries, answers, strict=True)},
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
    lines += [
        texts.grades_version.format(
            version=version.version,
            successes=version.measure.successes,
            attempts=version.measure.attempts,
            ratio=_ratio_text(version.measure.ratio),
            interval=_interval_text(version.measure),
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
    return "\n".join(lines) + "\n"


__all__ = [
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
    "VersionGrade",
    "WindowGrade",
    "WorkflowGrade",
    "build_grade_report",
    "grade_report",
    "plan_grade_queries",
    "render_grade_report",
]
