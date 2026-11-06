"""A stopped step carries a typed failure class (#3476): the step knows the cause, so it passes the
class in its outcome, and no one reads the words of the reason or of the last message of the agent.

The model is a pydantic-ai `FunctionModel` from `ModelScript`. Git runs for real on a checkout in
`tmp_path`, and every other program is answered by `process_fake`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior
from pydantic_ai.messages import ModelResponse

from devops_cli.exceptions.ai_pydantic import OutputCapReached
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.implement_step import (
    FixRequest,
    StepOutcome,
    StepStatus,
    run_fix_step,
    run_step,
)
from tests.support.fakes.process import ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.implement_step import (
    WINDOW,
    git,
    the_whole_group,
)
from tests.support.model_script import ModelScript, say, tool_calls

pytestmark = pytest.mark.usefixtures("keyring_store")

LADDER = {"roadmap": {"implement": {"ladder": {"edit": ["devops-coder", "devops-reasoning"]}}}}
CLAIM = "The item is already implemented. All acceptance criteria are met."


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


def _step(
    store: InMemoryRoadmapStore, checkout: Path, script: ModelScript, group: int = 1
) -> StepOutcome:
    return run_step(
        store, item=1, group=group, source=checkout, model=script.model(), window=WINDOW
    )


def _fix(store: InMemoryRoadmapStore, checkout: Path, script: ModelScript) -> StepOutcome:
    return run_fix_step(
        store,
        item=1,
        fix=FixRequest(check="Tests & Coverage", log="FAILED tests/test_x.py::test_y"),
        source=checkout,
        model=script.model(),
        window=WINDOW,
    )


def test_a_fix_step_that_changes_no_file_is_no_change_in_fix_whatever_the_agent_claims(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    outcome = _fix(store, checkout, ModelScript(say(CLAIM)))

    assert (outcome.status, outcome.reason, outcome.failure_class) == (
        StepStatus.STOPPED,
        "The agent changed no file.",
        FailureClass.NO_CHANGE_IN_FIX,
    )


def test_a_group_step_that_changes_no_file_is_a_plan_defect(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    outcome = _step(store, checkout, ModelScript(say(CLAIM)), group=2)

    assert (outcome.status, outcome.reason, outcome.failure_class) == (
        StepStatus.STOPPED,
        "The agent changed no file.",
        FailureClass.PLAN_DEFECT,
    )


def test_an_agent_that_moves_head_stops_the_step_with_head_moved(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    def agent_commits() -> None:
        (checkout / "src" / "other.py").write_text("OTHER = 3\n", encoding="utf-8")
        git(checkout, "add", "-A")
        git(checkout, "commit", "-q", "-m", "own commit")

    script = ModelScript(tool_calls(*the_whole_group()), say("Done."), effects={2: agent_commits})

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.failure_class) == (StepStatus.STOPPED, FailureClass.HEAD_MOVED)


def test_a_step_that_ends_done_has_no_failure_class(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    outcome = _step(store, checkout, ModelScript(tool_calls(*the_whole_group()), say("Done.")))

    assert (outcome.status, outcome.failure_class) == (StepStatus.DONE, None)


def test_a_failure_that_the_text_classifies_is_typed_once_for_the_decision_and_the_outcome(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    """The parser failure moves the step to the next tier, and the outcome of the step holds the
    class that the decision read."""
    config(**LADDER)
    parser = UnexpectedModelBehavior("Ollama_chatException: failed to parse the tool call")
    script = ModelScript(parser, parser)

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.tiers, outcome.failure_class) == (
        StepStatus.STOPPED,
        ("devops-coder", "devops-reasoning"),
        FailureClass.PARSER,
    )


def test_the_output_cap_keeps_the_tier_even_when_its_text_has_the_words_of_a_parser_failure(
    store: InMemoryRoadmapStore,
    checkout: Path,
    programs: ProcessFake,
    config: Callable[..., Path],
) -> None:
    """The tier decision reads the class of the run: `output_cap` selects `raise_limit`, so the
    step does not move, whatever words the message of the error holds."""
    config(**LADDER)
    capped = OutputCapReached(
        "The model reply reached the output cap, failed to parse the tool call.",
        response=ModelResponse(parts=[]),
    )
    script = ModelScript(capped, say("Never asked."))

    outcome = _step(store, checkout, script)

    assert (outcome.status, outcome.tiers, outcome.failure_class) == (
        StepStatus.STOPPED,
        ("devops-coder",),
        FailureClass.OUTPUT_CAP,
    )
