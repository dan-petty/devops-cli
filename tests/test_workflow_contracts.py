"""Workflow contract tests verifying structural integrity, security guards, and expressions.

These tests enforce invariant rules for GitHub Actions workflows, ensuring permissions
remain minimal, triggers are guarded against unauthorized invocation, and shell injection
risks from inline expressions inside run blocks are eliminated.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.commands.ci import get_check_spec
from devops_cli.core.command_resolver import ArgvPlaceholder, ArgvToken, resolve_devops_argv
from devops_cli.tools_lock import load_tools_lock
from tests.markdown_examples import CodeSnippet, devops_commands

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
    assert [
        (job_id, step.get("with", {}).get("subject-name")) for job_id, step in attest_steps
    ] == [
        ("devcontainer", "ghcr.io/${{ github.repository }}/devcontainer"),
        ("service-image", "ghcr.io/${{ github.repository }}/service"),
    ]


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


# ── Every `devops` command the automation runs (#861) ─────────────────────────

GITHUB_DIR = Path(".github")
PRE_COMMIT_PATH = Path(".pre-commit-config.yaml")


def _automation_files() -> list[Path]:
    """Every workflow and composite action."""
    return sorted([*WORKFLOWS_DIR.glob("*.y*ml"), *(GITHUB_DIR / "actions").glob("*/action.y*ml")])


def _run_blocks(node: Any) -> Iterator[str]:
    """Every `run:` script under `node`: workflow job steps and composite action steps alike."""
    if isinstance(node, dict):
        if isinstance(node.get("run"), str):
            yield node["run"]
        for value in node.values():
            yield from _run_blocks(value)
    elif isinstance(node, list):
        for value in node:
            yield from _run_blocks(value)


def _extract_devops_commands(document: Any) -> list[list[ArgvToken]]:
    """The words after `devops` in each command the document's `run:` scripts run, read as a
    shell reads them: a variable or command substitution is a placeholder."""
    return [
        tokens
        for script in _run_blocks(document)
        for _, tokens in devops_commands(CodeSnippet(1, script, fenced=True))
    ]


def _pre_commit_commands() -> list[list[ArgvToken]]:
    """Each pre-commit hook's `devops` command: its entry, its `args`, then the staged files
    pre-commit passes unless `pass_filenames` is false."""
    config = yaml.safe_load(PRE_COMMIT_PATH.read_text(encoding="utf-8"))
    hooks = [hook for repo in config["repos"] for hook in repo.get("hooks", [])]
    return [
        [
            *tokens,
            *hook.get("args", []),
            *(
                [ArgvPlaceholder(expression="staged files")]
                if hook.get("pass_filenames", True)
                else []
            ),
        ]
        for hook in hooks
        for _, tokens in devops_commands(CodeSnippet(1, str(hook.get("entry", "")), fenced=True))
    ]


def test_every_devops_command_the_workflows_actions_and_hooks_run_resolves() -> None:
    """A renamed or removed command or option breaks the workflow that runs it only when that
    workflow next runs; this finds it against the command tree first."""
    workflow_commands = [
        tokens
        for path in _automation_files()
        for tokens in _extract_devops_commands(_load_workflow(path))
    ]
    hook_commands = _pre_commit_commands()
    unresolved = [
        (" ".join(map(str, tokens)), finding.describe())
        for tokens in [*workflow_commands, *hook_commands]
        if (finding := resolve_devops_argv(tokens)) is not None
    ]
    assert (bool(workflow_commands), bool(hook_commands), unresolved) == (True, True, [])


def test_a_misspelled_command_in_a_workflow_is_reported() -> None:
    """The negative control: extraction and resolution together report a command that does not
    exist, inside a command substitution and a compound line."""
    workflow = {
        "jobs": {
            "job": {
                "steps": [
                    {"run": 'OUT=$(uv run devops gh milestones clsoe "$VERSION") || true'},
                    {"run": 'uv run devops release notes --raw -v \\\n  "$VERSION"'},
                ]
            }
        }
    }
    found = [resolve_devops_argv(tokens) for tokens in _extract_devops_commands(workflow)]
    assert [None if f is None else f.token for f in found] == ["clsoe", None]


def test_no_run_block_interpolates_an_actions_expression() -> None:
    """Actions pastes a `${{ }}` expression into the script before the shell parses it, so a
    value holding `$(...)` runs; each value reaches `run:` through the step's `env:` (#861)."""
    interpolating = [
        str(path)
        for path in _automation_files()
        for script in _run_blocks(_load_workflow(path))
        if "${{" in script
    ]
    assert interpolating == []


def _uses(node: Any) -> Iterator[str]:
    """Every `uses:` reference under `node`: steps, composite action steps and reusable workflows."""
    if isinstance(node, dict):
        if isinstance(node.get("uses"), str):
            yield node["uses"]
        for value in node.values():
            yield from _uses(value)
    elif isinstance(node, list):
        for value in node:
            yield from _uses(value)


def test_every_remote_action_is_pinned_to_a_commit_sha() -> None:
    """A tag or branch can be moved to other code; a 40-character commit SHA cannot. Local
    `./` actions are this repository's own."""
    unpinned = [
        f"{path}: {ref}"
        for path in _automation_files()
        for ref in _uses(_load_workflow(path))
        if not ref.startswith("./") and not re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", ref)
    ]
    assert unpinned == []


def test_sdlc_names_only_the_supply_chain_controls_the_repository_runs() -> None:
    """SDLC.md once claimed weekly Dependabot audits, pip-audit and SLSA Level 3, none of which
    the repository had; the audit and the workflow gate it names are the checks `devops ci`
    runs."""
    sdlc = Path("docs/SDLC.md").read_text(encoding="utf-8")
    assert (
        [claim for claim in ("Dependabot", "pip-audit", "SLSA Level 3") if claim in sdlc],
        get_check_spec("audit").cmd,
        "zizmor" in sdlc,
    ) == ([], ["uv", "audit"], True)


def test_workflow_contract_fail_to_pass() -> None:
    """Validate `.github/workflows/fail-to-pass.yml` triggers, env, self-check, and no `${{` in `run:` (#844)."""
    workflow = _load_workflow(WORKFLOWS_DIR / "fail-to-pass.yml")
    pr_trigger = workflow.get("on", {}).get("pull_request", {})
    jobs = workflow.get("jobs", {})
    gate_steps = jobs.get("fail-to-pass", {}).get("steps", [])
    self_steps = jobs.get("self-check", {}).get("steps", [])
    all_steps = [*gate_steps, *self_steps]
    replay_step = next(
        (s for s in gate_steps if "devops ci fail-to-pass" in str(s.get("run", ""))),
        {},
    )
    self_replay = next(
        (s for s in self_steps if "5768cd9" in str(s.get("run", ""))),
        {},
    )
    commands = _extract_devops_commands(workflow)
    assert (
        pr_trigger.get("types"),
        pr_trigger.get("branches"),
        all(
            s.get("with", {}).get("fetch-depth") == 0
            for s in all_steps
            if "actions/checkout" in str(s.get("uses", ""))
        ),
        {"PR_TITLE", "PR_LABELS", "PR_BODY"} <= set(replay_step.get("env", {})),
        "devops ci fail-to-pass" in str(replay_step.get("run", "")),
        any("${{" in str(s.get("run", "")) for s in all_steps),
        "36b2bee" in str(self_replay.get("run", ""))
        and "16 failed and 24 passed in tests/test_ai_fixer.py" in str(self_replay.get("run", "")),
        [resolve_devops_argv(tokens) for tokens in commands],
    ) == (
        ["opened", "synchronize", "reopened", "edited", "labeled"],
        ["main", "release/**"],
        True,
        True,
        True,
        False,
        True,
        [None, None],
    )
