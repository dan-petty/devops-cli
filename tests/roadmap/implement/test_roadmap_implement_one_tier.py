"""A stop on a ladder of one tier names the setting that a person must change (#3569).

A failure whose class selects `change_tier` asks for another model. When
`roadmap.implement.ladder` holds one tier, the step cannot move, so the reason of the stop names the
setting and its tier, and a person sees what to change.

Git runs for real on a checkout in `tmp_path`; every other program is answered by
`process_fake`.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.implement.implement_step import StepOutcome, StepStatus, run_step
from tests.support.fakes.process import ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.implement_step import WINDOW
from tests.support.model_script import ModelScript

pytestmark = pytest.mark.usefixtures("keyring_store")

TIER = "devops-coder"
PARSER_ERROR = "Ollama_chatException: failed to parse the tool call"


@pytest.fixture
def store(implement_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    return implement_store


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


def _one_tier_step(store: InMemoryRoadmapStore, checkout: Path, script: ModelScript) -> StepOutcome:
    """The step on a ladder that holds one tier, with one model for that tier."""
    return run_step(
        store,
        item=1,
        group=1,
        source=checkout,
        model=script.model(),
        window=WINDOW,
        ladder=[TIER],
        tier_health=lambda names: dict.fromkeys(names, True),
    )


def test_a_change_tier_stop_on_one_tier_names_the_ladder(
    store: InMemoryRoadmapStore, checkout: Path, programs: ProcessFake
) -> None:
    """A parser failure selects `change_tier`, and the ladder holds one tier, so the reason of the
    stopped step names `roadmap.implement.ladder` and its tier (#3569)."""
    script = ModelScript(UnexpectedModelBehavior(PARSER_ERROR))

    outcome = _one_tier_step(store, checkout, script)

    assert (outcome.status, outcome.failure_class) == (StepStatus.STOPPED, FailureClass.PARSER)
    assert outcome.reason.splitlines()[-1] == MESSAGES.roadmap.implement_stop_one_tier.format(
        tier=TIER
    )
