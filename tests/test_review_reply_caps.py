"""Review replies are capped, so one runaway generation cannot stall a review."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx2
import pytest

from devops_cli.ai.client import LLMClient
from devops_cli.ai.client.network import completion_cap, limit_completion_tokens
from devops_cli.ai.review.pipeline import _execute_page_review_steps
from devops_cli.ai.review.verification import _validate_segment_findings
from devops_cli.ai.review_schema import Finding, ReviewResult
from devops_cli.config.defaults import (
    DEFAULT_REVIEW_PERSONA_REPLY_MAX_TOKENS,
    DEFAULT_REVIEW_VERIFICATION_REPLY_BASE_TOKENS,
    DEFAULT_REVIEW_VERIFICATION_REPLY_MAX_TOKENS,
    DEFAULT_REVIEW_VERIFICATION_REPLY_TOKENS_PER_FINDING,
)
from devops_cli.config.settings import AIConfig

GATEWAY_URL = "http://gateway.example.com:4000/v1"


@pytest.fixture(autouse=True)
def _allow_private_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVOPS_CLI_AI_ALLOW_PRIVATE_NETWORK", "true")


def _capture_payloads(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []

    def fake_post(self: Any, url: str, **kwargs: Any) -> httpx2.Response:
        if url.startswith(GATEWAY_URL):
            payloads.append(kwargs.get("json") or {})
        return httpx2.Response(
            200,
            json={"choices": [{"message": {"content": "[]"}}]},
            request=httpx2.Request("POST", url),
        )

    monkeypatch.setattr(httpx2.Client, "post", fake_post)
    return payloads


def _client(max_tokens: int | None = None) -> LLMClient:
    return LLMClient(
        AIConfig(
            provider="gateway",
            gateway_url=GATEWAY_URL,
            model="devops-review",
            max_tokens=max_tokens,
        ),
        api_key="sk",
        cache_enabled=False,
    )


def _finding(title: str) -> Finding:
    return Finding(
        severity="HIGH",
        location="src/app.py:3-4",
        title=title,
        description="Input reaches a shell command.",
        fix="Quote it.",
    )


def test_call_cap_limits_the_reply_and_config_still_applies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a call's cap sets max_tokens, the smaller limit wins, and nothing leaks past it."""
    payloads = _capture_payloads(monkeypatch)

    with limit_completion_tokens(500):
        _client().chat("s", "u", use_cache=False)
        _client(max_tokens=300).chat("s", "u", use_cache=False)
    _client().chat("s", "u", use_cache=False)

    assert [p.get("max_tokens") for p in payloads] == [500, 300, None]


def test_verification_reply_is_capped_by_the_number_of_findings() -> None:
    """Verify a verification call runs under a cap sized to the verdicts it must return."""
    seen: list[int | None] = []
    client = MagicMock()

    def chat(**kwargs: Any) -> str:
        seen.append(completion_cap.get())
        return "[]"

    client.chat.side_effect = chat
    findings = [_finding(f"Finding {n}") for n in range(3)]

    _validate_segment_findings(ReviewResult(findings=findings), ["code"], client)

    expected = min(
        DEFAULT_REVIEW_VERIFICATION_REPLY_MAX_TOKENS,
        DEFAULT_REVIEW_VERIFICATION_REPLY_BASE_TOKENS
        + 3 * DEFAULT_REVIEW_VERIFICATION_REPLY_TOKENS_PER_FINDING,
    )
    assert (seen, completion_cap.get()) == ([expected], None)


def test_persona_review_replies_are_capped() -> None:
    """Verify persona review runs under the persona reply cap."""
    seen: list[int | None] = []
    pipeline = MagicMock()

    def run(*args: Any, **kwargs: Any) -> Any:
        seen.append(completion_cap.get())
        return MagicMock(steps=[])

    pipeline.run.side_effect = run

    _execute_page_review_steps(pipeline, "prompt", "src/app.py", 1, 1, {}, [], [], [])

    assert seen == [DEFAULT_REVIEW_PERSONA_REPLY_MAX_TOKENS]
