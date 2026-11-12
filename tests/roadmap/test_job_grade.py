"""The job grade of a roadmap workflow from the counts of its attempts (#5165).

The grade is the floor of the success ratio `p` of the attempts that are no infrastructure cut,
`100` when every attempt is a first pass, and `too few` under 30 attempts. The report also gives
the point grade, the Wilson 95% interval of `p` and the grades that the interval spans.
"""

from __future__ import annotations

import pytest

from devops_cli.roadmap.job_grade import (
    GRADE_POLICIES,
    EfficiencyWork,
    GradeMeasure,
    JobGrade,
    grade_policy,
    measure_grade,
    render_grade_table,
    sync_grade_table,
)


def test_22_of_25_attempts_give_point_grade_80_with_range_70_to_90() -> None:
    """22 successes of 25 attempts give p 0.88, the interval [0.70, 0.96], the point grade 80
    and the range 70 to 90, and the grade `too few`, because 25 attempts are under 30."""
    assert measure_grade(attempts=25, successes=22, first_pass=None) == GradeMeasure(
        attempts=25,
        successes=22,
        first_pass=None,
        ratio=0.88,
        lower=0.7004,
        upper=0.9583,
        point_grade=JobGrade.ACCEPTABLE,
        grade=JobGrade.TOO_FEW,
        range_low=JobGrade.DEGRADED,
        range_high=JobGrade.WELL,
    )


def test_29_attempts_are_too_few_for_a_grade() -> None:
    """29 attempts, all of them first-pass successes, give no grade."""
    measure = measure_grade(attempts=29, successes=29, first_pass=29)

    assert (measure.point_grade, measure.grade) == (JobGrade.CHECK_MEASURE, JobGrade.TOO_FEW)


def test_30_first_pass_attempts_of_30_give_grade_100() -> None:
    """30 attempts that are all first-pass successes give the grade `100`."""
    assert measure_grade(attempts=30, successes=30, first_pass=30).grade == JobGrade.CHECK_MEASURE


def test_all_successes_with_a_fix_round_give_grade_90() -> None:
    """30 successes of 30 with one fix round are not `100`: the floor of p 1.00 is 90."""
    assert measure_grade(attempts=30, successes=30, first_pass=29).grade == JobGrade.WELL


def test_all_successes_with_no_first_pass_count_give_grade_90() -> None:
    """A job whose line has no count of fix rounds gets no `100`: its first pass is unknown."""
    assert measure_grade(attempts=30, successes=30, first_pass=None).grade == JobGrade.WELL


@pytest.mark.parametrize(
    ("successes", "grade"),
    [
        (27, JobGrade.WELL),
        (26, JobGrade.ACCEPTABLE),
        (24, JobGrade.ACCEPTABLE),
        (23, JobGrade.DEGRADED),
        (21, JobGrade.DEGRADED),
        (18, JobGrade.INEFFECTIVE),
        (17, JobGrade.COIN_FLIP),
        (0, JobGrade.COIN_FLIP),
    ],
)
def test_the_grade_is_the_floor_of_the_ratio(successes: int, grade: JobGrade) -> None:
    """With 30 attempts, a ratio at a floor gets the grade of that floor: 27 of 30 is 0.90."""
    assert measure_grade(attempts=30, successes=successes, first_pass=0).grade == grade


def test_no_attempt_gives_no_ratio_and_no_interval() -> None:
    """A workflow with no attempt in the window has no ratio, no interval and no point grade."""
    assert measure_grade(attempts=0, successes=0, first_pass=None) == GradeMeasure(
        attempts=0,
        successes=0,
        first_pass=None,
        ratio=None,
        lower=None,
        upper=None,
        point_grade=None,
        grade=JobGrade.TOO_FEW,
        range_low=None,
        range_high=None,
    )


def test_efficiency_work_starts_at_grade_80() -> None:
    """The grades 100, 90 and 80 optimize efficiency; the others report it only."""
    assert {policy.grade: policy.efficiency for policy in GRADE_POLICIES} == {
        JobGrade.CHECK_MEASURE: EfficiencyWork.OPTIMIZE,
        JobGrade.WELL: EfficiencyWork.OPTIMIZE,
        JobGrade.ACCEPTABLE: EfficiencyWork.OPTIMIZE,
        JobGrade.DEGRADED: EfficiencyWork.REPORT_ONLY,
        JobGrade.INEFFECTIVE: EfficiencyWork.REPORT_ONLY,
        JobGrade.COIN_FLIP: EfficiencyWork.REPORT_ONLY,
        JobGrade.TOO_FEW: EfficiencyWork.REPORT_ONLY,
    }


def test_each_grade_has_one_action() -> None:
    """The action of the grade `<60` is the owner action: re-architect the workflow."""
    assert grade_policy(JobGrade.COIN_FLIP).action == "Re-architect the workflow."


def test_the_page_gets_the_grade_table_between_its_markers() -> None:
    """The sync puts the table of the code between the markers and keeps the text around them."""
    page = "# Title\n\n<!-- JOB_GRADES_START -->\nold table\n<!-- JOB_GRADES_END -->\n\nEnd.\n"

    assert sync_grade_table(page) == (
        "# Title\n\n<!-- JOB_GRADES_START -->\n\n"
        f"{render_grade_table()}\n\n<!-- JOB_GRADES_END -->\n\nEnd.\n"
    )


def test_a_page_with_no_markers_gets_no_table() -> None:
    """A page with no markers is left alone."""
    assert sync_grade_table("# Title\n") is None
