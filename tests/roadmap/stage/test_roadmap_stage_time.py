"""The CI job-time premise of the stage job (#4026)."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import cast

import pytest

from devops_cli.ci.job_time import JobTimeReport
from devops_cli.exceptions import GitHubOperationError
from devops_cli.github.client import JobRunTime
from devops_cli.roadmap.stage.stage import FalsePremise, _plan_each, _time_premise_of
from devops_cli.roadmap.stage.stage_time import (
    JobTimePremise,
    job_time_failure,
    job_time_premise,
)

REPO = "dan-petty/devops-cli"
_BODY = (
    "Keep the checks fast.\n\n## Acceptance criteria\n\n"
    "- [ ] The `Tests & Coverage` average job duration stays under 300 s.\n"
)


def _report(*seconds: float, limit: float = 300) -> JobTimeReport:
    runs = tuple(JobRunTime(run_id=index, seconds=value) for index, value in enumerate(seconds))
    return JobTimeReport("Tests & Coverage", len(runs), limit, runs)


def test_the_limit_is_read_from_the_item_body() -> None:
    assert job_time_premise(_BODY) == JobTimePremise("Tests & Coverage", 300)


def test_a_body_with_no_limit_needs_no_job_time_read() -> None:
    assert job_time_premise("The job drops the last comment.") is None


def test_a_mean_over_the_limit_is_a_failure_naming_the_evidence() -> None:
    failure = job_time_failure(JobTimePremise("Tests & Coverage", 300), _report(328, 328))

    assert failure is not None
    assert ("Tests & Coverage" in failure, "328" in failure, "300" in failure) == (
        True,
        True,
        True,
    )


def test_a_mean_equal_to_the_limit_passes() -> None:
    assert job_time_failure(JobTimePremise("Tests & Coverage", 300), _report(300, 300)) is None


class _Planner:
    """The two calls of `_plan_each` that run before a plan: a timed premise must skip the plan."""

    def __init__(self) -> None:
        self.calls = 0
        self.refused_problems: tuple[str, ...] = ()
        self.stopped_by_checks = False

    def plan(self, target: object) -> object:
        self.calls += 1
        raise AssertionError("the planner ran for an item whose premise failed")

    def note_attempt(self, number: int, seconds: float) -> None:
        pass


def _target() -> object:
    item = SimpleNamespace(number=1, title="fix(roadmap): the item", body=_BODY)
    return SimpleNamespace(item=item, type_="fix", slug="the-item")


def test_a_failed_premise_skips_the_planner_and_returns_the_item() -> None:
    target = _target()
    planner = _Planner()
    premise = FalsePremise(target, ("`Tests & Coverage` averages 328 s and the limit is 300 s.",))

    _, _, _, _, premises = _plan_each(planner, [target], time_premise=lambda _: premise)

    assert (planner.calls, premises) == (0, [premise])


def test_a_job_time_read_error_is_a_ci_infra_failure() -> None:
    target = _target()
    planner = _Planner()

    def failing(_: object) -> object:
        raise GitHubOperationError("the GitHub read failed")

    _, _, failed, _, premises = _plan_each(planner, [target], time_premise=failing)

    assert (planner.calls, premises) == (0, [])
    (failure,) = failed
    assert failure.failure_class == "ci_infra"


def _body_target(body: str) -> object:
    item = SimpleNamespace(number=1, title="fix(roadmap): the item", body=body)
    return SimpleNamespace(item=item, type_="fix", slug="the-item")


def test_the_rule_is_absent_without_a_repository() -> None:
    assert _time_premise_of(None) is None


def test_a_body_with_no_limit_makes_no_read(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    monkeypatch.setattr(
        "devops_cli.ci.job_time.check_job_time", lambda *args, **kwargs: calls.append(1)
    )

    premise_of = _time_premise_of(REPO)
    assert premise_of is not None
    assert premise_of(_body_target("The job drops the last comment.")) is None
    assert calls == []


def test_a_mean_over_the_limit_returns_the_item(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Session:
        client = object()

    monkeypatch.setattr("devops_cli.github.session.get_github_session", lambda: _Session())
    monkeypatch.setattr(
        "devops_cli.ci.job_time.check_job_time", lambda *args, **kwargs: _report(328, 328)
    )

    premise_of = _time_premise_of(REPO)
    assert premise_of is not None
    result = premise_of(_body_target(_BODY))

    assert isinstance(result, FalsePremise)
    assert "328" in result.evidence[0]


def test_a_failed_read_is_retried_once(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Session:
        client = object()

    calls: list[int] = []

    def flaky(*args: object, **kwargs: object) -> JobTimeReport:
        calls.append(1)
        if len(calls) == 1:
            raise GitHubOperationError("the first read failed")
        return _report(300, 300)

    monkeypatch.setattr("devops_cli.github.session.get_github_session", lambda: _Session())
    monkeypatch.setattr("devops_cli.ci.job_time.check_job_time", flaky)

    premise_of = _time_premise_of(REPO)
    assert premise_of is not None
    assert premise_of(_body_target(_BODY)) is None
    assert calls == [1, 1]


def test_a_read_that_fails_twice_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Session:
        client = object()

    def failing(*args: object, **kwargs: object) -> JobTimeReport:
        raise GitHubOperationError("the read failed")

    monkeypatch.setattr("devops_cli.github.session.get_github_session", lambda: _Session())
    monkeypatch.setattr("devops_cli.ci.job_time.check_job_time", failing)

    premise_of = cast("Callable[[object], FalsePremise | None]", _time_premise_of(REPO))
    with pytest.raises(GitHubOperationError, match="the read failed"):
        premise_of(_body_target(_BODY))
