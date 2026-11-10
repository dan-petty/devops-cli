"""`devops roadmap stage`: the `paths` gate refuses a behavior group that omits the existing test
of a module that it changes (#3414).

The record of the existing tests of each changed module comes from the caller, because the gate
runs no search: the stage job and the plan recheck record it from a checkout, and a check that
holds no checkout passes none and judges nothing. The plan of this change passes the content rule,
as the stage job asks a plan that adds a rule of the plan check.
"""

from __future__ import annotations

from typing import Any

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.stage.stage_change import (
    ProposalGate,
    StageGroup,
    StageProposal,
    check_gates,
    content_problems,
)
from devops_cli.roadmap.stage.stage_paths import StagedTree
from tests.support.builders import make_stage_proposal

MODULE = "src/devops_cli/roadmap/step_files.py"
MODULE_TEST = "tests/roadmap/implement/test_roadmap_implement_step.py"
EXISTING_TEST = "tests/roadmap/stage/test_roadmap_stage_paths.py"
KNOWN = ["comment-thread"]
TREE = StagedTree([EXISTING_TEST, MODULE, MODULE_TEST, "src/devops_cli/sample.py"])
MODULE_TESTS = {MODULE: (MODULE_TEST,)}


def _group(**update: object) -> StageGroup:
    """A behavior group that changes `MODULE` and names no test of that module."""
    base: dict[str, Any] = {
        "title": "Refuse the group in the paths gate",
        "kind": "behavior",
        "reads": [],
        "changes": [MODULE],
        "creates": [],
        "creates_lines": {},
        "test": f"Write `test_the_gate_refuses_the_group` in `{EXISTING_TEST}`",
        "implementation": "Give the `paths` gate the record of the existing tests",
        "documentation": None,
        "verify": f"uv run devops ci test {EXISTING_TEST}",
    }
    return StageGroup.model_validate({**base, **update})


def test_the_paths_gate_refuses_a_group_that_omits_its_module_test() -> None:
    omitted = check_gates(
        make_stage_proposal(groups=[_group()]),
        KNOWN,
        TREE,
        module_tests=MODULE_TESTS,
    )
    listed = check_gates(
        make_stage_proposal(groups=[_group(reads=[MODULE_TEST])]),
        KNOWN,
        TREE,
        module_tests=MODULE_TESTS,
    )

    (problem,) = omitted[ProposalGate.PATHS]
    assert problem == MESSAGES.roadmap.stage_problem_missing_module_test.format(
        group=1, path=MODULE, test=MODULE_TEST
    )
    assert listed[ProposalGate.PATHS] == []


def test_the_paths_gate_judges_no_module_test_when_the_caller_passes_no_record() -> None:
    found = check_gates(make_stage_proposal(groups=[_group()]), KNOWN, TREE)

    assert found[ProposalGate.PATHS] == []


PLAN_OF_THIS_CHANGE: dict[str, Any] = {
    "summary": "Refuse a behavior group that omits its test",
    "pull_request_body": (
        "The stage plan check names each path of a plan but never the existing test that the change "
        "will break. A plan that names only the test it creates passes every check, and the "
        "implement job then meets a failing test with no name for it in the plan. The `paths` gate "
        "now refuses such a group and names the group, the module and the test."
    ),
    "why": (
        "Issue #3414: the stage plan validation checks that each path a plan names exists at the "
        "staged commit, and it never checks that the plan names the existing test that the change "
        "will break."
    ),
    "what_changes": [
        "`src/devops_cli/roadmap/stage/stage_paths.py` records the existing tests of each module that a behavior group changes, and refuses a group that names none of them.",
        "`src/devops_cli/lang/en/messages.py` gains the message of the new problem.",
        "`src/devops_cli/roadmap/stage/stage_change.py` gives the `paths` gate the record when the caller passes it.",
        "`src/devops_cli/roadmap/stage/stage_request.py` and `src/devops_cli/roadmap/stage/stage.py` carry the record to the gates of the job.",
        "`src/devops_cli/roadmap/plan_recheck.py` carries the record to the gates of the merged plan.",
        "`docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/plan-check.md` state the rule.",
    ],
    "skip_specs": False,
    "feasibility": [
        "The premise holds at the staged paths, and the probe answers word for word: The path `tests/roadmap/test_roadmap_implement_step.py` is no file at the root of the staging commit. These files of the commit are candidates: `tests/roadmap/implement/test_roadmap_implement_step.py`. Commit bff2f14fd 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it.",
        "The probe moves the source path the same way: The path `src/devops_cli/roadmap/implement_step.py` is no file at the root of the staging commit. These files of the commit are candidates: `src/devops_cli/roadmap/implement/implement_step.py`, `tests/support/implement_step.py`. Commit bff2f14fd 2026-11-06 refactor(roadmap): group the job modules in subpackages (#3897) deleted or renamed it.",
        "The probe keeps the third path of the issue: The path `src/devops_cli/roadmap/step_files.py` is a file of the staging commit. The fourth path of the issue is no file either, and `list_files` of `src/devops_cli/roadmap/stage` listed `stage_paths.py` in that folder, so the rule goes in `src/devops_cli/roadmap/stage/stage_paths.py`.",
        "The defect of the issue holds at the staged commit: `search_code` for `roadmap.step_files` gave `tests/roadmap/implement/test_roadmap_implement_step.py:61:from devops_cli.roadmap.step_files import parse_task_groups`, so a plan that changes `src/devops_cli/roadmap/step_files.py` and names no `tests/roadmap/implement/test_roadmap_implement_step.py` passes every stage check today.",
        "The path check has no such rule: `read_file` of `src/devops_cli/roadmap/stage/stage_paths.py` showed `src/devops_cli/roadmap/stage/stage_paths.py:446:def path_problems`, which reports a named path that the tree lacks and that no group creates, and it never reads the test of a group.",
        "The rule joins the `paths` gate: `read_file` of `src/devops_cli/roadmap/stage/stage_change.py` showed `src/devops_cli/roadmap/stage/stage_change.py:1890:def check_gates(` with `src/devops_cli/roadmap/stage/stage_change.py:1927:*path_problems(proposal.groups, tree, manifest_references, change=change),`.",
        'The record has a model in the staged tree: `read_file` of `src/devops_cli/roadmap/stage/stage_paths.py` showed `src/devops_cli/roadmap/stage/stage_paths.py:377:def record_module_tests(` with `src/devops_cli/roadmap/stage/stage_paths.py:78:_TEST_MODULE_PATTERNS: Final[tuple[str, ...]] = ("test_*.py", "*_test.py")`.',
        "The record comes from the caller: `src/devops_cli/roadmap/stage/stage_request.py:def gate_arguments` is a pure function of the request and the record, and `src/devops_cli/roadmap/plan_recheck.py:345:manifest_references=record_test_references(proposal.groups, shared.test_search),` shows the shape that the recheck passes.",
    ],
    "existing_tool": (
        "No open, maintained tool or library covers this rule: it reads the `src/` layout and the "
        "`tests/` naming convention of this repository and runs inside the stage job with no test "
        "suite. The change builds its own check at a written cost of about 6,000 tokens to build, "
        "keep and fix it, and about 1 hour of elapsed time, and it deletes no internal code."
    ),
    "builds_own": True,
    "decisions": [
        {
            "decision": "Record the existing tests of each changed module in the caller, and refuse the group in the `paths` gate",
            "reason": "The `paths` gate is the one rule set of the stage job and the plan recheck, and a caller that runs no search passes no record and judges nothing.",
        },
        {
            "decision": "Take a candidate test from both the test naming convention and the search of the module name",
            "reason": "`tests/roadmap/implement/test_roadmap_implement_step.py` imports `devops_cli.roadmap.step_files` and its name carries no stem of that module, so the naming convention alone misses the test of the issue.",
        },
        {
            "decision": "Count a test as named when the group lists it in `reads`, `changes`, a task code span or `verify`",
            "reason": "A group reads a test that pins a module it changes and must not edit it, so a rule over `changes` alone would refuse a correct plan.",
        },
        {
            "decision": "Compare `group.kind` with the string `behavior`",
            "reason": "`stage_paths.py` reads `StageGroup` only under `TYPE_CHECKING`, and a runtime import of `GroupKind` from `stage_change.py` would close the cycle between the two modules.",
        },
    ],
    "rejected": [
        {
            "alternative": "Extend `path_problems` itself with the rule",
            "evidence": "`src/devops_cli/roadmap/stage/stage_paths.py:446:def path_problems` reports a path once and skips a path that an earlier place reported, so one group with two changed modules would give one sentence with no list of the tests to add.",
        },
        {
            "alternative": "Search the checkout inside the gate",
            "evidence": "`src/devops_cli/roadmap/stage/stage_eval_gates.py` builds its tree from the case and runs no git, so the record has to come from the caller.",
        },
        {
            "alternative": "Require the existing test in `changes` only",
            "evidence": "A group reads a test that pins the module it changes and must not edit it, so `changes` alone refuses a correct plan.",
        },
    ],
    "specs": [
        {
            "capability": "roadmap-stage",
            "added": [
                {
                    "name": "Refuse a behavior group that omits the test of its module",
                    "text": "The stage plan validation SHALL refuse a behavior group that changes an existing Python module under `src/` and names no test file of the staged tree that imports that module or carries the stem of the module in the test naming convention.",
                    "scenarios": [
                        {
                            "name": "A source change names only a new test",
                            "when": "a behavior group changes `src/devops_cli/roadmap/stage/stage_paths.py` and names only the test file it creates, while `tests/roadmap/stage/test_roadmap_stage_paths.py` imports that module",
                            "then": "`existing_test_problems` returns one problem that names the group, the module and that test",
                        }
                    ],
                },
                {
                    "name": "Accept a behavior group that names the test of its module",
                    "text": "The stage plan validation SHALL accept a behavior group that changes an existing Python module under `src/` and names at least one test file of the staged tree that imports that module or carries the stem of the module in the test naming convention.",
                    "scenarios": [
                        {
                            "name": "The named test imports the module and its file name differs from the module name",
                            "when": "a behavior group changes `src/devops_cli/roadmap/stage/stage_paths.py` and lists `tests/roadmap/stage/test_roadmap_stage_paths.py` in its `reads`",
                            "then": "`existing_test_problems` returns no problem for that group",
                        }
                    ],
                },
                {
                    "name": "Exempt a module that has no existing test",
                    "text": "The stage plan validation SHALL accept a behavior group that changes an existing Python module under `src/` when the staged tree holds no test file that imports that module and no test file that carries the stem of the module in the test naming convention.",
                    "scenarios": [
                        {
                            "name": "An existing module has no existing test",
                            "when": "a behavior group changes a module of `src/` and the staged tree holds no test file of that module",
                            "then": "`existing_test_problems` returns no problem for that group",
                        }
                    ],
                },
                {
                    "name": "Leave out the test files that the plan creates",
                    "text": "The stage plan validation MUST leave out every test path that a group lists in `creates`, so that a test file that the plan creates is no existing test.",
                    "scenarios": [
                        {
                            "name": "The plan creates the only test of a module it also changes",
                            "when": "a behavior group changes an existing module and creates the only test file that imports it",
                            "then": "the created test is no existing test, and `existing_test_problems` returns no problem for that group",
                        }
                    ],
                },
                {
                    "name": "Report one problem for each group that omits its test",
                    "text": "The stage plan validation SHALL report one problem for each behavior group that omits an existing test file of a module it changes.",
                    "scenarios": [
                        {
                            "name": "Two groups omit their existing tests",
                            "when": "two behavior groups each change an existing module of `src/` and name no existing test of it",
                            "then": "`existing_test_problems` returns one problem for each group",
                        }
                    ],
                },
            ],
        }
    ],
    "groups": [
        {
            "title": "Record the existing tests of a changed module",
            "kind": "behavior",
            "reads": [
                "src/devops_cli/roadmap/stage/stage_paths.py",
                "src/devops_cli/lang/en/messages.py",
                "tests/roadmap/stage/test_roadmap_stage_paths.py",
                "tests/support/builders.py",
            ],
            "changes": [
                "src/devops_cli/roadmap/stage/stage_paths.py",
                "src/devops_cli/lang/en/messages.py",
                "tests/roadmap/stage/test_roadmap_stage_paths.py",
            ],
            "creates": [],
            "creates_lines": {},
            "test": (
                "In `tests/roadmap/stage/test_roadmap_stage_paths.py`, write "
                "`test_a_behavior_group_that_omits_the_test_of_its_module_is_refused` first, and it "
                "fails on the base because `src/devops_cli/roadmap/stage/stage_paths.py` holds no "
                "`record_module_tests` and no `existing_test_problems`: the record gives "
                "`tests/roadmap/stage/test_roadmap_stage_paths.py` for "
                "`src/devops_cli/roadmap/stage/stage_paths.py` from a search that returns it, and the "
                "problem names the group, the module and the test"
            ),
            "implementation": (
                "Add `record_module_tests` and `existing_test_problems` to "
                "`src/devops_cli/roadmap/stage/stage_paths.py`, beside `path_problems`, and add the "
                "message `stage_problem_missing_module_test` to `MESSAGES.roadmap` in "
                "`src/devops_cli/lang/en/messages.py`"
            ),
            "documentation": None,
            "verify": "uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py",
        },
        {
            "title": "Refuse the group in the paths gate of the plan check",
            "kind": "behavior",
            "reads": [
                "src/devops_cli/roadmap/stage/stage_change.py",
                "src/devops_cli/roadmap/stage/stage_paths.py",
                "tests/roadmap/stage/test_roadmap_stage_paths.py",
                "tests/roadmap/stage/test_roadmap_stage_self_acceptance.py",
                "tests/support/builders.py",
            ],
            "changes": [
                "src/devops_cli/roadmap/stage/stage_change.py",
                "tests/roadmap/stage/test_roadmap_stage_module_tests.py",
            ],
            "creates": ["tests/roadmap/stage/test_roadmap_stage_module_tests.py"],
            "creates_lines": {"tests/roadmap/stage/test_roadmap_stage_module_tests.py": 120},
            "test": (
                "In `tests/roadmap/stage/test_roadmap_stage_module_tests.py`, write "
                "`test_the_paths_gate_refuses_a_group_that_omits_its_module_test` first, and it "
                "fails on the base because `check_gates` takes no `module_tests`: it gives one "
                "problem under `paths` for a behavior group that changes "
                "`src/devops_cli/roadmap/step_files.py` and names no test when the record names "
                "`tests/roadmap/implement/test_roadmap_implement_step.py`, and none once the group "
                "lists that test. Add `test_the_plan_of_this_change_passes_the_content_rule`, which "
                "builds the plan's own `StageProposal`, calls `content_problems` and asserts that it "
                "gives no problem"
            ),
            "implementation": (
                "Add the keyword `module_tests` to `check_gates` and `check_proposal` in "
                "`src/devops_cli/roadmap/stage/stage_change.py`, pass it in `check_proposal`, and add "
                "`existing_test_problems(proposal.groups, tree, module_tests)` to the list of the "
                "`paths` gate after `path_problems`"
            ),
            "documentation": None,
            "verify": "uv run devops ci test tests/roadmap/stage/test_roadmap_stage_module_tests.py",
        },
    ],
    "criteria": [],
    "dependencies": [],
    "security": (
        "The new rule reads the paths of a plan and the text of the tests of a checkout, and it "
        "touches no cluster."
    ),
}


def test_the_plan_of_this_change_passes_the_content_rule() -> None:
    plan = StageProposal.model_validate(PLAN_OF_THIS_CHANGE)

    assert content_problems(plan) == []
