"""A kept plan holds the trace facts of the run that made it, so the trace gate checks the plan and
each revision of it in a process that made no plan run (#4281)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from devops_cli.exceptions.roadmap import RoadmapStageError
from devops_cli.roadmap.agent_run import RunTrace, ToolCallRecord
from devops_cli.roadmap.stage.stage import PlanFiles, StageTarget, _Planner
from devops_cli.roadmap.stage.stage_change import StageProposal
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.stage.stage_plan_record import (
    StagePlanRecord,
    plan_record_path,
    read_plan_record,
)
from devops_cli.roadmap.stage.stage_request import StageRequest
from devops_cli.roadmap.stage.stage_specs import BaseSpec
from devops_cli.roadmap.stage.stage_toolbox import ToolboxClient
from devops_cli.roadmap.stores.store import Item
from tests.support.builders import make_stage_proposal

PLAN_ROW = "stage"
REPO = "example/repo"
CLAIM = "The run called `read_issue` for the issue and read it."
MISSING = "tests/test_missing.py"


def _call(name: str, **argument: Any) -> ToolCallRecord:
    return ToolCallRecord(name, json.dumps(argument))


class _ScriptedToolbox(ToolboxClient):
    """A toolbox client whose runs are scripted: each call returns the next reply and adds the next
    trace to the shared list, as `ToolboxClient.chat_structured` does."""

    def __init__(self, script: list[tuple[StageProposal, RunTrace]]) -> None:
        self._script = list(script)
        self.traces: list[RunTrace] = []

    def chat_structured(
        self, system: str, prompt: str, schema: type[Any], *, max_retries: int
    ) -> Any:
        proposal, trace = self._script.pop(0)
        self.traces.append(trace)
        return proposal


def _planner(client: ToolboxClient, *, model: str = "model-a") -> _Planner:
    specs = {"comment-thread": BaseSpec(purpose="Defines thread comments.", requirements=())}
    return _Planner(
        client=client,
        source=Path("."),
        sha="",
        specs=specs,
        tree=StagedTree(["src/devops_cli/sample.py"]),
        budget=20000,
        window=100000,
        tool=None,
        plan_files=PlanFiles(REPO, model, "extended"),
    )


def _target() -> StageTarget:
    item = Item(number=1, title="feat: sample", url="https://example.com/1", body="")
    return StageTarget(item, "feat", "sample")


def _request() -> StageRequest:
    return StageRequest(
        number=1,
        title="feat: sample",
        body="",
        context="",
        capabilities=["comment-thread"],
        budget=20000,
    )


def _plan(*, feasibility: list[str] | None = None, unknown_file: bool = False) -> Any:
    group = make_stage_proposal().groups[0]
    if unknown_file:
        group = group.model_copy(update={"changes": [*group.changes, MISSING]})
    return make_stage_proposal(
        groups=[group], feasibility=[CLAIM] if feasibility is None else feasibility
    )


def _file() -> Path:
    return plan_record_path(REPO, 1)


def _kept_by_a_run_that_called_read_issue() -> Any:
    """Run a planner whose one plan run calls `read_issue` and whose plan cites it: the file it
    keeps is the one under test."""
    run = RunTrace(tool_calls=[_call("read_issue", number=7)], row=PLAN_ROW)
    client = _ScriptedToolbox([(_plan(), run)])
    planner = _planner(client)

    planner.plan(_target_with_request(planner))

    return _file()


def _target_with_request(planner: _Planner) -> StageTarget:
    """The target, with the request of the planner stubbed so that the run needs no checkout."""
    planner._request = lambda target: _request()  # type: ignore[method-assign]
    return _target()


def test_a_plan_kept_after_a_run_that_called_a_tool_holds_the_tool_in_its_facts() -> None:
    path = _kept_by_a_run_that_called_read_issue()

    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["facts"] == {"tools": ["read_issue"], "paths": []}


def _write_record(proposal: StageProposal, facts: dict[str, list[str]] | None) -> None:
    """The plan file of item 1 under the key of the planner, with `facts` or, for the format of an
    older job, with no facts field."""
    key = _planner(_ScriptedToolbox([]))._plan_files.key(_target().item)  # type: ignore[union-attr]
    data = StagePlanRecord(key=key, proposal=proposal, request=_request()).model_dump(mode="json")
    if facts is not None:
        data["facts"] = facts
    _file().parent.mkdir(parents=True, exist_ok=True)
    _file().write_text(json.dumps(data), encoding="utf-8")


def test_a_revision_of_a_kept_plan_keeps_the_claims_of_the_run_that_made_it() -> None:
    # In a new process the commit has moved: the kept plan lists a file that the tree lacks, the
    # gates refuse it, and the revision of the planner calls no tool.
    _write_record(_plan(unknown_file=True), {"tools": ["read_issue"], "paths": []})
    fresh = _planner(_ScriptedToolbox([(_plan(), RunTrace(row=PLAN_ROW))]))

    change = fresh.plan(_target_with_request(fresh))

    assert change.proposal.feasibility == [CLAIM]  # type: ignore[union-attr]


def test_a_kept_plan_is_gated_with_its_facts_and_not_skipped() -> None:
    _write_record(_plan(), {"tools": [], "paths": []})
    fresh = _planner(_ScriptedToolbox([(_plan(), RunTrace(row=PLAN_ROW))]))

    with pytest.raises(RoadmapStageError, match="read_issue"):
        fresh.plan(_target_with_request(fresh))


def test_a_record_in_the_old_format_loads_and_is_planned_again() -> None:
    _write_record(_plan(), None)
    key = _planner(_ScriptedToolbox([]))._plan_files.key(_target().item)  # type: ignore[union-attr]
    assert read_plan_record(_file(), key) is not None
    run = RunTrace(tool_calls=[_call("read_issue", number=7)], row=PLAN_ROW)
    client = _ScriptedToolbox([(_plan(), run)])
    fresh = _planner(client)

    fresh.plan(_target_with_request(fresh))

    assert len(client.traces) == 1
    assert json.loads(_file().read_text(encoding="utf-8"))["facts"]["tools"] == ["read_issue"]


def test_the_facts_hold_only_the_paths_that_the_feasibility_cites() -> None:
    cited, other = "src/devops_cli/sample.py", "src/devops_cli/other.py"
    run = RunTrace(
        tool_calls=[_call("read_file", path=cited), _call("read_file", path=other)], row=PLAN_ROW
    )
    plan = _plan(feasibility=[f"The run read `{cited}` and found the function."])
    planner = _planner(_ScriptedToolbox([(plan, run)]))

    planner.plan(_target_with_request(planner))

    data = json.loads(_file().read_text(encoding="utf-8"))
    assert data["facts"] == {"tools": ["read_file"], "paths": [cited]}


def test_a_new_planner_model_is_a_miss() -> None:
    path = _kept_by_a_run_that_called_read_issue()
    run = RunTrace(tool_calls=[_call("read_issue", number=7)], row=PLAN_ROW)
    client = _ScriptedToolbox([(_plan(), run)])
    other = _planner(client, model="model-b")

    other.plan(_target_with_request(other))

    assert len(client.traces) == 1
    assert path.is_file()
