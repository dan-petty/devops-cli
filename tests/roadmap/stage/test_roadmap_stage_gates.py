"""`check_gates`: the problems of `check_proposal` under the name of the gate that found each
(#3498)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pytest

from devops_cli.roadmap.agent_run import RunTrace, ToolCallRecord
from devops_cli.roadmap.stage.stage import RoadmapStageError, StageTarget, _Planner, _Refused
from devops_cli.roadmap.stage.stage_change import (
    STAGE_EVAL_LIVE,
    STAGE_EVAL_REPLAY,
    ProposalGate,
    StageProposal,
    check_gates,
    check_proposal,
    content_problems,
)
from devops_cli.roadmap.stage.stage_paths import StagedTree
from devops_cli.roadmap.stage.stage_registry import RegistryCount
from devops_cli.roadmap.stage.stage_request import StageRequest
from devops_cli.roadmap.stage.stage_specs import BaseSpec
from devops_cli.roadmap.stage.stage_toolbox import ToolboxClient
from devops_cli.roadmap.stores.store import Item
from tests.support.builders import make_stage_proposal
from tests.support.paths import REPO_ROOT

if TYPE_CHECKING:
    from tests.support.roadmap_stage import StageRepo

PLAN_ROW = "stage"  # The job row of a plan run.
TREE_FILES = ["src/devops_cli/sample.py"]
TREE = StagedTree(TREE_FILES)
STAGE_CHANGE = "src/devops_cli/roadmap/stage/stage_change.py"
STAGE_PROMPT = "src/devops_cli/ai/tasks/roadmap_stage_change.md"
PROMPT_RULES = "tests/roadmap/stage/test_roadmap_stage_prompt_rules.py"
STAGE_TREE = StagedTree([*TREE_FILES, STAGE_CHANGE, STAGE_PROMPT, PROMPT_RULES])
MODULE_FILE = "src/devops_cli/roadmap/step_files.py"
MESSAGES_FILE = "src/devops_cli/lang/en/messages.py"
TEST_FILE = "tests/roadmap/stage/test_roadmap_stage_gates.py"
MODULE_TREE = StagedTree([*TREE_FILES, MODULE_FILE])
KNOWN = ["comment-thread"]
MISSING = "src/devops_cli/missing.py"
NO_SPEC_DELTA = "skip_specs is false, and the reply gives no spec delta."
DEFECT = "- The earlier reply was wrong to read the probe answer as a false premise."
QUOTE = f"> {DEFECT}"


def _staged_module(path: str) -> str | None:
    """The text of a module of the checkout, as the citation gate reads the staged commit."""
    file = REPO_ROOT / path
    return file.read_text(encoding="utf-8") if file.is_file() else None


def _module_plan(line: str) -> StageProposal:
    """The stock plan with one feasibility line that names a module of `src/`."""
    return make_stage_proposal(feasibility=[line])


def test_the_module_quote_rule_accepts_the_plan_of_this_change() -> None:
    """The plan's own acceptance test (#3404): the plan extends the plan check, so it builds its
    own `StageProposal` and asserts that `content_problems` returns no problem for it."""
    group = (
        make_stage_proposal()
        .groups[0]
        .model_copy(
            update={
                "title": "Refuse a claim line that names a module with no statement",
                "reads": [MODULE_FILE, TEST_FILE],
                "changes": [STAGE_CHANGE, MESSAGES_FILE, TEST_FILE],
                "creates": [TEST_FILE],
                "creates_lines": {TEST_FILE: 70},
                "test": (
                    "Write `test_the_module_quote_rule_accepts_the_plan_of_this_change` in "
                    f"`{TEST_FILE}` first, build the plan's own `StageProposal`, assert that "
                    "`content_problems` returns no problem for it, and refuse a `feasibility` "
                    f"line that names `{MODULE_FILE}` with no statement; it fails on the base"
                ),
                "implementation": (
                    "Add `module_quote_problems` to "
                    "`src/devops_cli/roadmap/stage/stage_change.py` and call it in the "
                    "`citation` gate"
                ),
                "verify": f"uv run devops ci test {TEST_FILE}",
            }
        )
    )
    plan = make_stage_proposal(
        summary="Refuse a module claim with no statement",
        why=(
            "Issue #3458: the plan of #3417 named `src/devops_cli/roadmap/step_files.py` and gave "
            "no statement of that module."
        ),
        what_changes=[
            f"`{STAGE_CHANGE}` refuses a claim line that names a module with no statement.",
            f"`{MESSAGES_FILE}` gains the message of the module-quote problem.",
            f"`{TEST_FILE}` pins the rule.",
        ],
        feasibility=[
            f"`read_file` of `{MODULE_FILE}` showed `class TaskGroup:`, so the module holds the "
            "group parser."
        ],
        existing_tool=(
            "No open tool covers the check, so the change builds it: about 2,000 tokens to build, "
            "1,000 tokens for each later fix, and about 30 minutes of elapsed time."
        ),
        groups=[group],
        builds_own=True,
    )

    assert content_problems(plan) == []


def test_the_meta_text_rule_accepts_the_plan_of_this_change() -> None:
    """The plan's own acceptance test (#3404): the plan adds the gate `meta-text`, so it builds
    its own `StageProposal`, whose Feasibility section quotes the defect inside a block quotation,
    and asserts that `content_problems` returns no problem for it. A line of prose with the same
    words is the one problem of the gate `meta-text`, with its line and its phrase (#4111)."""
    plan = make_stage_proposal(feasibility=[QUOTE])

    assert content_problems(plan) == []
    assert check_gates(plan, KNOWN, TREE, registry=())[ProposalGate.META_TEXT] == []

    found = check_gates(make_stage_proposal(feasibility=[DEFECT]), KNOWN, TREE, registry=())

    assert ProposalGate.META_TEXT == "meta-text"
    (problem,) = found[ProposalGate.META_TEXT]
    assert "line 1" in problem
    assert "earlier reply" in problem
    assert [gate for gate, problems in found.items() if problems] == [ProposalGate.META_TEXT]

    twice = check_gates(
        make_stage_proposal(feasibility=[DEFECT, "I apologize for the previous turn."]),
        KNOWN,
        TREE,
        registry=(),
    )

    first, second = twice[ProposalGate.META_TEXT]
    assert ("line 1" in first, "earlier reply" in first) == (True, True)
    assert ("line 2" in second, "previous turn" in second) == (True, True)


def _reads_a_missing_file(**overrides: object) -> StageProposal:
    """The stock plan with a group that reads and changes a file that no commit holds."""
    group = make_stage_proposal().groups[0]
    update = {"reads": [MISSING], "changes": [MISSING, *group.changes[1:]]}
    return make_stage_proposal(groups=[group.model_copy(update=update)], **overrides)


def test_a_good_plan_has_a_key_for_every_gate_and_no_problem() -> None:
    found = check_gates(make_stage_proposal(), KNOWN, TREE, registry=())

    assert set(found) == set(ProposalGate)
    assert not any(found.values())


def test_a_missing_spec_delta_is_a_problem_of_the_gate_spec_delta() -> None:
    found = check_gates(make_stage_proposal(specs=[]), KNOWN, TREE, registry=())

    assert found[ProposalGate.SPEC_DELTA] == [NO_SPEC_DELTA]
    assert [gate for gate, problems in found.items() if problems] == [ProposalGate.SPEC_DELTA]


def test_a_path_that_no_commit_holds_is_a_problem_of_the_gate_paths() -> None:
    found = check_gates(_reads_a_missing_file(), KNOWN, TREE, registry=())

    assert any(MISSING in problem for problem in found[ProposalGate.PATHS])
    assert not found[ProposalGate.SPEC_DELTA]


def test_a_stage_check_change_with_no_replay_task_is_a_problem_of_the_gate_eval_replay() -> None:
    group = make_stage_proposal().groups[0]
    # The group holds its self-acceptance test (#3404) and gate defect quote (#3386),
    # so the gate `content` finds nothing.
    update = {
        "changes": [*group.changes, STAGE_CHANGE],
        "test": (
            "Build a `StageProposal` and assert that `content_problems` finds no problem, "
            "and that `src/devops_cli/sample.py` fails on the base"
        ),
    }
    plan = make_stage_proposal(groups=[group.model_copy(update=update)])

    found = check_gates(plan, KNOWN, StagedTree([*TREE_FILES, STAGE_CHANGE]), registry=())

    (problem,) = found[ProposalGate.EVAL_REPLAY]
    assert STAGE_EVAL_REPLAY in problem
    assert [gate for gate, problems in found.items() if problems] == [ProposalGate.EVAL_REPLAY]


def _prompt_plan(*commands: str) -> StageProposal:
    group = make_stage_proposal().groups[0]
    update = {
        "changes": [*group.changes, STAGE_PROMPT],
        "reads": [*group.reads, PROMPT_RULES],
        "test": (
            "Build a `StageProposal` and assert that `content_problems` finds no problem, "
            "and that `src/devops_cli/sample.py` fails on the base"
        ),
        "implementation": " ".join(commands),
        "verify": "uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py",
    }
    return make_stage_proposal(groups=[group.model_copy(update=update)])


def test_a_prompt_change_with_the_replay_names_the_live_command() -> None:
    plan = _prompt_plan(
        "Run `uv run devops roadmap eval stage --replay` and state the score before and after."
    )

    found = check_gates(plan, KNOWN, STAGE_TREE, registry=())

    (problem,) = found[ProposalGate.EVAL_REPLAY]
    assert STAGE_EVAL_LIVE in problem
    assert [gate for gate, problems in found.items() if problems] == [ProposalGate.EVAL_REPLAY]


def test_a_prompt_change_with_a_bounded_live_run_is_accepted() -> None:
    for command in (
        "Run `uv run devops roadmap eval stage --limit 3` and state the score before and after.",
        "Run `uv run devops roadmap eval stage --case 2260` and state the score before and after.",
    ):
        plan = _prompt_plan(command)

        found = check_gates(plan, KNOWN, STAGE_TREE, registry=())

        assert found[ProposalGate.EVAL_REPLAY] == []


def test_a_prompt_change_that_states_no_score_is_a_problem_that_names_the_live_command() -> None:
    plan = _prompt_plan("Run `uv run devops roadmap eval stage --limit 3`.")

    found = check_gates(plan, KNOWN, STAGE_TREE, registry=())

    (problem,) = found[ProposalGate.EVAL_REPLAY]
    assert STAGE_EVAL_LIVE in problem


def test_a_plan_that_changes_the_prompt_and_a_gate_needs_both_commands() -> None:
    group = make_stage_proposal().groups[0]
    plan = _prompt_plan(
        "Run `uv run devops roadmap eval stage --replay` and state the score before and after."
    )
    plan = plan.model_copy(
        update={
            "groups": [
                plan.groups[0].model_copy(
                    update={"changes": [*group.changes, STAGE_PROMPT, STAGE_CHANGE]}
                )
            ]
        }
    )

    found = check_gates(plan, KNOWN, STAGE_TREE, registry=())

    (problem,) = found[ProposalGate.EVAL_REPLAY]
    assert STAGE_EVAL_LIVE in problem


def test_check_proposal_joins_the_problems_of_the_gates_in_the_order_of_the_gates() -> None:
    plan = _reads_a_missing_file(specs=[])

    found = check_gates(plan, KNOWN, TREE, registry=())

    assert sum(1 for problems in found.values() if problems) >= 2
    assert check_proposal(plan, KNOWN, TREE, registry=()) == [
        problem for problems in found.values() for problem in problems
    ]
    assert list(found) == list(ProposalGate)


def test_a_stale_citation_is_a_problem_of_the_gate_citation() -> None:
    plan = make_stage_proposal(feasibility=["The probe shows `src/sample.py:4:def g():` here."])

    found = check_gates(
        plan, KNOWN, TREE, read_text={"src/sample.py": "x\n\n\ndef f():\n"}.get, registry=()
    )

    assert [gate for gate, problems in found.items() if problems] == [ProposalGate.CITATION]


def test_a_claim_line_that_names_a_module_with_no_statement_is_refused() -> None:
    plan = _module_plan(f"The probe of `{MODULE_FILE}` confirms the group parser.")

    found = check_gates(plan, KNOWN, MODULE_TREE, read_text=_staged_module, registry=())

    (problem,) = found[ProposalGate.CITATION]
    assert MODULE_FILE in problem
    assert [gate for gate, problems in found.items() if problems] == [ProposalGate.CITATION]


def test_a_claim_line_that_quotes_its_module_passes() -> None:
    plan = _module_plan(
        f"The probe of `{MODULE_FILE}` confirms the group parser, as `class TaskGroup:` shows."
    )

    found = check_gates(plan, KNOWN, MODULE_TREE, read_text=_staged_module, registry=())

    assert found[ProposalGate.CITATION] == []
    assert not any(found.values())


def test_a_quote_that_the_staged_module_lacks_is_refused() -> None:
    plan = _module_plan(f"The probe of `{MODULE_FILE}` shows `kind: str` in the group parser.")

    found = check_gates(plan, KNOWN, MODULE_TREE, read_text=_staged_module, registry=())

    (problem,) = found[ProposalGate.CITATION]
    assert MODULE_FILE in problem


def test_a_claim_line_that_names_no_module_is_not_judged() -> None:
    plan = _module_plan("The probe shows the group parser at the first line of the file.")

    found = check_gates(plan, KNOWN, MODULE_TREE, read_text=_staged_module, registry=())

    assert found[ProposalGate.CITATION] == []


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


def test_planner_gates_proposal_with_trace_facts(stage_repo: StageRepo) -> None:
    path = "src/devops_cli/roadmap/agent_run.py"
    proposal = make_stage_proposal(
        feasibility=[f"The run read `{path}` to confirm the facts, as `class RunTrace:` shows."]
    )
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
    call_trace = RunTrace(
        tool_calls=[ToolCallRecord("read_file", json.dumps({"path": path}))], row=PLAN_ROW
    )
    client_with_calls = _FakeToolboxClient(proposal, call_trace)
    planner_with_calls = _Planner(
        client=client_with_calls,
        source=stage_repo.clone,
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
    zero_trace = RunTrace(row=PLAN_ROW)
    client_zero = _FakeToolboxClient(proposal, zero_trace)
    planner_zero = _Planner(
        client=client_zero,
        source=stage_repo.clone,
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


def test_check_gates_and_check_proposal_require_registry_keyword_argument() -> None:
    """check_gates and check_proposal raise TypeError when registry is omitted (#4695)."""
    proposal = make_stage_proposal()
    with pytest.raises(TypeError, match="registry"):
        cast(Any, check_gates)(proposal, KNOWN, TREE)

    with pytest.raises(TypeError, match="registry"):
        cast(Any, check_proposal)(proposal, KNOWN, TREE)


def test_the_registry_gate_judges_the_passed_table_not_the_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gate judges the passed registry table and never the process directory (#4695)."""
    from devops_cli.roadmap.stage.stage_change import StageGroup

    workdir = tmp_path / "workdir"
    workdir.mkdir()
    (workdir / "tests").mkdir()
    (workdir / "tests" / "test_workdir.py").write_text(
        'REGISTRY_COUNTS = (("ratchet", "workdir_token", "tests/test_w.py"),)\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(workdir)

    judged_table = (
        RegistryCount(
            kind="ratchet",
            token="judged_token",
            path="tests/test_judged.py",
            line=5,
            declaring_path="tests/test_judged_decl.py",
        ),
    )
    group = StageGroup.model_validate(
        {
            "kind": "behavior",
            "title": "A group mentioning both tokens",
            "test": "Check judged_token and workdir_token in test.",
            "implementation": "Do work.",
            "documentation": "Docs.",
            "changes": ["src/devops_cli/sample.py"],
            "reads": [],
            "creates": [],
            "verify": "uv run pytest tests/test_sample.py",
        }
    )
    plan = make_stage_proposal(groups=[group])
    problems = check_proposal(plan, KNOWN, TREE, registry=judged_table)

    assert any("judged_token" in p and "tests/test_judged.py" in p for p in problems)
    assert not any("workdir_token" in p for p in problems)
