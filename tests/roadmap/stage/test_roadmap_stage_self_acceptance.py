"""`devops roadmap stage`: the plan of #3972 passes the content rule of the plan check.

The plan adds a rule of the plan check, so the stage job asks it for a test that builds its own
`StageProposal` and asserts that `content_problems` gives no problem (#3404). The plan below is
the plan of this change, with its four groups, as the stage job reads it.
"""

from __future__ import annotations

from typing import Any

from devops_cli.roadmap.stage.stage_change import StageProposal, content_problems

PLAN_OF_THIS_CHANGE: dict[str, Any] = {
    "summary": "Stage names the test of a manifest plan",
    "pull_request_body": (
        "The stage job leaves out the tests that assert on a manifest it plans to change, and the "
        "implement job cannot edit a test outside its `Changes:` list. The plan check now refuses "
        "a manifest plan that leaves such a test out."
    ),
    "why": (
        "Issue #3972: the stage job plans a change of a perimeter network policy with no test that "
        "asserts on it, and the implement job loops until the item stops blocked."
    ),
    "what_changes": [
        "`src/devops_cli/roadmap/stage/stage_paths.py` records the tests that each changed manifest reaches and refuses a plan that leaves one out.",
        "`src/devops_cli/lang/en/messages.py` gains the message of the new problem.",
        "The stage job, the replay and the plan recheck pass the record to the plan check.",
        "`docs/ROADMAP_WORKFLOW.md` and `docs/roadmap/plan-check.md` state the rule.",
    ],
    "skip_specs": False,
    "feasibility": [
        "The path `k8s/logging/networkpolicy.yaml` is a file of the staging commit, and `tests/commands/k8s/test_k8s_logging_stack.py` asserts on its two egress rules.",
        "`src/devops_cli/roadmap/stage/stage_paths.py:def path_problems` joins the path checks, and `check_gates` gives its result to the `paths` gate.",
        "`src/devops_cli/roadmap/stage/stage_form.py:def record_search_evidence` records a staged search for the gates, so the new record follows the same shape.",
    ],
    "existing_tool": (
        "No open tool covers the check, so the change builds its own code at a cost of about 150k "
        "tokens to build, keep and fix it, and about 16 hours of elapsed time."
    ),
    "builds_own": True,
    "decisions": [
        {
            "decision": "Record the tests that each changed manifest reaches, and refuse the plan in the path check",
            "reason": "The path check already refuses a plan that leaves out a caller file, and the replay reads the record from its case.",
        }
    ],
    "rejected": [
        {
            "alternative": "Search the checkout inside the path check and leave the replay out",
            "evidence": "`src/devops_cli/roadmap/stage/stage_eval_gates.py:class PlanUnderTest` builds its tree from the case and runs no git.",
        }
    ],
    "specs": [
        {
            "capability": "roadmap-stage",
            "modified": [
                {
                    "name": "A manifest plan names the tests that reference it",
                    "text": "A plan that changes a YAML manifest under `k8s/` SHALL name every test file that references the manifest.",
                    "scenarios": [
                        {
                            "name": "The omitted test",
                            "when": "a plan changes `k8s/logging/networkpolicy.yaml` and leaves out a test that holds its name and its folder",
                            "then": "the path check refuses the plan and names the test",
                        }
                    ],
                }
            ],
        }
    ],
    "groups": [
        {
            "title": "Record the tests that a changed manifest reaches",
            "kind": "behavior",
            "reads": [
                "src/devops_cli/roadmap/stage/stage_paths.py",
                "src/devops_cli/lang/en/messages.py",
                "tests/roadmap/stage/test_roadmap_stage_paths.py",
                "tests/support/roadmap_stage.py",
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
                "`test_the_record_names_the_test_that_builds_the_path_from_its_parts` first, with a "
                "temporary checkout that holds `k8s/logging/networkpolicy.yaml`, a test file whose "
                "text holds `logging` and `networkpolicy.yaml` in separate strings, and a test file "
                "whose text holds `logging` alone"
            ),
            "implementation": (
                "Add `record_test_references` and `missing_reference_problems` to "
                "`src/devops_cli/roadmap/stage/stage_paths.py`, give `path_problems` the record as an "
                "optional argument, and add the message `stage_problem_missing_perimeter_test` to "
                "`MESSAGES.roadmap` in `src/devops_cli/lang/en/messages.py`"
            ),
            "documentation": None,
            "verify": "uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py",
        },
        {
            "title": "Refuse a manifest plan that omits its reference",
            "kind": "behavior",
            "reads": [
                "src/devops_cli/roadmap/stage/stage_paths.py",
                "src/devops_cli/roadmap/stage/stage_change.py",
                "src/devops_cli/roadmap/plan_recheck.py",
                "tests/roadmap/stage/test_roadmap_stage_paths.py",
                "tests/support/builders.py",
            ],
            "changes": [
                "src/devops_cli/roadmap/stage/stage_change.py",
                "src/devops_cli/roadmap/plan_recheck.py",
                "tests/roadmap/stage/test_roadmap_stage_paths.py",
            ],
            "creates": [],
            "creates_lines": {},
            "test": (
                "In `tests/roadmap/stage/test_roadmap_stage_paths.py`, write "
                "`test_a_manifest_plan_that_omits_its_test_is_refused` first: `check_gates` gives "
                "one `paths` problem for a group that changes `k8s/logging/networkpolicy.yaml` when "
                "the record names a test and the plan lists only the manifest"
            ),
            "implementation": (
                "Add the keyword `manifest_references` to `check_gates` and `check_proposal` in "
                "`src/devops_cli/roadmap/stage/stage_change.py`, pass it to the `paths` gate, and "
                "pass the record in `_record` of `src/devops_cli/roadmap/plan_recheck.py`"
            ),
            "documentation": None,
            "verify": "uv run devops ci test tests/roadmap/stage/test_roadmap_stage_paths.py",
        },
        {
            "title": "Record the references in the job and the replay",
            "kind": "behavior",
            "reads": [
                "src/devops_cli/roadmap/stage/stage.py",
                "src/devops_cli/roadmap/stage/stage_request.py",
                "src/devops_cli/roadmap/stage/stage_eval_cases.py",
                "src/devops_cli/roadmap/stage/stage_eval_gates.py",
                "tests/roadmap/stage/test_roadmap_stage_eval_gates.py",
                "tests/roadmap/stage/test_roadmap_stage_request.py",
            ],
            "changes": [
                "src/devops_cli/roadmap/stage/stage.py",
                "src/devops_cli/roadmap/stage/stage_request.py",
                "src/devops_cli/roadmap/stage/stage_eval_cases.py",
                "src/devops_cli/roadmap/stage/stage_eval_gates.py",
                "tests/roadmap/stage/test_roadmap_stage_eval_gates.py",
                "tests/roadmap/stage/test_roadmap_stage_request.py",
                "tests/roadmap/stage/test_roadmap_stage_self_acceptance.py",
            ],
            "creates": ["tests/roadmap/stage/test_roadmap_stage_self_acceptance.py"],
            "creates_lines": {"tests/roadmap/stage/test_roadmap_stage_self_acceptance.py": 200},
            "test": (
                "In `tests/roadmap/stage/test_roadmap_stage_self_acceptance.py`, write "
                "`test_this_plan_passes_the_content_gate` first: it builds the `StageProposal` of "
                "this plan with its four groups, calls `content_problems` and asserts that it gives "
                "no problem"
            ),
            "implementation": (
                "Add the keyword `manifest_references` to `gate_arguments` in "
                "`src/devops_cli/roadmap/stage/stage_request.py`, record the references in "
                "`_Planner._problems` of `src/devops_cli/roadmap/stage/stage.py`, and add the field "
                "to `CaseFacts` and `PlanUnderTest`"
            ),
            "documentation": None,
            "verify": "uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py",
        },
        {
            "title": "State the rule of a manifest plan",
            "kind": "other",
            "reads": [
                "docs/ROADMAP_WORKFLOW.md",
                "docs/roadmap/plan-check.md",
                "src/devops_cli/roadmap/stage/stage_paths.py",
            ],
            "changes": [
                "docs/ROADMAP_WORKFLOW.md",
                "docs/roadmap/plan-check.md",
            ],
            "creates": [],
            "creates_lines": {},
            "test": None,
            "implementation": (
                "State the rule at the plan check of `docs/ROADMAP_WORKFLOW.md` and on the plan-check "
                "page of `docs/roadmap/plan-check.md`"
            ),
            "documentation": "The plan-check page states the rule and the `paths` gate that refuses it.",
            "verify": "uv run devops ci docs",
        },
    ],
    "criteria": [],
    "dependencies": [],
    "security": (
        "The new rule reads the manifest paths and the test paths of a plan and the text of the "
        "tests of a checkout, and it touches no cluster."
    ),
}


def test_this_plan_passes_the_content_gate() -> None:
    plan = StageProposal.model_validate(PLAN_OF_THIS_CHANGE)

    assert content_problems(plan) == []
