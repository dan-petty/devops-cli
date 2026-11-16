"""Each roadmap job logs one result line for each attempt, with counts and fixed names only, so a
Loki query gives the success ratio of the job (#4845)."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from devops_cli import __version__
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.intake.intake import CandidateResult
from devops_cli.roadmap.job_result import SUCCESS_RESULTS, RoadmapJob, log_job_result
from devops_cli.roadmap.refine.refine import NextStep
from devops_cli.roadmap.stage.stage import StageResult
from devops_cli.roadmap.steps.fix_checks import FixChecksResult
from devops_cli.roadmap.steps.fix_plan import FixPlanResult
from devops_cli.roadmap.steps.review import ReviewResult
from devops_cli.roadmap.stores.store import ImplementResult, JudgeVerdict, Verdict
from tests.support.roadmap_job_result import result_lines

RetitleResult: Any = None
try:
    from devops_cli.roadmap.retitle import RetitleResult as _RetitleResult

    RetitleResult = _RetitleResult
except ImportError:
    pass

ISSUE_TEXT = "The job drops the last comment of a thread"


def test_a_line_holds_the_job_the_item_the_result_its_class_and_counts_in_order(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        log_job_result(
            RoadmapJob.STAGE,
            "owner/repo",
            12,
            "failed",
            failure=FailureClass.PROVIDER,
            counts={"plan_calls": 2, "gate_returns": 1, "tokens": 900},
        )

    assert result_lines(caplog) == [
        "roadmap job result: job=stage repo=owner/repo item=#12 result=failed success=false "
        f"class=provider infra=true first_pass=false plan_calls=2 gate_returns=1 tokens=900 version={__version__}"
    ]


def test_an_intended_result_with_no_failure_is_a_success_and_no_infrastructure_cut(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        log_job_result(RoadmapJob.IMPLEMENT, "owner/repo", 3, "ready")
        log_job_result(RoadmapJob.IMPLEMENT, "owner/repo", 4, "stopped", failure=FailureClass.TEST)

    assert [line.split(" class=")[0].split(" result=")[1] for line in result_lines(caplog)] == [
        "ready success=true",
        "stopped success=false",
    ]
    assert [" infra=false " in line for line in result_lines(caplog)] == [True, True]


def test_a_line_holds_no_text_of_an_issue(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        log_job_result(
            RoadmapJob.ALTERNATIVES,
            ISSUE_TEXT,
            None,
            ISSUE_TEXT,
            counts={ISSUE_TEXT: -3},
            names={"reason": ISSUE_TEXT},
        )

    assert result_lines(caplog) == [
        "roadmap job result: job=alternatives repo=none item=none result=other success=false "
        f"class=none infra=false first_pass=false other=0 reason=other version={__version__}"
    ]


def test_each_intended_result_is_a_result_of_its_job() -> None:
    results: dict[RoadmapJob, set[str]] = {
        RoadmapJob.STAGE: {result.value for result in StageResult},
        RoadmapJob.IMPLEMENT: {result.value for result in ImplementResult},
        RoadmapJob.REFINE: {step.value for step in NextStep},
        RoadmapJob.REFINE_JUDGE: {verdict.value for verdict in JudgeVerdict},
        RoadmapJob.ALTERNATIVES: {verdict.value for verdict in Verdict},
        RoadmapJob.INTAKE: {result.value for result in CandidateResult},
        RoadmapJob.FIX_PLAN: {result.value for result in FixPlanResult},
        RoadmapJob.FIX_CHECKS: {result.value for result in FixChecksResult},
        RoadmapJob.REVIEW: {result.value for result in ReviewResult},
    }
    if RetitleResult is not None and hasattr(RoadmapJob, "RETITLE"):
        results[RoadmapJob.RETITLE] = {result.value for result in RetitleResult}

    assert {job: SUCCESS_RESULTS[job] <= results[job] for job in RoadmapJob} == dict.fromkeys(
        RoadmapJob, True
    )


# The next steps of refine that are no wait: the job failed (`retry`, `failed`), or refine changes
# no item (`none`). Each other next step is a wait that refine set (#6037).
REFINE_NO_WAIT = frozenset({NextStep.RETRY, NextStep.FAILED, NextStep.NONE})


def test_refine_counts_each_wait_as_a_success() -> None:
    """Each next step that is a wait is in the success set of refine, and no other next step is
    in it, so a new next step cannot be left out (#6037). `alternatives` waits on the verdict of
    the alternatives row (#2951). `edit` waits on a body edit: the body stops the design, and the
    job did not fail."""
    waits = {step.value for step in NextStep} - {step.value for step in REFINE_NO_WAIT}

    assert SUCCESS_RESULTS[RoadmapJob.REFINE] == waits


def test_a_refine_wait_on_the_alternatives_verdict_is_a_first_pass(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The first try of refine that sets the next step `alternatives` is a first pass, and a try
    that sets `retry` is a failure (#6037)."""
    with caplog.at_level(logging.INFO):
        log_job_result(RoadmapJob.REFINE, "owner/repo", 7, "alternatives", counts={"tries": 1})
        log_job_result(RoadmapJob.REFINE, "owner/repo", 8, "retry", counts={"tries": 1})

    assert [line.split(" result=")[1].split(" tries=")[0] for line in result_lines(caplog)] == [
        "alternatives success=true class=none infra=false first_pass=true",
        "retry success=false class=none infra=false first_pass=false",
    ]


def test_fix_plan_counts_only_a_pushed_repair_as_success() -> None:
    """A fix-plan attempt is a success only when it pushes a repair that its review finds better
    than the review of the head in the same attempt (#5213)."""
    results = {result.value for result in FixPlanResult}

    assert SUCCESS_RESULTS[RoadmapJob.FIX_PLAN] == {"revised", "cleared"}
    assert {"regated", "dismissed", "unchanged", "stopped", "failed"} & set(
        SUCCESS_RESULTS[RoadmapJob.FIX_PLAN]
    ) == set()
    assert SUCCESS_RESULTS[RoadmapJob.FIX_PLAN] <= results
