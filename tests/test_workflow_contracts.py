"""Workflow contract tests verifying structural integrity, security guards, and expressions.

These tests enforce invariant rules for GitHub Actions workflows, ensuring permissions
remain minimal, triggers are guarded against unauthorized invocation, and shell injection
risks from inline expressions inside run blocks are eliminated.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOWS_DIR = Path(".github/workflows")
UPDATE_PRS_PATH = WORKFLOWS_DIR / "update-prs.yml"


def _load_workflow(path: Path) -> dict[str, Any]:
    """Load and parse a GitHub Actions workflow YAML file."""
    assert path.is_file(), f"Workflow file not found: {path}"
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(content, dict), f"Workflow {path} does not parse as a mapping"
    return content


def _assert_update_prs_guard(condition: str) -> None:
    """Assert that the update-pull-requests job condition enforces collaborator authorization."""
    required_tokens = (
        "github.event.comment.author_association",
        "OWNER",
        "MEMBER",
        "COLLABORATOR",
        "github.event_name == 'push'",
        "github.event_name == 'workflow_dispatch'",
    )
    missing = [token for token in required_tokens if token not in condition]
    assert not missing, f"Missing required authorization tokens in job condition: {missing}"


def _assert_no_run_expressions(workflow: dict[str, Any]) -> None:
    """Assert that no step in any job interpolates GitHub Actions expressions directly inside run:."""
    violating_steps: list[tuple[str, str, str]] = []
    jobs = workflow.get("jobs", {})
    assert isinstance(jobs, dict), "Workflow jobs must be a mapping"

    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps", [])
        if not isinstance(steps, list):
            continue
        for step in steps:
            if not isinstance(step, dict):
                continue
            run_cmd = step.get("run")
            if isinstance(run_cmd, str) and "${{" in run_cmd:
                violating_steps.append((job_id, step.get("name", "unnamed"), run_cmd))

    assert not violating_steps, f"Found expressions inside run blocks: {violating_steps}"


def test_update_prs_workflow_collaborator_guard() -> None:
    """Validate that update-prs.yml requires collaborator association for issue comments."""
    workflow = _load_workflow(UPDATE_PRS_PATH)
    job = workflow.get("jobs", {}).get("update-pull-requests", {})
    assert isinstance(job, dict), "Missing update-pull-requests job"

    job_if = job.get("if", "")
    assert isinstance(job_if, str), "Job if condition must be a string"
    _assert_update_prs_guard(job_if)


def test_update_prs_workflow_collaborator_guard_mutation() -> None:
    """Validate that mutation removing author_association causes the guard assertion to fail."""
    workflow = _load_workflow(UPDATE_PRS_PATH)
    job = workflow.get("jobs", {}).get("update-pull-requests", {})
    assert isinstance(job, dict)
    job_if = str(job.get("if", ""))

    # Strip the author_association check
    mutated_condition = job_if.replace("github.event.comment.author_association", "STUB")
    with pytest.raises(AssertionError, match="Missing required authorization tokens"):
        _assert_update_prs_guard(mutated_condition)


def test_update_prs_workflow_no_inline_run_expressions() -> None:
    """Validate that no step in update-prs.yml uses ${{ ... }} inside run blocks."""
    workflow = _load_workflow(UPDATE_PRS_PATH)
    _assert_no_run_expressions(workflow)


def test_update_prs_workflow_no_inline_run_expressions_mutation() -> None:
    """Validate that injecting an expression into a run block triggers assertion failure."""
    import copy

    workflow = _load_workflow(UPDATE_PRS_PATH)
    mutated_wf = copy.deepcopy(workflow)
    steps = mutated_wf["jobs"]["update-pull-requests"]["steps"]
    steps[0]["run"] = 'echo "${{ github.event.inputs.pr_number }}"'

    with pytest.raises(AssertionError, match="Found expressions inside run blocks"):
        _assert_no_run_expressions(mutated_wf)


def test_update_prs_workflow_invariants_and_permissions() -> None:
    """Validate permissions, trigger events, and command invocation count in update-prs.yml."""
    raw_text = UPDATE_PRS_PATH.read_text(encoding="utf-8")
    workflow = _load_workflow(UPDATE_PRS_PATH)

    # Validate permissions block
    job = workflow["jobs"]["update-pull-requests"]
    perms = job.get("permissions", {})
    expected_perms = {
        "contents": "write",
        "pull-requests": "write",
        "issues": "write",
    }
    assert perms == expected_perms
    assert "actions" not in perms

    # Validate 4 invocations of devops pr update
    update_count = raw_text.count("uv run devops pr update")
    assert update_count == 4
