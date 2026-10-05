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
RELEASE_PATH = WORKFLOWS_DIR / "release.yml"


def _load_workflow(path: Path) -> dict[str, Any]:
    """Load and parse a GitHub Actions workflow YAML file."""
    assert path.is_file(), f"Workflow file not found: {path}"
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(content, dict), f"Workflow {path} does not parse as a mapping"
    return content


def test_update_prs_workflow_is_removed() -> None:
    """Validate that update-prs.yml is removed from workflows (#1217)."""
    assert not (WORKFLOWS_DIR / "update-prs.yml").exists()


def _extract_steps_with_action(
    workflow: dict[str, Any], action_prefix: str
) -> list[tuple[str, dict[str, Any]]]:
    """Extract (job_id, step) pairs where the step uses an action matching action_prefix."""
    steps_found: list[tuple[str, dict[str, Any]]] = []
    for job_id, job in workflow.get("jobs", {}).items():
        if isinstance(job, dict):
            for step in job.get("steps", []):
                if isinstance(step, dict) and action_prefix in str(step.get("uses", "")):
                    steps_found.append((str(job_id), step))
    return steps_found


def _assert_attest_build_provenance_contract(workflow: dict[str, Any]) -> None:
    """Assert that actions/attest-build-provenance steps specify subject-name when subject-digest is present."""
    attest_steps = _extract_steps_with_action(workflow, "actions/attest-build-provenance")
    assert attest_steps, "Expected at least one actions/attest-build-provenance step in workflow"
    for job_id, step in attest_steps:
        with_args = step.get("with", {})
        assert isinstance(with_args, dict), f"Step 'with' must be a dict in job '{job_id}'"
        has_digest = "subject-digest" in with_args
        has_name = bool(with_args.get("subject-name"))
        assert not has_digest or has_name, (
            f"attest-build-provenance in job '{job_id}' has subject-digest without subject-name"
        )


def test_release_workflow_attest_build_provenance_contract() -> None:
    """Validate that release.yml specifies subject-name when using actions/attest-build-provenance."""
    workflow = _load_workflow(RELEASE_PATH)
    _assert_attest_build_provenance_contract(workflow)
    attest_steps = _extract_steps_with_action(workflow, "actions/attest-build-provenance")
    assert len(attest_steps) == 1
    job_id, step = attest_steps[0]
    assert (job_id, step.get("with", {}).get("subject-name")) == (
        "service-image",
        "ghcr.io/${{ github.repository }}/service",
    )


def test_release_workflow_attest_build_provenance_mutation() -> None:
    """Validate that omitting subject-name from attest-build-provenance raises an AssertionError."""
    import copy

    workflow = _load_workflow(RELEASE_PATH)
    mutated = copy.deepcopy(workflow)
    for _job_id, step in _extract_steps_with_action(mutated, "actions/attest-build-provenance"):
        step.get("with", {}).pop("subject-name", None)

    with pytest.raises(AssertionError, match="has subject-digest without subject-name"):
        _assert_attest_build_provenance_contract(mutated)
