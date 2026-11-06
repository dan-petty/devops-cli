"""A parser failure of the provider gets one message that asks for a smaller edit (#3053).

Ollama refuses a tool call of the model when its XML is not whole. The failure is deterministic for
one conversation (ollama/ollama pull request 18571), so a new send of the same request fails the
same way. The first parser failure on a tier sends the request again with one more part that asks
for a smaller edit, and a second one stops the step with its work kept.

The model is a pydantic-ai `FunctionModel` from `ModelScript`. Git runs for real on a checkout in
`tmp_path`, and every other program is answered by `process_fake`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import UserPromptPart

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.implement_step import StepOutcome, StepStatus, run_step
from tests.support.fakes.process import ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.implement_step import (
    SHOUT_CODE,
    TASKS,
    TASKS_PATH,
    TEST_BODY,
    WINDOW,
    git,
    write_call,
)
from tests.support.model_script import InStream, ModelScript, say, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

XML_ERROR = "XML syntax error on line 75: unexpected EOF"
TICK_FIRST = TASKS.replace("- [ ] Add the failing test", "- [x] Add the failing test")
TEST_FILE = write_call("tests/test_sample.py", TEST_BODY)


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


def _fails_with(message: str) -> InStream:
    """The error that the gateway sends inside an open stream when the provider fails."""
    body = {"message": message, "type": None, "param": None, "code": "400"}
    return InStream(ModelHTTPError(400, "example-model", body, in_stream=True))


def _step(store: InMemoryRoadmapStore, checkout: Path, script: ModelScript) -> StepOutcome:
    return run_step(store, item=1, group=1, source=checkout, model=script.model(), window=WINDOW)


def _user_texts(request: object) -> list[str]:
    return [
        str(part.content)
        for part in getattr(request, "parts", ())
        if isinstance(part, UserPromptPart)
    ]


def test_the_request_after_a_parser_failure_asks_for_a_smaller_edit_once(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_calls(TEST_FILE), _fails_with(XML_ERROR), say("Done."))

    _step(store, checkout, script)

    asked = MESSAGES.roadmap.implement_parser_smaller_edit
    assert asked not in [text for request in script.seen[2][:-1] for text in _user_texts(request)]
    assert asked not in _user_texts(script.seen[1][-1])
    assert _user_texts(script.seen[2][-1])[-1] == asked


def test_a_second_parser_failure_stops_the_step_with_class_parser_and_no_third_send(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    script = ModelScript(tool_calls(TEST_FILE), _fails_with(XML_ERROR))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.failure_class) == (StepStatus.STOPPED, FailureClass.PARSER)
    assert len(script.seen) == 3
    assert XML_ERROR in outcome.reason


def test_the_ticked_task_of_a_step_stays_as_a_wip_commit_after_two_parser_failures(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """The step stops on the second parser failure, and the task that passed its verification
    before the failure stays in the branch."""
    start = git(checkout, "rev-parse", "HEAD")
    script = ModelScript(
        tool_calls(TEST_FILE),
        tool_calls(write_call(TASKS_PATH, TICK_FIRST)),
        tool_calls(write_call("src/sample.py", SHOUT_CODE)),
        _fails_with(XML_ERROR),
    )

    outcome = _step(store, checkout, script)

    assert outcome.status is StepStatus.STOPPED
    assert git(checkout, "log", "--format=%s", f"{start}..HEAD") == (
        "wip: 1 of 2 tasks of group 1, The first group (#1)"
    )
    assert git(checkout, "show", "HEAD:tests/test_sample.py") == TEST_BODY.strip()


def test_a_new_tier_gets_its_own_smaller_edit_request_after_a_parser_stop(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """A tier is a new agent with a new conversation, so the count of parser failures starts
    again: the first parser failure on the second tier gets the message and a send, not a stop."""
    script = ModelScript(
        tool_calls(TEST_FILE),
        _fails_with(XML_ERROR),
        _fails_with(XML_ERROR),
        _fails_with(XML_ERROR),
        say("Done."),
    )

    outcome = run_step(
        store,
        item=1,
        group=1,
        source=checkout,
        model=script.model(),
        window=WINDOW,
        ladder=["devops-coder", "devops-reasoning"],
    )

    asked = MESSAGES.roadmap.implement_parser_smaller_edit
    assert outcome.tiers == ("devops-coder", "devops-reasoning")
    assert len(script.seen) == 5
    assert _user_texts(script.seen[4][-1])[-1] == asked
