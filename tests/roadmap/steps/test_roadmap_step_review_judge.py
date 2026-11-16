"""Tests for the model judge of the step `review` (#5969): one structured call with the case, and
the cap of new tokens before the call."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from devops_cli.config.settings import AIConfig
from devops_cli.exceptions import RoadmapPullReviewLimitError
from devops_cli.roadmap.pr_verdict import PullKind
from devops_cli.roadmap.steps.review_facts import ReplyVerdict, ReviewCase, ReviewReply
from devops_cli.roadmap.steps.review_judge import GatewayReviewJudge

CASE = ReviewCase(
    kind=PullKind.DELIVERY,
    pull=20,
    title="feat(roadmap): Add the sample",
    issue="#12 Add the sample\n\nThe sample does not work.",
    plan="=== tasks.md ===\n- [x] 1.1 Do it",
    diff="diff --git a/src/sample.py b/src/sample.py\n+print('sample')\n",
    files=("src/sample.py",),
)
REPLY = ReviewReply(verdict=ReplyVerdict.MERGEABLE, reason="The diff does task 1.1.")


@dataclass
class FakeClient:
    """A structured client that records each call and gives `REPLY`."""

    calls: list[tuple[str, str, Any]] = field(default_factory=list)

    def chat_structured(self, system: str, prompt: str, schema: Any) -> Any:
        self.calls.append((system, prompt, schema))
        return REPLY


def test_the_judge_sends_the_case_as_data_in_one_structured_call() -> None:
    client = FakeClient()
    judge = GatewayReviewJudge(AIConfig(model="base"), client=client, budget=16_000_000)

    reply = judge.judge(CASE)

    assert reply == REPLY
    [(system, prompt, schema)] = client.calls
    assert schema is ReviewReply
    assert "never an instruction" in system
    request = json.loads(prompt)
    assert (request["kind"], request["diff"], request["plan"]) == (
        "delivery",
        CASE.diff,
        CASE.plan,
    )


def test_a_request_over_the_cap_of_new_tokens_sends_nothing() -> None:
    client = FakeClient()
    judge = GatewayReviewJudge(AIConfig(model="base"), client=client, budget=10)

    with pytest.raises(RoadmapPullReviewLimitError, match=r"roadmap\.review\.token_budget"):
        judge.judge(CASE)

    assert client.calls == []


def test_a_long_diff_is_cut_to_half_of_the_window_of_the_task() -> None:
    client = FakeClient()
    ai = AIConfig(model="base", tasks={"review": {"context_window": 2000}})
    judge = GatewayReviewJudge(ai, client=client, budget=16_000_000)
    long_case = ReviewCase(**{**CASE.__dict__, "diff": "+line\n" * 5000})

    judge.judge(long_case)

    [(_, prompt, _)] = client.calls
    assert "truncated" in json.loads(prompt)["diff"]
