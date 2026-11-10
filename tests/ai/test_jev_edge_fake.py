"""The Jev edge fake answers as the `/v1/systemone` endpoint does (#4298): the real
`SystemOneModel` validates every answer, so an answer the endpoint would not send fails here."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, cast

import httpx2
import pytest
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError
from pydantic_ai.models.decision import (
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionRequest,
    DecisionResponse,
    NoulAnswer,
    NoulQuestion,
    ScoreAnswer,
    ScoreQuestion,
)

if TYPE_CHECKING:
    from tests.support.fakes.jev import JevFake

REQUEST = DecisionRequest(
    state={"title": "Cache embeddings"},
    questions={
        "kind": ChoiceQuestion(
            instructions="Which kind?", criteria={"type/bug": "A defect.", "type/docs": "A guide."}
        ),
        "size": ScoreQuestion(instructions="How big?", criteria=["small", "medium", "large"]),
        "same": NoulQuestion(instructions="The same change?"),
    },
)


def _decide(jev: JevFake) -> DecisionResponse:
    return asyncio.run(jev.model.decide(REQUEST, {}))


def test_every_kind_of_question_gets_an_answer_the_library_accepts(jev: JevFake) -> None:
    jev.picks = {"kind": "type/docs", "size": 2, "same": 0.95}

    answers = _decide(jev).answers

    assert answers["kind"] == ChoiceAnswer(
        choice="type/docs", confidence=0.9, probabilities={"type/bug": 0.1, "type/docs": 0.9}
    )
    assert cast(ScoreAnswer, answers["size"]).score > 1.5
    assert answers["same"] == NoulAnswer(noul=0.95)
    assert jev.asked == [["kind", "size", "same"]]


def test_a_question_with_no_pick_gets_the_first_option_the_lowest_level_and_a_clear_no(
    jev: JevFake,
) -> None:
    kind, size, same = _decide(jev).answers.values()

    assert (cast(ChoiceAnswer, kind).choice, round(cast(ScoreAnswer, size).score)) == (
        "type/bug",
        0,
    )
    assert same == NoulAnswer(noul=0.02)


def test_a_status_the_test_sets_is_the_http_error_of_the_library(jev: JevFake) -> None:
    jev.fail(503)

    with pytest.raises(ModelHTTPError) as raised:
        _decide(jev)

    assert raised.value.status_code == 503


def test_a_transport_error_the_test_sets_is_a_model_api_error(jev: JevFake) -> None:
    jev.unreachable(httpx2.ConnectError("no route"))

    with pytest.raises(ModelAPIError) as raised:
        _decide(jev)

    assert "no route" in str(raised.value)
