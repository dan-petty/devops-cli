"""`devops roadmap stage`: a task group has the kind manifest, whose failing case comes first
(#3251). A manifest group names its case in `test`, the work that the case proves in
`implementation`, and the command that runs the case in `verify`."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from devops_cli.roadmap.stage.stage_change import (
    StageGroup,
    StageProposal,
    content_problems,
    group_text,
)

CASE = "tests/fixtures/prometheus_rules/roadmap_service_activity_tests.yaml"
CASE_TEST = "uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py"
MANIFEST: dict[str, Any] = {
    "title": "Add the alert rule and its promtool case",
    "kind": "manifest",
    "reads": ["k8s/monitoring/prometheus-values.yaml"],
    "changes": ["k8s/monitoring/prometheus-values.yaml", CASE],
    "creates": [],
    "creates_lines": {},
    "test": f"Write the case for the alert rule in `{CASE}`",
    "implementation": "Add the alert rule to `k8s/monitoring/prometheus-values.yaml`",
    "documentation": None,
    "verify": CASE_TEST,
}


def _problem(group: dict[str, Any]) -> str:
    """The text that the schema gives back to the model for `group`."""
    with pytest.raises(ValidationError) as raised:
        StageGroup.model_validate(group)
    return str(raised.value)


def _task_lines(group: dict[str, Any]) -> list[str]:
    """The task lines that `group_text` writes for `group`, numbered from group 1, each with the
    line `Verification:` under it."""
    text = group_text(1, StageGroup.model_validate(group))
    return [line for line in text.splitlines() if line.startswith(("- [ ] ", "  - Verification:"))]


def test_a_manifest_group_with_a_case_and_a_verify_is_valid() -> None:
    group = StageGroup.model_validate(MANIFEST)

    assert (group.kind, group.test, group.process) == (
        "manifest",
        f"Write the case for the alert rule in `{CASE}`",
        None,
    )


def test_a_manifest_group_with_no_case_is_refused_with_the_kind_and_the_missing_test() -> None:
    problem = _problem({**MANIFEST, "test": None})

    assert "has the kind manifest" in problem
    assert "no test" in problem


def test_a_manifest_group_with_no_verify_is_refused_with_the_kind_and_the_missing_verify() -> None:
    problem = _problem({**MANIFEST, "verify": None})

    assert "has the kind manifest" in problem
    assert "no verify" in problem


def test_a_manifest_group_with_a_process_is_refused_with_the_kind() -> None:
    problem = _problem({**MANIFEST, "process": "Open the dashboard and read the panel."})

    assert "has the kind manifest" in problem
    assert "process" in problem


def test_a_manifest_group_renders_its_case_first_and_then_its_work() -> None:
    assert _task_lines(MANIFEST) == [
        f"- [ ] 1.1 Write the case for the alert rule in `{CASE}`",
        f"  - Verification: `$ {CASE_TEST}` fails on the base",
        "- [ ] 1.2 Add the alert rule to `k8s/monitoring/prometheus-values.yaml`",
        f"  - Verification: `$ {CASE_TEST}` passes",
    ]


PLAN_OF_THIS_CHANGE: dict[str, Any] = {
    "summary": "Add a test-first manifest kind",
    "pull_request_body": (
        "The stage plan holds no kind for a manifest with a failing case. The change adds the kind "
        "`manifest`, whose case task comes first, and refuses an `other` group that changes a case."
    ),
    "why": "Issue #3251: a plan for an alert rule has a failing case first, and no kind holds it.",
    "what_changes": [
        "`GroupKind` gains the member `manifest`, and a manifest group renders its case first.",
        "An `other` group that changes a case path is refused, and so is a manifest verify that runs no case.",
        "The planner prompts name the kind, and the golden set replays the plan of #3173.",
    ],
    "skip_specs": False,
    "feasibility": [
        "The schema in `src/devops_cli/roadmap/stage/stage_change.py` and the form check hold the two kinds of today, so the new kind has a place.",
        "The plan of #3173 changes a promtool case with the kind other, so the replay pins the rule.",
    ],
    "existing_tool": "No open tool covers the form of the stage plan, so the change builds its own.",
    "decisions": [
        {
            "decision": "Name the kind manifest, and keep other beside it",
            "reason": "The kind names the artifact, and many other groups change a manifest with no test.",
        }
    ],
    "rejected": [
        {
            "alternative": "Name the kind test-first",
            "evidence": "The name states the form and not the artifact, so a second form needs a third name.",
        }
    ],
    "groups": [
        {
            "title": "Add the manifest kind to the schema and its render",
            "kind": "behavior",
            "reads": [
                "src/devops_cli/roadmap/stage/stage_change.py",
                "src/devops_cli/lang/en/messages.py",
                "tests/roadmap/stage/test_roadmap_stage_kind.py",
            ],
            "changes": [
                "src/devops_cli/roadmap/stage/stage_change.py",
                "src/devops_cli/lang/en/messages.py",
                "tests/roadmap/stage/test_roadmap_stage_kind.py",
                "tests/roadmap/stage/test_roadmap_stage_manifest.py",
            ],
            "creates": ["tests/roadmap/stage/test_roadmap_stage_manifest.py"],
            "creates_lines": {"tests/roadmap/stage/test_roadmap_stage_manifest.py": 150},
            "test": (
                "Write `test_a_manifest_group_renders_its_case_first_and_then_its_work` in "
                "`tests/roadmap/stage/test_roadmap_stage_manifest.py`, and "
                "`test_the_plan_check_accepts_the_plan_of_this_change`, which builds the plan's "
                "own `StageProposal` and asserts that `content_problems` returns no problem for it, "
                "and verify that `src/devops_cli/roadmap/stage/stage_change.py` fails on the base"
            ),
            "implementation": (
                "Add `MANIFEST` to `GroupKind` and `_manifest_problems`, and render the case of a "
                "manifest group first"
            ),
            "documentation": None,
            "verify": "uv run devops ci test tests/roadmap/stage/test_roadmap_stage_manifest.py",
        },
        {
            "title": "Refuse an other group that changes a case path",
            "kind": "behavior",
            "reads": [
                "src/devops_cli/roadmap/stage/stage_form.py",
                "src/devops_cli/lang/en/messages.py",
                "tests/roadmap/stage/test_roadmap_stage_form.py",
            ],
            "changes": [
                "src/devops_cli/roadmap/stage/stage_form.py",
                "src/devops_cli/lang/en/messages.py",
                "tests/roadmap/stage/test_roadmap_stage_form.py",
            ],
            "test": (
                "Add `test_an_other_group_that_changes_a_case_path_is_refused_with_the_manifest_kind` "
                "to `tests/roadmap/stage/test_roadmap_stage_form.py`"
            ),
            "implementation": (
                "Add `_CASE_SUFFIXES` and `_is_case_path` to `stage_form.py`, and refuse an other "
                "group that changes a case path"
            ),
            "documentation": None,
            "verify": "uv run devops ci test tests/roadmap/stage/test_roadmap_stage_form.py",
        },
        {
            "title": "Refuse a manifest verify that runs no case",
            "kind": "behavior",
            "reads": [
                "src/devops_cli/roadmap/stage/stage_form.py",
                "src/devops_cli/lang/en/messages.py",
                "tests/roadmap/stage/test_roadmap_stage_form.py",
            ],
            "changes": [
                "src/devops_cli/roadmap/stage/stage_form.py",
                "src/devops_cli/lang/en/messages.py",
                "tests/roadmap/stage/test_roadmap_stage_form.py",
            ],
            "test": (
                "Add `test_a_manifest_verify_that_is_not_a_case_of_the_group_is_refused` and "
                "`test_a_manifest_verify_that_runs_a_path_of_the_group_is_accepted` to "
                "`tests/roadmap/stage/test_roadmap_stage_form.py`"
            ),
            "implementation": (
                "Add `_manifest_verify_problems` to `stage_form.py`, so a manifest verify is "
                "`uv run devops ci test` and a path of the group"
            ),
            "documentation": None,
            "verify": "uv run devops ci test tests/roadmap/stage/test_roadmap_stage_form.py",
        },
        {
            "title": "Name the manifest kind in the planner prompts",
            "kind": "other",
            "reads": [
                "src/devops_cli/ai/tasks/roadmap_stage_change.md",
                "src/devops_cli/ai/tasks/roadmap_stage_split.md",
                "tests/roadmap/stage/test_roadmap_stage_prompt_rules.py",
            ],
            "changes": [
                "src/devops_cli/ai/tasks/roadmap_stage_change.md",
                "src/devops_cli/ai/tasks/roadmap_stage_split.md",
                "tests/roadmap/stage/test_roadmap_stage_prompt_rules.py",
            ],
            "test": None,
            "implementation": (
                "Name the kind `manifest`, its case-first rule and its verify rule in "
                "`roadmap_stage_change.md` and `roadmap_stage_split.md`"
            ),
            "documentation": None,
            "verify": "uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py",
        },
        {
            "title": "Replay the hand-written plan of #3173",
            "kind": "other",
            "reads": [
                "tests/fixtures/roadmap_eval/stage/3331-a-plan-that-changes-a-check/case.json",
                "tests/roadmap/stage/test_roadmap_stage_eval_gates.py",
            ],
            "changes": [
                "tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/case.json",
                "tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/facts.json",
                "tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/issue.txt",
                "tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/plan.json",
                "tests/roadmap/stage/test_roadmap_stage_eval_gates.py",
            ],
            "creates": [
                "tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/case.json",
                "tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/facts.json",
                "tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/issue.txt",
                "tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/plan.json",
            ],
            "creates_lines": {
                "tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/case.json": 40,
                "tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/facts.json": 30,
                "tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/issue.txt": 40,
                "tests/fixtures/roadmap_eval/stage/3173-a-plan-for-an-alert-rule/plan.json": 120,
            },
            "test": None,
            "implementation": (
                "Add the replay case `3173-a-plan-for-an-alert-rule` from the plan of #3173, and "
                "update the pinned counts of the replay"
            ),
            "documentation": None,
            "verify": "uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py",
        },
    ],
}


def test_the_plan_check_accepts_the_plan_of_this_change() -> None:
    assert content_problems(StageProposal.model_validate(PLAN_OF_THIS_CHANGE)) == []
