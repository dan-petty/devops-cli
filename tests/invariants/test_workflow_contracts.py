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
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
import yaml

from devops_cli.commands.ci import get_check_spec, resolve_step_rows
from devops_cli.config.constants import (
    CONST_DEFECT_TITLE_PATTERN,
    CONST_OPENSPEC_CHANGE_FOLDER_RE,
    CONST_ROADMAP_SCOPE_LABEL_PREFIX,
)
from devops_cli.core.command_resolver import ArgvPlaceholder, ArgvToken, resolve_devops_argv
from devops_cli.roadmap.title_labels import declared_label_names
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
        dict.fromkeys(
            ("assets", "devcontainer-image", "service-image", "runner-image"), _RELEASE_CREATED
        ),
    )
    assert [name for name in jobs if name != "release-please" and not _gated(jobs, name)] == []


_URGENT_MERGE_STEP = "Merge the Release Pull Request on an Urgent Fix"
_URGENT_LABELS = ("release-now", "priority/p0-critical", "scope/security", "priority/p1-high")


def test_an_urgent_fix_turns_on_auto_merge_of_the_release_pull_request() -> None:
    """After release-please updates the release pull request, the release App turns on its
    auto-merge when the pushed commit's pull request carries `release-now`, or closes an issue
    labeled `priority/p0-critical`, or `scope/security` with `priority/p1-high` (#1966, #2768,
    ADR 0013). Intake gives a security fix `scope/security`, and no title gives `type/security`.
    The App token does it, because a merge that GITHUB_TOKEN makes starts no Release run, and the
    run of a release merge does nothing. RELEASE_CYCLE.md states the rule, and the label exists."""
    steps = _load_workflow(RELEASE_PATH)["jobs"]["release-please"]["steps"]
    names = [step["name"] for step in steps]
    step = steps[names.index(_URGENT_MERGE_STEP)]
    script = step["run"]
    labels = yaml.safe_load(Path(".github/labels.yml").read_text(encoding="utf-8"))
    cycle = Path("RELEASE_CYCLE.md").read_text(encoding="utf-8")

    assert (
        names.index(_URGENT_MERGE_STEP) > names.index("Run release-please"),
        step["if"],
        step["env"],
        'gh pr merge "$RELEASE_PR" --repo "$REPOSITORY" --auto --squash' in script,
        [label for label in _URGENT_LABELS if label not in script],
        {"release-now", "scope/security"} <= {label["name"] for label in labels},
        "type/security" in script,
        [label for label in _URGENT_LABELS if f"`{label}`" not in cycle],
    ) == (
        True,
        "steps.release.outputs.releases_created != 'true' && steps.release.outputs.pr != ''",
        {
            "GH_TOKEN": "${{ steps.app.outputs.token }}",
            "REPOSITORY": "${{ github.repository }}",
            "PUSHED_SHA": "${{ github.sha }}",
            "RELEASE_PR": "${{ steps.release.outputs.pr }}",
        },
        True,
        [],
        True,
        False,
        [],
    )


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
        ("assets", "devcontainer-image", "devcontainer-smoke", "service-image", "runner-image"),
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


def _title_summary_accepted(pattern: str, summary: str) -> bool:
    """The action's own rule: the first match of `subjectPattern` must cover the whole summary."""
    match = re.search(pattern, summary)
    return match is not None and len(match.group(0)) == len(summary)


def test_a_pull_request_title_summary_has_at_most_60_characters() -> None:
    """The squash subject and the changelog line are the pull request title, so its summary, the
    text after `<type>(<scope>): `, has at most 60 characters (#1803, CONTRIBUTING.md section 4).
    The error names the limit and the document that sets it."""
    workflow = _load_workflow(WORKFLOWS_DIR / "pr-title.yml")
    inputs = workflow["jobs"]["semantic-title"]["steps"][0]["with"]
    pattern = inputs["subjectPattern"]

    assert (
        _title_summary_accepted(pattern, "a" * 60),
        _title_summary_accepted(pattern, "a" * 61),
        _title_summary_accepted(pattern, "devops gh issues close records a close reason"),
        "60 characters" in inputs["subjectPatternError"],
        "CONTRIBUTING.md" in inputs["subjectPatternError"],
    ) == (True, False, True, True, True)


# release-please opens its pull request from the branch `main`, so its title has the scope `main`.
RELEASE_PLEASE_TITLE_SCOPE = "main"


def test_the_title_check_allows_exactly_the_declared_scopes() -> None:
    """The scope of a title gives the label `scope/<scope>` only when `.github/labels.yml`
    declares it (#2800). The title check holds the scopes to the declared ones, so a pull request
    with another scope fails at the title and not with a warning after it opens. The one scope
    with no label is the scope of the release pull request."""
    labels_text = Path(".github/labels.yml").read_text(encoding="utf-8")
    prefix = CONST_ROADMAP_SCOPE_LABEL_PREFIX
    declared = {
        name.removeprefix(prefix)
        for name in declared_label_names(labels_text)
        if name.startswith(prefix)
    }
    workflow = _load_workflow(WORKFLOWS_DIR / "pr-title.yml")
    inputs = workflow["jobs"]["semantic-title"]["steps"][0]["with"]
    allowed = inputs.get("scopes", "").split()

    assert (sorted(allowed), len(allowed) == len(set(allowed))) == (
        sorted(declared | {RELEASE_PLEASE_TITLE_SCOPE}),
        True,
    )


def test_the_title_check_and_the_workflow_hold_the_same_rule() -> None:
    """`roadmap/pull_form.py` is the one source of the title rule (#3198), and the workflow cannot
    read it: an action takes static inputs. So the summary pattern of the workflow allows exactly
    `SUMMARY_MAX_CHARS` characters, and each scope it lists passes `title_problems`."""
    from devops_cli.roadmap.pull_form import SUMMARY_MAX_CHARS, title_problems

    workflow = _load_workflow(WORKFLOWS_DIR / "pr-title.yml")
    inputs = workflow["jobs"]["semantic-title"]["steps"][0]["with"]
    labels = declared_label_names(Path(".github/labels.yml").read_text(encoding="utf-8"))
    scopes = inputs["scopes"].split()
    summary = "a" * SUMMARY_MAX_CHARS

    assert (
        inputs["subjectPattern"],
        [scope for scope in scopes if title_problems(f"fix({scope}): {summary}", labels)],
        bool(title_problems(f"fix(pr): {summary}a", labels)),
    ) == (f"^.{{1,{SUMMARY_MAX_CHARS}}}$", [], True)


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
        ("runner-image", "ghcr.io/${{ github.repository }}/runner"),
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
    ] == [
        ("ci.yml", "service-image", pinned),
        ("ci.yml", "runner-image", pinned),
        ("release.yml", "service-image", pinned),
        ("release.yml", "runner-image", pinned),
    ]


def assert_audit_workflow_contract(workflow: dict[str, Any], text: str) -> None:
    """Assert that the defect PR hardening audit workflow, parsed and as text, keeps its contract."""
    triggers = workflow.get("on", {})
    pr_trigger = triggers.get("pull_request", {})
    pr_types = pr_trigger.get("types", []) if isinstance(pr_trigger, dict) else []
    assert "closed" in pr_types, "Workflow must trigger on pull_request types [closed]"

    perms = workflow.get("permissions", {})
    assert isinstance(perms, dict), "Workflow permissions must be a mapping"
    assert perms == {"contents": "read", "pull-requests": "read"}, (
        "Workflow permissions must be contents: read and pull-requests: read, with no issues entry (#3479)"
    )

    env_vars = workflow.get("env", {})
    assert env_vars.get("UV_MANAGED_PYTHON") == "1", "Workflow must set UV_MANAGED_PYTHON: '1'"

    jobs = workflow.get("jobs", {})
    assert "audit-hardening" in jobs, "Workflow must contain job 'audit-hardening'"
    job = jobs["audit-hardening"]
    assert isinstance(job, dict)
    assert job.get("runs-on") == "ubuntu-26.04", "Job must run on ubuntu-26.04"

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

    report_runs = [run for run in step_runs if "devops pr hardening-report" in run]
    assert report_runs, "Workflow must execute 'devops pr hardening-report'"
    assert all("GITHUB_STEP_SUMMARY" in run for run in report_runs), (
        "The report step must append its output to GITHUB_STEP_SUMMARY (#3479)"
    )
    assert not any("--fail-on-missing" in run for run in step_runs), (
        "Workflow must not pass --fail-on-missing: the audit runs after the merge and cannot block it (#3479)"
    )
    assert not any("issues create" in run or "devops roadmap intake" in run for run in step_runs), (
        "Workflow must not file an issue: the text has no root cause and uses an intake round (#3479)"
    )

    assert "AGENTS.md" not in text, "Workflow text must not cite AGENTS.md: it holds no such rule"
    assert "docs/SELF_IMPROVEMENT.md" in text, (
        "Workflow text must cite docs/SELF_IMPROVEMENT.md, which owns the hardening rule"
    )


def test_defect_pr_hardening_audit_workflow_contract() -> None:
    """Validate that defect-pr-hardening-audit.yml satisfies its structural contract."""
    workflow = _load_workflow(AUDIT_PATH)
    assert_audit_workflow_contract(workflow, AUDIT_PATH.read_text(encoding="utf-8"))


def test_defect_pr_hardening_audit_workflow_mutation() -> None:
    """Validate that mutating audit workflow contract invariants raises an AssertionError."""
    workflow = _load_workflow(AUDIT_PATH)
    text = AUDIT_PATH.read_text(encoding="utf-8")

    mutated1 = copy.deepcopy(workflow)
    mutated1["on"]["pull_request"]["types"] = ["opened"]
    with pytest.raises(AssertionError, match="pull_request types"):
        assert_audit_workflow_contract(mutated1, text)

    mutated2 = copy.deepcopy(workflow)
    for step in mutated2["jobs"]["audit-hardening"]["steps"]:
        if "hardening-report" in step.get("run", ""):
            step["run"] += " --fail-on-missing\n"
    with pytest.raises(AssertionError, match="--fail-on-missing"):
        assert_audit_workflow_contract(mutated2, text)

    mutated3 = copy.deepcopy(workflow)
    for step in mutated3["jobs"]["audit-hardening"]["steps"]:
        if "hardening-report" in step.get("run", ""):
            step["run"] = step["run"].replace("GITHUB_STEP_SUMMARY", "GITHUB_OUTPUT")
    with pytest.raises(AssertionError, match="GITHUB_STEP_SUMMARY"):
        assert_audit_workflow_contract(mutated3, text)

    mutated4 = copy.deepcopy(workflow)
    mutated4["jobs"]["audit-hardening"]["steps"].append({"run": "uv run devops gh issues create"})
    with pytest.raises(AssertionError, match="must not file an issue"):
        assert_audit_workflow_contract(mutated4, text)

    mutated5 = copy.deepcopy(workflow)
    mutated5["jobs"]["audit-hardening"]["steps"].append({"run": "uv run devops roadmap intake"})
    with pytest.raises(AssertionError, match="must not file an issue"):
        assert_audit_workflow_contract(mutated5, text)

    mutated6 = copy.deepcopy(workflow)
    mutated6["permissions"]["issues"] = "write"
    with pytest.raises(AssertionError, match="permissions"):
        assert_audit_workflow_contract(mutated6, text)

    with pytest.raises(AssertionError, match=r"must not cite AGENTS\.md"):
        assert_audit_workflow_contract(workflow, text + "# See AGENTS.md\n")

    with pytest.raises(AssertionError, match=r"must cite docs/SELF_IMPROVEMENT\.md"):
        assert_audit_workflow_contract(workflow, text.replace("docs/SELF_IMPROVEMENT.md", "docs"))


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


# The fast static checks that a push runs (#1752): rows of the `devops ci` check table. The two
# workflow checks run only when the push changes a workflow (#3043): the runner image holds no
# `actionlint`, and a push that changes no workflow has nothing for the two checks to read.
FAST_STATIC_CHECKS = ["lint", "format"]
WORKFLOW_CHECKS = ["actionlint", "zizmor"]


def _pre_push_hooks() -> list[dict[str, Any]]:
    """The hooks of the `pre-push` stage of `.pre-commit-config.yaml`, in file order."""
    config = yaml.safe_load(PRE_COMMIT_PATH.read_text(encoding="utf-8"))
    default_stages = config.get("default_stages", ["pre-commit"])
    return [
        hook
        for repo in config["repos"]
        for hook in repo.get("hooks", [])
        if "pre-push" in hook.get("stages", default_stages)
    ]


def _argv(hook: dict[str, Any]) -> list[str]:
    return [*shlex.split(str(hook.get("entry", ""))), *map(str, hook.get("args", []))]


def test_the_pre_push_hooks_run_only_the_fast_static_checks() -> None:
    """A push runs the fast static checks and changes no file. The required checks of CI run the
    test suite and the other checks before a merge, and the full `devops ci` is a manual run
    (#1752)."""
    hooks = _pre_push_hooks()
    commands = [_argv(hook) for hook in hooks]
    assert [resolve_step_rows(shlex.join(argv)) for argv in commands] == [
        FAST_STATIC_CHECKS,
        WORKFLOW_CHECKS,
    ]
    assert [argv for argv in commands if "--check" not in argv] == []


def test_the_workflow_checks_run_only_when_a_push_changes_a_workflow() -> None:
    """The first hook has no file filter and always runs. The second runs when the pushed commits
    change a file of `.github/workflows/` or `.github/actions/`."""
    always, workflows = _pre_push_hooks()
    pattern = re.compile(str(workflows["files"]))
    assert (always.get("always_run"), workflows.get("always_run"), workflows["pass_filenames"]) == (
        True,
        None,
        False,
    )
    assert [
        pattern.search(name) is not None
        for name in (
            ".github/workflows/ci.yml",
            ".github/actions/setup/action.yml",
            ".github/labels.yml",
            "src/devops_cli/main.py",
        )
    ] == [True, True, False, False]


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
    `./` actions are this repository's own. `docker://` images are pinned by digest (#1119)."""
    unpinned = [
        f"{path}: {ref}"
        for path in _automation_files()
        for ref in _uses(_load_workflow(path))
        if not ref.startswith("./")
        and not re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", ref)
        and not (ref.startswith("docker://") and re.search(r"@sha256:[0-9a-f]{64}", ref))
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


def _starts_on(paths: list[str], changed: str) -> bool:
    """Whether a `pull_request` path filter starts its workflow for a change to `changed`: the
    last pattern that matches decides, and a `!` pattern excludes, as GitHub documents."""
    started = False
    for pattern in paths:
        if PurePosixPath(changed).full_match(pattern.removeprefix("!")):
            started = not pattern.startswith("!")
    return started


@pytest.mark.parametrize(
    ("changed", "starts"),
    [
        ("src/devops_cli/ci/fail_to_pass.py", True),
        ("src/devops_cli/commands/ci.py", True),
        ("src/devops_cli/ai/knowledge_base/devops_cli/tasks/testing.md", False),
        ("tests/test_fail_to_pass.py", False),
        ("Dockerfile", False),
        ("docs/TESTING.md", False),
        # The files of a release pull request (the last `chore(main): release` commit).
        (".release-please-manifest.json", False),
        ("CHANGELOG.md", False),
        ("pyproject.toml", False),
        ("uv.lock", False),
    ],
)
def test_fail_to_pass_starts_only_for_a_change_to_src_outside_the_knowledge_base(
    changed: str, starts: bool
) -> None:
    """Only a change to the code under src/ can make a test fail on base, so the workflow starts
    for no other change, the release pull request among them (#1879). It keeps one concurrency
    group for each ref, where a newer event cancels an older run (#1960)."""
    workflow = _load_workflow(WORKFLOWS_DIR / "fail-to-pass.yml")
    paths = workflow["on"]["pull_request"]["paths"]
    assert (_starts_on(paths, changed), workflow["concurrency"]) == (
        starts,
        {"group": "fail-to-pass-${{ github.ref }}", "cancel-in-progress": True},
    )


def test_workflow_contract_fail_to_pass() -> None:
    """`.github/workflows/fail-to-pass.yml` runs one replay job on a pull request into main that
    changes `src/` outside the knowledge base, and passes the replay no title, label or body
    (#844, #1879)."""
    workflow = _load_workflow(WORKFLOWS_DIR / "fail-to-pass.yml")
    pr_trigger = workflow.get("on", {}).get("pull_request", {})
    jobs = workflow.get("jobs", {})
    gate_steps = jobs.get("fail-to-pass", {}).get("steps", [])
    replay_step = next(
        (s for s in gate_steps if "devops ci fail-to-pass" in str(s.get("run", ""))),
        {},
    )
    commands = _extract_devops_commands(workflow)
    assert (
        pr_trigger.get("types"),
        pr_trigger.get("branches"),
        pr_trigger.get("paths"),
        sorted(jobs),
        all(
            s.get("with", {}).get("fetch-depth") == 0
            for s in gate_steps
            if "actions/checkout" in str(s.get("uses", ""))
        ),
        sorted(replay_step.get("env", {})),
        "devops ci fail-to-pass" in str(replay_step.get("run", "")),
        any("${{" in str(s.get("run", "")) for s in gate_steps),
        [resolve_devops_argv(tokens) for tokens in commands],
    ) == (
        ["opened", "synchronize", "reopened", "edited"],
        ["main"],
        ["src/**", "!src/devops_cli/ai/knowledge_base/**"],
        ["fail-to-pass"],
        True,
        ["BASE_REF"],
        True,
        False,
        [None],
    )


# A job condition that only joins `startsWith(<pull request title>, '<prefix>')` terms with `||`.
_TITLE_PREFIX_TERM = re.compile(r"startsWith\(github\.event\.pull_request\.title, '([^']+)'\)")


def _title_prefixes(condition: str) -> list[str]:
    """The title prefixes of a job condition that only joins `startsWith` terms on the pull
    request title with `||`, failing on any other form."""
    expression = condition.strip().removeprefix("${{").removesuffix("}}").strip()
    matches = [_TITLE_PREFIX_TERM.fullmatch(term.strip()) for term in expression.split("||")]
    assert all(matches), expression
    return [match.group(1) for match in matches if match]


@pytest.mark.parametrize(
    "title",
    [
        "fix(ci): replay the changed tests",
        "fix: replay the changed tests",
        "FIX(ci): replay the changed tests",
        "fix(ci)!: replay the changed tests",
        "fix!: replay the changed tests",
        "feat(ci): add a check",
        "docs(ci): describe the check",
        "refactor(ci): move the check",
        "ci(fail-to-pass): scope the check",
        "chore(main): release 1.0.0",
        "fixup: squash a commit",
        "fix the check",
    ],
)
def test_the_fail_to_pass_job_runs_for_a_fix_title_and_no_other(title: str) -> None:
    """The replay job runs for a title that `CONST_DEFECT_TITLE_PATTERN` reads as a fix, and is
    skipped for every other title. GitHub's `startsWith` ignores case, as the pattern does."""
    job = _load_workflow(WORKFLOWS_DIR / "fail-to-pass.yml")["jobs"]["fail-to-pass"]
    prefixes = _title_prefixes(str(job.get("if", "")))
    runs = any(title.lower().startswith(prefix.lower()) for prefix in prefixes)
    is_fix = re.match(CONST_DEFECT_TITLE_PATTERN, title, re.IGNORECASE) is not None
    assert runs == is_fix


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


def test_the_test_job_installs_the_pinned_promtool_before_the_gate() -> None:
    """The test job puts the pinned promtool on PATH before the gate, so the rule checks and
    rule unit tests of `tests/test_k8s_monitoring_alerting.py` run and do not skip (#2472)."""
    steps = _steps(WORKFLOWS_DIR / "ci.yml", "test-shard")
    names = [step.get("name") for step in steps]
    install = steps[names.index("Install promtool")]
    assert (
        install["run"].splitlines(),
        names.index("Install promtool") < names.index("Tests & Coverage Quality Gate"),
        "promtool" in load_tools_lock().binary,
    ) == (
        [
            'echo "$HOME/.local/bin" >> "$GITHUB_PATH"',
            "uv run devops install-tools --tool promtool --only-missing",
        ],
        True,
        True,
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

    with pytest.raises(AssertionError) as raised:
        assert bandit_starts == 1
    assert raised.value is not None


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
    """The action builds .devcontainer/image/devcontainer.json with the Dev Containers CLI that the tools
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
                "' .devcontainer/image/devcontainer.json > .devcontainer/image/devcontainer.build.json\n",
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
                "  --config .devcontainer/image/devcontainer.build.json \\\n"
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
LYCHEE = (
    "lycheeverse/lychee@sha256:eaff3e0a13603c9a701accfcc84f44158bb77bf36ecfa4622b626056c3463892"
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
                "run": 'mkdir -p "$GITHUB_WORKSPACE/_site"\n'
                "docker run --rm --network none --dns 127.0.0.1 \\\n"
                '  --volume "$GITHUB_WORKSPACE/docs:/github/workspace/docs:ro" \\\n'
                '  --volume "$GITHUB_WORKSPACE/_site:/github/site" \\\n'
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
            {
                "name": "Verify Built Site Pages and Links",
                "if": built,
                "env": {"LYCHEE": LYCHEE},
                "run": 'test -f "$GITHUB_WORKSPACE/_site/index.html" || {\n'
                '  echo "::error::Built site is missing index.html at root"\n'
                "  exit 1\n"
                "}\n"
                'if [ -n "$(find "$GITHUB_WORKSPACE/_site" -name \'*.md\')" ]; then\n'
                '  echo "::error::Built site contains source markdown (.md) files"\n'
                "  find \"$GITHUB_WORKSPACE/_site\" -name '*.md'\n"
                "  exit 1\n"
                "fi\n"
                "docker run --rm --network none \\\n"
                '  --volume "$GITHUB_WORKSPACE/_site:/site/devops-cli:ro" \\\n'
                '  "$LYCHEE" \\\n'
                "  --offline \\\n"
                "  --root-dir /site \\\n"
                "  --exclude '^file:///[^s]' \\\n"
                "  --exclude '^file:///s[^i]' \\\n"
                "  --exclude '^file:///si[^t]' \\\n"
                "  --exclude '^file:///sit[^e]' \\\n"
                "  --exclude '^file:///site[^/]' \\\n"
                "  --exclude '\\.(md|yaml|py)(#.*)?$' \\\n"
                "  --exclude '/src/' \\\n"
                "  --exclude '/lang/en' \\\n"
                '  "/site/devops-cli/**/*.html"\n',
            },
        ],
    )


def test_a_pull_request_that_changes_an_image_pin_resolves_each_pinned_image() -> None:
    """A wrong image tag under `k8s/` fails only when Argo CD syncs, so the `image-pins` job runs
    `devops k8s image-pins` on the pull request first. It runs for every pull request and checks
    only when the manifests, the command's two modules or `ci.yml` changed, so on any other pull
    request it reports success. No job needs it, and it holds no write scope. It installs the
    pinned helm, which renders the chart Applications, with the lock's installer (#1994)."""
    jobs = _load_workflow(WORKFLOWS_DIR / "ci.yml")["jobs"]
    job = jobs["image-pins"]
    changed = "steps.changes.outputs.pins == 'true'"

    assert (
        job["if"],
        job["permissions"],
        job["timeout-minutes"],
        [name for name, other in jobs.items() if "image-pins" in _needs(other)],
        job["steps"],
    ) == (
        "github.event_name == 'pull_request'",
        {"contents": "read", "pull-requests": "read"},
        10,
        [],
        [
            {
                "name": "Detect Image Pin Changes",
                "id": "changes",
                "uses": PATHS_FILTER,
                "with": {
                    "filters": "pins:\n  - 'k8s/**'\n  - 'src/devops_cli/**/image_pins.py'\n"
                    "  - '.github/workflows/ci.yml'\n"
                },
            },
            {
                "name": "Check out repository",
                "if": changed,
                "uses": CHECKOUT,
                "with": {"persist-credentials": False},
            },
            {
                "name": "Set up uv toolchain",
                "if": changed,
                "uses": "./.github/actions/setup-toolchain",
                "with": {"cache-suffix": "image-pins", "save-uv-cache": "false"},
            },
            {
                "name": "Install Helm",
                "if": changed,
                "run": 'echo "$HOME/.local/bin" >> "$GITHUB_PATH"\n'
                "uv run devops install-tools --tool helm --only-missing\n",
            },
            {
                "name": "Resolve the Image Pins",
                "if": changed,
                "run": "uv run devops k8s image-pins",
            },
        ],
    )


def test_actionlint_digest_pinned_in_dockerfile_and_ci() -> None:
    """The Dockerfile FROM and the ci.yml uses: reference the same digest-pinned image (#1119)."""
    dockerfile = Path(".devcontainer/Dockerfile").read_text(encoding="utf-8")
    ci_yaml = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    dockerfile_match = re.search(
        r"FROM\s+(docker\.io/kjanat/actionlint:1\.17\.0@sha256:[0-9a-f]{64})\s+AS\s+actionlint",
        dockerfile,
    )
    assert dockerfile_match, "Dockerfile FROM actionlint digest-pinned image not found"

    ci_yaml_match = re.search(
        r"uses:\s+(docker://docker\.io/kjanat/actionlint:1\.17\.0@sha256:[0-9a-f]{64})",
        ci_yaml,
    )
    assert ci_yaml_match, "ci.yml uses: actionlint digest-pinned image not found"

    dockerfile_ref = dockerfile_match.group(1)
    ci_yaml_ref = ci_yaml_match.group(1).removeprefix("docker://")
    assert dockerfile_ref == ci_yaml_ref, (
        f"Dockerfile and ci.yml actionlint digests differ: {dockerfile_ref} != {ci_yaml_ref}"
    )


# ── The plan-only pull request (#2860) ────────────────────────────────────────

# The REST list of the files of a pull request holds 3000 files at most and gives no sign of a cut.
PLAN_WHEN = "github.event_name == 'pull_request' && github.event.pull_request.changed_files < 3000"
PLAN_FILTERS = "outside_plan:\n  - '**'\n  - '!openspec/changes/[0-9]*-*/**/*'\n"
PLAN_STEP = "Detect Plan-Only Changes"
FULL_SUITE_STEP = "Tests & Coverage Quality Gate"
PLAN_SUITE_STEP = "Plan-Only Invariant Tests"
COVERAGE_STEP = "Changed-Line Coverage"
SHARDS_STEP = "Require Passing Test Shards"
COMBINE_STEP = "Combine and Check Coverage"
# Only the exact text `false` selects the reduced run: a skipped filter step leaves no output.
FULL_SUITE_WHEN = "steps.changes.outputs.outside_plan != 'false'"
PLAN_SUITE_WHEN = "steps.changes.outputs.outside_plan == 'false' && matrix.shard == 1"
COVERAGE_WHEN = f"github.event_name == 'pull_request' && {FULL_SUITE_WHEN}"
FULL_GATE = 'uv run devops ci --check --no-cache --only test --shard "$SHARD" --shards "$SHARDS"'
PLAN_GATE = "uv run devops ci test tests/invariants"
# The test row runs in shards on separate runners, and the job `Tests & Coverage` joins them
# (#3050). The job ids: the shards are `test-shard`, the required check is `test`.
SHARD_JOB = "test-shard"
JOIN_JOB = "test"
SHARD_NAME = "Tests & Coverage (shard ${{ matrix.shard }} of ${{ strategy.job-total }})"
JOIN_IF = "${{ !cancelled() && github.event_name != 'schedule' }}"
SHARD_MATRIX = {"fail-fast": False, "matrix": {"shard": [1, 2, 3, 4]}}
# The steps of the join that a plan-only pull request skips, as they need the data of the shards.
JOIN_FULL_STEPS = (
    "Check out repository",
    "Set up uv toolchain",
    "Download Coverage Data",
    COMBINE_STEP,
)


def _plan_only_problems(jobs: dict[str, Any]) -> list[str]:
    """What differs from the plan-only contract in the jobs `test-shard` and `test` of a
    workflow's `jobs`: the filter step of each, the shard run and the join steps with their
    conditions, and a required job that no condition can make skip, and that waits only for the
    shards, so the required check always reports."""
    shard, join = jobs[SHARD_JOB], jobs[JOIN_JOB]
    shard_steps = {step.get("name"): step for step in shard["steps"]}
    join_steps = {step.get("name"): step for step in join["steps"]}
    full, reduced = shard_steps.get(FULL_SUITE_STEP, {}), shard_steps.get(PLAN_SUITE_STEP, {})
    coverage, required = join_steps.get(COVERAGE_STEP, {}), join_steps.get(SHARDS_STEP, {})
    order = [step.get("name") for step in join["steps"]]
    expected = [
        ("shard job name", shard["name"], SHARD_NAME),
        ("shard job if", shard["if"], "github.event_name != 'schedule'"),
        ("shard job needs", _needs(shard), []),
        ("shard matrix", shard.get("strategy"), SHARD_MATRIX),
        ("job name", join["name"], "Tests & Coverage"),
        ("job if", join["if"], JOIN_IF),
        ("job needs", _needs(join), [SHARD_JOB]),
        ("jobs that need it", [n for n, o in jobs.items() if JOIN_JOB in _needs(o)], []),
        ("shard permissions", shard["permissions"], {"contents": "read", "pull-requests": "read"}),
        ("permissions", join["permissions"], {"contents": "read", "pull-requests": "read"}),
        ("full suite", (full.get("if"), full.get("run")), (FULL_SUITE_WHEN, FULL_GATE)),
        ("plan suite", (reduced.get("if"), reduced.get("run")), (PLAN_SUITE_WHEN, PLAN_GATE)),
        ("coverage condition", coverage.get("if"), COVERAGE_WHEN),
        (
            "failed shards fail the check",
            required.get("if"),
            "needs.test-shard.result != 'success'",
        ),
        (
            "plan-only skips the join",
            [join_steps.get(name, {}).get("if") for name in JOIN_FULL_STEPS],
            [FULL_SUITE_WHEN] * len(JOIN_FULL_STEPS),
        ),
        (
            "order",
            [n for n in order if n in (PLAN_STEP, SHARDS_STEP, COMBINE_STEP, COVERAGE_STEP)],
            [PLAN_STEP, SHARDS_STEP, COMBINE_STEP, COVERAGE_STEP],
        ),
    ]
    for label, job in (("shard", shard), ("join", join)):
        plan = {step.get("name"): step for step in job["steps"]}.get(PLAN_STEP, {})
        expected += [
            (f"{label} filter id", plan.get("id"), "changes"),
            (f"{label} filter action", plan.get("uses"), PATHS_FILTER),
            (f"{label} filter event", plan.get("if"), PLAN_WHEN),
            (
                f"{label} filter inputs",
                plan.get("with"),
                {"filters": PLAN_FILTERS, "predicate-quantifier": "some-with-excludes"},
            ),
            (f"{label} filter fails open", plan.get("continue-on-error"), None),
        ]
    return [f"{label}: {actual!r}" for label, actual, wanted in expected if actual != wanted]


def test_a_plan_only_pull_request_runs_the_invariant_tests_and_no_more() -> None:
    """The test row takes 355 s to 528 s on one runner, and a pull request that only adds a
    plan under `openspec/changes/` changes no line that the suite tests, except the files that
    the tests of `tests/invariants` read: names and forms, private addresses, the pull request
    template and the architectural rules. A `dorny/paths-filter` step finds such a pull request,
    and shard 1 then runs `tests/invariants` while no shard runs the gate or a coverage step. Any
    other pull request, push or manual run gets the full gate. The job `Tests & Coverage` keeps
    its name and waits only for the shards, and its steps are skipped, not the job, so the
    required check reports success (#2860, #3050)."""
    jobs = _load_workflow(WORKFLOWS_DIR / "ci.yml")["jobs"]

    assert _plan_only_problems(jobs) == []
    assert Path("tests/invariants").is_dir()


def _with_steps(jobs: dict[str, Any], name: str, change: Any) -> dict[str, Any]:
    """`jobs` with `change(step)` applied to every step named `name` of the shard and join jobs;
    a step it returns None for is removed."""
    changed = copy.deepcopy(jobs)
    for job_id in (SHARD_JOB, JOIN_JOB):
        steps = [change(s) if s.get("name") == name else s for s in changed[job_id]["steps"]]
        changed[job_id]["steps"] = [s for s in steps if s is not None]
    return changed


def _without_step(jobs: dict[str, Any], name: str) -> dict[str, Any]:
    """`jobs` with the step `name` removed."""
    return _with_steps(jobs, name, lambda _step: None)


def _with_step_field(jobs: dict[str, Any], name: str, field: str, value: Any) -> dict[str, Any]:
    """`jobs` with `field` of the step `name` set to `value`."""
    return _with_steps(jobs, name, lambda step: {**step, field: value})


def _with_filters(jobs: dict[str, Any], filters: str) -> dict[str, Any]:
    """`jobs` with the filters of the plan step set to `filters`."""
    return _with_steps(
        jobs, PLAN_STEP, lambda step: {**step, "with": {**step["with"], "filters": filters}}
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda jobs: _without_step(jobs, PLAN_STEP),
        lambda jobs: _with_step_field(jobs, PLAN_STEP, "if", "github.event_name == 'pull_request'"),
        lambda jobs: _without_step(jobs, PLAN_SUITE_STEP),
        lambda jobs: _with_step_field(jobs, PLAN_SUITE_STEP, "run", "uv run pytest"),
        lambda jobs: _with_step_field(jobs, PLAN_SUITE_STEP, "if", "always()"),
        lambda jobs: _with_step_field(jobs, FULL_SUITE_STEP, "if", PLAN_SUITE_WHEN),
        lambda jobs: _with_step_field(jobs, FULL_SUITE_STEP, "if", "github.event_name == 'push'"),
        lambda jobs: _with_step_field(
            jobs, COVERAGE_STEP, "if", "github.event_name == 'pull_request'"
        ),
        lambda jobs: _with_filters(jobs, "outside_plan:\n  - '**'\n  - '!openspec/changes/**'\n"),
        lambda jobs: _with_filters(jobs, "outside_plan:\n  - 'src/**'\n"),
        lambda jobs: _without_step(jobs, SHARDS_STEP),
        lambda jobs: _with_step_field(
            jobs, SHARDS_STEP, "if", "needs.test-shard.result == 'failure'"
        ),
        lambda jobs: _without_step(jobs, COMBINE_STEP),
        lambda jobs: _with_step_field(jobs, COMBINE_STEP, "if", "always()"),
    ],
    ids=[
        "no filter",
        "filter reads a list that the API cuts at 3000 files",
        "no reduced run",
        "reduced run without the directory",
        "reduced run always",
        "full suite only for a plan",
        "full suite only for a push",
        "coverage runs for a plan",
        "archive counts as plan",
        "only src counts as outside",
        "no failing step for a failed shard",
        "a failed shard fails only on a failure result",
        "no combine of the coverage data",
        "combine always runs",
    ],
)
def test_the_plan_only_contract_fails_when_a_part_is_removed_or_widened(
    mutate: Any,
) -> None:
    """Each part of the rule is held by the contract: dropping the filter or the reduced run, or
    widening the plan paths to the archive, makes the contract report a problem (#2860)."""
    jobs = _load_workflow(WORKFLOWS_DIR / "ci.yml")["jobs"]

    assert _plan_only_problems(mutate(jobs)) != []


def _outside_plan(path: str, filters: str) -> bool:
    """Whether a changed file `path` makes the filter `outside_plan` true, with the rule of
    `predicate-quantifier: some-with-excludes`: some pattern includes it, and no negated pattern
    excludes it. A negated pattern excludes the files that match it once the `!` is dropped.
    `PurePosixPath.full_match` stands for picomatch with `dot: true`; the plan of #2860 shows both
    agree on these paths."""
    patterns = yaml.safe_load(filters)["outside_plan"]
    included = any(PurePosixPath(path).full_match(p) for p in patterns if not p.startswith("!"))
    excluded = any(PurePosixPath(path).full_match(p[1:]) for p in patterns if p.startswith("!"))
    return included and not excluded


@pytest.mark.parametrize(
    ("path", "is_plan_file"),
    [
        ("openspec/changes/2860-plan-only/proposal.md", True),
        ("openspec/changes/2860-plan-only/specs/ci/spec.md", True),
        ("openspec/changes/2860-plan-only/.openspec.yaml", True),
        ("openspec/changes/2860-plan-only/a/b/c.md", True),
        ("openspec/changes/2026-10-31-plan-only/proposal.md", True),
        ("openspec/changes/archive/2026-10-31-2860-plan-only/proposal.md", False),
        ("openspec/changes/archive/notes.md", False),
        ("openspec/changes/README.md", False),
        ("openspec/changes/.gitkeep", False),
        ("openspec/changes/2860-plan-only", False),
        ("openspec/changes/2860/proposal.md", False),
        ("openspec/changes/plan-only/proposal.md", False),
        ("openspec/specs/ci-job-time/spec.md", False),
        ("openspec/config.yaml", False),
        (".github/workflows/ci.yml", False),
        ("src/devops_cli/commands/ci.py", False),
        ("tests/invariants/test_change_folders.py", False),
        ("docs/SDLC.md", False),
        ("README.md", False),
        ("pyproject.toml", False),
    ],
)
def test_only_a_file_of_an_active_change_folder_counts_as_plan_only(
    path: str, is_plan_file: bool
) -> None:
    """The filter lets a file count as plan-only only when it lies in an active change folder,
    `openspec/changes/<issue>-<slug>/<file>`. The archive, the living specs, the OpenSpec
    config, the workflows, `docs/`, the README, source and tests all run the full suite. A
    rename out of `src/` lists its old path as a deleted file, so it is outside the plan, too.
    The paths agree with the grammar of an active change in `CONST_OPENSPEC_CHANGE_FOLDER_RE`
    (#2860)."""
    assert (
        not _outside_plan(path, PLAN_FILTERS),
        re.fullmatch(CONST_OPENSPEC_CHANGE_FOLDER_RE, path) is not None,
    ) == (is_plan_file, is_plan_file)


# ── The plan check of a Service plan pull request (#3103) ─────────────────────

PR_TITLE_PATH = WORKFLOWS_DIR / "pr-title.yml"
PLAN_CHECK_JOB = "plan-check"
# The paths of the expressions that the condition of the job reads, and a path it must not read.
EVENT_AUTHOR = "github.event.pull_request.user.login"
EVENT_TITLE = "github.event.pull_request.title"
EVENT_ACTOR = "github.actor"
# A real plan pull request of the Service: the title of #3261, which its App's bot opened.
SERVICE_PLAN_TITLE = "docs(openspec): plan #3201 add a plan-check command for a plan pull request"
_EQUALS_TERM = re.compile(r"(?P<path>[\w.]+) == '(?P<value>[^']*)'")
_STARTS_WITH_TERM = re.compile(r"startsWith\((?P<path>[\w.]+), '(?P<prefix>[^']*)'\)")


def _plan_check_job() -> dict[str, Any]:
    """The job `plan-check` of the workflow `pr-title.yml`."""
    return dict(_load_workflow(PR_TITLE_PATH)["jobs"][PLAN_CHECK_JOB])


def _condition_terms(job: dict[str, Any]) -> list[str]:
    """The terms of the `if` of `job`, which the test reads as terms joined with `&&`."""
    expression = str(job["if"]).strip().removeprefix("${{").removesuffix("}}").strip()
    return [term.strip() for term in expression.split("&&")]


def _runs(job: dict[str, Any], event: dict[str, str]) -> bool:
    """Whether the `if` of `job` is true for `event`, which maps an expression path to its value.
    The condition may hold only `always()`, `==` and `startsWith` terms, joined with `&&`: any
    other term fails the test. GitHub compares strings with no regard to case in both operators."""
    for term in _condition_terms(job):
        equals, starts = _EQUALS_TERM.fullmatch(term), _STARTS_WITH_TERM.fullmatch(term)
        if term == "always()":
            continue
        if equals is not None:
            holds = event[equals["path"]].lower() == equals["value"].lower()
        elif starts is not None:
            holds = event[starts["path"]].lower().startswith(starts["prefix"].lower())
        else:
            raise AssertionError(f"the condition holds a term the test cannot read: {term}")
        if not holds:
            return False
    return True


def test_the_plan_check_job_waits_for_the_title_check_and_runs_after_a_failed_one() -> None:
    """The command reads the check `Semantic PR title` and reports a problem when it is missing
    or has not passed (`plan_check.py`), so the job runs after it. `always()` lets the job run
    when that check fails, since the command then reports the title as a problem. Without it,
    GitHub skips a job whose needed job failed. The job that the command reads has the name that
    the command looks for (#3103)."""
    from devops_cli.roadmap.plan_check import SEMANTIC_TITLE_CHECK

    jobs = _load_workflow(PR_TITLE_PATH)["jobs"]
    job = jobs[PLAN_CHECK_JOB]

    assert (
        job["needs"],
        _condition_terms(job)[0],
        jobs["semantic-title"]["name"],
    ) == ("semantic-title", "always()", SEMANTIC_TITLE_CHECK)


def test_the_plan_check_job_reads_checks_contents_and_pull_requests_only() -> None:
    """The workflow grants nothing by default. The job reads the check runs for the title check,
    the repository for the head of the pull request, and the pull request for its title and body.
    The planned issue is public, so the job needs no `issues` permission. It writes nothing, and
    it holds no `statuses` permission: a status is the design that #3103 gave up (#3103)."""
    workflow = _load_workflow(PR_TITLE_PATH)

    assert (workflow["permissions"], workflow["jobs"][PLAN_CHECK_JOB]["permissions"]) == (
        {},
        {"checks": "read", "contents": "read", "pull-requests": "read"},
    )


@pytest.mark.parametrize(
    ("author", "title", "runs"),
    [
        ("devops-cli-service[bot]", SERVICE_PLAN_TITLE, True),
        ("devops-cli-service[bot]", SERVICE_PLAN_TITLE.upper(), True),
        (
            "devops-cli-service[bot]",
            "fix(roadmap): the plan check fails a citation of a line that moved",
            False,
        ),
        ("devops-cli-service[bot]", "docs(openspec): archive the change 3103", False),
        ("dan-petty", SERVICE_PLAN_TITLE, False),
        ("github-actions[bot]", SERVICE_PLAN_TITLE, False),
        ("dan-petty-release[bot]", "chore(main): release 0.64.1", False),
    ],
)
def test_the_plan_check_job_runs_for_a_plan_of_the_service_and_for_no_other_pull_request(
    author: str, title: str, runs: bool
) -> None:
    """The job runs for the plan pull request of the Service's bot, and is skipped for its
    implement pull request, for a plan of a person or of another bot, and for the release pull
    request. A skipped job reports Success, so these pull requests pass (#3103). The event holds
    a person as the actor and the author as the bot, as the run of #3261 did: the condition reads
    the author, not the actor."""
    event = {EVENT_ACTOR: "dan-petty", EVENT_AUTHOR: author, EVENT_TITLE: title}

    assert _runs(_plan_check_job(), event) is runs


def test_the_plan_check_job_names_the_login_of_the_bot_of_the_service_app() -> None:
    """The login in the condition is `<slug>[bot]` for the slug of the Service App, which the
    example ConfigMap of the cluster sets and ADR 0015 records. The pull request API gives the
    login of #3261, `devops-cli-service[bot]`, with the user type `Bot` (#3103)."""
    from devops_cli.config.settings import Settings

    configmap = yaml.safe_load(
        Path("k8s/devops/configmap.example.yaml").read_text(encoding="utf-8")
    )
    config = yaml.safe_load(configmap["data"]["devops-cli.yaml"])
    login = Settings.model_validate(config).service.github_app.bot_login
    logins = [
        match["value"]
        for match in map(_EQUALS_TERM.fullmatch, _condition_terms(_plan_check_job()))
        if match is not None and match["path"] == EVENT_AUTHOR
    ]

    assert (login, logins) == ("devops-cli-service[bot]", ["devops-cli-service[bot]"])


def test_the_plan_check_job_selects_the_title_that_the_stage_job_gives_a_plan() -> None:
    """The stage job opens a plan pull request with `staging_title`, and the plan check reads
    that form. So the title prefix of the condition is the start of every title that the stage job
    gives: the type, then `plan #` (#3103)."""
    from devops_cli.roadmap.stage_change import staging_title

    job = _plan_check_job()
    event = {
        EVENT_ACTOR: "dan-petty",
        EVENT_AUTHOR: "devops-cli-service[bot]",
        EVENT_TITLE: staging_title(3103, "run the plan check on a plan pull request"),
    }

    assert _runs(job, event) is True


def test_the_plan_check_job_checks_out_the_history_and_runs_the_command_for_the_pull_request() -> (
    None
):
    """The command fetches `refs/pull/<number>/head`, reads the log of the change folder and runs
    the pinned OpenSpec, so the job checks out the whole history with no kept credentials, puts
    Node and OpenSpec in place before the command, and gives the command the number of the pull
    request and the token of the job through `env`, never through an expression in `run`."""
    steps = _plan_check_job()["steps"]
    names = [step.get("name") for step in steps]
    checkout = steps[names.index("Check out repository")]
    check = steps[names.index("Check the Plan")]

    assert (
        checkout["with"],
        names.index("Set up Node.js")
        < names.index("Install OpenSpec")
        < names.index("Check the Plan"),
        check["env"],
        check["run"],
    ) == (
        {"persist-credentials": False, "fetch-depth": 0},
        True,
        {
            "PR_NUMBER": "${{ github.event.pull_request.number }}",
            "GH_TOKEN": "${{ secrets.GITHUB_TOKEN }}",
        },
        'uv run devops roadmap plan-check "$PR_NUMBER" --repo "$GITHUB_REPOSITORY"',
    )
