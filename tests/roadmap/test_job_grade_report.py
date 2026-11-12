"""The job grade report reads the result lines in Loki with metric queries (#5165).

The recorded replies of `tests/fixtures/roadmap/job_grades/replies.json` hold a hand count: the
expected rows below repeat that count, so the report equals it.
"""

from __future__ import annotations

import httpx2
import pytest
from syrupy.assertion import SnapshotAssertion

from devops_cli.exceptions.k8s import KubernetesLoggingError
from devops_cli.github.repo_ref import RepoRef
from devops_cli.roadmap.job_grade import EfficiencyWork, JobGrade, grade_policy, measure_grade
from devops_cli.roadmap.job_grade_report import (
    ClassCount,
    Efficiency,
    GradeReport,
    GradeSignal,
    GradeWindow,
    VersionGrade,
    WindowGrade,
    WorkflowGrade,
    grade_report,
    plan_grade_queries,
    render_grade_report,
)
from tests.support.fakes.http import WebFake
from tests.support.roadmap_job_grades import LOKI_URL, QUERY_PATH, serve_grade_replies


def _row(report: GradeReport, job: str, repo: str | None) -> WorkflowGrade:
    return next(row for row in report.workflows if (row.job, row.repo) == (job, repo))


def _no_trend() -> list[WindowGrade]:
    return [
        WindowGrade(
            window=window,
            measure=measure_grade(attempts=0, successes=0, first_pass=None),
            all_attempts=0,
            infra_share=None,
        )
        for window in (GradeWindow.H24, GradeWindow.H6)
    ]


def test_each_workflow_and_repository_gets_one_row(web: WebFake) -> None:
    """Each job gets a row for each repository with lines, in the order of the jobs, and a job
    with no line gets one row with no repository."""
    serve_grade_replies(web)

    report = grade_report(GradeWindow.D7, None, LOKI_URL)

    assert [(row.job, row.repo) for row in report.workflows] == [
        ("stage", "example/app"),
        ("stage", "example/infra"),
        ("implement", "example/app"),
        ("refine", "example/app"),
        ("refine_judge", None),
        ("alternatives", None),
        ("intake", "example/app"),
        ("fix_plan", None),
    ]


def test_the_refine_row_equals_the_hand_count(web: WebFake) -> None:
    """22 successes of 25 attempts with no infrastructure cut, and 1 cut: p 0.88, the interval
    [0.70, 0.96], the point grade 80 in the range 70 to 90, and `too few`. The cut changes the
    infrastructure share and not p. 3 of 10 attempts in 24 h are cuts: the infrastructure
    signal."""
    serve_grade_replies(web)

    report = grade_report(GradeWindow.D7, None, LOKI_URL)

    assert _row(report, "refine", "example/app") == WorkflowGrade(
        job="refine",
        repo="example/app",
        measure=measure_grade(attempts=25, successes=22, first_pass=None),
        all_attempts=26,
        all_ratio=0.8462,
        infra_attempts=1,
        infra_share=0.0385,
        first_pass_ratio=None,
        top_classes=[
            ClassCount(failure_class="none", attempts=2),
            ClassCount(failure_class="head_moved", attempts=1),
        ],
        action=grade_policy(JobGrade.TOO_FEW).action,
        efficiency=None,
        versions=[
            VersionGrade(
                version="0.120.0", measure=measure_grade(attempts=25, successes=22, first_pass=None)
            )
        ],
        trend=[
            WindowGrade(
                window=GradeWindow.H24,
                measure=measure_grade(attempts=7, successes=6, first_pass=None),
                all_attempts=10,
                infra_share=0.3,
            ),
            WindowGrade(
                window=GradeWindow.H6,
                measure=measure_grade(attempts=0, successes=0, first_pass=None),
                all_attempts=0,
                infra_share=None,
            ),
        ],
        signals=[GradeSignal.INFRA],
    )


def test_the_intake_row_gets_a_grade_and_the_broken_signal(web: WebFake) -> None:
    """25 successes of 41 attempts give the grade 60. The top 3 classes are the largest, a tie
    in the order of the names. Only a version with 10 attempts or more gets a row. 5 attempts
    with no success in 6 h are the broken signal."""
    serve_grade_replies(web)

    report = grade_report(GradeWindow.D7, None, LOKI_URL)

    assert _row(report, "intake", "example/app") == WorkflowGrade(
        job="intake",
        repo="example/app",
        measure=measure_grade(attempts=41, successes=25, first_pass=None),
        all_attempts=41,
        all_ratio=0.6098,
        infra_attempts=0,
        infra_share=0.0,
        first_pass_ratio=None,
        top_classes=[
            ClassCount(failure_class="head_moved", attempts=12),
            ClassCount(failure_class="concurrency", attempts=2),
            ClassCount(failure_class="parser", attempts=1),
        ],
        action=grade_policy(JobGrade.INEFFECTIVE).action,
        efficiency=None,
        versions=[
            VersionGrade(
                version="0.118.0", measure=measure_grade(attempts=34, successes=20, first_pass=None)
            )
        ],
        trend=[
            WindowGrade(
                window=GradeWindow.H24,
                measure=measure_grade(attempts=0, successes=0, first_pass=None),
                all_attempts=0,
                infra_share=None,
            ),
            WindowGrade(
                window=GradeWindow.H6,
                measure=measure_grade(attempts=5, successes=0, first_pass=None),
                all_attempts=5,
                infra_share=0.0,
            ),
        ],
        signals=[GradeSignal.BROKEN],
    )
    assert _row(report, "intake", "example/app").measure.grade == JobGrade.INEFFECTIVE


def test_the_stage_row_counts_first_passes_and_efficiency(web: WebFake) -> None:
    """1 of the 2 staged items had no fix round. Tokens and seconds for each success are the
    sums of all attempts over the 2 successes."""
    serve_grade_replies(web)

    report = grade_report(GradeWindow.D7, None, LOKI_URL)

    assert _row(report, "stage", "example/app") == WorkflowGrade(
        job="stage",
        repo="example/app",
        measure=measure_grade(attempts=3, successes=2, first_pass=1),
        all_attempts=3,
        all_ratio=0.6667,
        infra_attempts=0,
        infra_share=0.0,
        first_pass_ratio=0.3333,
        top_classes=[ClassCount(failure_class="plan_defect", attempts=1)],
        action=grade_policy(JobGrade.TOO_FEW).action,
        efficiency=Efficiency(
            tokens_p50=70000.0,
            tokens_p90=2100000.4,
            tokens_max=2400000.0,
            tokens_per_success=1250000.0,
            seconds_p50=600.0,
            seconds_p90=1500.0,
            seconds_max=1800.0,
            seconds_per_success=1350.0,
            work=EfficiencyWork.REPORT_ONLY,
        ),
        versions=[],
        trend=_no_trend(),
        signals=[],
    )


def test_a_workflow_with_only_infrastructure_cuts_has_no_ratio(web: WebFake) -> None:
    """An attempt that an infrastructure cut ended counts in the share and not in p."""
    serve_grade_replies(web)

    row = _row(grade_report(GradeWindow.D7, None, LOKI_URL), "stage", "example/infra")

    assert (row.measure, row.all_attempts, row.infra_share, row.first_pass_ratio) == (
        measure_grade(attempts=0, successes=0, first_pass=0),
        1,
        1.0,
        None,
    )


def test_a_job_with_no_line_has_no_ratio(web: WebFake) -> None:
    """A job that wrote no line in the window gets `too few`, no ratio and no efficiency."""
    serve_grade_replies(web)

    row = _row(grade_report(GradeWindow.D7, None, LOKI_URL), "refine_judge", None)

    assert row == WorkflowGrade(
        job="refine_judge",
        repo=None,
        measure=measure_grade(attempts=0, successes=0, first_pass=None),
        all_attempts=0,
        all_ratio=None,
        infra_attempts=0,
        infra_share=None,
        first_pass_ratio=None,
        top_classes=[],
        action=grade_policy(JobGrade.TOO_FEW).action,
        efficiency=None,
        versions=[],
        trend=_no_trend(),
        signals=[],
    )


def test_the_report_sends_one_request_for_each_planned_query(web: WebFake) -> None:
    """The report sends each planned query once to the instant query of Loki."""
    serve_grade_replies(web)

    grade_report(GradeWindow.D7, None, LOKI_URL)

    assert [
        (request.url.split("?")[0], httpx2.URL(request.url).params["query"])
        for request in web.recorded
    ] == [(f"{LOKI_URL}{QUERY_PATH}", query.expr) for query in plan_grade_queries(GradeWindow.D7)]


def test_a_trend_window_that_is_the_report_window_is_queried_once() -> None:
    """With the 24-hour window, the counts of 24 h serve the report and the trend."""
    assert [query.key for query in plan_grade_queries(GradeWindow.H24)] == [
        "counts@24h",
        "classes@24h",
        "first_pass@24h",
        "tokens_p50@24h",
        "tokens_p90@24h",
        "tokens_max@24h",
        "tokens_sum@24h",
        "seconds_p50@24h",
        "seconds_p90@24h",
        "seconds_max@24h",
        "seconds_sum@24h",
        "counts@6h",
    ]


def test_a_repository_filter_reaches_each_query() -> None:
    """`--repo` puts a case-insensitive match of the repository, its dots escaped, in each query."""
    queries = plan_grade_queries(GradeWindow.D7, RepoRef("example/my.app"))

    assert [
        query.key for query in queries if "| repo=~`(?i)example/my\\.app`" not in query.expr
    ] == []


def test_a_refused_query_raises_the_loki_error(web: WebFake) -> None:
    """A query that Loki refuses stops the report with the status of the reply."""
    web.serve(lambda _request: httpx2.Response(400, text="parse error at line 1"))

    with pytest.raises(KubernetesLoggingError) as raised:
        grade_report(GradeWindow.D7, None, LOKI_URL)

    assert (raised.value.status_code, raised.value.exit_code) == (400, 1)


def test_an_unreachable_loki_raises_the_loki_error(web: WebFake) -> None:
    """A Loki that refuses the connection stops the report with no status."""

    def refuse(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("Connection refused", request=request)

    web.serve(refuse)

    with pytest.raises(KubernetesLoggingError) as raised:
        grade_report(GradeWindow.D7, None, LOKI_URL)

    assert raised.value.status_code is None


def test_the_table_shows_each_workflow(web: WebFake, snapshot: SnapshotAssertion) -> None:
    """The table gives one line for each workflow and repository, then the classes, the
    action, the versions, the efficiency and the signals of each row with attempts."""
    serve_grade_replies(web)

    assert render_grade_report(grade_report(GradeWindow.D7, None, LOKI_URL)) == snapshot
