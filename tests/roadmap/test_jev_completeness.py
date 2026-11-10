"""The Jev completeness check of a draft pull request (#4308).

The HTTP edge is faked: the check builds the real Jev model, and the fake web answers the one
request that it posts to the gateway route `/systemone`.
"""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_JEV_CRITERION_THRESHOLD,
    CONST_ROADMAP_JEV_MAX_CRITERIA,
    CONST_ROADMAP_JEV_MAX_DIFF_TOKENS,
    CONST_ROADMAP_JEV_MIN_TEST_SCORE,
)
from devops_cli.config.settings import Settings
from devops_cli.roadmap.jev_completeness import (
    CompletenessOutcome,
    check_completeness,
    completeness_note,
)
from devops_cli.telemetry.instruments import ROADMAP_JEV_COMPLETENESS_TOTAL
from tests.support.fakes.http import WebFake

GATEWAY = "http://example.com:4000/v1"
ROUTE = f"{GATEWAY}/systemone"
CRITERIA = ["The job keeps every comment.", "A test shows it."]
DIFF = "diff --git a/tasks.md b/tasks.md\n+- [ ] 1.1 Keep every comment\n"


def _settings() -> Settings:
    settings = Settings()
    settings.ai.provider = "gateway"
    settings.ai.gateway_url = GATEWAY
    return settings


@pytest.fixture(autouse=True)
def _gateway_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from devops_cli.ai import pydantic_ai_bridge

    monkeypatch.setattr(pydantic_ai_bridge, "get_ai_api_key", lambda _s: "sk-test")


@pytest.fixture
def counted(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, float]]:
    """The `(outcome, value)` pairs that the check sends to the counter."""
    sent: list[tuple[str, float]] = []

    def fake_emit(instrument: Any, value: float, attributes: dict[str, Any] | None = None) -> None:
        assert instrument is ROADMAP_JEV_COMPLETENESS_TOTAL
        sent.append((str((attributes or {})["outcome"]), value))

    monkeypatch.setattr("devops_cli.roadmap.jev_completeness.emit", fake_emit)
    return sent


def _answer(probabilities: list[float], test_score: float = 2.0) -> dict[str, Any]:
    """Jev's answer: one Noul value for each criterion and the score of the tests."""
    answers: dict[str, Any] = {
        f"criterion_{number}": {"type": "noul", "noul": value, "confidence": 0.9}
        for number, value in enumerate(probabilities, start=1)
    }
    levels = {str(level): 0.0 for level in range(4)}
    levels[str(round(test_score))] = 1.0
    answers["tests"] = {
        "type": "score",
        "score": float(round(test_score)),
        "probabilities": levels,
        "confidence": 0.9,
    }
    return {
        "model": "typesafe/jev-1.14",
        "answers": answers,
        "usage": {"input_tokens": 100, "output_tokens": len(answers)},
    }


def test_one_request_holds_a_noul_question_per_criterion_and_one_score_question(
    web: WebFake,
) -> None:
    web.respond("POST", ROUTE, 200, _answer([0.9, 0.8]))

    result = check_completeness(CRITERIA, DIFF, "plan", settings=_settings())

    body = web.recorded[0].json
    assert (len(web.recorded), result.outcome) == (1, CompletenessOutcome.PASSED)
    assert {name: question["type"] for name, question in body["questions"].items()} == {
        "criterion_1": "noul",
        "criterion_2": "noul",
        "tests": "score",
    }
    assert CRITERIA[0] in body["questions"]["criterion_1"]["instructions"]
    assert body["state"]["diff"] == DIFF
    assert body["state"]["criteria"] == {"criterion_1": CRITERIA[0], "criterion_2": CRITERIA[1]}


def test_a_probability_below_the_threshold_holds_the_draft_and_names_the_criterion(
    web: WebFake, counted: list[tuple[str, float]]
) -> None:
    low = CONST_ROADMAP_JEV_CRITERION_THRESHOLD - 0.3
    web.respond("POST", ROUTE, 200, _answer([0.95, low]))

    result = check_completeness(CRITERIA, DIFF, "plan", settings=_settings())

    note = completeness_note(result, 7)
    assert (result.outcome, result.holds, [d.criterion for d in result.doubts]) == (
        CompletenessOutcome.HELD,
        True,
        [CRITERIA[1]],
    )
    assert (CRITERIA[1] in note, CRITERIA[0] in note, "#7" in note) == (True, False, True)
    assert ("held", 1) in counted


def test_a_weak_test_score_holds_the_draft_with_no_criterion_in_doubt(web: WebFake) -> None:
    web.respond("POST", ROUTE, 200, _answer([0.9, 0.9], test_score=0.0))

    result = check_completeness(CRITERIA, DIFF, "change", settings=_settings())

    assert (result.outcome, result.doubts, result.test_score) == (
        CompletenessOutcome.HELD,
        (),
        0.0,
    )
    assert CONST_ROADMAP_JEV_MIN_TEST_SCORE > 0.0
    assert "0.0 of 3" in completeness_note(result, 7)


def test_an_error_of_jev_holds_the_draft_and_is_counted(
    web: WebFake, counted: list[tuple[str, float]], caplog: pytest.LogCaptureFixture
) -> None:
    web.respond("POST", ROUTE, 500, {"error": "boom"})

    result = check_completeness(CRITERIA, DIFF, "plan", settings=_settings())

    assert (result.outcome, result.holds) == (CompletenessOutcome.ERROR, True)
    assert "Jev gave no answer" in completeness_note(result, 7)
    assert ("error", 1) in counted
    assert "got no answer" in caplog.text


def test_the_counter_sends_one_series_for_each_outcome(
    web: WebFake, counted: list[tuple[str, float]]
) -> None:
    web.respond("POST", ROUTE, 200, _answer([0.9, 0.9]))

    check_completeness(CRITERIA, DIFF, "plan", settings=_settings())

    assert sorted(counted) == [("error", 0), ("held", 0), ("passed", 1), ("skipped", 0)]


@pytest.mark.parametrize(
    ("criteria", "diff", "reason"),
    [
        ([], DIFF, "no acceptance criterion"),
        (["c"] * (CONST_ROADMAP_JEV_MAX_CRITERIA + 1), DIFF, "acceptance criteria"),
        (CRITERIA, "word " * (CONST_ROADMAP_JEV_MAX_DIFF_TOKENS + 1), "tokens"),
    ],
    ids=["no-criteria", "too-many-criteria", "diff-too-large"],
)
def test_a_check_that_cannot_run_is_skipped_with_a_logged_reason_and_no_request(
    web: WebFake,
    counted: list[tuple[str, float]],
    caplog: pytest.LogCaptureFixture,
    criteria: list[str],
    diff: str,
    reason: str,
) -> None:
    caplog.set_level("INFO")

    result = check_completeness(criteria, diff, "plan", settings=_settings())

    assert (result.outcome, result.holds, web.recorded) == (CompletenessOutcome.SKIPPED, False, [])
    assert reason in result.reason
    assert reason in caplog.text
    assert ("skipped", 1) in counted


def test_a_pass_marks_nothing_and_makes_no_request_but_the_one(web: WebFake) -> None:
    """The result is data: it holds no call that marks a pull request ready, merges or closes."""
    web.respond("POST", ROUTE, 200, _answer([0.99, 0.99], test_score=3.0))

    result = check_completeness(CRITERIA, DIFF, "plan", settings=_settings())

    assert (result.holds, [(r.method, r.url) for r in web.recorded]) == (
        False,
        [("POST", ROUTE)],
    )
