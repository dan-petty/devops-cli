"""Tests for one-retry rebuild of a refused pull request body (#3599)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from devops_cli.ai.client.models import StructuredOutputValidationError
from devops_cli.exceptions.validation import ValidationError
from devops_cli.roadmap.pull_retry import (
    BodyReply,
    GatewayPullBody,
    RefusedPullReply,
    retried_body,
)


def test_a_refused_body_is_rebuilt_once_from_the_problems() -> None:
    calls: list[str] = []

    def fake_build(text: str) -> str:
        calls.append(text)
        if text == "first bad text":
            raise ValidationError("- text is too long\n- text has a cut mark")
        if text == "second good text":
            return "final accepted body"
        raise ValidationError("- second text is also bad")

    rewrites: list[tuple[str, tuple[str, ...]]] = []

    def fake_rewrite(text: str, problems: Any) -> str:
        rewrites.append((text, tuple(problems)))
        return "second good text"

    result = retried_body(text="first bad text", build=fake_build, rewrite=fake_rewrite)
    assert result == "final accepted body"
    assert calls == ["first bad text", "second good text"]
    assert rewrites == [
        ("first bad text", ("text is too long", "text has a cut mark")),
    ]

    # Verify that refusing both raises RefusedPullReply with problems of second text
    # after one rewrite call and no third call.
    calls.clear()
    rewrites.clear()

    def fake_rewrite_bad(text: str, problems: Any) -> str:
        rewrites.append((text, tuple(problems)))
        return "still bad text"

    with pytest.raises(RefusedPullReply) as exc_info:
        retried_body(text="first bad text", build=fake_build, rewrite=fake_rewrite_bad)

    assert exc_info.value.problems == ("second text is also bad",)
    assert calls == ["first bad text", "still bad text"]
    assert len(rewrites) == 1


def test_retried_body_without_rewrite_raises_on_first_refusal() -> None:
    def fake_build(text: str) -> str:
        raise ValidationError("- problem one")

    with pytest.raises(RefusedPullReply) as exc_info:
        retried_body(text="bad", build=fake_build, rewrite=None)

    assert exc_info.value.problems == ("problem one",)


def test_retried_body_returns_immediately_when_valid() -> None:
    rewrite = MagicMock()
    result = retried_body(text="good text", build=lambda t: f"built: {t}", rewrite=rewrite)
    assert result == "built: good text"
    rewrite.assert_not_called()


def test_gateway_pull_body_rewrite_calls_analysis_client() -> None:
    client = MagicMock()
    client.chat_structured.return_value = BodyReply(text="rebuilt body")
    gateway = GatewayPullBody(client=client)

    result = gateway.rewrite("original text", ["cut mark", "too long"])
    assert result == "rebuilt body"
    client.chat_structured.assert_called_once()


def test_gateway_pull_body_rewrite_returns_empty_string_on_structured_validation_error() -> None:
    client = MagicMock()
    client.chat_structured.side_effect = StructuredOutputValidationError("Invalid output")
    gateway = GatewayPullBody(client=client)

    result = gateway.rewrite("text", ["problem"])
    assert result == ""


def test_gateway_pull_body_rewrite_raises_model_gateway_unreachable_on_error() -> None:
    from devops_cli.exceptions.ai import ModelGatewayUnreachableError
    from devops_cli.exceptions.base import DevOpsCLIError

    client = MagicMock()
    client.chat_structured.side_effect = DevOpsCLIError("inference failure")
    gateway = GatewayPullBody(client=client)

    with pytest.raises(ModelGatewayUnreachableError) as exc_info:
        gateway.rewrite("text", ["problem"])

    assert "body rewrite wrote nothing" in str(exc_info.value)


def test_gateway_pull_body_builds_client_when_none(model_fake: Any) -> None:
    model_fake.answer(BodyReply(text="built client response"))

    gateway = GatewayPullBody()
    result = gateway.rewrite("text", ["problem"])
    assert result == "built client response"


def test_extract_problems_with_problems_attribute() -> None:
    from devops_cli.roadmap.pull_retry import _extract_problems

    err = ValidationError("fallback error message")
    setattr(err, "problems", ["first rule broken", "second rule broken"])
    assert _extract_problems(err) == ["first rule broken", "second rule broken"]
