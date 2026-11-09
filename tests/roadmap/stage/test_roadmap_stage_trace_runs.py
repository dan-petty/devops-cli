"""The trace gate reads every planner run of the item, not the last run alone (#4257)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from devops_cli.roadmap.agent_run import RunTrace, ToolCallRecord
from devops_cli.roadmap.stage.stage import StageTarget, _Planner
from devops_cli.roadmap.stage.stage_change import StageProposal
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.stage.stage_request import StageRequest
from devops_cli.roadmap.stage.stage_specs import BaseSpec
from devops_cli.roadmap.stage.stage_toolbox import PLAN_ROW, REVIEW_ROW, ToolboxClient
from devops_cli.roadmap.stores.store import Item
from tests.support.builders import make_stage_proposal

PATH = "src/devops_cli/roadmap/agent_run.py"
SECURITY = "Answers what crosses a trust boundary, what a person must confirm, and what fails."


def _read(path: str, row: str = PLAN_ROW) -> RunTrace:
    return RunTrace(tool_calls=[ToolCallRecord("read_file", json.dumps({"path": path}))], row=row)


class _ScriptedToolbox(ToolboxClient):
    """A toolbox client whose runs are scripted: each call returns the next reply and adds the next
    trace to the shared list, as `ToolboxClient.chat_structured` does."""

    def __init__(self, script: Sequence[tuple[StageProposal, RunTrace]]) -> None:
        self._script = list(script)
        self.traces: list[RunTrace] = []

    def chat_structured(
        self, system: str, prompt: str, schema: type[Any], *, max_retries: int
    ) -> Any:
        proposal, trace = self._script.pop(0)
        self.traces.append(trace)
        return proposal


def _planner(client: ToolboxClient) -> _Planner:
    specs = {"comment-thread": BaseSpec(purpose="Defines thread comments.", requirements=())}
    return _Planner(
        client=client,
        source=Path("."),
        sha="",
        specs=specs,
        tree=StagedTree(["src/devops_cli/sample.py", PATH]),
        budget=20000,
        window=100000,
        tool=None,
    )


def _target_and_request() -> tuple[StageTarget, StageRequest]:
    item = Item(number=1, title="feat: sample", url="https://example.com/1", body="")
    request = StageRequest(
        number=1,
        title="feat: sample",
        body="",
        context="",
        capabilities=["comment-thread"],
        budget=20000,
    )
    return StageTarget(item, "feat", "sample"), request


def _plan(*, security: str) -> StageProposal:
    group = (
        make_stage_proposal()
        .groups[0]
        .model_copy(update={"implementation": "Store the credential in the keyring"})
    )
    return make_stage_proposal(
        groups=[group],
        security=security,
        feasibility=[f"The run read `{PATH}` to confirm the facts."],
    )


def test_a_claim_of_the_first_run_holds_after_the_return() -> None:
    # The first run read the path and its reply was refused for the missing security text. The
    # second run, which makes the corrected reply, reads nothing (#4257).
    client = _ScriptedToolbox(
        [(_plan(security=""), _read(PATH)), (_plan(security=SECURITY), RunTrace(row=PLAN_ROW))]
    )
    target, request = _target_and_request()

    change = _planner(client)._gated(target, request)

    assert change.proposal.security == SECURITY


def test_the_facts_hold_the_calls_of_every_planner_run() -> None:
    client = _ScriptedToolbox([])
    client.traces = [_read(PATH), RunTrace(row=PLAN_ROW)]

    facts = _planner(client)._trace_facts()

    assert facts is not None
    assert facts.paths == {PATH}
    assert facts.tools == {"read_file"}


def test_a_read_of_the_review_supports_no_claim_of_the_planner() -> None:
    client = _ScriptedToolbox([])
    client.traces = [RunTrace(row=PLAN_ROW), _read(PATH, row=REVIEW_ROW)]

    facts = _planner(client)._trace_facts()

    assert facts is not None
    assert facts.paths == frozenset()
    assert facts.tools == frozenset()
