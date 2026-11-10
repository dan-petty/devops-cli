"""The stage job adds the base scenarios that a MODIFIED requirement omits (#4310).

OpenSpec refuses a MODIFIED block that leaves out a scenario of the base requirement, because the
block replaces the whole requirement. The omitted text is in the base spec, so the job copies it
into the block before it validates the change, and the model needs no second try.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from devops_cli.roadmap.stage.stage import StagedChange, parse_filters, plan_stage
from devops_cli.roadmap.stage.stage_change import StageProposal
from tests.support.builders import make_stage_proposal
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

CHANGE = "1-the-job-drops-a-comment"
SPEC_FILE = f"openspec/changes/{CHANGE}/specs/comment-thread/spec.md"
BASE_FILE = "openspec/specs/comment-thread/spec.md"
SHOW = ("show", "comment-thread", "--type", "spec", "--json")
REQUIREMENT = "The job keeps every comment"
KEPT = "- **WHEN** a thread has two comments\n- **THEN** both comments are kept"
DROPPED = "- **WHEN** a thread has no comment\n- **THEN** the job keeps nothing and fails no check"
EXTENDED = (
    "- **WHEN** a comment is deleted\n- **THEN** the job keeps the others\n- **AND** it logs it"
)


def _base(*scenarios: tuple[str, str]) -> str:
    """What `openspec show comment-thread --type spec --json` prints for a base requirement."""
    return json.dumps(
        {
            "id": "comment-thread",
            "requirements": [
                {
                    "name": REQUIREMENT,
                    "text": "The job SHALL keep every comment of a thread.",
                    "scenarios": [{"name": name, "rawText": raw} for name, raw in scenarios],
                }
            ],
        }
    )


def _modified(*scenarios: tuple[str, str, str], name: str = REQUIREMENT) -> StageProposal:
    return make_stage_proposal(
        specs=[
            {
                "capability": "comment-thread",
                "added": [],
                "modified": [
                    {
                        "name": name,
                        "text": "The job SHALL keep every comment of a thread.",
                        "scenarios": [
                            {"name": n, "when": when, "then": then} for n, when, then in scenarios
                        ],
                    }
                ],
            }
        ]
    )


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(store)
    return store


def _staged(
    store: InMemoryRoadmapStore, repo: StageRepo, model_fake: ModelFake, proposal: StageProposal
) -> StagedChange:
    repo.track({BASE_FILE: "## Purpose\nKeep comments.\n"})
    model_fake.answer(proposal)
    plan = plan_stage(
        store, repo=STAGE_REPO, source=repo.clone, filters=parse_filters(()), model=None
    )
    (change,) = plan.ready
    return change


def test_a_modified_block_that_omits_a_base_scenario_gets_it_back(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
) -> None:
    openspec_fake.script_sequence(validate_args(CHANGE), (0, VALID_REPORT))
    openspec_fake.script_sequence(
        SHOW, (0, _base(("The last comment", KEPT), ("An empty thread", DROPPED)))
    )
    reply = _modified(("The last comment", "a thread has two comments", "both comments are kept"))

    change = _staged(store, stage_repo, model_fake, reply)

    text = change.files[SPEC_FILE]
    assert text.count("#### Scenario:") == 2
    assert f"#### Scenario: An empty thread\n{DROPPED}" in text
    assert text.index("#### Scenario: The last comment") < text.index("An empty thread")


def test_the_scenarios_of_the_reply_keep_their_text_and_the_omitted_one_comes_last(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
) -> None:
    openspec_fake.script_sequence(validate_args(CHANGE), (0, VALID_REPORT))
    openspec_fake.script_sequence(
        SHOW, (0, _base(("An empty thread", DROPPED), ("The last comment", KEPT)))
    )
    reply = _modified(
        ("The last comment", "a thread has three comments", "all comments are kept"),
        ("A new case", "a comment is edited", "the job keeps the edit"),
    )

    change = _staged(store, stage_repo, model_fake, reply)

    text = change.files[SPEC_FILE]
    names = [line for line in text.splitlines() if line.startswith("#### Scenario:")]
    assert names == [
        "#### Scenario: The last comment",
        "#### Scenario: A new case",
        "#### Scenario: An empty thread",
    ]
    assert "a thread has three comments" in text
    assert "a thread has two comments" not in text


def test_a_restored_scenario_keeps_every_line_of_its_raw_text(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
) -> None:
    openspec_fake.script_sequence(validate_args(CHANGE), (0, VALID_REPORT))
    openspec_fake.script_sequence(SHOW, (0, _base(("A deleted comment", EXTENDED))))
    reply = _modified(("The last comment", "a thread has two comments", "both comments are kept"))

    change = _staged(store, stage_repo, model_fake, reply)

    assert f"#### Scenario: A deleted comment\n{EXTENDED}" in change.files[SPEC_FILE]


def test_a_complete_block_is_not_changed(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
) -> None:
    openspec_fake.script_sequence(validate_args(CHANGE), (0, VALID_REPORT))
    openspec_fake.script_sequence(SHOW, (0, _base(("The last comment", KEPT))))
    reply = _modified(("The last comment", "a thread has two comments", "both comments are kept"))

    change = _staged(store, stage_repo, model_fake, reply)

    assert change.files[SPEC_FILE].count("#### Scenario:") == 1


def test_a_modified_block_of_an_unknown_requirement_is_left_to_openspec(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
) -> None:
    openspec_fake.script_sequence(validate_args(CHANGE), (0, VALID_REPORT))
    openspec_fake.script_sequence(SHOW, (0, _base(("An empty thread", DROPPED))))
    reply = _modified(
        ("The last comment", "a thread has two comments", "both comments are kept"),
        name="A requirement the base lacks",
    )

    change = _staged(store, stage_repo, model_fake, reply)

    assert change.files[SPEC_FILE].count("#### Scenario:") == 1


def test_an_added_requirement_is_not_changed(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    openspec_fake: OpenSpecFake,
) -> None:
    openspec_fake.script_sequence(validate_args(CHANGE), (0, VALID_REPORT))

    change = _staged(store, stage_repo, model_fake, make_stage_proposal())

    assert change.files[SPEC_FILE].count("#### Scenario:") == 1
    assert not any(call.argv[:1] == ("show",) for call in openspec_fake.calls)
