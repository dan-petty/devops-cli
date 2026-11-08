"""`devops roadmap stage`: a split of the groups is judged by every gate of the first pass (#4040).

A group over the token budget makes the planner ask the model to split the groups once. The split
replaces `groups` and `criteria`, and the model can bring an old fault back with the new groups.
Each case here scripts a first plan that passes, then a split that brings back one fault that only
one gate refuses. The planner sends the refusal back to the model, with the problem of that gate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.roadmap.stage.stage import StagePlan, parse_filters, plan_stage
from devops_cli.roadmap.stage.stage_change import (
    STAGE_EVAL_REPLAY,
    ProposalGate,
    StageGroup,
    StageProposal,
    StageSplit,
    check_gates,
)
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.stage.stage_registry import registry_table
from tests.support.builders import make_stage_proposal
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import (
    NO_FILES,
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    heavy_group,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

BUDGET = 6000
CHANGE = "1-the-job-drops-a-comment"
FORM_GATE = "src/devops_cli/roadmap/stage/stage_form.py"
OTHER_SOURCE = "src/devops_cli/other.py"
READY = "src/devops_cli/widgets/panel_ready.py"
VERIFY = "src/devops_cli/widgets/panel_verify.py"
READY_NEW = "src/devops_cli/widgets/panel/ready.py"
REGISTRY_TEST = "tests/test_registry_example.py"
REGISTRY_TOKEN = "CONST_PANEL_"
REGISTRY_PATH = "tests/widgets/test_panel_limits.py"
REGISTRY_DECLARATION = f'REGISTRY_COUNTS = (("prefix", "{REGISTRY_TOKEN}", "{REGISTRY_PATH}"),)\n'
SOURCE_TEXT = "VALUE = 1\n"


@dataclass(frozen=True)
class SplitCase:
    """One split that brings back one fault: the files that the commit holds, the first plan
    (which passes), the groups of the split, the gate that refuses the split and a phrase of its
    problem."""

    tracked: dict[str, str]
    gate: ProposalGate
    phrase: str
    first: Callable[[StageGroup], dict[str, Any]] = field(default=lambda group: {})
    split: Callable[[StageGroup], list[StageGroup]] = field(default=lambda group: [group])


def _light(group: StageGroup, **update: Any) -> StageGroup:
    """`group` with no file to read, so it measures under the budget."""
    return group.model_copy(update={**NO_FILES, **update})


def _behavior(group: StageGroup, title: str, path: str) -> StageGroup:
    """A group that changes the one existing file `path`, with a test and a task of its own, so
    the content gate finds no two tasks that state the same work."""
    return _light(
        group,
        title=title,
        changes=[path],
        creates=[],
        creates_lines={},
        test=f"Write `test_{title.lower().replace(' ', '_')}` in `tests/test_sample.py`",
        implementation=f"Rework `{path}` for the step {title}",
    )


def _eval_replay(group: StageGroup) -> list[StageGroup]:
    """A split with a group that changes a trigger path and no task that runs the replay."""
    return [_light(group), _behavior(group, "Tighten the form check", FORM_GATE)]


def _what_changes_first(group: StageGroup) -> dict[str, Any]:
    """The first plan: What Changes names a second source file, and the one group lists it."""
    return {
        "groups": [group.model_copy(update={"changes": [*group.changes, OTHER_SOURCE]})],
        "what_changes": [
            "`src/devops_cli/sample.py` keeps the last comment.",
            f"`{OTHER_SOURCE}` keeps the last comment.",
        ],
    }


def _what_changes(group: StageGroup) -> list[StageGroup]:
    """A split in which no group lists the second source file."""
    return [_light(group)]


def _move_prefix(group: StageGroup) -> list[StageGroup]:
    """A split with a group that moves one module of a prefix and leaves the other one."""
    moved = _light(
        group,
        title="Move the ready module",
        test="Write `test_the_ready_module_moves` in `tests/test_sample.py`",
        changes=[READY, READY_NEW],
        creates=[READY_NEW],
        creates_lines={READY_NEW: 20},
        implementation=f"Move `{READY}` into the subpackage `src/devops_cli/widgets/panel`",
    )
    return [_light(group), moved]


def _registry(group: StageGroup) -> list[StageGroup]:
    """A split with a group whose task names a registry item and not its test module."""
    counted = _behavior(group, "Count the panels", OTHER_SOURCE).model_copy(
        update={"implementation": f"Add the item {REGISTRY_TOKEN}LIMIT in `{OTHER_SOURCE}`"}
    )
    return [_light(group), counted]


CASES = {
    "eval_replay": SplitCase(
        {FORM_GATE: SOURCE_TEXT},
        ProposalGate.EVAL_REPLAY,
        STAGE_EVAL_REPLAY,
        split=_eval_replay,
    ),
    "what_changes": SplitCase(
        {OTHER_SOURCE: SOURCE_TEXT},
        ProposalGate.WHAT_CHANGES,
        "A What Changes item names",
        first=_what_changes_first,
        split=_what_changes,
    ),
    "move_prefix": SplitCase(
        {READY: SOURCE_TEXT, VERIFY: SOURCE_TEXT},
        ProposalGate.MOVE_PREFIX,
        f"`{VERIFY}`",
        split=_move_prefix,
    ),
    "registry": SplitCase(
        {OTHER_SOURCE: SOURCE_TEXT, REGISTRY_TEST: REGISTRY_DECLARATION},
        ProposalGate.REGISTRY,
        REGISTRY_PATH,
        split=_registry,
    ),
}


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture(autouse=True)
def _item(store: InMemoryRoadmapStore) -> int:
    """The one Ready bug the plans are about: #1."""
    return seed_stageable(store)


@pytest.fixture(autouse=True)
def _openspec(openspec_fake: OpenSpecFake) -> None:
    """OpenSpec, found, and valid about the change of #1 for every plan."""
    openspec_fake.script_sequence(validate_args(CHANGE), (0, VALID_REPORT))


def _plans(case: SplitCase, stage_repo: StageRepo) -> tuple[StageProposal, StageSplit]:
    """The first plan, with one group over the budget, and the split of the case."""
    stage_repo.track(case.tracked)
    heavy = heavy_group(stage_repo)
    first = make_stage_proposal(**{"groups": [heavy], **case.first(heavy)})
    return first, StageSplit(groups=case.split(heavy))


def _plan(store: InMemoryRoadmapStore, stage_repo: StageRepo) -> StagePlan:
    return plan_stage(
        store,
        repo=STAGE_REPO,
        source=stage_repo.clone,
        filters=parse_filters(()),
        item_number=None,
        step_tokens=BUDGET,
        model=None,
    )


def _gates_of(
    stage_repo: StageRepo, first: StageProposal, split: StageSplit
) -> dict[ProposalGate, list[str]]:
    """What each gate finds in the first plan with the groups of the split."""
    files = stage_repo.git("ls-files").splitlines()
    proposal = first.model_copy(update={"groups": split.groups, "criteria": split.criteria})
    return check_gates(
        proposal,
        {"roadmap-refine"},
        StagedTree(files),
        registry=registry_table(stage_repo.clone),
    )


@pytest.mark.parametrize("name", CASES)
def test_a_split_that_brings_back_a_fault_goes_back_to_the_model_once(
    name: str, store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    case = CASES[name]
    first, split = _plans(case, stage_repo)
    model_fake.answer(first, split, make_stage_proposal())

    plan = _plan(store, stage_repo)

    assert model_fake.call_count == 3
    assert case.phrase in model_fake.calls[2].prompt
    assert [g.group.title for g in plan.ready[0].groups] == ["Keep the last comment"]


@pytest.mark.parametrize("name", CASES)
def test_a_split_is_refused_by_only_one_gate_and_the_planner_sends_its_problem(
    name: str, store: InMemoryRoadmapStore, stage_repo: StageRepo, model_fake: ModelFake
) -> None:
    case = CASES[name]
    first, split = _plans(case, stage_repo)
    found = {
        gate: problems for gate, problems in _gates_of(stage_repo, first, split).items() if problems
    }
    assert list(found) == [case.gate], found
    model_fake.answer(first, split, make_stage_proposal())

    _plan(store, stage_repo)

    assert model_fake.call_count == 3
    assert " ".join(found[case.gate]) in model_fake.calls[2].prompt
