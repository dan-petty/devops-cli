"""`check_gates`: the problems of `check_proposal` under the name of the gate that found each
(#3498)."""

from __future__ import annotations

from devops_cli.roadmap.stage_change import (
    STAGE_EVAL_REPLAY,
    ProposalGate,
    StageProposal,
    check_gates,
    check_proposal,
)
from devops_cli.roadmap.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal

TREE_FILES = ["src/devops_cli/sample.py"]
TREE = StagedTree(TREE_FILES)
STAGE_CHANGE = "src/devops_cli/roadmap/stage_change.py"
KNOWN = ["comment-thread"]
MISSING = "src/devops_cli/missing.py"
NO_SPEC_DELTA = "skip_specs is false, and the reply gives no spec delta."


def _reads_a_missing_file(**overrides: object) -> StageProposal:
    """The stock plan with a group that reads and changes a file that no commit holds."""
    group = make_stage_proposal().groups[0]
    update = {"reads": [MISSING], "changes": [MISSING, *group.changes[1:]]}
    return make_stage_proposal(groups=[group.model_copy(update=update)], **overrides)


def test_a_good_plan_has_a_key_for_every_gate_and_no_problem() -> None:
    found = check_gates(make_stage_proposal(), KNOWN, TREE)

    assert set(found) == set(ProposalGate)
    assert not any(found.values())


def test_a_missing_spec_delta_is_a_problem_of_the_gate_spec_delta() -> None:
    found = check_gates(make_stage_proposal(specs=[]), KNOWN, TREE)

    assert found[ProposalGate.SPEC_DELTA] == [NO_SPEC_DELTA]
    assert [gate for gate, problems in found.items() if problems] == [ProposalGate.SPEC_DELTA]


def test_a_path_that_no_commit_holds_is_a_problem_of_the_gate_paths() -> None:
    found = check_gates(_reads_a_missing_file(), KNOWN, TREE)

    assert any(MISSING in problem for problem in found[ProposalGate.PATHS])
    assert not found[ProposalGate.SPEC_DELTA]


def test_a_stage_check_change_with_no_replay_task_is_a_problem_of_the_gate_eval_replay() -> None:
    group = make_stage_proposal().groups[0]
    update = {"changes": [*group.changes, STAGE_CHANGE]}
    plan = make_stage_proposal(groups=[group.model_copy(update=update)])

    found = check_gates(plan, KNOWN, StagedTree([*TREE_FILES, STAGE_CHANGE]))

    (problem,) = found[ProposalGate.EVAL_REPLAY]
    assert STAGE_EVAL_REPLAY in problem
    assert [gate for gate, problems in found.items() if problems] == [ProposalGate.EVAL_REPLAY]


def test_check_proposal_joins_the_problems_of_the_gates_in_the_order_of_the_gates() -> None:
    plan = _reads_a_missing_file(specs=[])

    found = check_gates(plan, KNOWN, TREE)

    assert sum(1 for problems in found.values() if problems) >= 2
    assert check_proposal(plan, KNOWN, TREE) == [
        problem for problems in found.values() for problem in problems
    ]
    assert list(found) == list(ProposalGate)
