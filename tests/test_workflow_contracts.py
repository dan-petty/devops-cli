"""Workflow contract tests verifying structural integrity, security guards, and expressions.

These tests enforce invariant rules for GitHub Actions workflows, ensuring permissions
remain minimal, triggers are guarded against unauthorized invocation, and shell injection
risks from inline expressions inside run blocks are eliminated.
"""

from __future__ import annotations

import copy
import os
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from devops_cli.commands.ci import get_check_spec
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


def _git(repo: Path, *args: str) -> str:
    """Run git in `repo` and return its output; a failure raises."""
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _commit_in_a_clone(tmp_path: Path) -> tuple[Path, str, str]:
    """A clone of a bare origin with two commits, both pushed: the repository, its first commit
    and its second."""
    origin = tmp_path / "origin.git"
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    subprocess.run(["git", "clone", "-q", str(origin), str(repo)], check=True)
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.com")
    shas = []
    for number in (1, 2):
        (repo / "version.txt").write_text(f"{number}\n", encoding="utf-8")
        _git(repo, "add", "version.txt")
        _git(repo, "commit", "-q", "-m", f"commit {number}")
        shas.append(_git(repo, "rev-parse", "HEAD"))
    _git(repo, "push", "-q", "origin", "HEAD")
    return repo, shas[0], shas[1]


def _run_tag_step(repo: Path, tag: str, published_sha: str) -> subprocess.CompletedProcess[str]:
    """Run the release job's tag step script for `tag`, publishing `published_sha`."""
    steps = _load_workflow(RELEASE_PATH)["jobs"]["release"]["steps"]
    script = next(s for s in steps if s.get("name", "").startswith("Create Git Tag"))["run"]
    env = {**os.environ, "TAG": tag, "TITLE": tag, "GITHUB_SHA": published_sha}
    return subprocess.run(
        ["bash", "-e", "-c", script], cwd=repo, env=env, capture_output=True, text=True, check=False
    )


@pytest.mark.live("bash")
def test_the_release_tags_the_commit_it_publishes(tmp_path: Path) -> None:
    """With no tag for the version, the tag step creates it on the published commit and pushes
    it."""
    repo, _first, second = _commit_in_a_clone(tmp_path)

    done = _run_tag_step(repo, "v0.2.38", second)

    assert (done.returncode, _git(repo, "ls-remote", "origin", "refs/tags/v0.2.38").split()[0]) == (
        0,
        _git(repo, "rev-parse", "v0.2.38"),
    )


@pytest.mark.live("bash")
def test_a_tag_already_on_the_published_commit_is_kept(tmp_path: Path) -> None:
    """A rerun of the same release finds the tag on its commit, and the step goes on."""
    repo, _first, second = _commit_in_a_clone(tmp_path)
    _git(repo, "tag", "-a", "v0.2.38", "-m", "v0.2.38", second)

    done = _run_tag_step(repo, "v0.2.38", second)

    assert (done.returncode, "already exists" in done.stdout) == (0, True)


@pytest.mark.live("bash")
def test_a_tag_on_another_commit_stops_the_release_naming_both(tmp_path: Path) -> None:
    """A version already tagged on another commit is not published again. This is a push to main
    whose pyproject still holds the last release's version: the step fails, naming both commits,
    before the release, its assets or the images are touched (#1805)."""
    repo, first, second = _commit_in_a_clone(tmp_path)
    _git(repo, "tag", "-a", "v0.2.37", "-m", "v0.2.37", first)
    _git(repo, "push", "-q", "origin", "v0.2.37")

    done = _run_tag_step(repo, "v0.2.37", second)

    assert (
        done.returncode != 0,
        first in done.stdout + done.stderr,
        second in done.stdout + done.stderr,
        _git(repo, "rev-parse", "v0.2.37^{commit}"),
    ) == (True, True, True, first)


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
        ["release/**"],
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
    follows it, and both come before the gate that runs the openspec row; the checkout holds the
    history the cut's order is read from."""
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
        checkout["with"]["fetch-depth"],
    ) == (
        SETUP_NODE,
        {"node-version-file": ".node-version"},
        [
            'echo "$HOME/.local/bin" >> "$GITHUB_PATH"',
            "uv run devops install-tools --tool openspec --only-missing",
        ],
        True,
        True,
        0,
    )


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
    lock pins, so the Dev Container Features and the user vscode are in the image, for both
    platforms, pushed by digest. The labels, the SBOM, the provenance and the metadata file that
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
                "name": "Set up QEMU",
                "uses": "docker/setup-qemu-action@99012661954931238ded8c8b007157a8430204e1",
            },
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
                "  --platform linux/amd64,linux/arm64 \\\n"
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
    devcontainer.metadata label, and each platform must run as vscode, uid and gid 1000, with a
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
                "name": "Set up QEMU",
                "uses": "docker/setup-qemu-action@99012661954931238ded8c8b007157a8430204e1",
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
                "for PLATFORM in linux/amd64 linux/arm64; do\n"
                '  docker run --rm --platform "$PLATFORM" --user vscode "$REF" sh -ec \'\n'
                '    test "$(id -u):$(id -g)" = 1000:1000\n'
                "    for TOOL in zsh git gh copilot node npm docker kubectl helm minikube claude; do\n"
                '      command -v "$TOOL" > /dev/null || { echo "missing: $TOOL" >&2; exit 1; }\n'
                "    done\n"
                "    devops --version > /dev/null'\n"
                "done\n",
            },
        ],
    )
