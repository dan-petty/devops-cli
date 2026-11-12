"""Each roadmap job logs one result line for each attempt, with counts and fixed names only, so a
Loki query gives the success ratio of the job (#4845)."""

from __future__ import annotations

import logging

import pytest

from devops_cli import __version__
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.intake.intake import CandidateResult
from devops_cli.roadmap.job_result import SUCCESS_RESULTS, RoadmapJob, log_job_result
from devops_cli.roadmap.refine.refine import NextStep
from devops_cli.roadmap.stage.stage import StageResult
from devops_cli.roadmap.stores.store import ImplementResult, JudgeVerdict, Verdict
from tests.support.roadmap_job_result import result_lines

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
        f"class=provider infra=true plan_calls=2 gate_returns=1 tokens=900 version={__version__}"
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
        f"class=none infra=false other=0 reason=other version={__version__}"
    ]


def test_each_intended_result_is_a_result_of_its_job() -> None:
    results = {
        RoadmapJob.STAGE: {result.value for result in StageResult},
        RoadmapJob.IMPLEMENT: {result.value for result in ImplementResult},
        RoadmapJob.REFINE: {step.value for step in NextStep},
        RoadmapJob.REFINE_JUDGE: {verdict.value for verdict in JudgeVerdict},
        RoadmapJob.ALTERNATIVES: {verdict.value for verdict in Verdict},
        RoadmapJob.INTAKE: {result.value for result in CandidateResult},
    }

    assert {job: SUCCESS_RESULTS[job] <= results[job] for job in RoadmapJob} == dict.fromkeys(
        RoadmapJob, True
    )
