"""Workflow contract tests verifying structural integrity, security guards, and expressions.

These tests enforce invariant rules for GitHub Actions workflows, ensuring permissions
remain minimal, triggers are guarded against unauthorized invocation, and shell injection
risks from inline expressions inside run blocks are eliminated.
"""

from __future__ import annotations

import copy
import json
import re
import shlex
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.commands.ci import get_check_spec, resolve_step_rows
from devops_cli.core.command_resolver import ArgvPlaceholder, ArgvToken, resolve_devops_argv
from devops_cli.tools_lock import load_tools_lock
from tests.support.markdown_examples import CodeSnippet, devops_commands

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


_RELEASE_CREATED = "needs.release-please.outputs.release_created == 'true'"


def _needs(job: dict[str, Any]) -> list[str]:
    """The jobs a job needs, as a list."""
    needs = job.get("needs", [])
    return [needs] if isinstance(needs, str) else list(needs)


def _gated(jobs: dict[str, Any], name: str) -> bool:
    """Whether a job runs only when release-please created a release: it carries the gate
    itself, or it has no condition of its own and needs a gated job, since a skipped need skips
    it."""
    job = jobs[name]
    if "if" in job:
        return job["if"] == _RELEASE_CREATED
    return any(name != "release-please" and _gated(jobs, need) for need in _needs(job))


def test_release_please_makes_every_release_on_a_push_to_main() -> None:
    """release.yml runs release-please on each push to main with the release App token, limited
    to the permissions release-please needs, so the release pull request it opens runs its checks.
    Each publish job runs only in the run where release-please created a release, and no step
    reads, sets or tags a version (ADR 0013)."""
    workflow = _load_workflow(RELEASE_PATH)
    jobs = workflow["jobs"]
    release_please = jobs["release-please"]
    steps = {step["name"]: step for step in release_please["steps"]}
    roots = {name: job["if"] for name, job in jobs.items() if "if" in job}

    assert (
        workflow["on"],
        workflow["permissions"],
        workflow["concurrency"],
        (release_please["environment"], release_please["permissions"]),
        steps["Mint the Release App Token"]["with"],
        steps["Run release-please"]["uses"].split("@")[0],
        steps["Run release-please"]["with"],
        release_please["outputs"],
        roots,
    ) == (
        {"push": {"branches": ["main"]}},
        {},
        {"group": "release", "cancel-in-progress": False},
        ("release", {}),
        {
            "client-id": "${{ vars.RELEASE_APP_CLIENT_ID }}",
            "private-key": "${{ secrets.RELEASE_APP_PRIVATE_KEY }}",
            "permission-contents": "write",
            "permission-issues": "write",
            "permission-pull-requests": "write",
        },
        "googleapis/release-please-action",
        {
            "token": "${{ steps.app.outputs.token }}",
            "config-file": "release-please-config.json",
            "manifest-file": ".release-please-manifest.json",
        },
        {
            "release_created": "${{ steps.release.outputs.release_created }}",
            "tag_name": "${{ steps.release.outputs.tag_name }}",
            "sha": "${{ steps.release.outputs.sha }}",
        },
        dict.fromkeys(("assets", "devcontainer-image", "service-image"), _RELEASE_CREATED),
    )
    assert [name for name in jobs if name != "release-please" and not _gated(jobs, name)] == []


def test_every_publish_job_checks_out_the_commit_release_please_tagged() -> None:
    """A run that a later push starts can create the release of an earlier merge, so each job
    that checks out the repository builds the commit that the release tags, not the commit of
    the run."""
    jobs = _load_workflow(RELEASE_PATH)["jobs"]
    checkouts = {
        name: (
            "release-please" in _needs(job),
            next(s for s in job["steps"] if s.get("name") == "Check out repository")["with"],
        )
        for name, job in jobs.items()
        if any(s.get("name") == "Check out repository" for s in job.get("steps", []))
    }
    assert checkouts == dict.fromkeys(
        ("assets", "devcontainer-image", "devcontainer-smoke", "service-image"),
        (True, {"ref": "${{ needs.release-please.outputs.sha }}", "persist-credentials": False}),
    )


def test_release_please_tags_each_release_v_and_its_version_only() -> None:
    """The tag is `v<version>` with no component, so release-please finds the existing tags,
    such as the last tag of the old pipeline."""
    config = json.loads(Path("release-please-config.json").read_text(encoding="utf-8"))
    assert (
        config["release-type"],
        config["include-v-in-tag"],
        config["include-component-in-tag"],
        list(config["packages"]),
    ) == ("python", True, False, ["."])


def test_the_release_uploads_the_wheel_the_sdist_and_their_checksums() -> None:
    """The assets job builds the packages of the merged tree and uploads them to the release that
    release-please created, by its tag."""
    job = _load_workflow(RELEASE_PATH)["jobs"]["assets"]
    steps = {step["name"]: step for step in job["steps"]}
    upload = steps["Upload the Packages to the Release"]

    assert (
        job["permissions"],
        steps["Build Distribution Packages (Wheel & sdist)"]["run"].split("\n")[0],
        upload["env"]["TAG"],
        upload["run"],
    ) == (
        {"contents": "write"},
        "uv build",
        "${{ needs.release-please.outputs.tag_name }}",
        'gh release upload --clobber "$TAG" dist/*.whl dist/*.tar.gz dist/SHA256SUMS.txt',
    )


def test_no_workflow_targets_a_release_branch_or_runs_release_tooling() -> None:
    """release-please owns the version, the changelog, the tag and the release. No workflow
    triggers on a release branch, tags a commit, or runs the old release or close commands."""
    needles = ("release/", "devops release", "devops roadmap close", "git tag")
    hits = [
        f"{path.name}: {needle}"
        for path in sorted(WORKFLOWS_DIR.glob("*.yml"))
        for needle in needles
        if needle in path.read_text(encoding="utf-8")
    ]

    assert hits == []


def test_every_pull_request_title_into_main_is_a_conventional_commit() -> None:
    """release-please drops a squash title it cannot parse without a warning, so pr-title.yml
    checks the title of every pull request into main, with read access only."""
    workflow = _load_workflow(WORKFLOWS_DIR / "pr-title.yml")
    job = workflow["jobs"]["semantic-title"]

    assert (
        workflow["on"],
        workflow["permissions"],
        (job["name"], job["permissions"]),
        [step["uses"].split("@")[0] for step in job["steps"]],
    ) == (
        {
            "pull_request": {
                "types": ["opened", "edited", "synchronize", "reopened"],
                "branches": ["main"],
            }
        },
        {},
        ("Semantic PR title", {"pull-requests": "read"}),
        ["amannn/action-semantic-pull-request"],
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


def test_no_pre_commit_hook_runs_the_test_suite() -> None:
    """A commit runs only the fast hooks. The required checks of CI run the tests (#2086)."""
    config = yaml.safe_load(PRE_COMMIT_PATH.read_text(encoding="utf-8"))
    default_stages = config.get("default_stages", ["pre-commit"])
    commit_entries = [
        str(hook.get("entry", ""))
        for repo in config["repos"]
        for hook in repo.get("hooks", [])
        if "pre-commit" in hook.get("stages", default_stages)
    ]
    runs_tests = [
        entry
        for entry in commit_entries
        if "pytest" in entry.split() or re.search(r"\bdevops ci( test\b|$)", entry)
    ]
    assert (bool(commit_entries), runs_tests) == (True, [])


def _branch_name_pattern() -> str:
    """The pattern of the `no-commit-to-branch` hook that refuses a branch by its name."""
    config = yaml.safe_load(PRE_COMMIT_PATH.read_text(encoding="utf-8"))
    [pattern] = [
        hook["args"][hook["args"].index("--pattern") + 1]
        for repo in config["repos"]
        for hook in repo.get("hooks", [])
        if hook["id"] == "no-commit-to-branch" and "--pattern" in hook.get("args", [])
    ]
    return str(pattern)


def test_a_commit_on_a_branch_that_breaks_the_naming_form_is_refused() -> None:
    """The hook refuses a commit when its pattern matches the branch name (`re.match`), so the
    pattern matches each name that is not `<type>/<issue>-<slug>`: one of the types that
    release-please reads, the number of the issue, and a slug of lowercase words and digits
    (#2292)."""
    sections = json.loads(Path("release-please-config.json").read_text(encoding="utf-8"))
    types = [section["type"] for section in sections["changelog-sections"]]
    pattern = _branch_name_pattern()
    accepted = [f"{kind}/2292-naming-section" for kind in types] + ["fix/1-a", "docs/2292-a1-b2"]
    refused = [
        "main",
        "implement_issue_1388",
        "fix/pin-ty-redundant-cast",
        "feat/12",
        "feat/12-",
        "fix/12-a--b",
        "fix/12-Upper",
        "fix/12-a/b",
        "Fix/12-a",
        "fix/x12-a",
        "feature/12-widget",
        "wip/12-widget",
    ]
    assert (
        len(types),
        [name for name in accepted if re.match(pattern, name)],
        [name for name in refused if not re.match(pattern, name)],
    ) == (11, [], [])


def test_the_main_branch_stays_refused_by_name() -> None:
    """The first `no-commit-to-branch` entry names `main`, which the pattern entry also refuses."""
    config = yaml.safe_load(PRE_COMMIT_PATH.read_text(encoding="utf-8"))
    args = [
        hook.get("args", [])
        for repo in config["repos"]
        for hook in repo.get("hooks", [])
        if hook["id"] == "no-commit-to-branch"
    ]
    assert ["--branch", "main"] in args


# The fast static checks that a push runs (#1752): rows of the `devops ci` check table.
FAST_STATIC_CHECKS = ["lint", "format", "actionlint", "zizmor"]


def test_the_pre_push_hook_runs_only_the_fast_static_checks() -> None:
    """A push runs the fast static checks and changes no file. The required checks of CI run the
    test suite and the other checks before a merge, and the full `devops ci` is a manual run
    (#1752)."""
    config = yaml.safe_load(PRE_COMMIT_PATH.read_text(encoding="utf-8"))
    default_stages = config.get("default_stages", ["pre-commit"])
    push_commands = [
        [*shlex.split(str(hook.get("entry", ""))), *map(str, hook.get("args", []))]
        for repo in config["repos"]
        for hook in repo.get("hooks", [])
        if "pre-push" in hook.get("stages", default_stages)
    ]
    assert [resolve_step_rows(shlex.join(argv)) for argv in push_commands] == [FAST_STATIC_CHECKS]
    assert [argv for argv in push_commands if "--check" not in argv] == []


def test_a_misspelled_command_in_a_workflow_is_reported() -> None:
    """The negative control: extraction and resolution together report a command that does not
    exist, inside a command substitution and a compound line."""
    workflow = {
        "jobs": {
            "job": {
                "steps": [
                    {"run": 'OUT=$(uv run devops gh milestones clsoe "$NAME") || true'},
                    {"run": 'uv run devops gh milestones status \\\n  "$NAME"'},
                ]
            }
        }
    }
    found = [resolve_devops_argv(tokens) for tokens in _extract_devops_commands(workflow)]
    assert [None if f is None else f.token for f in found] == ["clsoe", None]


def _every_step(path: Path) -> list[dict[str, Any]]:
    """The steps of a workflow's jobs, or of a composite action."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if "runs" in data:
        return list(data["runs"].get("steps", []))
    return [step for job in data["jobs"].values() for step in job.get("steps", [])]


def test_no_image_build_emulates_a_platform() -> None:
    """Every node that runs the images is amd64, so no workflow or action sets up QEMU, and every
    image build names linux/amd64 only. The arm64 builds under emulation made the devcontainer
    check take about 25 minutes and the release service image job 9.5 (#1951, #1954)."""
    paths = [*WORKFLOWS_DIR.glob("*.yml"), *Path(".github/actions").glob("*/action.yml")]
    steps = [step for path in paths for step in _every_step(path)]
    assert (
        [step["uses"] for step in steps if "setup-qemu-action" in step.get("uses", "")],
        sorted(
            {step["with"]["platforms"] for step in steps if "platforms" in step.get("with", {})}
        ),
    ) == ([], ["linux/amd64"])


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


def test_every_checkout_states_its_credentials_and_only_a_pushing_job_keeps_them() -> None:
    """actions/checkout leaves the job's token in `.git/config` unless told not to, where any later
    step, or an uploaded artifact, can read it (zizmor's artipacked). Only a job that runs
    `git push` keeps it."""
    checkouts = []
    for path in sorted(WORKFLOWS_DIR.glob("*.y*ml")):
        for job_id, job in _load_workflow(path).get("jobs", {}).items():
            steps = job.get("steps", [])
            pushes = any(re.search(r"\bgit\s+push\b", str(s.get("run", ""))) for s in steps)
            checkouts += [
                (f"{path.name}:{job_id}", step.get("with", {}).get("persist-credentials"), pushes)
                for step in steps
                if str(step.get("uses", "")).startswith("actions/checkout@")
            ]
    assert [(where, kept) for where, kept, pushes in checkouts if kept is not pushes] == []


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


def test_fail_to_pass_skips_the_release_pull_request_without_cancelled_runs() -> None:
    """The release pull request changes only the changelog, the manifest and the version lines,
    so no test replays there and both jobs skip. release-please pushes, then edits and labels the
    pull request, so three events start runs on one head; each run of a release-please branch gets
    its own concurrency group, so none cancels another and the pull request shows no cancelled
    check (#1960). Every other pull request keeps one group, where a newer event cancels an older
    run."""
    workflow = _load_workflow(WORKFLOWS_DIR / "fail-to-pass.yml")
    skip = "${{ !startsWith(github.head_ref, 'release-please--') }}"
    assert (
        {name: job.get("if") for name, job in workflow["jobs"].items()},
        workflow["concurrency"],
    ) == (
        {"fail-to-pass": skip, "self-check": skip},
        {
            "group": "fail-to-pass-${{ startsWith(github.head_ref, 'release-please--')"
            " && github.run_id || github.ref }}",
            "cancel-in-progress": True,
        },
    )


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
        ["main"],
        True,
        True,
        True,
        False,
        True,
        [None, None],
    )


# ── The OpenSpec gate's workflows (#1844) ─────────────────────────────────────


def _steps(workflow: Path, job: str) -> list[dict[str, Any]]:
    """The steps of `job` in the workflow file `workflow`."""
    loaded = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    return list(loaded["jobs"][job]["steps"])


SETUP_NODE = "actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1"


def test_the_static_job_installs_the_pinned_node_and_openspec_before_the_gate() -> None:
    """`setup-node` is pinned by the commit of v7.1.0 and reads `.node-version`, the install step
    follows it, and both come before the gate that runs the openspec row; the checkout is the
    default shallow one, since the gate reads no git history."""
    steps = _steps(WORKFLOWS_DIR / "ci.yml", "static")
    names = [step.get("name") for step in steps]
    node, install = (steps[names.index(name)] for name in ("Set up Node.js", "Install OpenSpec"))
    checkout = steps[names.index("Check out repository")]
    assert (
        node["uses"].split(" ")[0],
        node["with"],
        install["run"].splitlines(),
        names.index("Set up Node.js") < names.index("Install OpenSpec"),
        names.index("Install OpenSpec") < names.index("Static Analysis Quality Gate"),
        "fetch-depth" in checkout["with"],
    ) == (
        SETUP_NODE,
        {"node-version-file": ".node-version"},
        [
            'echo "$HOME/.local/bin" >> "$GITHUB_PATH"',
            "uv run devops install-tools --tool openspec --only-missing",
        ],
        True,
        True,
        False,
    )


def test_the_static_job_starts_bandit_once() -> None:
    """The Static Analysis CI job runs Bandit once: the gate's security row covers it, and the
    scan report step skips it (#1746)."""
    workflow = _load_workflow(WORKFLOWS_DIR / "ci.yml")
    steps = workflow["jobs"]["static"]["steps"]

    bandit_starts = 0
    for step in steps:
        run = str(step.get("run", ""))
        if not run:
            continue
        if "security" in resolve_step_rows(run):
            bandit_starts += 1
        try:
            from devops_cli.commands.scan import resolve_scan_report_scanners

            scanners = resolve_scan_report_scanners(run)
        except ImportError:
            scanners = (
                []
                if ("--skip" in run or "--skip-scanner" in run) and "bandit" in run
                else ["bandit"]
                if "devops scan report" in run
                else []
            )
        if "bandit" in scanners:
            bandit_starts += 1

    assert bandit_starts == 1


def test_the_static_job_starts_bandit_once_mutation() -> None:
    """Omitting --skip bandit causes Bandit to run twice and fails the contract (#1746)."""
    workflow = _load_workflow(WORKFLOWS_DIR / "ci.yml")
    steps = copy.deepcopy(workflow["jobs"]["static"]["steps"])
    for step in steps:
        if "devops scan report" in str(step.get("run", "")):
            step["run"] = "uv run devops scan report --sarif .data/scan.sarif"

    bandit_starts = 0
    for step in steps:
        run = str(step.get("run", ""))
        if not run:
            continue
        if "security" in resolve_step_rows(run):
            bandit_starts += 1
        try:
            from devops_cli.commands.scan import resolve_scan_report_scanners

            scanners = resolve_scan_report_scanners(run)
        except ImportError:
            scanners = (
                []
                if ("--skip" in run or "--skip-scanner" in run) and "bandit" in run
                else ["bandit"]
                if "devops scan report" in run
                else []
            )
        if "bandit" in scanners:
            bandit_starts += 1

    with pytest.raises(AssertionError):
        assert bandit_starts == 1


def test_copilot_setup_steps_installs_the_pinned_openspec_with_the_opt_outs() -> None:
    """GitHub runs the `copilot-setup-steps` job from the default branch before the Copilot cloud
    agent starts. The file is written by hand, since `openspec init --copilot-cloud` writes a
    workflow that runs an unpinned checkout and `npm install -g`: here every action is pinned
    (the workflow contract tests check each), nothing installs globally, and the job asks for
    no more than to read the repository."""
    path = WORKFLOWS_DIR / "copilot-setup-steps.yml"
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    job = workflow["jobs"]["copilot-setup-steps"]
    scripts = [str(step["run"]) for step in job["steps"] if "run" in step]

    assert (
        workflow["env"],
        job["permissions"],
        [step.get("uses", "").split(" ")[0] for step in job["steps"]][2:3],
        job["steps"][2]["with"],
        [line for script in scripts for line in script.splitlines()],
    ) == (
        {
            "DO_NOT_TRACK": "1",
            "OPENSPEC_TELEMETRY": "0",
            "OPENSPEC_NO_UPDATE_CHECK": "1",
            "UV_MANAGED_PYTHON": "1",
        },
        {"contents": "read"},
        [SETUP_NODE],
        {"node-version-file": ".node-version"},
        [
            'echo "$HOME/.local/bin" >> "$GITHUB_PATH"',
            "uv run devops install-tools --tool openspec --only-missing",
        ],
    )
    code = "\n".join(
        line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("#")
    )
    assert ("npm install -g" in code, "--copilot-cloud" in code) == (False, False)


# ── The devcontainer image build (#1895) ─────────────────────────────────────

DEVCONTAINER_ACTIONS_DIR = GITHUB_DIR / "actions"


def _composite_steps(name: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """A composite action of this repository, and each of its steps as the fields it sets."""
    action = _load_workflow(DEVCONTAINER_ACTIONS_DIR / name / "action.yml")
    fields = ("name", "uses", "with", "env", "run")
    return action, [
        {field: step[field] for field in fields if field in step}
        for step in action["runs"]["steps"]
    ]


def test_the_devcontainer_image_action_builds_the_features_with_the_locked_cli() -> None:
    """The action builds .devcontainer/devcontainer.json with the Dev Containers CLI that the tools
    lock pins, so the Dev Container Features and the user vscode are in the image, for linux/amd64
    only, with no emulation, pushed by digest. The labels, the SBOM, the provenance and the metadata file that
    holds the digest reach buildx through `build.options`, which the CLI passes on for a
    Dockerfile configuration where `--label` does nothing (devcontainers/cli#930). The action
    writes no GITHUB_PATH, so it changes nothing for its caller's later steps."""
    action, steps = _composite_steps("devcontainer-image")
    cli = load_tools_lock().npm["devcontainers-cli"]

    assert ((cli.version, cli.bin), action["outputs"], steps) == (
        ("0.89.0", "devcontainer"),
        {
            "digest": {
                "description": "Digest of the pushed image index.",
                "value": "${{ steps.build.outputs.digest }}",
            }
        },
        [
            {
                "name": "Set up Docker Buildx",
                "uses": "docker/setup-buildx-action@f87e5991a6d7451dcb8d9637bfbc97413f497069",
                "with": {"driver-opts": "network=host"},
            },
            {
                "name": "Set up Node.js",
                "uses": "actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1",
                "with": {"node-version-file": ".node-version"},
            },
            {
                "name": "Install the Dev Containers CLI",
                "run": "uv run devops install-tools --tool devcontainers-cli --only-missing",
            },
            {
                "name": "Write the build configuration",
                "env": {"LABELS": "${{ inputs.labels }}"},
                "run": "set -euo pipefail\n"
                'jq --arg labels "$LABELS" --arg metadata '
                '"$RUNNER_TEMP/devcontainer-build-metadata.json" \'\n'
                "  .build.options = (.build.options // [])\n"
                '    + [$labels | split("\\n")[] | select(length > 0) | ("--label", .)]\n'
                '    + ["--sbom=true", "--provenance=mode=max", "--metadata-file", $metadata]\n'
                "' .devcontainer/devcontainer.json > .devcontainer/devcontainer.build.json\n",
            },
            {
                "name": "Build the image with its features and push it by digest",
                "env": {
                    "IMAGE": "${{ inputs.image }}",
                    "CACHE_FROM": "${{ inputs.cache-from }}",
                    "CACHE_TO": "${{ inputs.cache-to }}",
                },
                "run": "set -euo pipefail\n"
                'export PATH="$HOME/.local/bin:$PATH"\n'
                "CACHE_ARGS=()\n"
                'if [ -n "$CACHE_FROM" ]; then CACHE_ARGS+=(--cache-from "$CACHE_FROM"); fi\n'
                'if [ -n "$CACHE_TO" ]; then CACHE_ARGS+=(--cache-to "$CACHE_TO"); fi\n'
                "devcontainer build \\\n"
                "  --workspace-folder . \\\n"
                "  --config .devcontainer/devcontainer.build.json \\\n"
                "  --frozen-lockfile \\\n"
                '  --image-name "$IMAGE" \\\n'
                "  --platform linux/amd64 \\\n"
                "  --output type=image,push-by-digest=true,name-canonical=true,push=true \\\n"
                '  "${CACHE_ARGS[@]}"\n'
                'echo "digest=$(jq -er \'."containerimage.digest"\' '
                '"$RUNNER_TEMP/devcontainer-build-metadata.json")" >> "$GITHUB_OUTPUT"\n',
            },
            {"name": "Free the builder's disk space", "run": "docker buildx prune --all --force"},
        ],
    )


def test_the_devcontainer_smoke_action_starts_the_pushed_digest_as_vscode() -> None:
    """A child repository that names only the image must open as vscode through the image's
    devcontainer.metadata label, and the image must run as vscode, uid and gid 1000, with a
    command from each Dev Container Feature on its path (#1895)."""
    action, steps = _composite_steps("devcontainer-smoke")

    assert (action["inputs"], steps) == (
        {
            "image-ref": {
                "description": "The image to start, as repository@digest.",
                "required": True,
            }
        },
        [
            {
                "name": "Set up Node.js",
                "uses": "actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1",
                "with": {"node-version-file": ".node-version"},
            },
            {
                "name": "Install the Dev Containers CLI",
                "run": "uv run devops install-tools --tool devcontainers-cli --only-missing",
            },
            {
                "name": "Start the image as its remote user",
                "env": {"REF": "${{ inputs.image-ref }}"},
                "run": "set -euo pipefail\n"
                'export PATH="$HOME/.local/bin:$PATH"\n'
                'CHILD="$RUNNER_TEMP/devcontainer-child"\n'
                'mkdir -p "$CHILD/.devcontainer" "$HOME/.ssh"\n'
                "jq -n --arg image \"$REF\" '{image: $image, updateRemoteUserUID: false}' > "
                '"$CHILD/.devcontainer/devcontainer.json"\n'
                'devcontainer up --workspace-folder "$CHILD" --skip-post-create > /dev/null\n'
                'test "$(devcontainer exec --workspace-folder "$CHILD" id -un)" = vscode\n'
                'docker run --rm --user vscode "$REF" sh -ec \'\n'
                '  test "$(id -u):$(id -g)" = 1000:1000\n'
                "  for TOOL in zsh git gh copilot node npm docker kubectl helm minikube claude; do\n"
                '    command -v "$TOOL" > /dev/null || { echo "missing: $TOOL" >&2; exit 1; }\n'
                "  done\n"
                "  devops --version > /dev/null'\n",
            },
        ],
    )


# ── The docs site build (#1651) ───────────────────────────────────────────────

PATHS_FILTER = "dorny/paths-filter@ceb8a2b8f2d89434be7ff52d3de7ec3738c5cc9d"
CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
PAGES_BUILDER = (
    "ghcr.io/actions/jekyll-build-pages"
    "@sha256:6791ebfd912185ed59bfb5fb102664fa872496b79f87ff8b9cfba292a7345041"
)


def test_a_pull_request_that_changes_the_site_builds_it_with_the_pages_builder() -> None:
    """GitHub Pages publishes `main:/docs` when a pull request merges, so a Liquid or Jekyll error
    in `docs/` breaks the site at the merge. The `docs-site` job builds `docs/` on the pull request
    first, with the image that `actions/jekyll-build-pages` v1.0.13 runs, by digest, because the
    action names its image by a tag. The job runs for every pull request and builds only when
    `docs/` or `ci.yml` changed, so on any other pull request it reports success. Its `if` names
    no branch, no job needs it, and it holds no write scope. The container has no network and
    mounts `docs/` read-only, so the build needs no token and writes nothing to the checkout. Its
    resolver is loopback: the GitHub metadata plugin then gets a failed DNS lookup, which it
    catches, and builds without metadata. The runner's own resolver is unreachable without a
    network, which raises an error that the plugin does not catch (#1651)."""
    jobs = _load_workflow(WORKFLOWS_DIR / "ci.yml")["jobs"]
    job = jobs["docs-site"]
    built = "steps.changes.outputs.docs == 'true'"

    assert (
        job["if"],
        job["permissions"],
        job["timeout-minutes"],
        [name for name, other in jobs.items() if "docs-site" in _needs(other)],
        job["steps"],
    ) == (
        "github.event_name == 'pull_request'",
        {"contents": "read", "pull-requests": "read"},
        10,
        [],
        [
            {
                "name": "Detect Docs Site Changes",
                "id": "changes",
                "uses": PATHS_FILTER,
                "with": {"filters": "docs:\n  - 'docs/**'\n  - '.github/workflows/ci.yml'\n"},
            },
            {
                "name": "Check out repository",
                "if": built,
                "uses": CHECKOUT,
                "with": {"persist-credentials": False},
            },
            {
                "name": "Build the Site with the GitHub Pages Builder",
                "if": built,
                "env": {"PAGES_BUILDER": PAGES_BUILDER},
                "run": "docker run --rm --network none --dns 127.0.0.1 \\\n"
                '  --volume "$GITHUB_WORKSPACE/docs:/github/workspace/docs:ro" \\\n'
                "  --env GITHUB_WORKSPACE=/github/workspace \\\n"
                "  --env GITHUB_REPOSITORY \\\n"
                "  --env GITHUB_API_URL \\\n"
                "  --env INPUT_SOURCE=docs \\\n"
                "  --env INPUT_DESTINATION=../site \\\n"
                '  --env INPUT_BUILD_REVISION="$GITHUB_SHA" \\\n'
                "  --env INPUT_VERBOSE=true \\\n"
                "  --env INPUT_FUTURE=false \\\n"
                "  --env DO_NOT_TRACK=1 \\\n"
                '  "$PAGES_BUILDER"\n',
            },
        ],
    )
