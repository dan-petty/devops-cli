"""`devops ai ask-jev` asks TypeSafe Jev one question and prints the typed answer (#4306).

The gateway is the HTTP fake and the key of the gateway is in the keyring fake. The live check
waits for the fix of the route `POST /v1/systemone` on the gateway (#4289): these tests prove the
command against the wire shape of the System One endpoint.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest

from devops_cli.config.constants import CONST_AI_JEV_ASK_MAX_INPUT_CHARS, CONST_AI_JEV_MODEL
from tests.support.fakes.http import WebFake
from tests.support.fakes.keyring import FakeKeyring

_GATEWAY = "http://127.0.0.1:4000/v1"
_URL = "http://127.0.0.1:4000/v1/systemone"
_KEY = "gateway-secret-key"


def _reply(
    answer: dict[str, Any], input_tokens: int = 61, output_tokens: int = 3
) -> dict[str, Any]:
    """A System One reply that holds the one answer."""
    return {
        "model": CONST_AI_JEV_MODEL,
        "answers": {"answer": answer},
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }


@pytest.fixture
def jev(config: Callable[..., Path], keyring_store: FakeKeyring, web: WebFake) -> WebFake:
    """The gateway with a System One route, and its key in the credential store."""
    config(ai={"provider": "gateway", "gateway_url": _GATEWAY})
    keyring_store.set_password("devops-cli", "ai_api_key", _KEY)
    return web


def test_a_choice_prints_the_option_with_its_probability_and_the_tokens(
    cli: Callable[..., Any], jev: WebFake
) -> None:
    jev.respond(
        "POST",
        _URL,
        200,
        _reply(
            {
                "type": "choice",
                "choice": "bug",
                "probabilities": {"bug": 0.91, "idea": 0.09},
                "confidence": 0.9,
            }
        ),
    )

    result = cli(
        "ai",
        "ask-jev",
        "choice",
        "Which label fits?",
        "--context",
        "The command crashes on start.",
        "--option",
        "bug=A defect",
        "--option",
        "idea=A proposal",
    )

    assert result.exit_code == 0
    assert "Answer: bug" in result.output
    assert "Probability: 0.91" in result.output
    assert "Tokens: 61 in, 3 out" in result.output
    assert "evidence, not a verdict" in result.output
    assert _KEY not in result.output


def test_the_request_holds_the_state_the_question_and_the_options(
    cli: Callable[..., Any], jev: WebFake
) -> None:
    jev.respond(
        "POST",
        _URL,
        200,
        _reply(
            {
                "type": "choice",
                "choice": "bug",
                "probabilities": {"bug": 0.6, "idea": 0.4},
                "confidence": 0.5,
            }
        ),
    )

    cli(
        "ai",
        "ask-jev",
        "choice",
        "Which label fits?",
        "-c",
        "The command crashes.",
        "-o",
        "bug=A defect",
        "-o",
        "idea",
    )

    (sent,) = jev.recorded
    assert sent.headers["authorization"] == f"Bearer {_KEY}"
    assert sent.json["state"] == "The command crashes."
    assert sent.json["questions"]["answer"] == {
        "type": "choice",
        "instructions": "Which label fits?",
        "criteria": {"bug": "A defect", "idea": "idea"},
    }


def test_a_yes_no_question_says_yes_at_or_above_one_half_and_json_is_typed(
    cli: Callable[..., Any], jev: WebFake
) -> None:
    jev.respond("POST", _URL, 200, _reply({"type": "noul", "noul": 0.83}))

    result = cli("ai", "ask-jev", "noul", "Is this a docs-only change?", "--json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["kind"] == "noul"
    assert payload["answer"] == "yes"
    assert payload["probability"] == pytest.approx(0.83)
    assert payload["input_tokens"] == 61
    assert payload["model"] == CONST_AI_JEV_MODEL
    (sent,) = jev.recorded
    assert sent.json["state"] == "Is this a docs-only change?"


def test_a_yes_no_question_says_no_below_one_half(cli: Callable[..., Any], jev: WebFake) -> None:
    jev.respond("POST", _URL, 200, _reply({"type": "noul", "noul": 0.2}))

    result = cli("ai", "ask-jev", "noul", "Is it safe?", "--yes", "Safe", "--no", "Unsafe")

    assert "Answer: no" in result.output
    assert jev.recorded[0].json["questions"]["answer"]["criteria"] == {
        "true": "Safe",
        "false": "Unsafe",
    }


def test_a_score_prints_the_score_and_the_confidence(cli: Callable[..., Any], jev: WebFake) -> None:
    jev.respond(
        "POST",
        _URL,
        200,
        _reply(
            {
                "type": "score",
                "score": 1.7,
                "probabilities": {"0": 0.0, "1": 0.3, "2": 0.7},
                "confidence": 0.8,
            }
        ),
    )

    result = cli(
        "ai",
        "ask-jev",
        "score",
        "How complex is the task?",
        "-l",
        "Trivial",
        "-l",
        "Normal",
        "-l",
        "Hard",
    )

    assert result.exit_code == 0
    assert "Score: 1.70" in result.output
    assert "Confidence: 0.80" in result.output


@pytest.mark.parametrize(
    ("args", "reason"),
    [
        (("noul", "   "), "The question is empty"),
        (("choice", "Which?", "-o", "only"), "from 2 to 32 options"),
        (("choice", "Which?", "-o", "a", "-o", "a"), "same label"),
        (("choice", "Which?", "-o", "=x", "-o", "b"), "has no label"),
        (("score", "How?", "-l", "one"), "from 2 to 10 levels"),
        (("noul", "Is it?", "-o", "a=b"), "--option does not belong to a noul question"),
        (("choice", "Which?", "-o", "a", "-o", "b", "--yes", "x"), "--yes does not belong"),
        (("noul", "x" * (CONST_AI_JEV_ASK_MAX_INPUT_CHARS + 1)), "Jev takes at most"),
        (("noul", "Does token ghp_" + "a" * 36 + " work?"), "holds a secret"),
    ],
)
def test_a_refused_input_exits_non_zero_with_the_reason_and_sends_nothing(
    cli: Callable[..., Any], jev: WebFake, args: tuple[str, ...], reason: str
) -> None:
    result = cli("ai", "ask-jev", *args)

    assert result.exit_code != 0
    assert reason in result.output
    assert "ghp_" not in result.output
    assert jev.recorded == []


def test_an_unknown_kind_is_refused(cli: Callable[..., Any], jev: WebFake) -> None:
    result = cli("ai", "ask-jev", "poem", "Write one.")

    assert result.exit_code != 0
    assert jev.recorded == []


def test_a_gateway_failure_exits_non_zero_without_the_key(
    cli: Callable[..., Any], jev: WebFake
) -> None:
    jev.respond("POST", _URL, 404, {"error": "not found"})

    result = cli("ai", "ask-jev", "noul", "Is it?")

    assert result.exit_code != 0
    assert "did not answer" in result.output
    assert _KEY not in result.output


def test_a_lost_connection_exits_non_zero(cli: Callable[..., Any], jev: WebFake) -> None:
    jev.fail(_URL, httpx2.ConnectError("Connection refused"))

    result = cli("ai", "ask-jev", "noul", "Is it?")

    assert result.exit_code != 0
    assert "did not answer" in result.output


def test_an_answer_that_does_not_match_its_question_is_refused(
    cli: Callable[..., Any], jev: WebFake
) -> None:
    jev.respond(
        "POST",
        _URL,
        200,
        _reply(
            {
                "type": "choice",
                "choice": "other",
                "probabilities": {"other": 1.0},
                "confidence": 1.0,
            }
        ),
    )

    result = cli("ai", "ask-jev", "noul", "Is it?")

    assert result.exit_code != 0
    assert "cannot be read" in result.output


def test_a_dry_run_sends_nothing_and_prints_the_request(
    cli: Callable[..., Any], jev: WebFake
) -> None:
    result = cli(
        "ai", "ask-jev", "choice", "Which?", "-o", "a=First", "-o", "b=Second", "--dry-run"
    )

    assert result.exit_code == 0
    assert "POST http://127.0.0.1:4000/v1/systemone" in result.output
    assert "<ai.api_key>" in result.output
    assert '"instructions": "Which?"' in result.output or "Which?" in result.output
    assert _KEY not in result.output
    assert jev.recorded == []


def test_a_dry_run_refuses_the_input_that_a_real_run_refuses(
    cli: Callable[..., Any], jev: WebFake
) -> None:
    result = cli("ai", "ask-jev", "choice", "Which?", "-o", "only", "--dry-run")

    assert result.exit_code != 0
    assert "from 2 to 32 options" in result.output
