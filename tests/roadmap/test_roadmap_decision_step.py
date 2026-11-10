"""The shared parts of a decision step (ADR 0019): the bands that fitted cuts give, the request
that fails open, and the cuts as data."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.decision import DecisionRequest, NoulQuestion

from devops_cli.roadmap.decision_step import (
    Band,
    Cut,
    DecisionStepError,
    Thresholds,
    band_of,
    decide_all,
    probabilities_of,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tests.support.fakes.jev import JevFake

CUTS = {"a": Cut(continue_below=0.2, flag_at=0.8), "b": Cut(continue_below=0.4, flag_at=0.9)}


def _request(*names: str) -> DecisionRequest:
    return DecisionRequest(
        state="a short piece", questions={name: NoulQuestion(instructions=name) for name in names}
    )


@pytest.mark.parametrize(
    ("probabilities", "band"),
    [
        ({"a": 0.19, "b": 0.39}, Band.CONTINUE),
        ({"a": 0.2, "b": 0.0}, Band.REVIEW),
        ({"a": 0.0, "b": 0.4}, Band.REVIEW),
        ({"a": 0.8, "b": 0.0}, Band.FLAG),
        ({"a": 0.5, "b": 0.95}, Band.FLAG),
    ],
)
def test_the_cuts_give_the_band(probabilities: dict[str, float], band: Band) -> None:
    assert band_of(probabilities, CUTS) is band


def test_a_question_with_no_cut_or_no_answer_is_an_error() -> None:
    with pytest.raises(DecisionStepError, match="no answer"):
        band_of({"a": 0.0}, CUTS)
    with pytest.raises(DecisionStepError, match="no cut"):
        band_of({"a": 0.0, "b": 0.0, "c": 0.5}, CUTS)


def test_the_requests_are_answered_in_order_and_each_is_one_request(jev: JevFake) -> None:
    jev.picks = {"a": 0.7, "b": 0.1}

    responses = decide_all([_request("a"), _request("b"), _request("a", "b")], model=jev.model)

    assert [probabilities_of(r) for r in responses] == [
        {"a": 0.7},
        {"b": 0.1},
        {"a": 0.7, "b": 0.1},
    ]
    assert sorted(jev.asked) == [["a"], ["a", "b"], ["b"]]


def test_a_failed_request_raises_so_the_step_can_fail_open(jev: JevFake) -> None:
    jev.fail(503)

    with pytest.raises(ModelHTTPError, match="503"):
        decide_all([_request("a")], model=jev.model)


def test_the_cuts_are_data_with_their_provenance(tmp_path: Path) -> None:
    path = tmp_path / "cuts.json"
    path.write_text(
        json.dumps(
            {
                "step": "demo",
                "model": "typesafe/jev-1.14",
                "fitted": "2026-11-10",
                "cases": 56,
                "cuts": {"a": {"continue_below": 0.2, "flag_at": 0.8}},
                "report": {"skip_rate": 0.1},
            }
        ),
        encoding="utf-8",
    )

    loaded = Thresholds.load(path)

    assert (loaded.step, loaded.cases, loaded.cuts["a"]) == (
        "demo",
        56,
        Cut(continue_below=0.2, flag_at=0.8),
    )


def test_a_cut_must_leave_a_review_band() -> None:
    with pytest.raises(ValueError, match="flag_at"):
        Cut(continue_below=0.5, flag_at=0.4)
