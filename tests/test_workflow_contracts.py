"""Workflow contract tests verifying structural integrity, security guards, and expressions.

These tests enforce invariant rules for GitHub Actions workflows, ensuring permissions
remain minimal, triggers are guarded against unauthorized invocation, and shell injection
risks from inline expressions inside run blocks are eliminated.
"""

from __future__ import annotations

import copy
import shlex
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.core.command_resolver import ArgvPlaceholder, resolve_devops_argv
from devops_cli.tools_lock import load_tools_lock

WORKFLOWS_DIR = Path(".github/workflows")
RELEASE_PATH = WORKFLOWS_DIR / "release.yml"
AUDIT_PATH = WORKFLOWS_DIR / "defect-pr-hardening-audit.yml"


def _load_workflow(path: Path) -> dict[str, Any]:
    """Load and parse a GitHub Actions workflow YAML file."""
    assert path.is_file(), f"Workflow file not found: {path}"
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(content, dict), f"Workflow {path} does not parse as a mapping"
    return {"on" if k is True else str(k): v for k, v in content.items()}


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


def test_every_trivy_scan_runs_the_trivy_tools_lock_pins() -> None:
    """CI's Trivy scans run the Trivy `devops install-tools` installs, so CI and local scans agree (#1499)."""
    pinned = f"v{load_tools_lock().binary['trivy'].version}"

    assert [
        (path.name, job_id, step.get("with", {}).get("version"))
        for path in sorted(WORKFLOWS_DIR.glob("*.yml"))
        for job_id, step in _extract_steps_with_action(
            _load_workflow(path), "aquasecurity/trivy-action"
        )
    ] == [("ci.yml", "service-image", pinned), ("release.yml", "service-image", pinned)]


def assert_audit_workflow_contract(workflow: dict[str, Any]) -> None:
    """Assert that the defect PR hardening audit workflow satisfies structural contract invariants."""
    triggers = workflow.get("on", {})
    pr_trigger = triggers.get("pull_request", {})
    pr_types = pr_trigger.get("types", []) if isinstance(pr_trigger, dict) else []
    assert "closed" in pr_types, "Workflow must trigger on pull_request types [closed]"

    perms = workflow.get("permissions", {})
    assert isinstance(perms, dict), "Workflow permissions must be a mapping"
    assert (
        perms.get("contents"),
        perms.get("pull-requests"),
        perms.get("issues"),
        "actions" in perms,
    ) == ("read", "read", "write", False)

    env_vars = workflow.get("env", {})
    assert env_vars.get("UV_MANAGED_PYTHON") == "1", "Workflow must set UV_MANAGED_PYTHON: '1'"

    jobs = workflow.get("jobs", {})
    assert "audit-hardening" in jobs, "Workflow must contain job 'audit-hardening'"
    job = jobs["audit-hardening"]
    assert isinstance(job, dict)
    assert job.get("runs-on") == "ubuntu-24.04", "Job must run on ubuntu-24.04"

    job_if = str(job.get("if", ""))
    assert (
        "merged == true" in job_if,
        "type/bug" in job_if,
        "type/security" in job_if,
    ) == (True, True, True)

    steps = job.get("steps", [])
    step_runs = [str(s.get("run", "")) for s in steps if isinstance(s, dict)]
    assert any(
        "fork" in str(s.get("if", "")) or "fork" in run
        for s, run in zip(steps, step_runs, strict=False)
    ), "Workflow must include fork handling (skip-not-fail)"

    has_hardening_report = any(
        "devops pr hardening-report" in run and "--fail-on-missing" in run for run in step_runs
    )
    assert has_hardening_report, (
        "Workflow must execute 'devops pr hardening-report' with '--fail-on-missing'"
    )

    has_intake = any(
        "devops roadmap intake" in run and "create_repository_issue" not in run for run in step_runs
    )
    assert has_intake, (
        "Workflow failure path must hand findings to intake via 'devops roadmap intake' (not create_repository_issue)"
    )


def test_defect_pr_hardening_audit_workflow_contract() -> None:
    """Validate that defect-pr-hardening-audit.yml satisfies its structural contract."""
    workflow = _load_workflow(AUDIT_PATH)
    assert_audit_workflow_contract(workflow)


def test_defect_pr_hardening_audit_workflow_mutation() -> None:
    """Validate that mutating audit workflow contract invariants raises an AssertionError."""
    workflow = _load_workflow(AUDIT_PATH)

    mutated1 = copy.deepcopy(workflow)
    mutated1["on"]["pull_request"]["types"] = ["opened"]
    with pytest.raises(AssertionError, match="pull_request types"):
        assert_audit_workflow_contract(mutated1)

    mutated2 = copy.deepcopy(workflow)
    for step in mutated2["jobs"]["audit-hardening"]["steps"]:
        if "hardening-report" in step.get("run", ""):
            step["run"] = step["run"].replace("--fail-on-missing", "")
    with pytest.raises(AssertionError, match="--fail-on-missing"):
        assert_audit_workflow_contract(mutated2)

    mutated3 = copy.deepcopy(workflow)
    for step in mutated3["jobs"]["audit-hardening"]["steps"]:
        if "roadmap intake" in step.get("run", ""):
            step["run"] = step["run"].replace("roadmap intake", "create_repository_issue")
    with pytest.raises(AssertionError, match="intake"):
        assert_audit_workflow_contract(mutated3)


def _tokenize_devops_line(line: str) -> list[str | ArgvPlaceholder]:
    """Tokenize a devops command line, replacing shell expressions with placeholders."""
    cmd_str = line.removeprefix("uv run devops ").strip()
    return [
        ArgvPlaceholder(expression=t, single_token=True) if t.startswith("$") or "${" in t else t
        for t in shlex.split(cmd_str)
    ]


def _extract_devops_commands(workflow: dict[str, Any]) -> list[list[str | ArgvPlaceholder]]:
    """Extract all `uv run devops` command lines from workflow steps."""
    commands: list[list[str | ArgvPlaceholder]] = []
    jobs = workflow.get("jobs", {})
    steps = [
        step
        for job in jobs.values()
        if isinstance(job, dict)
        for step in job.get("steps", [])
        if isinstance(step, dict)
    ]
    for step in steps:
        run = str(step.get("run", ""))
        for raw_line in run.splitlines():
            line = raw_line.strip()
            if line.startswith("uv run devops "):
                commands.append(_tokenize_devops_line(line))
    return commands


def test_audit_workflow_devops_commands_resolve() -> None:
    """Verify all `uv run devops` command lines in the audit workflow resolve against Typer app."""
    workflow = _load_workflow(AUDIT_PATH)
    commands = _extract_devops_commands(workflow)
    assert len(commands) >= 2, "Expected at least 2 devops commands in audit workflow"
    findings = [resolve_devops_argv(tokens) for tokens in commands]
    assert all(f is None for f in findings), f"Unresolved devops commands in workflow: {findings}"
