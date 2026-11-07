"""An alternatives round writes each check when that check is done (#4034).

A kill of the worker or a rate limit on a write ends the round and loses at most the check in
progress: the body block, the record and the comment of check N are written before check N+1
starts. A plan with `--plan` writes nothing.

The roadmap is the in-memory store, pydantic-ai's `FunctionModel` answers each model request from a
script, and Firecrawl is answered at the HTTP edge. The rounds run through the row of the Service
(`_run_alternatives_adapter`) and the command, so no test names a writer.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai.messages import ModelMessage, ToolReturnPart, UserPromptPart
from typer.testing import CliRunner

from devops_cli.commands.roadmap import app as roadmap_app
from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER,
    CONST_ROADMAP_ALTERNATIVES_START_MARKER,
)
from devops_cli.config.defaults import DEFAULT_FIRECRAWL_SEARCH_URL
from devops_cli.exceptions.git import GitHubRateLimitError
from devops_cli.roadmap.alternatives import AlternativesReply, Verdict
from devops_cli.roadmap.run import _run_alternatives_adapter
from devops_cli.roadmap.stores.store import AlternativesRecordKey, ItemField
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.scripted_model import Script, call

if TYPE_CHECKING:
    from tests.support.fakes.http import WebFake

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
REASON = "No open tool covers the need."
SEARCH = call("search_web", query="scanner")


class WorkerKilled(BaseException):
    """The kill of the worker: a `BaseException`, so no handler of the job catches it."""


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    """A public roadmap with five open items that have no check."""
    roadmap = InMemoryRoadmapStore(repo=REPO, is_private=False)
    for n in range(5):
        roadmap.seed_issue(
            f"Scan a directory {n}",
            body=f"The job needs to read every file of directory {n}.",
            fields={ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: "New"},
        )
    return roadmap


@pytest.fixture(autouse=True)
def web_key(config: Callable[..., Any], monkeypatch: pytest.MonkeyPatch, web: WebFake) -> None:
    """A Firecrawl key in the settings, and a Firecrawl that answers each search with one result."""
    for name in ("DEVOPS_CLI_FIRECRAWL_API_KEY", "FIRECRAWL_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    config(search={"providers": ["firecrawl"]}, firecrawl={"api_key": "fc-test"})
    results = [
        {"title": "Result", "url": "https://example.com/scanner", "description": "A scanner."}
    ]
    web.content(
        DEFAULT_FIRECRAWL_SEARCH_URL,
        json.dumps({"success": True, "data": {"web": results}}).encode(),
    )


def _prompt_of(messages: list[ModelMessage]) -> dict[str, Any]:
    text = next(
        part.content
        for message in messages
        for part in getattr(message, "parts", ())
        if isinstance(part, UserPromptPart)
    )
    document: dict[str, Any] = json.loads(str(text))
    return document


def _searched(messages: list[ModelMessage]) -> bool:
    return any(
        isinstance(part, ToolReturnPart) and part.tool_name == "search_web"
        for message in messages
        for part in getattr(message, "parts", ())
    )


class _Model:
    """A model that searches once for each item and then says that no tool covers it. It keeps the
    numbers of the items it was asked about, in order, and raises `WorkerKilled` for the item
    that is the `kill_at`-th it sees."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, kill_at: int = 0) -> None:
        self.asked: list[int] = []
        self.kill_at = kill_at
        self.script = Script(self._answer)
        monkeypatch.setattr(
            "devops_cli.roadmap.alternatives.get_task_model", lambda _task: self.script.model()
        )

    def _answer(self, messages: list[ModelMessage]) -> Any:
        number = _prompt_of(messages)["number"]
        if number not in self.asked:
            self.asked.append(number)
            if len(self.asked) == self.kill_at:
                raise WorkerKilled("the worker was killed")
        if _searched(messages):
            return AlternativesReply(reason=REASON, verdict=Verdict.NONE)
        return SEARCH


def _written(store: InMemoryRoadmapStore, number: int) -> tuple[bool, bool, bool]:
    """Whether item `number` has the body block, the record and the comment of a check."""
    item = store.item(number)
    assert item is not None
    return (
        CONST_ROADMAP_ALTERNATIVES_START_MARKER in store.read_issue_body(number),
        AlternativesRecordKey.CHECKED_AT in item.job_record,
        any(
            c.body.startswith(CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER)
            for c in store.comments_on(number)
        ),
    )


def test_killed_between_items_the_first_two_checks_are_written_and_the_others_have_nothing(
    store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = _Model(monkeypatch, kill_at=3)

    with pytest.raises(WorkerKilled, match="worker was killed"):
        _run_alternatives_adapter(store, repo=REPO)

    first, second, _killed = model.asked
    nothing = (False, False, False)
    assert (
        len(model.asked),
        _written(store, first),
        _written(store, second),
        [_written(store, n) for n in range(1, 6) if n not in (first, second)],
    ) == (3, (True, True, True), (True, True, True), [nothing] * 3)


def test_rate_limit_in_the_write_of_check_two_ends_the_round_and_keeps_check_one(
    store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = _Model(monkeypatch)
    store.fail_write(
        write="write_issue_body",
        item=2,
        error=GitHubRateLimitError("No requests are left.", operation="roadmap.write"),
    )

    with pytest.raises(GitHubRateLimitError, match="No requests are left"):
        _run_alternatives_adapter(store, repo=REPO)

    nothing = (False, False, False)
    assert (
        model.asked,
        _written(store, 1),
        [_written(store, n) for n in range(2, 6)],
    ) == ([1, 2], (True, True, True), [nothing] * 4)


def test_plan_only_the_command_makes_no_write(
    roadmap_store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    for n in range(3):
        roadmap_store.seed_issue(
            f"Scan a directory {n}",
            body=f"The job needs to read every file of directory {n}.",
            fields={ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: "New"},
        )
    model = _Model(monkeypatch)
    before = len(roadmap_store.writes)

    result = CliRunner().invoke(roadmap_app, ["alternatives", "--repo", REPO, "--plan"])

    assert result.exit_code == 0, result.output
    assert (roadmap_store.writes[before:], len(model.asked)) == ([], 3)
