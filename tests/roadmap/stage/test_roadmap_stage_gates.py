"""`check_gates`: the problems of `check_proposal` under the name of the gate that found each
(#3498)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from devops_cli.roadmap.agent_run import RunTrace, ToolCallRecord
from devops_cli.roadmap.stage.stage import RoadmapStageError, StageTarget, _Planner, _Refused
from devops_cli.roadmap.stage.stage_change import (
    STAGE_EVAL_REPLAY,
    ProposalGate,
    StageProposal,
    check_gates,
    check_proposal,
)
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.stage.stage_request import StageRequest
from devops_cli.roadmap.stage.stage_specs import BaseSpec
from devops_cli.roadmap.stage.stage_toolbox import ToolboxClient
from devops_cli.roadmap.stores.store import Item
from tests.support.builders import make_stage_proposal

TREE_FILES = ["src/devops_cli/sample.py"]
TREE = StagedTree(TREE_FILES)
STAGE_CHANGE = "src/devops_cli/roadmap/stage/stage_change.py"
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
    # The group holds its self-acceptance test (#3404), so the gate `content` finds nothing.
    update = {
        "changes": [*group.changes, STAGE_CHANGE],
        "test": "Build a `StageProposal` and assert that `content_problems` finds no problem",
    }
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


def test_a_stale_citation_is_a_problem_of_the_gate_citation() -> None:
    plan = make_stage_proposal(feasibility=["The probe shows `src/sample.py:4:def g():` here."])

    found = check_gates(plan, KNOWN, TREE, read_text={"src/sample.py": "x\n\n\ndef f():\n"}.get)

    assert [gate for gate, problems in found.items() if problems] == [ProposalGate.CITATION]


class _FakeToolboxClient(ToolboxClient):
    def __init__(self, proposal: StageProposal, trace: RunTrace) -> None:
        self._proposal = proposal
        self._trace = trace
        self.traces: list[RunTrace] = [trace]

    def chat_structured(
        self, system: str, prompt: str, schema: type[Any], *, max_retries: int
    ) -> Any:
        self.traces.append(self._trace)
        return self._proposal


def test_planner_gates_proposal_with_trace_facts() -> None:
    path = "src/devops_cli/roadmap/agent_run.py"
    proposal = make_stage_proposal(feasibility=[f"The run read `{path}` to confirm the facts."])
    item = Item(
        number=1,
        title="feat: sample",
        url="https://example.com/1",
        body="",
    )
    target = StageTarget(item, "feat", "sample")
    request = StageRequest(
        number=1,
        title="feat: sample",
        body="",
        context="",
        capabilities=["comment-thread"],
        budget=20000,
    )
    tree = StagedTree([*TREE_FILES, path])
    specs = {"comment-thread": BaseSpec(purpose="Defines thread comments.", requirements=())}

    # Calls read the path: proposal passes the gate.
    call_trace = RunTrace(tool_calls=[ToolCallRecord("read_file", json.dumps({"path": path}))])
    client_with_calls = _FakeToolboxClient(proposal, call_trace)
    planner_with_calls = _Planner(
        client=client_with_calls,
        source=Path("."),
        sha="",
        specs=specs,
        tree=tree,
        budget=20000,
        window=100000,
        tool=None,
    )
    settled = planner_with_calls._settle(
        target, proposal, request, trace=planner_with_calls._trace_facts()
    )
    assert not isinstance(settled, _Refused)

    # Zero-call trace: refused with problem that names the path.
    zero_trace = RunTrace()
    client_zero = _FakeToolboxClient(proposal, zero_trace)
    planner_zero = _Planner(
        client=client_zero,
        source=Path("."),
        sha="",
        specs=specs,
        tree=tree,
        budget=20000,
        window=100000,
        tool=None,
    )
    refused = planner_zero._settle(target, proposal, request, trace=planner_zero._trace_facts())
    assert isinstance(refused, _Refused)
    assert path in refused.problem

    with pytest.raises(RoadmapStageError) as exc_info:
        planner_zero._gated(target, request)
    assert path in str(exc_info.value)
