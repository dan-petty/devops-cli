"""Workflow contract tests verifying structural integrity, security guards, and expressions.

These tests enforce invariant rules for GitHub Actions workflows, ensuring permissions
remain minimal, triggers are guarded against unauthorized invocation, and shell injection
risks from inline expressions inside run blocks are eliminated.
"""

from __future__ import annotations

import json
import re
import shlex
import tomllib
from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
import yaml

from devops_cli.commands.ci import get_check_spec
from devops_cli.config.constants import (
    CONST_DEFECT_TITLE_PATTERN,
    CONST_OPENSPEC_CHANGE_FOLDER_RE,
)
from devops_cli.core.command_resolver import ArgvPlaceholder, ArgvToken, resolve_devops_argv
from devops_cli.roadmap.title_labels import declared_label_names
from tests.support.markdown_examples import CodeSnippet, devops_commands

WORKFLOWS_DIR = Path(".github/workflows")
RELEASE_PATH = WORKFLOWS_DIR / "release.yml"
RELEASE_IMAGE_PATH = WORKFLOWS_DIR / "release-image.yml"
ALERTS_PATH = WORKFLOWS_DIR / "trivy-config-alerts.yml"


def _load_workflow(path: Path) -> dict[str, Any]:
    """Load and parse a GitHub Actions workflow YAML file."""
    assert path.is_file(), f"Workflow file not found: {path}"
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(content, dict), f"Workflow {path} does not parse as a mapping"
    return {"on" if k is True else str(k): v for k, v in content.items()}


# The limit of the step that runs the gate or the tests, in minutes. The comment gives the longest
# run of the step. The limit leaves time in the job for the steps before it and after it (#4677).
SUITE_STEP_LIMIT_MINUTES = {
    ("ci.yml", "static", "Static Analysis Quality Gate"): 3,  # 108 s
    ("ci.yml", "test-shard", "Tests & Coverage Quality Gate"): 17,  # 610 s
    (
        "service-image-test.yml",
        "service-image-test",
        "Run Test Suite in Service Image",
    ): 14,  # 527 s
}


def _step_named(job: dict[str, Any], name: str) -> dict[str, Any]:
    """The step of `job` with the name `name`."""
    return next(step for step in job["steps"] if step.get("name") == name)


def test_the_step_that_runs_the_suite_stops_before_its_job() -> None:
    """A step that passes its own limit fails with a message that names the step and the limit,
    and the job ends in failure. The steps after it then run by their conditions, as after any
    other failure. A job that passes its limit is cancelled instead, and its log does not name the
    step that hung. So the step limit is under the job limit, and the job keeps time for the steps
    after the step, such as the Security Scan and its SARIF upload of `Static Analysis` (#4677)."""
    observed = {
        (name, job_id, step): _step_named(
            _load_workflow(WORKFLOWS_DIR / name)["jobs"][job_id], step
        ).get("timeout-minutes")
        for name, job_id, step in SUITE_STEP_LIMIT_MINUTES
    }

    assert observed == SUITE_STEP_LIMIT_MINUTES


def test_a_test_step_outlasts_the_hang_bound_of_one_test() -> None:
    """The time limits nest: one test < its step < its job (ARCHITECTURE.md, Nested Time Limits).
    pytest-timeout fails a hung test at the bound `timeout` of pyproject.toml and the run goes on,
    so the step that runs the tests lasts longer than that bound (#4677)."""
    pytest_options = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["tool"][
        "pytest"
    ]["ini_options"]
    test_steps = {
        key: minutes
        for key, minutes in SUITE_STEP_LIMIT_MINUTES.items()
        if key[1] in ("test-shard", "service-image-test")
    }

    assert len(test_steps) == 2
    assert all(minutes * 60 > pytest_options["timeout"] for minutes in test_steps.values())


def test_every_job_has_a_limit_and_each_step_limit_is_under_it() -> None:
    """With no `timeout-minutes`, a job runs for 360 minutes. A step limit that is not under the
    limit of its job never fires, because the job limit cancels the job first (#4677)."""
    problems = []
    for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        for job_id, job in _load_workflow(path)["jobs"].items():
            if "uses" in job:
                continue
            limit = job.get("timeout-minutes")
            if not isinstance(limit, int):
                problems.append(f"{path.name}:{job_id} has no timeout-minutes")
                continue
            problems.extend(
                f"{path.name}:{job_id}:{step.get('name')} step limit {step['timeout-minutes']}"
                f" is not under the job limit {limit}"
                for step in job.get("steps", [])
                if "timeout-minutes" in step and not step["timeout-minutes"] < limit
            )

    assert problems == []


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
    """Assert that actions/attest and actions/attest-build-provenance steps specify subject-name
    when subject-digest is present."""
    attest_steps = _extract_steps_with_action(workflow, "actions/attest")
    assert attest_steps, "Expected at least one actions/attest step in workflow"
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
        {"group": "release-${{ github.ref }}", "cancel-in-progress": False},
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
            ("assets", "devcontainer-image", "image"),
            _RELEASE_CREATED,
        ),
    )
    review_step = steps["Request review on the release pull request"]
    assert (
        review_step["if"],
        review_step["env"]["GH_TOKEN"],
        review_step["env"]["REVIEWER"],
        "requested_reviewers" in review_step["run"],
    ) == (
        "steps.release.outputs.releases_created != 'true' && steps.release.outputs.pr != ''",
        "${{ steps.app.outputs.token }}",
        "dan-petty",
        True,
    )
    assert [name for name in jobs if name != "release-please" and not _gated(jobs, name)] == []


RELEASE_MERGE_PATH = WORKFLOWS_DIR / "release-merge.yml"


def test_the_release_pull_request_merges_every_6_hours_with_the_least_permissions() -> None:
    """release-merge.yml runs on a schedule of every 6 hours and on dispatch, and on nothing else.
    GITHUB_TOKEN only reads; the release App token, minted with the two permissions of a merge,
    reaches only the step that merges; one concurrency group keeps two runs apart (#3921)."""
    workflow = _load_workflow(RELEASE_MERGE_PATH)
    job = workflow["jobs"]["merge"]
    steps = {step["name"]: step for step in job["steps"]}
    mint = steps["Mint the Release App Token"]
    pick = steps["Pick the Release Pull Request"]
    merge = steps["Merge the Release Pull Request"]

    assert (
        workflow["on"],
        workflow["permissions"],
        workflow["concurrency"],
        list(workflow["jobs"]),
        job["permissions"],
        job["environment"],
        {key: value for key, value in mint["with"].items() if key.startswith("permission-")},
        mint["with"]["client-id"],
        mint["with"]["private-key"],
        pick["env"]["GH_TOKEN"],
        "app.outputs.token" in str(pick),
        merge["if"],
        merge["env"],
        merge["run"],
    ) == (
        {"schedule": [{"cron": "0 */6 * * *"}], "workflow_dispatch": None},
        {},
        {"group": "release-merge", "cancel-in-progress": False},
        ["merge"],
        {"contents": "read", "pull-requests": "read", "checks": "read"},
        "release",
        {"permission-contents": "write", "permission-pull-requests": "write"},
        "${{ vars.RELEASE_APP_CLIENT_ID }}",
        "${{ secrets.RELEASE_APP_PRIVATE_KEY }}",
        "${{ secrets.GITHUB_TOKEN }}",
        False,
        "steps.pick.outputs.number != ''",
        {
            "GH_TOKEN": "${{ steps.app.outputs.token }}",
            "REPOSITORY": "${{ github.repository }}",
            "NUMBER": "${{ steps.pick.outputs.number }}",
            "HEAD_SHA": "${{ steps.pick.outputs.sha }}",
        },
        'gh pr merge "$NUMBER" --repo "$REPOSITORY" --squash --match-head-commit "$HEAD_SHA"',
    )


def test_the_release_merge_only_merges_and_reads_no_untrusted_input_in_a_script() -> None:
    """The workflow edits no branch, tag or release, runs no code of a pull request (it checks out
    the default branch with no credentials), and puts no expression in a `run` script (#3921)."""
    job = _load_workflow(RELEASE_MERGE_PATH)["jobs"]["merge"]
    scripts = [step["run"] for step in job["steps"] if "run" in step]
    checkout = next(step for step in job["steps"] if step.get("name") == "Check out repository")

    assert (
        [script for script in scripts if "${{" in script],
        [
            word
            for script in scripts
            for word in ("git push", "git tag", "gh release", "--admin", "--auto", "pr edit")
            if word in script
        ],
        checkout["with"],
        "ref" in checkout["with"],
        [step["uses"] for step in job["steps"] if "uses" in step and "@" not in step["uses"]],
    ) == ([], [], {"persist-credentials": False}, False, [])


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
    """Validate that the release workflows specify subject-name for each attestation of a digest."""
    workflows = (_load_workflow(RELEASE_PATH), _load_workflow(RELEASE_IMAGE_PATH))
    for workflow in workflows:
        _assert_attest_build_provenance_contract(workflow)
    assert [
        (job_id, step.get("with", {}).get("subject-name"))
        for workflow in workflows
        for job_id, step in _extract_steps_with_action(workflow, "actions/attest")
    ] == [
        ("devcontainer", "ghcr.io/${{ github.repository }}/devcontainer"),
        ("publish", "${{ env.IMAGE }}"),
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


# The default limit of the shell tool of an agent, which runs `git push` and so the pre-push
# hooks, and the time that a push takes outside the hook limits: the start of pre-commit, the
# transfer to GitHub, and the stop of the rows of two `devops ci` hooks after their limits, each
# at most SIGINT, SIGTERM and the reap with 3 s each. An inner limit ends before the limit around
# it (#4775).
AGENT_SHELL_LIMIT_SECONDS = 120
PUSH_OUTSIDE_HOOKS_SECONDS = 25
TIMEOUT_LIMIT = re.compile(r"\btimeout (\d+) ")


def _pre_push_overrun(hooks: list[dict[str, Any]]) -> list[str]:
    """The id of each hook that runs with no coreutils `timeout` limit, and the total time when
    the limits and the rest of the push do not end before the agent shell limit."""
    limits = {
        hook["id"]: [int(seconds) for seconds in TIMEOUT_LIMIT.findall(shlex.join(_argv(hook)))]
        for hook in hooks
    }
    total = sum(map(sum, limits.values())) + PUSH_OUTSIDE_HOOKS_SECONDS
    unbounded = [hook_id for hook_id, found in limits.items() if not found]
    return unbounded + ([f"{total} s"] if total >= AGENT_SHELL_LIMIT_SECONDS else [])


def test_the_pre_push_hooks_end_before_the_agent_shell_limit() -> None:
    """Each pre-push hook runs under coreutils `timeout`, and the limits and the rest of the push
    add up to less than the 120 s default limit of the agent shell. So a hook at its limit fails
    with its name, and `devops ci` stops its rows, before the shell ends the push (#4775)."""
    assert _pre_push_overrun(_pre_push_hooks()) == []


def test_a_pre_push_sum_past_the_shell_limit_or_a_hook_with_no_limit_is_refused() -> None:
    """The negative control: a total of 121 s and a hook with no limit are refused, and a total
    of 119 s passes."""

    def hooks(*entries: str) -> list[dict[str, Any]]:
        return [{"id": f"h{index}", "entry": entry} for index, entry in enumerate(entries)]

    hook_seconds = 121 - PUSH_OUTSIDE_HOOKS_SECONDS
    assert (
        _pre_push_overrun(hooks(f"timeout {hook_seconds - 6} sh -c true", "timeout 6 true")),
        _pre_push_overrun(hooks(f"timeout {hook_seconds - 2} true")),
        _pre_push_overrun(hooks("timeout 20 true", "uv run devops ci --check --only format")),
    ) == (["121 s"], [], ["h1"])


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


# A job condition that only joins `startsWith(<pull request title>, '<prefix>')` terms with `||`.
_TITLE_PREFIX_TERM = re.compile(r"startsWith\(github\.event\.pull_request\.title, '([^']+)'\)")

# An edit of the body alone: it changes neither the replay nor the job condition (#4651).
_BODY_EDIT = (
    "github.event.action == 'edited' && !github.event.changes.title && !github.event.changes.base"
)


# A pull request of the Renovate App, `dan-petty-renovate` (#4897): a dependency bump has no test
# that fails on its base (#4896).
_NOT_RENOVATE = "github.event.pull_request.user.login != 'dan-petty-renovate[bot]'"


def _title_prefixes(condition: str) -> list[str]:
    """The title prefixes of a job condition that skips a body edit and a pull request of the
    Renovate App, and then only joins `startsWith` terms on the pull request title with `||`,
    failing on any other form."""
    expression = " ".join(condition.split()).removeprefix("${{ ").removesuffix(" }}")
    guard = f"!({_BODY_EDIT}) && {_NOT_RENOVATE} && ("
    assert (expression.startswith(guard), expression.endswith(")")) == (True, True), expression
    terms = expression.removeprefix(guard).removesuffix(")").split("||")
    matches = [_TITLE_PREFIX_TERM.fullmatch(term.strip()) for term in terms]
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


SETUP_NODE = "actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1"


def test_copilot_setup_steps_installs_the_pinned_openspec_with_the_opt_outs() -> None:
    """GitHub runs the `copilot-setup-steps` job from the default branch before the Copilot cloud
    agent starts. The file is written by hand, since `openspec init --copilot-cloud` writes a
    workflow that runs an unpinned checkout and `npm install -g`: here every action is pinned
    (the workflow contract tests check each), nothing installs globally, and the job asks for
    no more than to read the repository. The step `Install the git hooks` installs the hooks of
    `.pre-commit-config.yaml`, so the commits of the agent run them (#5136)."""
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
            "PYDANTIC_AI_NO_BANNER": "1",
            "UV_MANAGED_PYTHON": "1",
        },
        {"contents": "read"},
        [SETUP_NODE],
        {"node-version-file": ".node-version"},
        [
            'echo "$PWD/node_modules/.bin" >> "$GITHUB_PATH"',
            "npm ci --ignore-scripts",
            'echo "$BIN_DIR" >> "$GITHUB_PATH"',
            "uv run pre-commit install --install-hooks",
        ],
    )
    assert [
        str(step["run"]) for step in job["steps"] if step.get("name") == "Install the git hooks"
    ] == ["uv run pre-commit install --install-hooks"]
    code = "\n".join(
        line for line in path.read_text(encoding="utf-8").splitlines() if not line.startswith("#")
    )
    assert ("npm install -g" in code, "--copilot-cloud" in code) == (False, False)


# ── The design tokens job (#5184) ─────────────────────────────────────────────

PATHS_FILTER = "dorny/paths-filter@ceb8a2b8f2d89434be7ff52d3de7ec3738c5cc9d"
DESIGN_FILTER = [
    "design/**",
    "package.json",
    "package-lock.json",
    "src/devops_cli/design/**",
    "docs/assets/css/**",
    "k8s/monitoring/dashboards/**",
    "src/devops_cli/grafana/service_dashboard.py",
    ".github/labels.yml",
    "Makefile",
    ".github/workflows/ci.yml",
]


def test_the_design_tokens_job_builds_the_tokens_only_when_a_path_of_its_filter_changes() -> None:
    """docs/DESIGN.md, "Token pipeline": the job builds the tokens with the pinned Style Dictionary
    and the service dashboards with `make dashboards` (#5184), and fails when a committed output
    is not the build. It runs for every pull request and does
    its steps only when a path of its filter changed. Each step limit is shorter than the job
    limit, so the step that hangs stops first and shows its name, and the bound of one design test
    is shorter than its step, so pytest-timeout names the test that hangs (ARCHITECTURE.md,
    "Nested Time Limits"). The diff step names a directory
    that holds each output of each Style Dictionary config, so an output that the diff does not
    see cannot be added."""
    job = _load_workflow(WORKFLOWS_DIR / "ci.yml")["jobs"]["design-tokens"]
    detect, *steps = job["steps"]
    runs = {step["name"]: step.get("run", "") for step in steps}
    design_tests = next(step for step in steps if step["name"] == "Run the Design Tests")
    words = shlex.split(design_tests["run"])
    test_bound = int(words[words.index("--timeout") + 1]) if "--timeout" in words else 0
    diff = next(text for text in runs.values() if "git diff --exit-code" in text)
    checked = [PurePosixPath(path) for path in shlex.split(diff.splitlines()[-1].split(" -- ")[1])]
    outputs = [
        PurePosixPath(platform["buildPath"], file["destination"])
        for config in sorted(Path("design/sd").glob("*.json"))
        for platform in json.loads(config.read_text(encoding="utf-8"))["platforms"].values()
        for file in platform["files"]
    ]

    assert (
        job["name"],
        job["if"],
        job["permissions"],
        detect["uses"],
        yaml.safe_load(detect["with"]["filters"]),
        {step.get("if") for step in steps},
        [
            step["name"]
            for step in steps
            if step.get("timeout-minutes", 0) >= job["timeout-minutes"]
        ],
        [
            runs[name]
            for name in (
                "Build the Design Tokens",
                "Build the Service Dashboards",
                "Run the Design Tests",
            )
        ],
        0 < test_bound < design_tests["timeout-minutes"] * 60,
        len(outputs),
        [str(path) for path in outputs if not any(path.is_relative_to(root) for root in checked)],
        PurePosixPath("k8s/monitoring/dashboards") in checked,
    ) == (
        "Design Tokens",
        "github.event_name == 'pull_request' && !(startsWith(github.head_ref, 'release-please--')"
        " && github.event.pull_request.head.repo.full_name == github.repository)",
        {"contents": "read", "pull-requests": "read"},
        PATHS_FILTER,
        {"design": DESIGN_FILTER},
        {"steps.changes.outputs.design == 'true'"},
        [],
        ["make design-tokens", "make dashboards", "uv run pytest tests/design -n 0 --timeout 60"],
        True,
        11,
        [],
        True,
    )


# ── The plan-only pull request (#2860) ────────────────────────────────────────


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
    """`CONST_OPENSPEC_CHANGE_FOLDER_RE` matches a file only when it lies in an active change
    folder, `openspec/changes/<issue>-<slug>/<file>`. The archive, the living specs, the OpenSpec
    config, the workflows, `docs/`, the README, source and tests do not match (#2860)."""
    assert (re.fullmatch(CONST_OPENSPEC_CHANGE_FOLDER_RE, path) is not None) == is_plan_file


# ── The plan check of a Service plan pull request (#3103) ─────────────────────

PR_TITLE_PATH = WORKFLOWS_DIR / "pr-title.yml"
PLAN_CHECK_JOB = "plan-check"
# The paths of the expressions that the condition of the job reads, and a path it must not read.
EVENT_AUTHOR = "github.event.pull_request.user.login"
EVENT_TITLE = "github.event.pull_request.title"
EVENT_ACTOR = "github.actor"
_EQUALS_TERM = re.compile(r"(?P<path>[\w.]+) == '(?P<value>[^']*)'")
_STARTS_WITH_TERM = re.compile(r"startsWith\((?P<path>[\w.]+), '(?P<prefix>[^']*)'\)")


def _plan_check_job() -> dict[str, Any]:
    """The job `plan-check` of the workflow `pr-title.yml`."""
    return dict(_load_workflow(PR_TITLE_PATH)["jobs"][PLAN_CHECK_JOB])


def _condition_terms(job: dict[str, Any]) -> list[str]:
    """The terms of the `if` of `job`, which the test reads as terms joined with `&&`."""
    expression = str(job["if"]).strip().removeprefix("${{").removesuffix("}}").strip()
    return [term.strip() for term in expression.split("&&")]


def _eval_term(term: str, event: dict[str, str]) -> bool:
    cleaned = term.strip()
    if cleaned.startswith("(") and cleaned.endswith(")") and "||" in cleaned:
        return any(_eval_term(part, event) for part in cleaned[1:-1].split("||"))
    equals, starts = _EQUALS_TERM.fullmatch(cleaned), _STARTS_WITH_TERM.fullmatch(cleaned)
    if cleaned in {"always()", "!cancelled()"}:
        return True
    if equals is not None:
        return event[equals["path"]].lower() == equals["value"].lower()
    if starts is not None:
        return event[starts["path"]].lower().startswith(starts["prefix"].lower())
    raise AssertionError(f"the condition holds a term the test cannot read: {term}")


def _runs(job: dict[str, Any], event: dict[str, str]) -> bool:
    """Whether the `if` of `job` is true for `event`, which maps an expression path to its value.
    The condition may hold only `always()`, `!cancelled()`, `==` and `startsWith` terms, joined
    with `&&` or grouped `(a || b)`: any other term fails the test. GitHub compares strings with
    no regard to case in both operators."""
    return all(_eval_term(term, event) for term in _condition_terms(job))


def test_the_plan_check_job_waits_for_the_title_check_and_runs_after_a_failed_one() -> None:
    """The command reads the check `Semantic PR title` and reports a problem when it is missing
    or has not passed (`plan_check.py`), so the job runs after it. `!cancelled()` lets the job run
    when that check fails, since the command then reports the title as a problem, and skips it in
    a cancelled run. Without it, GitHub skips a job whose needed job failed. The job that the
    command reads has the name that the command looks for (#3103, #3975)."""
    from devops_cli.roadmap.plan_check import SEMANTIC_TITLE_CHECK

    jobs = _load_workflow(PR_TITLE_PATH)["jobs"]
    job = jobs[PLAN_CHECK_JOB]

    assert (
        job["needs"],
        _condition_terms(job)[0],
        jobs["semantic-title"]["name"],
    ) == ("semantic-title", "!cancelled()", SEMANTIC_TITLE_CHECK)
    assert "always()" not in str(job["if"])


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


def test_the_plan_check_job_selects_the_title_that_the_stage_job_gives_a_plan() -> None:
    """The stage job opens a plan pull request with `staging_title`, and the plan check reads
    that form and legacy `docs(openspec): plan #` titles. The workflow `scopes` input uses `spec`
    instead of `openspec` (#3103, #6007)."""
    from devops_cli.roadmap.stage.stage_change import staging_title

    workflow = _load_workflow(PR_TITLE_PATH)
    scopes = workflow["jobs"]["semantic-title"]["steps"][0]["with"]["scopes"].split()
    job = _plan_check_job()
    base_event = {
        EVENT_ACTOR: "dan-petty",
        EVENT_AUTHOR: "devops-cli-service[bot]",
    }

    assert "spec" in scopes
    assert "openspec" not in scopes
    assert (
        _runs(
            job,
            {
                **base_event,
                EVENT_TITLE: staging_title(3103, "run the plan check on a plan pull request"),
            },
        )
        is True
    )
    assert (
        _runs(
            job,
            {**base_event, EVENT_TITLE: "docs(openspec): plan #3103 legacy plan title"},
        )
        is True
    )
    assert (
        _runs(
            job,
            {**base_event, EVENT_TITLE: "fix(roadmap): not a plan pull request"},
        )
        is False
    )


def test_the_alert_workflow_runs_every_day_and_has_no_workflow_run_trigger() -> None:
    """zizmor reports a `workflow_run` trigger as a HIGH finding, one more alert with no judge."""
    triggers = _load_workflow(ALERTS_PATH)["on"]

    assert triggers["schedule"] == [{"cron": "0 6 * * *"}]
    assert "workflow_run" not in triggers


def test_the_alert_workflow_holds_only_the_permissions_it_needs() -> None:
    workflow = _load_workflow(ALERTS_PATH)

    assert workflow["permissions"] == {
        "contents": "read",
        "security-events": "read",
        "issues": "write",
    }


def test_the_service_image_test_run_has_a_timeout_inside_the_job_limit() -> None:
    """A hung suite ends at 900 s, before the 20-minute job limit (#4683)."""
    workflow = _load_workflow(WORKFLOWS_DIR / "service-image-test.yml")

    runs = [
        step.get("run", "")
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if "docker run" in step.get("run", "")
    ]

    assert any("timeout --kill-after=30 900 docker run" in run for run in runs)
