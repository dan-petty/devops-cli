"""`devops roadmap stage`: split model call shared by stage and implement jobs (#3057)."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.roadmap.stage_change import GroupKind, StageGroup, StageSplit
from devops_cli.roadmap.stage_criteria import StageCriterion
from devops_cli.roadmap.stage_split import SPLIT_TASK, ask_split


class _ClientFake:
    def __init__(self, reply: StageSplit) -> None:
        self.reply = reply
        self.calls: list[tuple[str, str, type[BaseModel], int]] = []

    def chat_structured(
        self,
        prompt: str,
        content: str,
        response_model: type[BaseModel],
        *,
        max_retries: int = 1,
    ) -> BaseModel:
        self.calls.append((prompt, content, response_model, max_retries))
        return self.reply


def _make_split() -> StageSplit:
    group = StageGroup(
        title="Split group",
        kind=GroupKind.OTHER,
        reads=["src/a.py"],
        changes=["src/a.py"],
        implementation="implement it",
        verify="uv run devops ci test tests/test_a.py",
    )
    criterion = StageCriterion(group=1, criterion="It works", reason="matches group 1")
    return StageSplit(groups=[group], criteria=[criterion])


def test_ask_split_sends_arguments_with_split_prompt_and_returns_stage_split() -> None:
    reply = _make_split()
    client = _ClientFake(reply)
    request: dict[str, Any] = {
        "number": 42,
        "title": "Fix something",
        "budget": 35000,
        "groups": [
            {
                "number": 1,
                "title": "First",
                "tokens": 40000,
                "over_budget": True,
            }
        ],
        "criteria": [{"group": 1, "criterion": "It works", "reason": "matches group 1"}],
    }

    result = ask_split(client, request)

    assert result == reply
    assert len(client.calls) == 1
    prompt, content, model, max_retries = client.calls[0]
    assert prompt == load_task_prompt(SPLIT_TASK)
    assert model is StageSplit
    assert max_retries == 1

    payload = json.loads(content)
    assert payload["number"] == 42
    assert payload["title"] == "Fix something"
    assert payload["budget"] == 35000
    assert payload["groups"] == request["groups"]
    assert payload["criteria"] == request["criteria"]


def test_ask_split_sends_group_with_text_as_it_is() -> None:
    reply = _make_split()
    client = _ClientFake(reply)
    group_with_text = {
        "number": 2,
        "title": "Group from tasks.md",
        "tokens": 45000,
        "over_budget": True,
        "text": "## 2. Group from tasks.md\n\n- [ ] Task in group\n  - Verification: `uv run devops ci test`\n",
    }
    request: dict[str, Any] = {
        "number": 99,
        "title": "Item with text group",
        "budget": 30000,
        "groups": [group_with_text],
        "criteria": [],
    }

    ask_split(client, request)

    assert len(client.calls) == 1
    payload = json.loads(client.calls[0][1])
    assert payload["groups"][0]["text"] == group_with_text["text"]
