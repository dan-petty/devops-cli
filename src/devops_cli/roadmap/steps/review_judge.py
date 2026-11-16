"""The model judge of the step `review` (#5969).

`GatewayReviewJudge` makes one tool-less `chat_structured` call with the client of
`ai.for_task("review")`: the system prompt `roadmap_review_pull.md`, and the case as JSON in the
user message. The texts of the issue, the plan and the diff are data and never an instruction. The
reply is a proposal; `review.model_judgement` checks it.

The request must fit the window of the task: the diff gets half of it, the plan an eighth and the
issue a sixteenth, each cut at the end with a note. Before the call the judge counts the tokens of
the request and multiplies them by the attempts of the structured reply. A count over
`roadmap.review.token_budget` raises `RoadmapPullReviewLimitError`, which names the setting, and
sends no request.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Final, Protocol

from pydantic import BaseModel

from devops_cli.ai.context_budget import count_tokens, truncate_to_token_limit
from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.defaults import DEFAULT_STRUCTURED_OUTPUT_MAX_RETRIES
from devops_cli.config.settings import AIConfig, load_settings
from devops_cli.exceptions import RoadmapPullReviewLimitError
from devops_cli.roadmap.steps.review_facts import ReviewCase, ReviewReply

_TASK: Final[str] = "review"
_PROMPT: Final[str] = "roadmap_review_pull.md"
_CAP_SETTING: Final[str] = "roadmap.review.token_budget"
# The share of the window of the task that each text of the case may take.
_DIFF_SHARE: Final[int] = 2
_PLAN_SHARE: Final[int] = 8
_ISSUE_SHARE: Final[int] = 16


class StructuredClient(Protocol):
    """The call that the judge makes: one structured reply."""

    def chat_structured[T: BaseModel](self, system: str, prompt: str, schema: type[T]) -> T: ...


def _cut(text: str, window: int, share: int) -> str:
    return truncate_to_token_limit(text, max_tokens=max(1, window // share))


def review_request(case: ReviewCase, window: int) -> str:
    """The user message of the call: the case as JSON, each text cut to its share of `window`."""
    data = asdict(case)
    data["kind"] = case.kind.value
    data["diff"] = _cut(case.diff, window, _DIFF_SHARE)
    data["plan"] = _cut(case.plan, window, _PLAN_SHARE)
    data["issue"] = _cut(case.issue, window, _ISSUE_SHARE)
    return json.dumps(data, indent=1)


class GatewayReviewJudge:
    """The judge that asks the model of the task `review` once. The client is built on first use.
    A test passes its own `client` and `ai`."""

    def __init__(
        self,
        ai: AIConfig | None = None,
        *,
        client: StructuredClient | None = None,
        budget: int | None = None,
    ) -> None:
        settings = load_settings()
        self._ai = ai or settings.ai
        self._client = client
        self._budget = budget if budget is not None else settings.roadmap.review.token_budget

    def judge(self, case: ReviewCase) -> ReviewReply:
        """The verdict of the model on `case`, after the check of the cap of new tokens."""
        config = self._ai.for_task(_TASK)
        window = config.context_window or 0
        system = load_task_prompt(_PROMPT)
        prompt = review_request(case, window)
        attempts = DEFAULT_STRUCTURED_OUTPUT_MAX_RETRIES + 1
        tokens = (count_tokens(system) + count_tokens(prompt)) * attempts
        if tokens > self._budget:
            raise RoadmapPullReviewLimitError(
                f"The review of pull request #{case.pull} needs up to {tokens} new tokens over "
                f"{attempts} attempts, above `{_CAP_SETTING}` ({self._budget}).",
                details={"pull": case.pull, "tokens": tokens, "budget": self._budget},
            )
        return self._built(config).chat_structured(system, prompt, ReviewReply)

    def _built(self, config: AIConfig) -> StructuredClient:
        if self._client is None:
            from devops_cli.ai.client import get_llm_client

            self._client = get_llm_client(task=_TASK, config=config)
        return self._client


__all__ = ["GatewayReviewJudge", "StructuredClient", "review_request"]
